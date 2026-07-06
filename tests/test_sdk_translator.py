"""Translator tests against REAL SDK dataclasses (claude-agent-sdk installed in CI/dev).
This is the live half of the golden contract; parity with jsonl_replayer lands when
real work-transcript fixtures are committed."""
import pytest

sdk = pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk.types import (AssistantMessage, ResultMessage, TextBlock,  # noqa: E402
                                    ToolUseBlock, ToolResultBlock, UserMessage)

from nova.events.models import EventKind  # noqa: E402
from nova.events.sdk_translator import translate  # noqa: E402


def _mk_assistant(blocks):
    return AssistantMessage(content=blocks, model="claude-sonnet", parent_tool_use_id=None,
                            error=None, usage=None, message_id="m1", stop_reason=None,
                            session_id="s1", uuid="u1")


def test_assistant_text_and_tool_call_split():
    msg = _mk_assistant([TextBlock(text="Scanning imports"),
                         ToolUseBlock(id="t1", name="Read", input={"path": "a.py"})])
    evs = list(translate(msg, "s1"))
    assert [e.kind for e in evs] == [EventKind.assistant_text, EventKind.tool_call]
    assert evs[1].payload["name"] == "Read"
    assert evs[0].session_id == "s1"


def test_user_tool_result():
    msg = UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="file text",
                                               is_error=False)],
                      uuid="u2", parent_tool_use_id=None, tool_use_result=None)
    evs = list(translate(msg, "s1"))
    assert evs[0].kind == EventKind.tool_result
    assert evs[0].payload["tool_use_id"] == "t1"


def test_result_message():
    msg = ResultMessage(subtype="success", duration_ms=1200, duration_api_ms=1000,
                        is_error=False, num_turns=3, session_id="s1", stop_reason=None,
                        total_cost_usd=0.02, usage=None, result="done",
                        structured_output=None, model_usage=None, permission_denials=[],
                        deferred_tool_use=None, errors=[], api_error_status=None, uuid="u3")
    evs = list(translate(msg, "hint"))
    assert evs[0].kind == EventKind.session_result
    assert evs[0].session_id == "s1"          # real id wins over hint
    assert evs[0].payload["total_cost_usd"] == 0.02


def test_unknown_message_is_passthrough_never_dropped():
    class FutureMessage:
        session_id = "s1"
    evs = list(translate(FutureMessage(), "s1"))
    assert evs and evs[0].kind == EventKind.passthrough
    assert evs[0].payload["type"] == "FutureMessage"
