# Nova — working agreement for Claude Code sessions

## Read first, always
1. SPEC.md — source of truth. §3 (seven C0 contracts) and §14 (self-checks) govern everything.
2. NEXT_STEPS.md — the runbook; current position noted below.

## State (update this line as steps complete)
Runbook Steps 1–4 DONE: repo initialized, deps pinned (claude-agent-sdk==0.2.110),
41 tests green, live probe passed (PIPELINE_OK over Bedrock). Currently on Step 5.

## Hard rules
- Contracts (nova.events, nova.secrets, nova.connectors, nova.config, nova.audit)
  change only with a SPEC.md edit in the same commit, version bumps included.
  import-linter enforces the dependency direction — never work around it.
- Fixture-first: any new SDK/JSONL message shape gets a golden fixture in
  tests/fixtures/golden/ before a mapping change. Never delete passthrough
  handling; unknown types must survive.
- NEVER commit raw transcripts. Fixtures go through scripts/import_fixture.py;
  the human reviews every fixture line before it is committed — flag, don't decide.
- Secrets: values never at rest, references only (SPEC §16). If you see a secret
  pattern anywhere, stop and surface it.
- Tests: `python -m pytest -q` (never bare pytest — pyenv shim trap).
  Suite must be green before any commit. Current baseline: 41 passed, 1 skipped.
- Small commits, conventional prefixes (events:, fix:, docs:, scaffold:).
- The SDK pin is sacred: repin only after scripts/nova_feasibility.py --full passes.

## Environment
Bedrock-only (no ANTHROPIC_API_KEY). Vetted `claude` binary via cli_path.
Enterprise sandbox: no external egress assumptions in any code.