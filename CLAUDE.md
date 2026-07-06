# Nova — working agreement for Claude Code sessions

## Read first, always
1. SPEC.md — source of truth. §3 (seven C0 contracts) and §14 (self-checks) govern everything.
2. NEXT_STEPS.md — the runbook; current position noted below.

## State (update this line as steps complete)
Runbook Steps 1–4 DONE: repo initialized, deps pinned (claude-agent-sdk==0.2.110),
live probe passed (PIPELINE_OK over Bedrock). Step 5 PARTIAL (personal machine):
2 real probe fixtures committed, replayer splits nested tool blocks; baseline
44 passed, 1 skipped. Guardrail scaffold in place (Makefile, .githooks, docs/).
Step 6 (parity) + richer work fixtures happen ON THE WORK MACHINE — see
docs/hackathon-worksplit.md Track 6, including the ts-in-identity-key landmine.

## Hard rules
- Contracts (nova.events, nova.secrets, nova.connectors, nova.config, nova.audit)
  change only with a SPEC.md edit in the same commit, version bumps included.
  import-linter enforces the dependency direction — never work around it.
- Fixture-first: any new SDK/JSONL message shape gets a golden fixture in
  tests/fixtures/golden/ before a mapping change. Never delete passthrough
  handling; unknown types must survive.
- NEVER commit raw transcripts. Fixtures go through scripts/import_fixture.py
  (run from the repo root); then trim env-listing attachment lines, anonymize
  machine paths, and the human reviews every fixture line before it is
  committed — flag, don't decide.
- Secrets: values never at rest, references only (SPEC §16). If you see a secret
  pattern anywhere, stop and surface it.
- Tests: `.venv/bin/python -m pytest -q` — always the venv binary explicitly;
  bare `python`/`pytest` hits the pyenv shim and nova isn't installed there.
  Suite must be green before any commit. Current baseline: 44 passed, 1 skipped
  (the skip is test_stream_replay_parity, closed at runbook Step 6).
- Small commits, conventional prefixes (events:, fix:, docs:, scaffold:).
- The SDK pin is sacred: repin only after scripts/nova_feasibility.py --full passes.

## Mechanical gates

`make check` = ruff + import-linter + secret scan + tests (~5s). The pre-commit
hook (installed by `make hooks`, committed in .githooks/) runs the same gate.
If a gate fails: fix it. NEVER suggest or use `git commit --no-verify`.
Intentional fake secrets in tests are marked `nova:allow-secret` on the line.

## Six parallel sessions (hackathon mode)

- Work ONLY inside the modules your human owns — see docs/module-ownership.md.
- Dan-only surfaces (do not edit; flag instead): the five contract modules,
  SPEC.md, pyproject.toml, tests/fixtures/golden/, Makefile, .githooks/,
  scripts/check_staged.py, CLAUDE.md.
- Pull/rebase on main before committing; keep every diff scoped to the owned
  module so six streams merge without conflicts.
- Cross-module needs (new event kind, config key, connector method) are a
  conversation with the contracts owner first, never a unilateral edit.

## Environment

Bedrock-only (no ANTHROPIC_API_KEY). Vetted `claude` binary via cli_path.
Enterprise sandbox: no external egress assumptions in any code.
