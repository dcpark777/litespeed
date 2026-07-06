"""Versioned prompt/skill artifact loader (SPEC §3.4.3, C0).

Artifacts are markdown files with {id, version, ...} frontmatter under
artifacts/ (shipped defaults) or memory-repo overrides. Every use must record
{artifact_id, version} — load() returns both so callers can't forget.
"""
from __future__ import annotations

import io
from pathlib import Path

from pydantic import BaseModel
from ruamel.yaml import YAML

_yaml = YAML()


class Artifact(BaseModel):
    id: str
    version: str
    model_hint: str | None = None
    inputs: list[str] = []
    body: str


def load(path: Path) -> Artifact:
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter")
    _, fm_raw, body = text.split("---\n", 2)
    fm = _yaml.load(io.StringIO(fm_raw)) or {}
    return Artifact(**fm, body=body.strip())


def load_dir(directory: Path) -> dict[str, Artifact]:
    """Later-loaded directories override earlier by id (config precedence order)."""
    out: dict[str, Artifact] = {}
    for p in sorted(directory.glob("*.md")):
        art = load(p)
        out[art.id] = art
    return out
