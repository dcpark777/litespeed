"""T1 workstream persistence: one canonical YAML file per workstream under
~/.nova/workstreams/. Same byte-deterministic discipline as notes (SPEC §3.6);
the T2 catalog is a projection of this directory (reindex-time)."""
from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

from nova.workstreams.models import Workstream

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.width = 4096


class WorkstreamStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, ws_id: str) -> Path:
        return self.root / f"{ws_id}.yaml"

    def save(self, ws: Workstream) -> Path:
        buf = io.StringIO()
        _yaml.dump(ws.model_dump(mode="json"), buf)
        p = self._path(ws.id)
        p.write_text(buf.getvalue())
        return p

    def load(self, ws_id: str) -> Workstream:
        data = _yaml.load(io.StringIO(self._path(ws_id).read_text()))
        return Workstream(**data)

    def all(self) -> list[Workstream]:
        out = []
        for p in sorted(self.root.glob("*.yaml")):
            data = _yaml.load(io.StringIO(p.read_text()))
            out.append(Workstream(**data))
        return out
