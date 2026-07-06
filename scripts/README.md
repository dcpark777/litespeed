# scripts/

Operational scripts — not part of the `nova` package, run with
`.venv/bin/python scripts/<name>.py` from the repo root.

| Script | What | When |
|---|---|---|
| `nova_feasibility.py` | Phase 0 gate: stdlib-only diagnostics of the Bedrock/claude environment; `--full` adds file-edit, hook, and resume checks | Before ANY SDK repin (CLAUDE.md hard rule), and on every new machine |
| `live_probe.py` | First-principles pipeline check: `run_session` against a scratch dir, prints events + outcome; expects PIPELINE_OK | After environment changes; needs `nova[agent]` + Bedrock creds |
| `import_fixture.py` | Copies a `~/.claude/projects` transcript into `tests/fixtures/golden/` with redaction applied | Fixture-first workflow — see tests/fixtures/golden/README.md for the full ritual |
| `check_staged.py` | Pre-commit guard: secret patterns + stray `.jsonl` in staged blobs; `--all` scans every tracked file | Runs automatically via `.githooks/pre-commit` and `make secretscan` |

New scripts: keep them venv-explicit, stdlib-plus-nova only (they run in the
enterprise sandbox — no network assumptions), and document them here.
