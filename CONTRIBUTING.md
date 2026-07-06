# Contributing to Nova

Six people, one week, one repo. These rules exist so parallel work merges
instead of colliding. SPEC.md is the source of truth; CLAUDE.md is the working
agreement your Claude Code session must follow.

## Setup (once)

```bash
make setup        # venv + dev deps + git hooks
make check        # must pass before you start; ~5 seconds
```

**The venv rule.** Always `.venv/bin/python -m pytest -q` — never bare `pytest`
or `python`. On pyenv machines the bare commands resolve to a shim that doesn't
have nova installed, and you'll chase phantom `ModuleNotFoundError`s. The
Makefile and hooks already do this correctly; do the same in your terminal.

## The gates

`make check` = ruff + import-linter + secret scan + test suite. The pre-commit
hook runs the same gate. **Fix failures; never `--no-verify`.**

| Target | What |
|---|---|
| `make test` | test suite (quiet) |
| `make lint` / `make lint-fix` | ruff |
| `make importlint` | C0 contract: contract modules never import feature modules |
| `make secretscan` | secret patterns + stray transcripts, all tracked files |
| `make check` | all of the above |

## Hard rules (from CLAUDE.md — the hooks enforce most of them)

1. **Contract modules** (`nova.events`, `nova.secrets`, `nova.connectors`,
   `nova.config`, `nova.audit`) change only with a SPEC.md edit in the same
   commit, version bumps included. Pair with the contracts owner
   (docs/module-ownership.md) before touching them.
2. **Fixture-first.** Any new SDK/JSONL message shape gets a golden fixture in
   `tests/fixtures/golden/` *before* the mapping change. Never delete
   passthrough handling; unknown types must survive.
3. **Never commit raw transcripts.** Import via `scripts/import_fixture.py`
   (run from the repo root), then a human reviews **every line** before
   `git add`. Trim environment-listing attachment lines; anonymize paths
   (see the convention in the `events: add scrubbed golden fixtures` commit).
4. **Secrets are references, never values** (SPEC §16). If you see a secret
   pattern anywhere, stop and surface it. Intentional test fakes are marked
   `nova:allow-secret` on the line.
5. **Suite green before every commit** (the hook enforces this).
6. **The SDK pin is sacred.** Repin `claude-agent-sdk` only after
   `scripts/nova_feasibility.py --full` passes.

## Commits & PRs

- Small commits, conventional prefixes: `events:`, `fix:`, `docs:`,
  `scaffold:`, or your module name (`server:`, `memory:`, …).
- Rebase on main before pushing; keep diffs inside the module you own
  (docs/module-ownership.md) so merges stay trivial.
- PRs use the checklist template; SPEC.md changes go by PR even solo.

## Working with Claude Code

Start sessions at the repo root so CLAUDE.md is picked up. Your session
inherits the same rules you do — if it proposes editing a contract module,
a fixture, SPEC.md, or `pyproject.toml`, that's your cue to stop and pair
with the owner.
