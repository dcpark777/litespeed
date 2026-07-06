"""Translate Claude Code JSONL transcripts (~/.claude/projects/**) into NovaEvents.

This is the replay half of the dual-source normalizer (SPEC §3.1). It depends only
on the on-disk JSONL format — not on the Agent SDK — so it works regardless of the
sandbox smoke-test outcome.

Status: skeleton. The kind-mapping below covers the common record types; extend it
against real fixtures (tests/fixtures/golden/) rather than from documentation.
Unknown record types MUST become EventKind.passthrough, never be dropped.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nova.events.models import EventKind, NovaEvent, Provenance

_PROVENANCE = Provenance(source="jsonl_replay")

# Claude Code JSONL `type` -> NovaEvent kind. Extend via golden fixtures.
_KIND_MAP: dict[str, EventKind] = {
    "user": EventKind.user_message,
    "assistant": EventKind.assistant_text,
    "result": EventKind.session_result,
}


def replay_file(path: Path, workstream_id: str | None = None) -> Iterator[NovaEvent]:
    """Yield NovaEvents for one session transcript file."""
    for line_no, raw in enumerate(path.read_text().splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            rec: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            yield _error_event(path, line_no, raw, workstream_id)
            continue
        yield _translate(rec, workstream_id)


def _translate(rec: dict[str, Any], workstream_id: str | None) -> NovaEvent:
    kind = _KIND_MAP.get(rec.get("type", ""), EventKind.passthrough)
    # TODO(fixtures): tool_use / tool_result live inside assistant/user content
    # blocks in the JSONL format; split them into first-class events here so the
    # replay path matches the SDK stream path event-for-event.
    return NovaEvent(
        session_id=rec.get("sessionId", "unknown"),
        workstream_id=workstream_id,
        ts=_ts(rec),
        kind=kind,
        payload={k: v for k, v in rec.items() if k not in ("sessionId", "timestamp")},
        provenance=_PROVENANCE,
    )


def _ts(rec: dict[str, Any]) -> datetime:
    raw = rec.get("timestamp")
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return datetime.now(tz=timezone.utc)


def _error_event(path: Path, line_no: int, raw: str, workstream_id: str | None) -> NovaEvent:
    return NovaEvent(
        session_id="unknown",
        workstream_id=workstream_id,
        ts=datetime.now(tz=timezone.utc),
        kind=EventKind.error,
        payload={"reason": "jsonl_parse_failure", "file": str(path), "line": line_no},
        provenance=_PROVENANCE,
    )
