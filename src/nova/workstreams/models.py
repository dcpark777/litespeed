"""Workstream — the universal unit (SPEC §5.1)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from ulid import ULID


class WorkstreamType(str, Enum):
    repo_pr = "repo_pr"
    ephemeral = "ephemeral"
    maintained = "maintained"


class Status(str, Enum):
    inbox = "inbox"
    active = "active"
    gating = "gating"
    done = "done"
    interrupted = "interrupted"
    archived = "archived"


class Gate(str, Enum):
    pr = "pr"
    local_diff = "local_diff"
    change_plan = "change_plan"
    none = "none"


class Workstream(BaseModel):
    id: str = Field(default_factory=lambda: str(ULID()))
    type: WorkstreamType
    title: str
    status: Status = Status.inbox
    cwd: str
    gate: Gate
    sessions: list[str] = Field(default_factory=list)
    campaign_id: str | None = None
    created: datetime
    # type-specific (repo_pr)
    repo: str | None = None
    branch: str | None = None
    pr_url: str | None = None
