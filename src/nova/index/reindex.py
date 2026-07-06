"""Full T2 rebuild from T0+T1 (SPEC §4). SDK-independent.

Sources, in order:
  T0: raw Claude Code JSONL transcripts (~/.claude/projects) via jsonl_replayer
  T1: Nova's own NovaEvent logs (~/.nova/events) via EventStore
  T1: memory notes (inbox + curated dirs)
  T1: workstream files -> workstreams catalog table

Redaction (§16.3) applies to T0 at ingestion. T1 NovaEvents were redacted when
written, so they are indexed as-is. rm index.db + reindex is always safe (§14).
"""
from __future__ import annotations

import json
from pathlib import Path

from nova.events.jsonl_replayer import replay_file
from nova.events.models import EventKind, NovaEvent
from nova.events.store import EventStore
from nova.index.db import connect
from nova.memory.notes import Note
from nova.secrets.redaction import scrub


def reindex(db_path: Path, claude_projects: Path, note_dirs: list[Path],
            events_dir: Path | None = None, workstreams_dir: Path | None = None) -> dict:
    if db_path.exists():
        db_path.unlink()
    con = connect(db_path)
    stats = {"sessions": 0, "events": 0, "notes": 0, "nova_events": 0, "workstreams": 0}

    # --- T0: raw Claude Code transcripts (untrusted for secrets -> scrub) ---
    if claude_projects.exists():
        for jsonl in sorted(claude_projects.rglob("*.jsonl")):
            seen_session = None
            for ev in replay_file(jsonl):
                stats["events"] += 1
                seen_session = ev.session_id
                _index_event(con, ev, scrubbed=False)
                _maybe_session_row(con, ev)
            if seen_session:
                stats["sessions"] += 1

    # --- T1: Nova-run session events (already redacted at write time) ---
    if events_dir and events_dir.exists():
        store = EventStore(events_dir)
        for f in sorted(events_dir.glob("*.jsonl")):
            for ev in store.read(f.stem):
                stats["nova_events"] += 1
                _index_event(con, ev, scrubbed=True)
                _maybe_session_row(con, ev)

    # --- T1: memory notes ---
    for d in note_dirs:
        if not d.exists():
            continue
        for md in sorted(d.rglob("*.md")):
            note = Note.parse(md.read_text())
            stats["notes"] += 1
            con.execute(
                "INSERT INTO fts(doc_id, kind, title, body) VALUES(?,?,?,?)",
                (note.id, f"note:{note.type.value}", note.title, scrub(note.body)),
            )

    # --- T1: workstream catalog ---
    if workstreams_dir and workstreams_dir.exists():
        from nova.workstreams.store import WorkstreamStore
        for ws in WorkstreamStore(workstreams_dir).all():
            stats["workstreams"] += 1
            con.execute(
                "INSERT OR REPLACE INTO workstreams(id, type, status, cwd, repo, branch,"
                " pr_url, campaign_id, created) VALUES(?,?,?,?,?,?,?,?,?)",
                (ws.id, ws.type.value, ws.status.value, ws.cwd, ws.repo, ws.branch,
                 ws.pr_url, ws.campaign_id, ws.created.isoformat()),
            )

    con.commit()
    con.close()
    return stats


def _index_event(con, ev: NovaEvent, *, scrubbed: bool) -> None:
    text = json.dumps(ev.payload)
    if not scrubbed:
        text = scrub(text)
    con.execute(
        "INSERT INTO fts(doc_id, kind, title, body) VALUES(?,?,?,?)",
        (ev.event_id, ev.kind.value, "", text),
    )


def _maybe_session_row(con, ev: NovaEvent) -> None:
    if ev.kind != EventKind.session_result:
        return
    p = ev.payload
    status = p.get("subtype") or ("error" if p.get("is_error") else "ok")
    con.execute(
        "INSERT OR REPLACE INTO sessions(session_id, workstream_id, status, cost_usd, turns)"
        " VALUES(?,?,?,?,?)",
        (ev.session_id, ev.workstream_id, status,
         p.get("total_cost_usd"), p.get("num_turns")),
    )


def search(db_path: Path, query: str, limit: int = 20) -> list[dict]:
    con = connect(db_path)
    rows = con.execute(
        "SELECT doc_id, kind, title, snippet(fts, 3, '[', ']', '…', 12)"
        " FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
        (query, limit),
    ).fetchall()
    con.close()
    return [{"doc_id": r[0], "kind": r[1], "title": r[2], "snippet": r[3]} for r in rows]
