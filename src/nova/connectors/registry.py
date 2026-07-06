"""Connector discovery via entry points (SPEC §15.3). Enabling a connector is a
config change; shipping one is a wheel exposing `nova.connectors` entry points.
Interface conformance (connector_api N / N-1) is checked at load, not call, time.
"""
from __future__ import annotations

from importlib.metadata import entry_points

from nova.connectors.protocol import CONNECTOR_API_VERSION, Connector

_SUPPORTED = {CONNECTOR_API_VERSION, CONNECTOR_API_VERSION - 1}


class ConnectorLoadError(RuntimeError):
    pass


def discover(enabled: list[str]) -> dict[str, Connector]:
    found: dict[str, Connector] = {}
    for ep in entry_points(group="nova.connectors"):
        if ep.name not in enabled:
            continue
        conn = ep.load()()
        if not isinstance(conn, Connector):
            raise ConnectorLoadError(f"{ep.name}: does not satisfy Connector protocol")
        if conn.connector_api not in _SUPPORTED:
            raise ConnectorLoadError(
                f"{ep.name}: connector_api {conn.connector_api} unsupported (want {_SUPPORTED})"
            )
        found[conn.id] = conn
    missing = set(enabled) - set(found)
    if missing:
        raise ConnectorLoadError(f"enabled but not installed: {sorted(missing)}")
    return found
