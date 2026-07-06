"""Session runner — the ONLY module that touches the Agent SDK (SPEC §5.3, §3.2).

Feasibility-verified option names (SDK 0.2.110): cli_path, cwd, permission_mode,
resume, fork_session, hooks, max_turns, env.

Design for testability: the SDK query function is injectable (`query_fn`), so the
full lease/translate/persist pipeline is tested with a fake stream; only the
default import path requires nova[agent].
"""
from __future__ import annotations

import shutil
import sqlite3
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from nova.events.models import EventKind, NovaEvent
from nova.events.sdk_translator import make_provenance, translate
from nova.events.store import EventStore
from nova.sessions import leases


class AgentUnavailable(RuntimeError):
    """nova[agent] not installed or environment failed `nova doctor`."""


def _default_query():
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise AgentUnavailable(
            "claude-agent-sdk not installed; install nova[agent] (Phase 0 passed, so this "
            "is just a pip install)."
        ) from e

    def q(prompt: str, options: dict[str, Any]):
        return query(prompt=prompt, options=ClaudeAgentOptions(**options))
    return q


def build_options(cwd: Path, *, permission_mode: str = "default",
                  resume: str | None = None, fork: bool = False,
                  max_turns: int | None = None, hooks: dict | None = None,
                  cli_path: str | None = None) -> dict[str, Any]:
    """Assemble SDK option kwargs. Vetted binary via cli_path (auto-detected from
    PATH if not given) — the Bedrock config mechanism rides along with the CLI."""
    opts: dict[str, Any] = {"cwd": str(cwd), "permission_mode": permission_mode}
    binary = cli_path or shutil.which("claude")
    if binary:
        opts["cli_path"] = binary
    if resume:
        opts["resume"] = resume
        if fork:
            opts["fork_session"] = True
    if max_turns is not None:
        opts["max_turns"] = max_turns
    if hooks:
        opts["hooks"] = hooks
    return opts


async def run_session(
    con: sqlite3.Connection,
    events: EventStore,
    cwd: Path,
    prompt: str,
    *,
    workstream_id: str | None = None,
    session_hint: str = "pending",
    query_fn: Callable[..., Any] | None = None,
    **option_kwargs: Any,
) -> AsyncIterator[NovaEvent]:
    """Acquire lease -> stream SDK messages -> translate -> persist -> yield.

    Lease is keyed by cwd (single writer, §3.2) and always released. The true
    session_id arrives in the first SDK message; events before that use the hint
    and the store re-homes on first sight of the real id.
    """
    q = query_fn or _default_query()
    opts = build_options(cwd, **option_kwargs)
    leases.acquire(con, str(cwd), session_hint)
    session_id = session_hint
    prov = make_provenance()
    try:
        async for msg in q(prompt, opts):
            real = getattr(msg, "session_id", None)
            if real and session_id != real:
                session_id = real
                leases.release(con, str(cwd))
                leases.acquire(con, str(cwd), session_id)
            for ev in translate(msg, session_id, workstream_id, prov):
                events.append(ev)
                yield ev
            leases.heartbeat(con, str(cwd))
    finally:
        leases.release(con, str(cwd))


async def collect(aiter: AsyncIterator[NovaEvent]) -> list[NovaEvent]:
    """Convenience for callers/tests that want the full list."""
    return [ev async for ev in aiter]


def outcome(evs: list[NovaEvent]) -> dict[str, Any]:
    """Summarize a finished session from its events (feeds metrics + kanban)."""
    for ev in reversed(evs):
        if ev.kind == EventKind.session_result:
            p = ev.payload
            return {"status": "error" if p.get("is_error") else "ok",
                    "cost_usd": p.get("total_cost_usd"), "turns": p.get("num_turns"),
                    "session_id": ev.session_id}
    return {"status": "incomplete", "session_id": evs[-1].session_id if evs else None}
