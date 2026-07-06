"""Workstream domain: the universal unit of work (SPEC §5.1-5.2).

models (three types: repo_pr / ephemeral / maintained), store (deterministic
YAML persistence), worktrees (git worktree lifecycle for Type 1 — parallel
tasks per repo, transcripts naturally scoped by cwd). Git via subprocess,
deliberately.
"""
