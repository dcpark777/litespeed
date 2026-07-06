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


# Sidecar record types that legitimately normalize to passthrough (see
# jsonl_replayer._SIDECAR_TYPES). A passthrough event is "explainable" iff it is
# an elided thinking block or carries one of these types.
_EXPLAINABLE_TYPES = {"queue-operation", "attachment", "last-prompt"}


def _assert_passthroughs_explainable(events):
    for e in (e for e in events if e.kind == EventKind.passthrough):
        assert (
            e.payload.get("block") == "thinking"
            or e.payload.get("type") in _EXPLAINABLE_TYPES
        ), f"unexplained passthrough: {e.payload}"


def _tool_pairs(events):
    """(name, tool_use_id) per tool_call, joined to its tool_result by id."""
    calls = {e.payload["tool_use_id"]: e.payload["name"]
             for e in events if e.kind == EventKind.tool_call}
    results = [e.payload["tool_use_id"] for e in events if e.kind == EventKind.tool_result]
    return calls, results


def test_replay_probe_read_tool():
    """Real probe transcript: one Read round-trip (CLI 2.1.197)."""
    path = FIXTURES / "probe_read_tool.jsonl"
    events = list(replay_file(path))
    lines = path.read_text().strip().splitlines()
    assert len(events) >= len(lines)  # block-splitting can only add events
    kinds = {e.kind for e in events}
    assert {EventKind.user_message, EventKind.assistant_text,
            EventKind.tool_call, EventKind.tool_result} <= kinds
    calls, results = _tool_pairs(events)
    assert list(calls.values()) == ["Read"]
    assert results == list(calls)  # the result answers exactly that call
    _assert_passthroughs_explainable(events)


def test_replay_probe_edit_read_tools():
    """Real probe transcript: Read then Edit, each with a paired result."""
    path = FIXTURES / "probe_edit_read_tools.jsonl"
    events = list(replay_file(path))
    lines = path.read_text().strip().splitlines()
    assert len(events) >= len(lines)
    calls, results = _tool_pairs(events)
    assert sorted(calls.values()) == ["Edit", "Read"]
    assert sorted(results) == sorted(calls)
    texts = [e for e in events if e.kind == EventKind.assistant_text]
    assert texts and all(e.payload["model"] for e in texts)
    _assert_passthroughs_explainable(events)


@pytest.mark.skip(reason="phase-2: requires SDK-capture fixtures from smoke-tested env")
def test_stream_replay_parity():
    """Compare normalization_identity_key sequences from both translation paths."""
