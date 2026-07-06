import subprocess

import pytest

from nova.workstreams import worktrees


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "--allow-empty", "-qm", "init"], check=True)
    return r


def test_worktree_lifecycle(repo, tmp_path):
    wt = worktrees.add(repo, tmp_path / "wts", "task/bump-kubekit")
    assert wt.exists() and (wt / ".git").exists()
    assert not worktrees.dirty(wt)
    (wt / "f.txt").write_text("x")
    assert worktrees.dirty(wt)
    worktrees.remove(repo, wt, force=True)
    worktrees.prune(repo)
    assert not wt.exists()


def test_parallel_worktrees_one_repo(repo, tmp_path):
    a = worktrees.add(repo, tmp_path / "wts", "task/a")
    b = worktrees.add(repo, tmp_path / "wts", "task/b")
    assert a != b and a.exists() and b.exists()
