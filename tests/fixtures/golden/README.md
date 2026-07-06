# Golden fixtures — the ground truth for contract #1 (SPEC §3.1)

Real (scrubbed, trimmed, anonymized) Claude Code JSONL transcripts. The
normalizer's kind-mapping is extended ONLY against files in this directory —
never from documentation or memory of the format. Tests in
tests/test_normalizer.py assert each fixture's event kinds.

## The import ritual (every step is mandatory)

1. `.venv/bin/python scripts/import_fixture.py <transcript> <name>` from the
   repo root (applies `nova.secrets.redaction.scrub` per line).
2. **Trim** environment-listing attachment lines (agent/skill/MCP listings,
   hook outputs) — they fingerprint the source machine and bloat the fixture.
   Delete whole lines only; never edit inside a line.
3. **Anonymize** machine paths and usernames (`/tmp/nova-probe-a` style,
   `novauser`) — consistently, everywhere the string appears.
4. **A human reviews every line** before `git add`. The scrubber is a filter;
   your eyes are the gate. These files enter git and travel between machines.
5. Commit the fixture BEFORE the mapping change that consumes it
   (fixture-first, CLAUDE.md).

## Current fixtures

| File | Source | Exercises |
|---|---|---|
| `sample_session.jsonl` | hand-written scaffold | user/assistant/result + unknown-type passthrough |
| `probe_read_tool.jsonl` | real probe, CLI 2.1.197 | one Read tool_use/tool_result round-trip |
| `probe_edit_read_tools.jsonl` | real probe, CLI 2.1.197 | Read + Edit pairs, thinking block, sidecar types |

Wanted next (work machine, Track 6): a richer interactive session, one with a
subagent (`isSidechain`/agent records), and a stream/replay pair for the
parity test.
