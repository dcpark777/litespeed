"""Pre-commit guard: secret patterns and stray transcripts must not enter git.

Staged mode (default) scans the STAGED blobs (`git show :<path>`), not the
worktree — what you commit is what gets checked. `--all` scans every tracked
text file (used by `make secretscan` and CI).

Uses the same patterns as the runtime redaction filter (nova.secrets.redaction),
so the DLP boundary is one definition, enforced in three places: event ingestion,
memory promotion, and here (SPEC §16.3).
"""

from __future__ import annotations

import subprocess
import sys

from nova.secrets.redaction import contains_secret

GOLDEN_DIR = "tests/fixtures/golden/"
ALLOW_MARKER = "nova:allow-secret"


def _git_z(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], check=True, capture_output=True).stdout
    return [p.decode() for p in out.split(b"\0") if p]


def _staged_paths() -> list[str]:
    return _git_z("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z")


def _tracked_paths() -> list[str]:
    return _git_z("ls-files", "-z")


def _read(path: str, staged: bool) -> str | None:
    """File text, or None for binary/unreadable content."""
    try:
        if staged:
            blob = subprocess.run(["git", "show", f":{path}"], check=True,
                                  capture_output=True).stdout
        else:
            with open(path, "rb") as f:
                blob = f.read()
        return blob.decode("utf-8")
    except (subprocess.CalledProcessError, OSError, UnicodeDecodeError):
        return None


def main() -> int:
    scan_all = "--all" in sys.argv[1:]
    paths = _tracked_paths() if scan_all else _staged_paths()
    problems: list[str] = []

    for path in paths:
        if path.endswith(".jsonl") and not path.startswith(GOLDEN_DIR):
            problems.append(
                f"{path}: .jsonl outside {GOLDEN_DIR} — raw transcripts never enter "
                "git; import via scripts/import_fixture.py and review every line"
            )
        text = _read(path, staged=not scan_all)
        if text is None:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if ALLOW_MARKER in line:  # deliberate fake secret (tests); reviewed in PR
                continue
            if contains_secret(line):
                problems.append(f"{path}:{line_no}: secret pattern detected "
                                f"(intentional test fake? mark the line {ALLOW_MARKER})")

    if not scan_all:
        for path in paths:
            if path.startswith(GOLDEN_DIR):
                print(f"note: staging golden fixture {path} — a human must have "
                      "reviewed every line (CLAUDE.md fixture rule)")

    if problems:
        print("check_staged: BLOCKED", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
