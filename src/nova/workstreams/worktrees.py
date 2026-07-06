"""Type 1 backing: git worktree lifecycle (SPEC §5.2). Plain `git` subprocess —
deterministic, matches vetted tooling, trivially auditable."""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def add(repo: Path, worktrees_root: Path, branch: str, base: str = "HEAD") -> Path:
    """Create a worktree on a new task branch; return its path."""
    worktrees_root.mkdir(parents=True, exist_ok=True)
    path = worktrees_root / branch.replace("/", "__")
    _git(repo, "worktree", "add", "-b", branch, str(path), base)
    return path


def remove(repo: Path, worktree_path: Path, *, force: bool = False) -> None:
    args = ["worktree", "remove", str(worktree_path)]
    if force:
        args.append("--force")
    _git(repo, *args)


def prune(repo: Path) -> None:
    _git(repo, "worktree", "prune")


def dirty(worktree_path: Path) -> bool:
    return bool(_git(worktree_path, "status", "--porcelain"))
