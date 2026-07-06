"""Append-only audit log — SPEC §3.3 (C0). Local JSONL under ~/.nova/audit/;
never in shared git; exportable on demand. Records decisions and credential
*use* (refs), never secret values or file contents.

One AuditRecord per: tool permission decision, gate decision, external apply,
campaign launch, memory promotion. The typed model IS the contract — callers
cannot invent field shapes; readers support audit_version N and N-1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

AUDIT_VERSION = 1


class Actor(str, Enum):
    user = "user"
    policy = "policy"


class AuditRecord(BaseModel):
    audit_version: int = AUDIT_VERSION
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    actor: Actor
    action: str            # e.g. "permission_decision", "gate_decision", "external_apply"
    subject: str           # what was acted on: tool name, file path, connector id, note id
    workstream_id: str | None = None
    session_id: str | None = None
    decision: str | None = None    # e.g. "allow" | "deny" | "accept" | "reject" | "revise"
    rationale: str | None = None


def record(audit_dir: Path, rec: AuditRecord) -> Path:
    """Append one record to today's file; returns the file written."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{rec.ts:%Y-%m-%d}.jsonl"
    with path.open("a") as f:
        f.write(rec.model_dump_json() + "\n")
    return path


def load(audit_dir: Path) -> list[AuditRecord]:
    """All records, oldest file first (export path; the log is small by design)."""
    out: list[AuditRecord] = []
    for path in sorted(audit_dir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                out.append(AuditRecord.model_validate_json(line))
    return out
