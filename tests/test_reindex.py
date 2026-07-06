from pathlib import Path

from nova.index.reindex import reindex, search
from nova.memory.notes import Note, NoteType

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def test_reindex_from_fixtures_and_notes(tmp_path):
    projects = tmp_path / "projects" / "proj1"
    projects.mkdir(parents=True)
    (projects / "s_demo01.jsonl").write_text((FIXTURES / "sample_session.jsonl").read_text())

    inbox = tmp_path / "inbox"
    Note(type=NoteType.decision, title="kubekit bump decision",
         body="ghp_abcdefghij0123456789XYZ must be scrubbed; kubekit pinned to 2.3").write(inbox)

    db = tmp_path / "index.db"
    stats = reindex(db, tmp_path / "projects", [inbox])
    assert stats == {"sessions": 1, "events": 4, "notes": 1, "nova_events": 0, "workstreams": 0}

    hits = search(db, "kubekit")
    assert hits, "FTS should find the note and transcript"

    # redaction applied at ingestion: the token never reaches the index
    assert not search(db, '"ghp_abcdefghij0123456789XYZ"')
    assert search(db, "REDACTED")


def test_reindex_is_repeatable(tmp_path):
    db = tmp_path / "index.db"
    for _ in range(2):  # rm+rebuild is always safe (SPEC §14)
        stats = reindex(db, tmp_path / "nowhere", [])
        assert stats["events"] == 0


def test_reindex_ingests_t1_events_and_workstreams(tmp_path):
    from datetime import datetime, timezone

    from nova.events.models import EventKind, NovaEvent, Provenance
    from nova.events.store import EventStore
    from nova.workstreams.models import Gate, Workstream, WorkstreamType
    from nova.workstreams.store import WorkstreamStore

    events = EventStore(tmp_path / "events")
    prov = Provenance(source="sdk_stream")
    now = datetime.now(tz=timezone.utc)
    events.append(NovaEvent(session_id="s_live", workstream_id="w1", ts=now,
                            kind=EventKind.assistant_text,
                            payload={"text": "bumped snowflake connector"}, provenance=prov))
    events.append(NovaEvent(session_id="s_live", workstream_id="w1", ts=now,
                            kind=EventKind.session_result,
                            payload={"is_error": False, "total_cost_usd": 0.03,
                                     "num_turns": 2, "subtype": "success"}, provenance=prov))

    wss = WorkstreamStore(tmp_path / "workstreams")
    ws = Workstream(type=WorkstreamType.repo_pr, title="snowflake bump", cwd="/w",
                    gate=Gate.pr, created=now, repo="internal/repo-a")
    wss.save(ws)

    db = tmp_path / "index.db"
    stats = reindex(db, tmp_path / "no-t0", [], events_dir=tmp_path / "events",
                    workstreams_dir=tmp_path / "workstreams")
    assert stats["nova_events"] == 2 and stats["workstreams"] == 1

    assert search(db, "snowflake")  # T1 events reachable via FTS

    from nova.index.db import connect
    con = connect(db)
    row = con.execute("SELECT workstream_id, status, cost_usd, turns FROM sessions"
                      " WHERE session_id='s_live'").fetchone()
    assert row == ("w1", "success", 0.03, 2)
    ws_row = con.execute("SELECT type, repo FROM workstreams WHERE id=?", (ws.id,)).fetchone()
    assert ws_row == ("repo_pr", "internal/repo-a")
    con.close()
