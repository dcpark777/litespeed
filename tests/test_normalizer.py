"""Golden-fixture harness for the dual-source normalizer (SPEC §3.1).

The contract: for the same session, jsonl_replayer and sdk_translator produce
event sequences with identical normalization_identity_keys. Until Phase 0
provides real SDK captures, the replay side is exercised against committed
JSONL fixtures; add SDK-capture fixtures in Phase 2 and un-skip the parity test.
"""
from pathlib import Path

import pytest

from nova.events.jsonl_replayer import replay_file
from nova.events.models import SCHEMA_VERSION, EventKind

FIXTURES = Path(__file__).parent / "fixtures" / "golden"


def test_replay_sample_session():
    events = list(replay_file(FIXTURES / "sample_session.jsonl"))
    assert events, "fixture produced no events"
    assert all(e.schema_version == SCHEMA_VERSION for e in events)
    kinds = [e.kind for e in events]
    assert EventKind.user_message in kinds
    assert EventKind.assistant_text in kinds
    # nothing silently dropped: every fixture line yields an event
    lines = (FIXTURES / "sample_session.jsonl").read_text().strip().splitlines()
    assert len(events) == len(lines)


def test_unknown_types_become_passthrough_not_dropped():
    events = list(replay_file(FIXTURES / "sample_session.jsonl"))
    unknown = [e for e in events if e.kind == EventKind.passthrough]
    assert unknown, "fixture includes an unknown type; it must survive as passthrough"
    assert unknown[0].payload  # raw payload preserved


@pytest.mark.skip(reason="phase-2: requires SDK-capture fixtures from smoke-tested env")
def test_stream_replay_parity():
    """Compare normalization_identity_key sequences from both translation paths."""
