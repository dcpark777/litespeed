"""Translate live Agent SDK messages into NovaEvents (stream half of the normalizer).

Written against claude-agent-sdk 0.2.110 dataclasses, but structurally (attribute
access + type-name dispatch) so the module imports without the SDK installed and
degrades to passthrough on unknown types — never drops anything (SPEC §3.1).

Mapping (SDK type -> NovaEvent kinds):
  AssistantMessage      -> assistant_text (+ tool_call per ToolUseBlock in content)
  UserMessage           -> user_message   (+ tool_result per ToolResultBlock)
  ResultMessage         -> session_result
  Task{Started,...}     -> subagent_started / subagent_finished / passthrough
  HookEventMessage      -> permission_request|decision heuristics, else passthrough
  SystemMessage/other   -> passthrough (payload preserved verbatim)
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from nova.events.models import EventKind, NovaEvent, Provenance


def make_provenance(sdk_version: str | None = None, cli_version: str | None = None) -> Provenance:
    return Provenance(source="sdk_stream", sdk_version=sdk_version, cli_version=cli_version)


def translate(msg: Any, session_id: str, workstream_id: str | None = None,
              provenance: Provenance | None = None) -> Iterator[NovaEvent]:
    """Yield one or more NovaEvents for a single SDK message.

    One SDK message can carry several semantic events (e.g. an AssistantMessage
    whose content mixes text and tool_use blocks) — hence an iterator.
    """
    prov = provenance or make_provenance()
    now = datetime.now(tz=timezone.utc)
    sid = getattr(msg, "session_id", None) or session_id
    name = type(msg).__name__

    def ev(kind: EventKind, payload: dict[str, Any]) -> NovaEvent:
        return NovaEvent(session_id=sid, workstream_id=workstream_id, ts=now,
                         kind=kind, payload=payload, provenance=prov)

    if name == "AssistantMessage":
        for block in getattr(msg, "content", []) or []:
            bname = type(block).__name__
            if bname == "TextBlock":
                yield ev(EventKind.assistant_text, {"text": block.text,
                                                    "model": getattr(msg, "model", None)})
            elif bname in ("ToolUseBlock", "ServerToolUseBlock"):
                yield ev(EventKind.tool_call, {"tool_use_id": block.id, "name": block.name,
                                               "input": _plain(block.input)})
            elif bname == "ThinkingBlock":
                yield ev(EventKind.passthrough, {"block": "thinking"})  # content elided by default
            else:
                yield ev(EventKind.passthrough, {"block": bname, "data": _plain(block)})
        return

    if name == "UserMessage":
        content = getattr(msg, "content", None)
        blocks = content if isinstance(content, list) else []
        emitted = False
        for block in blocks:
            if type(block).__name__ in ("ToolResultBlock", "ServerToolResultBlock"):
                emitted = True
                yield ev(EventKind.tool_result, {"tool_use_id": block.tool_use_id,
                                                 "content": _plain(block.content),
                                                 "is_error": getattr(block, "is_error", None)})
        if not emitted:
            yield ev(EventKind.user_message, {"content": _plain(content)})
        return

    if name == "ResultMessage":
        yield ev(EventKind.session_result, {
            "subtype": msg.subtype, "is_error": msg.is_error, "num_turns": msg.num_turns,
            "duration_ms": msg.duration_ms, "total_cost_usd": msg.total_cost_usd,
            "result": getattr(msg, "result", None),
            "permission_denials": _plain(getattr(msg, "permission_denials", None)),
        })
        return

    if name == "TaskStartedMessage":
        yield ev(EventKind.subagent_started, {"task_id": msg.task_id,
                                              "description": getattr(msg, "description", None),
                                              "task_type": getattr(msg, "task_type", None)})
        return
    if name in ("TaskNotificationMessage", "TaskUpdatedMessage"):
        status = getattr(msg, "status", None)
        kind = (EventKind.subagent_finished
                if status in ("completed", "failed", "done") else EventKind.passthrough)
        yield ev(kind, {"task_id": msg.task_id, "status": status, "type": name,
                        "summary": getattr(msg, "summary", None)})
        return

    yield ev(EventKind.passthrough, {"type": name, "data": _plain(msg)})


def _plain(obj: Any) -> Any:
    """Best-effort conversion to JSON-safe primitives; defensive at the boundary."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        try:
            return asdict(obj)
        except Exception:  # noqa: BLE001
            return repr(obj)
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return repr(obj)
