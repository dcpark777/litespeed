"""Append-only audit log — C0 contract (SPEC §3.3).

One JSONL record per permission decision, gate decision, external apply,
campaign launch, memory promotion. Fields: ts, actor, workstream_id,
session_id, action, subject, decision, rationale. Never enters shared git;
never contains secret values (credential *use* is logged, not the value).
"""
