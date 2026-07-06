"""Translate Claude Code JSONL transcripts (~/.claude/projects/**) into NovaEvents.

This is the replay half of the dual-source normalizer (SPEC §3.1). It depends only
on the on-disk JSONL format — not on the Agent SDK — so it works regardless of the
sandbox smoke-test outcome.

Convergence contract: for the same session, this module and sdk_translator must
produce identical normalization_identity_key sequences (SPEC §3.1; parity test in
tests/test_normalizer.py, un-skipped at runbook Step 6). Payload shapes below
deliberately mirror sdk_translator's, key for key.

Kind-mapping is grounded in golden fixtures (tests/fixtures/golden/) — extend it
against new fixtures, never from documentation (fixture-first rule, CLAUDE.md).
Unknown record types MUST become EventKind.passthrough, never be dropped; every
input line yields at least one event.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nova.events.models import EventKind, NovaEvent, Provenance

_PROVENANCE = Provenance(source="jsonl_replay")

# Sidecar record types observed in real transcripts (CLI 2.1.197 fixtures; the
# unfixtured ones were profiled in the wild). Deliberate passthrough: they carry
# UI/bookkeeping state with no fixture-backed NovaEvent kind yet. Candidates for
# later fixture-driven mapping: system, permission-mode (permission_decision?),
# file-history-snapshot. Mapping any of them = fixture first (CLAUDE.md).
_SIDECAR_TYPES = {
    "queue-operation",
    "attachment",
    "last-prompt",
    "system",
    "mode",
    "permission-mode",
    "file-history-snapshot",
    "ai-title",
    "agent-name",
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
        yield from _translate(rec, workstream_id)


def _translate(rec: dict[str, Any], workstream_id: str | None) -> Iterator[NovaEvent]:
    rec_type = rec.get("type", "")

    def ev(kind: EventKind, payload: dict[str, Any]) -> NovaEvent:
        return NovaEvent(
            session_id=rec.get("sessionId", "unknown"),
            workstream_id=workstream_id,
            ts=_ts(rec),
            kind=kind,
            payload=payload,
            provenance=_PROVENANCE,
        )

    def raw_passthrough() -> NovaEvent:
        return ev(
            EventKind.passthrough,
            {k: v for k, v in rec.items() if k not in ("sessionId", "timestamp")},
        )

    emitted = 0

    if rec_type == "assistant":
        message = rec.get("message") or {}
        content = message.get("content")
        model = message.get("model")
        for block in content if isinstance(content, list) else []:
            btype = block.get("type") if isinstance(block, dict) else None
            emitted += 1
            if btype == "text":
                yield ev(EventKind.assistant_text, {"text": block["text"], "model": model})
            elif btype == "tool_use":
                # key named tool_use_id (not the block's "id") to match sdk_translator
                yield ev(EventKind.tool_call, {"tool_use_id": block["id"],
                                               "name": block["name"],
                                               "input": block.get("input")})
            elif btype == "thinking":
                # content elided (matches sdk_translator; keeps signature blobs out of T1)
                yield ev(EventKind.passthrough, {"block": "thinking"})
            else:
                yield ev(EventKind.passthrough, {"block": btype, "data": block})

    elif rec_type == "user":
        message = rec.get("message") or {}
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                emitted += 1
                yield ev(EventKind.tool_result, {"tool_use_id": block.get("tool_use_id"),
                                                 "content": block.get("content"),
                                                 "is_error": block.get("is_error")})
        if not emitted and content is not None:
            emitted += 1
            yield ev(EventKind.user_message, {"content": content})

    elif rec_type == "result":
        emitted += 1
        yield ev(EventKind.session_result, {
            "subtype": rec.get("subtype"), "is_error": rec.get("is_error"),
            "num_turns": rec.get("num_turns"), "duration_ms": rec.get("duration_ms"),
            "total_cost_usd": rec.get("total_cost_usd"), "result": rec.get("result"),
            "permission_denials": rec.get("permission_denials"),
        })

    elif rec_type in _SIDECAR_TYPES:
        emitted += 1
        yield raw_passthrough()

    # Invariant: every line yields >= 1 event — unknown types and records whose
    # content produced nothing (e.g. empty assistant block list) survive verbatim.
    if not emitted:
        yield raw_passthrough()


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
