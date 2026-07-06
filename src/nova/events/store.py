"""T1 event log: append-only NovaEvent JSONL per session under ~/.nova/events/.
Canonical serialization; the reindexer and transcript UI read from here for
Nova-run sessions (T0 remains the raw Claude Code source)."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from nova.events.models import NovaEvent


class EventStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        return self.root / f"{session_id}.jsonl"

    def append(self, ev: NovaEvent) -> None:
        with self.path_for(ev.session_id).open("a") as f:
            f.write(ev.canonical_json() + "\n")

    def read(self, session_id: str) -> Iterator[NovaEvent]:
        p = self.path_for(session_id)
        if not p.exists():
            return
        for line in p.read_text().splitlines():
            if line.strip():
                yield NovaEvent.model_validate_json(line)
