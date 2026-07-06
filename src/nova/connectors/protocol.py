"""Connector interface — SPEC §15, extension seam #4 (C0).

Rules encoded here, enforced in core:
- pull/plan may be exposed to agents; apply() is invoked only by core, post-gate.
- Connectors resolve their own credentials (nova.secrets) at execution time;
  secret values never enter agent context, config files, or logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

CONNECTOR_API_VERSION = 1


@dataclass(frozen=True)
class CredRef:
    """A credential *reference* (env: / keyring: / aws-sm: / aws-ssm:), never a value."""
    ref: str
    purpose: str


@dataclass
class HealthReport:
    ok: bool
    detail: str = ""


@dataclass
class PullScope:
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotResult:
    root: Path                      # canonical, deterministic files written under here
    summary: str = ""


@dataclass
class PlanArtifact:
    path: Path                      # changes.yaml — human-readable, idempotency-keyed
    summary: str = ""


@dataclass
class ApplyResult:
    ok: bool
    items: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class Connector(Protocol):
    id: str
    version: str
    connector_api: int
    credentials: list[CredRef]

    def health(self) -> HealthReport: ...
    def pull(self, scope: PullScope, dest: Path) -> SnapshotResult: ...
    def plan(self, intent: dict[str, Any], snapshot: Path) -> PlanArtifact: ...
    def apply(self, plan: PlanArtifact) -> ApplyResult: ...   # CORE-ONLY, post-gate
