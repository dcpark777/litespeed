"""Gate decision records — SPEC §5.5.

The data rules that must survive any UI iteration:
- Decisions persist at CHANGE-SET level and store the FULL proposed content
  per file. Gate granularity is a UI concern, not a data concern — a richer
  reviewer later is a component swap, not a schema migration.
- NEVER line-number-keyed records anywhere persistent.
- The workflow centers on accept-all / reject-and-revise: `feedback` carries
  the revise-with-feedback comment that reopens the session.

Recording the decision to the audit log (nova.audit, action="gate_decision")
is the caller's job — this module owns only the T1 decision record itself.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from ulid import ULID

GATE_DECISION_VERSION = 1


class Outcome(str, Enum):
    accept = "accept"
    reject = "reject"
    revise = "revise"


class ProposedChange(BaseModel):
    """One file in the change-set, with its complete proposed content."""
    path: str                          # workstream-relative
    proposed_content: str | None      # None = proposed deletion
    base_hash: str | None = None      # content hash the proposal was made against (§5.6)


class GateDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(ULID()))
    gate_decision_version: int = GATE_DECISION_VERSION
    workstream_id: str
    session_id: str | None = None
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    changes: list[ProposedChange]
    outcome: Outcome
    feedback: str | None = None        # revise-with-feedback comment; drives session resume


def append(path: Path, decision: GateDecision) -> None:
    """Append to the workstream's decisions.jsonl (T1, append-only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(decision.model_dump_json() + "\n")


def load(path: Path) -> list[GateDecision]:
    if not path.exists():
        return []
    return [GateDecision.model_validate_json(line)
            for line in path.read_text().splitlines() if line.strip()]
