# Phase 0 — feasibility provenance (STUB)

> TODO(Dan): paste the full `scripts/nova_feasibility.py --full` output from
> both machines, which Bedrock config mechanism check 2 detected,
> `claude --version`, `pip show claude-agent-sdk` version, and the run dates.
> Six months from now, "why did we build on the SDK path?" must have a
> committed answer (NEXT_STEPS Step 3).

Known so far (from CLAUDE.md state and commit history):

- SDK pinned at `claude-agent-sdk==0.2.110`, feasibility-verified.
- Live pipeline probe passed on the personal machine 2026-07-06
  (PIPELINE_OK over Bedrock through `run_session`; see scripts/live_probe.py).
- Personal-machine CLI at that date: 2.1.197 (recorded in the golden fixtures).
