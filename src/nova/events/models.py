"""NovaEvent — the normalized event schema (SPEC §3.1, contract C0-1).

Every renderer, index, and automation consumes NovaEvents. Raw SDK messages and
raw Claude Code JSONL are translated to this schema at the provider boundary and
nowhere else. Live-stream and JSONL-replay translation of the same session MUST
produce identical events (enforced by tests/test_normalizer.py golden fixtures).

Versioning rules:
- `schema_version` is REQUIRED on every stored record.
- Bump on any breaking change; readers support N and N-1.
- Unknown upstream message types are preserved (kind=passthrough), never dropped.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field
from ulid import ULID

SCHEMA_VERSION = 1


class EventKind(str, Enum):
    session_started = "session_started"
    user_message = "user_message"
    assistant_text = "assistant_text"
    tool_call = "tool_call"
    tool_result = "tool_result"
    subagent_started = "subagent_started"
    subagent_finished = "subagent_finished"
    permission_request = "permission_request"
    permission_decision = "permission_decision"
    session_interrupted = "session_interrupted"
    session_result = "session_result"
    error = "error"
    passthrough = "passthrough"  # unknown upstream types, payload preserved verbatim


class Provenance(BaseModel):
    source: Literal["sdk_stream", "jsonl_replay"]
    provider: str = "claude-code"
    sdk_version: str | None = None
    cli_version: str | None = None


class NovaEvent(BaseModel):
    schema_version: int = SCHEMA_VERSION
    event_id: str = Field(default_factory=lambda: str(ULID()))
    session_id: str
    workstream_id: str | None = None
    ts: datetime
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance

    def canonical_json(self) -> str:
        """Deterministic serialization for T1 storage (stable key order)."""
        return self.model_dump_json()  # pydantic v2: field-declaration order is stable


def normalization_identity_key(ev: NovaEvent) -> tuple:
    """The tuple two translation paths must agree on for the same underlying event.

    event_id and provenance.source legitimately differ between live and replay;
    everything semantic must match. Golden-fixture tests compare these keys.
    """
    return (ev.session_id, ev.ts.isoformat(), ev.kind, _stable(ev.payload))


def _stable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return tuple(sorted((k, _stable(v)) for k, v in obj.items()))
    if isinstance(obj, list):
        return tuple(_stable(v) for v in obj)
    return obj
