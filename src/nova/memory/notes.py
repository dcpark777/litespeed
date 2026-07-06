"""Memory note contract (SPEC §3.6, C0): frontmatter model + byte-deterministic
serialization so git diffs are always meaningful. Links are by id, never path.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from ruamel.yaml import YAML
from ulid import ULID

NOTE_VERSION = 1

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096
_yaml.sort_base_mapping_type_on_output = False  # we control order via model


class NoteType(str, Enum):
    decision = "decision"
    distillate = "distillate"
    standard = "standard"
    playbook = "playbook"
    entity = "entity"


class NoteStatus(str, Enum):
    inbox = "inbox"
    curated = "curated"


class Source(BaseModel):
    session_id: str | None = None
    workstream_id: str | None = None
    repo: str | None = None
    distiller: dict[str, str] | None = None  # {id, version}


class Note(BaseModel):
    # Field declaration order == canonical key order in serialized frontmatter.
    id: str = Field(default_factory=lambda: str(ULID()))
    note_version: int = NOTE_VERSION
    type: NoteType
    title: str
    created: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source: Source = Field(default_factory=Source)
    entities: list[str] = Field(default_factory=list)
    status: NoteStatus = NoteStatus.inbox
    body: str = ""  # markdown; not part of frontmatter

    def serialize(self) -> str:
        """Canonical: declared key order, LF, exactly one trailing newline."""
        fm = self.model_dump(mode="json", exclude={"body"})
        buf = io.StringIO()
        _yaml.dump(fm, buf)
        return f"---\n{buf.getvalue()}---\n{self.body.rstrip()}\n"

    @classmethod
    def parse(cls, text: str) -> "Note":
        if not text.startswith("---\n"):
            raise ValueError("missing frontmatter")
        _, fm_raw, body = text.split("---\n", 2)
        fm = _yaml.load(io.StringIO(fm_raw)) or {}
        return cls(**fm, body=body.strip("\n"))

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.id}.md"
        path.write_text(self.serialize())
        return path
