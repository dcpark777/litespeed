"""Registry conformance checks using an in-memory fake (no entry points needed)."""
from pathlib import Path

from nova.connectors.protocol import (ApplyResult, Connector, CredRef, HealthReport,
                                      PlanArtifact, PullScope, SnapshotResult,
                                      CONNECTOR_API_VERSION)


class FakeJira:
    id = "jira"
    version = "0.1"
    connector_api = CONNECTOR_API_VERSION
    credentials = [CredRef(ref="keyring:nova/jira-token", purpose="api")]

    def health(self) -> HealthReport: return HealthReport(ok=True)
    def pull(self, scope: PullScope, dest: Path) -> SnapshotResult: return SnapshotResult(root=dest)
    def plan(self, intent, snapshot) -> PlanArtifact: return PlanArtifact(path=snapshot / "changes.yaml")
    def apply(self, plan) -> ApplyResult: return ApplyResult(ok=True)


def test_fake_satisfies_protocol():
    assert isinstance(FakeJira(), Connector)


def test_credentials_are_references_not_values():
    for cred in FakeJira.credentials:
        assert ":" in cred.ref and not cred.ref.startswith(("ghp_", "AKIA"))
