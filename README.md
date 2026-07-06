# nova

Local-first cockpit for orchestrating Claude Code work — sessions, review gates,
curated memory, fleet campaigns. Bedrock-authenticated, sandbox-friendly.

**Read `SPEC.md` first.** It is the source of truth; this scaffold implements its
Phase 1 contracts as stubs with the C0 pieces (event schema, secrets, connector
protocol, config precedence) real enough to test.

## Quickstart (dev)
    uv venv && uv pip install -e '.[dev]'
    pytest                      # green before anything else
    nova doctor                 # environment / Phase 0 readiness
    cd frontend && npm i && npm run dev   # UI placeholder on :5173

The Agent SDK is deliberately optional (`nova[agent]`): install it only after the
Phase 0 smoke test (SPEC §13) passes in your sandbox. Everything else — schema,
index, secrets, config, tests — works without it.
