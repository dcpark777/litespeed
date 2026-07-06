"""Append-only audit log — SPEC §3.3 (C0). Local JSONL under ~/.nova/audit/;
never in shared git; exportable on demand. Records decisions and credential
*use* (refs), never secret values or file contents.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def record(audit_dir: Path, action: str, **fields: Any) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(tz=timezone.utc)
    entry = {"ts": day.isoformat(), "action": action, **fields}
    path = audit_dir / f"{day:%Y-%m-%d}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
