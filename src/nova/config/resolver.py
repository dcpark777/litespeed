"""Config precedence resolver — SPEC §3.5 (C0).

org(managed) -> commons defaults -> team -> user -> workstream; later wins,
except org keys marked `locked`. TODO(phase-1): loading, lock enforcement,
config_version compatibility (N, N-1), effective-config report for the UI.
"""
from __future__ import annotations

from typing import Any

CONFIG_VERSION = 1
LAYERS = ("org", "commons", "team", "user", "workstream")


def resolve(layers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    locked: dict[str, Any] = dict(layers.get("org", {}).get("locked", {}))
    effective: dict[str, Any] = {}
    for name in LAYERS:
        effective.update(layers.get(name, {}).get("values", {}))
    effective.update(locked)  # org-locked keys always win
    return effective
