# Module ownership

One owner per area. Owners review changes to their modules; nobody else merges
into them. Contract modules and shared config are Dan-only — changes there need
a SPEC.md edit in the same commit (CLAUDE.md hard rule #1).

Replace placeholders with internal GitHub handles at kickoff.

## Dan-only (contracts + shared surface)

| Path | SPEC | Why locked |
|---|---|---|
| `src/nova/events/` | §3.1 | C0 — normalized event schema |
| `src/nova/secrets/` | §16 | C0 — DLP boundary |
| `src/nova/connectors/` | §15 | C0 — connector interface |
| `src/nova/config/` | §3.5 | C0 — config precedence |
| `src/nova/audit/` | §3.3 | C0 — audit log |
| `SPEC.md`, `pyproject.toml` | — | source of truth; SDK pin |
| `tests/fixtures/golden/` | §3.1 | every line human-reviewed |
| `Makefile`, `.githooks/`, `scripts/check_staged.py` | — | the gates themselves |

## Feature modules (claim at kickoff)

| Path | SPEC | Tests today | Owner |
|---|---|---|---|
| `frontend/` + `src/nova/server/` | §7 | test_server.py | _Owner-1_ |
| `src/nova/workstreams/` | §5.1–5.2 | test_workstream_store.py, test_worktrees.py | _Owner-2_ |
| `src/nova/sessions/` | §5.3, §3.2 | test_runner.py, test_leases.py | _Owner-3_ |
| `src/nova/gates/` (GateDecision model done) | §5.5 | test_gates.py | _Owner-4_ |
| `src/nova/index/` + `src/nova/cli.py` (doctor) | §4, §9 | test_db.py, test_reindex.py | _Owner-5_ |
| `src/nova/memory/` | §6 | test_notes.py, test_artifacts.py | _Owner-6_ |
| `src/nova/campaigns/` (empty stub) | §5.4 | — | post-hackathon |

Cross-module needs (a new event kind, a config key, a connector method) are a
conversation with Dan first, then a paired change with the SPEC edit.
