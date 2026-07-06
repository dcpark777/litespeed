"""Runner pipeline tests with a fake SDK stream: lease lifecycle, session-id
re-homing, persistence, outcome summarization — no network, no binary."""
import pytest

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk.types import AssistantMessage, ResultMessage, TextBlock  # noqa: E402

from nova.events.store import EventStore  # noqa: E402
from nova.index.db import connect  # noqa: E402
from nova.sessions import leases  # noqa: E402
from nova.sessions.runner import build_options, collect, outcome, run_session  # noqa: E402


def _fake_stream(session_id="s_real"):
    async def q(prompt, options):
        yield AssistantMessage(content=[TextBlock(text=f"echo:{prompt}")], model="m",
                               parent_tool_use_id=None, error=None, usage=None,
                               message_id="m1", stop_reason=None,
                               session_id=session_id, uuid="u1")
        yield ResultMessage(subtype="success", duration_ms=10, duration_api_ms=8,
                            is_error=False, num_turns=1, session_id=session_id,
                            stop_reason=None, total_cost_usd=0.001, usage=None,
                            result="ok", structured_output=None, model_usage=None,
                            permission_denials=[], deferred_tool_use=None, errors=[],
                            api_error_status=None, uuid="u2")
    return q


@pytest.mark.asyncio
async def test_pipeline_persists_and_releases_lease(tmp_path):
    con = connect(tmp_path / "t.db")
    store = EventStore(tmp_path / "events")
    evs = await collect(run_session(con, store, tmp_path, "hi",
                                    query_fn=_fake_stream(), session_hint="hint"))
    assert [e.kind.value for e in evs] == ["assistant_text", "session_result"]
    assert all(e.session_id == "s_real" for e in evs)          # re-homed from hint
    assert store.path_for("s_real").exists()                   # persisted to T1
    assert list(store.read("s_real"))[0].payload["text"] == "echo:hi"
    leases.acquire(con, str(tmp_path), "next")                 # lease was released


@pytest.mark.asyncio
async def test_lease_released_on_stream_failure(tmp_path):
    async def boom(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="x")], model="m",
                               parent_tool_use_id=None, error=None, usage=None,
                               message_id="m", stop_reason=None, session_id="s", uuid="u")
        raise RuntimeError("stream died")

    con = connect(tmp_path / "t.db")
    with pytest.raises(RuntimeError):
        await collect(run_session(con, EventStore(tmp_path / "e"), tmp_path, "hi",
                                  query_fn=boom))
    leases.acquire(con, str(tmp_path), "recovered")


def test_build_options_shapes():
    opts = build_options(cwd=__import__("pathlib").Path("/w"), resume="abc", fork=True,
                         max_turns=3, cli_path="/usr/bin/claude")
    assert opts["resume"] == "abc" and opts["fork_session"] is True
    assert opts["cli_path"] == "/usr/bin/claude" and opts["cwd"] == "/w"


def test_outcome_summary(tmp_path):
    from nova.events.models import EventKind, NovaEvent, Provenance
    from datetime import datetime, timezone
    ev = NovaEvent(session_id="s", ts=datetime.now(tz=timezone.utc),
                   kind=EventKind.session_result,
                   payload={"is_error": False, "total_cost_usd": 0.5, "num_turns": 2},
                   provenance=Provenance(source="sdk_stream"))
    assert outcome([ev]) == {"status": "ok", "cost_usd": 0.5, "turns": 2, "session_id": "s"}
