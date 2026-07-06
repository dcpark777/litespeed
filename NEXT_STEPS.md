# Nova — Next Steps Runbook

Concrete, ordered, on the **work machine** unless noted. Each step has commands,
files to commit, and an acceptance check. Stop at any failed acceptance check.

---

## Step 1 — Stand up the repo (~15 min)

```bash
unzip nova-scaffold.zip && cd nova
git init -b main
git add SPEC.md
git commit -m "spec: Nova v0.2 — architecture, contracts, storage, build order"
git add .
git commit -m "scaffold: contracts + core loop (38 tests green, SDK 0.2.110-verified)"
```

Create the remote on internal GitHub (empty repo, no README) and push:

```bash
git remote add origin git@<internal-github>:<you>/nova.git
git push -u origin main
```

**Accept:** two commits pushed; SPEC.md is commit one.

---

## Step 2 — Environment + test baseline (~10 min)

```bash
uv venv && source .venv/bin/activate        # or: python3 -m venv .venv
uv pip install -e '.[dev,agent]'            # or: pip install -e '.[dev,agent]'
pytest -q
nova doctor
```

Pin what Phase 0 proved. In `pyproject.toml`, change the agent extra to the
version the feasibility run used:

```toml
agent = ["claude-agent-sdk==0.2.110"]   # match `pip show claude-agent-sdk`
```

```bash
git add pyproject.toml
git commit -m "deps: pin claude-agent-sdk to feasibility-verified version"
```

**Accept:** `38 passed, 1 skipped`; `nova doctor` all green (or known-noise only).

---

## Step 3 — Record Phase 0 provenance (~10 min)

Create `docs/phase0.md` containing: the full feasibility output (both machines),
which Bedrock config mechanism check 2 detected, `claude --version`, SDK version,
and the date. Then:

```bash
git add docs/phase0.md
git commit -m "docs: Phase 0 feasibility results and environment provenance"
```

**Accept:** six months from now, "why did we build on the SDK path?" has a
committed answer.

---

## Step 4 — Live pipeline probe (~20 min) ← the first real Bedrock run of Nova code

Save as `scripts/live_probe.py`:

```python
"""First live run of Nova's own pipeline: run_session against a scratch dir."""
import asyncio, tempfile
from pathlib import Path

from nova.events.store import EventStore
from nova.index.db import connect
from nova.sessions.runner import collect, outcome, run_session

async def main():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "nova-home"
        home.mkdir(parents=True, exist_ok=True)  # connect() also does this now
        con = connect(home / "index.db")
        events = EventStore(home / "events")
        evs = await collect(run_session(
            con, events, Path(td), "Reply with exactly: PIPELINE_OK",
            max_turns=1,
        ))
        for ev in evs:
            print(ev.kind.value, "|", str(ev.payload)[:100])
        print("outcome:", outcome(evs))

asyncio.run(main())
```

```bash
python scripts/live_probe.py
```

**Accept:** you see `assistant_text` containing `PIPELINE_OK`, then
`session_result`, and `outcome: {'status': 'ok', ...}` with a real cost figure.
Any translator mismatch (a message type appearing as `passthrough` that
shouldn't) — note it for Step 5; that's the file it fixes.

```bash
git add scripts/live_probe.py
git commit -m "scripts: live pipeline probe (first Bedrock run through run_session)"
```

---

## Step 5 — Real golden fixtures (~45 min) ← grounds contract #1 in reality

1. Pick 2–3 recent, boring transcripts from `~/.claude/projects/` (a small task,
   one with tool calls, one with a subagent if you have it).
2. Scrub and copy:

```python
# scripts/import_fixture.py — run once per transcript
import sys
from pathlib import Path
from nova.secrets.redaction import scrub

src, name = Path(sys.argv[1]), sys.argv[2]
out = Path("tests/fixtures/golden") / f"{name}.jsonl"
out.write_text("\n".join(scrub(l) for l in src.read_text().splitlines()) + "\n")
print("wrote", out)
```

3. **Manually review each fixture** before committing — redaction is a filter,
   your eyes are the gate (these files enter git).
4. Extend `tests/test_normalizer.py` with a test per fixture; run pytest; extend
   `jsonl_replayer.py`'s kind-mapping (tool_use/tool_result inside content
   blocks is the known TODO) until the real fixtures produce sensible kinds, not
   walls of `passthrough`.

```bash
git add tests/fixtures/golden/ tests/test_normalizer.py src/nova/events/jsonl_replayer.py scripts/import_fixture.py
git commit -m "events: replayer kind-mapping extended against real work transcripts"
```

**Accept:** replayer tests pass on real transcripts; `passthrough` events are
rare and explainable.

---

## Step 6 — Stream/replay parity (~30 min) ← closes contract #1

Capture one session both ways: run `scripts/live_probe.py` with the event-store
output kept (point `home` at a persistent dir), locate the same session's JSONL
under `~/.claude/projects/`, scrub, commit as a fixture pair. Un-skip
`test_stream_replay_parity` in `tests/test_normalizer.py` and make it compare
`normalization_identity_key` sequences from both paths.

```bash
git commit -am "events: stream/replay parity test un-skipped and green"
```

**Accept:** the previously-skipped test passes. **Contract #1 is now closed** —
everything downstream can trust the event model.

---

## Step 7 — First dogfood loop (~30 min)

Point Claude Code at the repo and let it do a Phase 2 task while you review:

```bash
cd nova && claude
# prompt: "Read SPEC.md and src/nova/index/reindex.py. Extend reindex() to also
# ingest the T1 EventStore directory (~/.nova/events/*.jsonl of NovaEvents) into
# the fts and sessions tables, with redaction already applied upstream skipped.
# Add tests mirroring tests/test_reindex.py. Keep it deterministic."
```

Review the diff, run pytest, commit. This is deliberately Nova's own workflow
run by hand — note every friction point; that list is Nova's UI backlog.

**Accept:** reindex covers both T0 and T1 sources; tests green; you have a
written friction list.

---

## Step 8 — Phase 2 proper (the next ~2–3 weeks, in order)

Each is one Claude Code session with SPEC.md in context; review via PR to your
own repo (dogfooding the gate model):

1. **Frontend transcript pane** — connect to `/ws/workstreams/{id}/session`,
   render NovaEvents (text, tool-call chips, result footer). First real UI;
   read SPEC §7 for layout, keep it dense.
2. **Workstream board** — left rail over `GET /api/workstreams`, create form,
   status from `outcome()`.
3. **Type 1 wiring** — endpoint that creates a repo_pr workstream via
   `worktrees.add()`, and archive-on-close via `worktrees.remove/prune`.
4. **Diff gate** — `git diff` endpoint per workstream + `@codemirror/merge`
   panel + revise-with-feedback (start a resumed session with the comment).
5. **`nova doctor` finishing** — fold in the feasibility script's mechanism
   diagnostic (check 2) so doctor tells new users which Bedrock mechanism
   their machine uses.

**Accept (end of Phase 2):** you run `nova up`, create a workstream on a real
repo, run a session from the UI, watch the transcript live, review the diff,
and push a branch — Nova's core loop, end to end, on your fleet.

---

## Standing rules while you build

- SPEC.md changes by PR to yourself, with a version bump — even solo.
- Any SDK upgrade → rerun `nova_feasibility.py --full` first, then repin.
- New event types found in the wild → fixture first, mapping second.
- The §14 self-checks are the definition of done for every phase.
