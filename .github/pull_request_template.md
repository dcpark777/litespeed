## What

<!-- one paragraph; link the track in docs/hackathon-worksplit.md -->

## Checklist (CLAUDE.md hard rules — the hooks check most of these; confirm anyway)

- [ ] `make check` green (`ruff`, `lint-imports`, secret scan, tests)
- [ ] Suite run via `.venv/bin/python -m pytest -q`; count matches CLAUDE.md State line (or this PR updates it)
- [ ] Diff stays inside modules I own (docs/module-ownership.md) — or the owner is a reviewer
- [ ] Touches a contract module? → SPEC.md edited **in this PR**, schema/config version bumped
- [ ] New SDK/JSONL message shape? → golden fixture committed **before** the mapping change; passthrough handling untouched
- [ ] No raw transcripts; any new fixture was imported via `scripts/import_fixture.py`, trimmed/anonymized, and human-reviewed line by line
- [ ] No secret values anywhere (references only, SPEC §16); intentional test fakes marked `nova:allow-secret`
- [ ] Small commits with conventional prefixes
