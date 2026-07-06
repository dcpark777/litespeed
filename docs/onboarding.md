# Onboarding — 15 minutes to productive

On the work machine (Bedrock-only enterprise sandbox), in order:

## 1. Clone and set up

```bash
git clone <internal-github>:<org>/nova.git && cd nova
make setup
```

If the internal PyPI mirror is unavailable, `pip install` will fail — ask Dan
for the pre-downloaded wheel bundle and install with
`.venv/bin/python -m pip install --no-index --find-links <wheels-dir> -e '.[dev]'`,
then run `make hooks` manually.

## 2. Verify the gate

```bash
make check        # must be fully green: ruff, import-linter, secret scan, tests
git config core.hooksPath   # must print: .githooks
```

Expected test baseline is recorded in CLAUDE.md's State line. If your numbers
differ, stop and ask — don't "fix" tests you didn't break.

## 3. Read (30 min well spent)

1. `SPEC.md` §3 — the seven C0 contracts. Everything downstream depends on
   them; this is the part you cannot skim.
2. `SPEC.md` §14 — the self-checks; they're the definition of done.
3. `CONTRIBUTING.md` — the working rules.
4. `docs/hackathon-worksplit.md` — pick your track.

## 4. Claim a track

Put your name on a track in `docs/hackathon-worksplit.md` and on your modules
in `docs/module-ownership.md` (one commit, `docs:` prefix).

## 5. Environment sanity (agent work only)

If your track runs live sessions: `nova doctor` must be green
(vetted `claude` binary on PATH, `CLAUDE_CODE_USE_BEDROCK=1`, AWS creds).
Frontend/UI tracks don't need this to start — the test suite runs a fake SDK
stream and never calls Bedrock.

## 6. Start

```bash
claude        # from the repo root, so CLAUDE.md governs the session
```

Work only inside your owned modules; everything else is a conversation first.
