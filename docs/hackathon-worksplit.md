# Hackathon work split — six tracks

Tracks follow SPEC §13 Phase 2 / NEXT_STEPS Step 8. Each track is one person +
their Claude Code session, working inside the modules they own
(docs/module-ownership.md). Definition of done for every track: SPEC §14
self-checks hold, `make check` green, PR through the checklist.

## Track 1 — Transcript pane (frontend + server WS)
Connect to `/ws/workstreams/{id}/session`, render NovaEvents live: streaming
text, tool-call chips, result footer. SPEC §7 layout — dense, keyboard-driven.
The UI must not care whether events come from live stream or replay (that's
the §3.1 contract working for you).

## Track 2 — Workstream board (frontend + server API)
Left-rail kanban over `GET /api/workstreams` (status columns, type badges),
plus the create form. Status derives from `outcome()` summaries.

## Track 3 — Type-1 worktree wiring (workstreams)
Endpoint creating a repo_pr workstream via `worktrees.add()`; archive-on-close
via `worktrees.remove/prune`. Single-writer-per-cwd invariant (§3.2) is
enforced by leases — don't reimplement it.

## Track 4 — Diff gate (gates + frontend)
`git diff` endpoint per workstream, `@codemirror/merge` panel, and
revise-with-feedback (reopen the session with the reviewer comment — SPEC §5.5
calls this the 10× feature). Persist decisions at change-set level, never
line-keyed.

## Track 5 — Doctor + reindex (index + cli)
Finish `nova doctor` (fold in the feasibility script's Bedrock-mechanism
diagnostic) and extend `reindex()` to ingest the T1 EventStore into fts +
sessions tables. `rm -rf ~/.nova/index.db && nova reindex` must always be safe
(§14).

## Track 6 — Stream/replay parity + real work fixtures (events; pairs with Dan)
**Work machine only.** Closes contract #1 (NEXT_STEPS Step 6).

1. Import 2–3 real work transcripts as golden fixtures
   (`scripts/import_fixture.py` → trim env-listing attachment lines →
   anonymize paths per the fixture-commit convention → Dan reviews every line).
2. Capture one session both ways (live probe with a persistent event-store
   home + its JSONL under `~/.claude/projects`), commit as a fixture pair.
3. Un-skip `test_stream_replay_parity`; compare `normalization_identity_key`
   sequences from both paths.

**Known landmine, hit this first:** the identity key includes `ts.isoformat()`.
sdk_translator stamps `now()` at translation time; the replayer uses record
timestamps; `last-prompt` records have no timestamp at all. Parity therefore
needs either a key relaxation (that's a SPEC §3.1 edit — contract change, same
commit) or sidecar exclusion in the comparison. Decide with Dan before coding.

Also expect the work CLI's JSONL to differ from the personal-machine fixtures
(different CLI version) — new record types are exactly what fixture-first is
for: fixture, then mapping, never the reverse.
