from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from nova.audit.log import AUDIT_VERSION, Actor, AuditRecord, load, record


def test_record_roundtrip(tmp_path):
    rec = AuditRecord(actor=Actor.user, action="gate_decision", subject="src/app.py",
                      workstream_id="ws1", session_id="s1", decision="accept")
    path = record(tmp_path, rec)
    assert path.name == f"{rec.ts:%Y-%m-%d}.jsonl"
    (loaded,) = load(tmp_path)
    assert loaded == rec
    assert loaded.audit_version == AUDIT_VERSION


def test_append_only_same_day(tmp_path):
    ts = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    for i in range(3):
        record(tmp_path, AuditRecord(ts=ts, actor=Actor.policy, action="permission_decision",
                                     subject=f"tool-{i}", decision="deny"))
    assert len(list(tmp_path.glob("*.jsonl"))) == 1
    assert [r.subject for r in load(tmp_path)] == ["tool-0", "tool-1", "tool-2"]


def test_required_fields_enforced():
    with pytest.raises(ValidationError):
        AuditRecord(action="external_apply", subject="jira")  # actor missing
    with pytest.raises(ValidationError):
        AuditRecord(actor="robot", action="x", subject="y")  # not user|policy
