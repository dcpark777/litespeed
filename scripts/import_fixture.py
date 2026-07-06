"""Import a real Claude Code transcript as a scrubbed golden fixture (Step 5).
Usage: python scripts/import_fixture.py ~/.claude/projects/<...>/<id>.jsonl name
REVIEW THE OUTPUT BY EYE before committing — redaction is a filter, you are the gate.
"""
import sys
from pathlib import Path

from nova.secrets.redaction import scrub

src, name = Path(sys.argv[1]), sys.argv[2]
out = Path("tests/fixtures/golden") / f"{name}.jsonl"
out.write_text("\n".join(scrub(line) for line in src.read_text().splitlines()) + "\n")
print("wrote", out, "- now review it manually before git add")
