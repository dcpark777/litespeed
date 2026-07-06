"""Lease manager — concurrency invariants (SPEC §3.2, C0).

Single writer per cwd; leases persisted in T2 so a crashed backend leaves an
inspectable record; stale leases are reaped on startup (dead pid or stale
heartbeat) and their workstreams marked interrupted by the caller.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

STALE_AFTER = timedelta(minutes=2)


class LeaseHeld(RuntimeError):
    """Another live session already owns this cwd."""


def acquire(con: sqlite3.Connection, cwd: str, session_id: str) -> None:
    row = con.execute("SELECT session_id, pid, heartbeat FROM leases WHERE cwd=?", (cwd,)).fetchone()
    if row and _alive(row[1], row[2]):
        raise LeaseHeld(f"cwd {cwd} held by session {row[0]}")
    con.execute(
        "INSERT OR REPLACE INTO leases(cwd, session_id, pid, heartbeat) VALUES(?,?,?,?)",
        (cwd, session_id, os.getpid(), _now()),
    )
    con.commit()


def heartbeat(con: sqlite3.Connection, cwd: str) -> None:
    con.execute("UPDATE leases SET heartbeat=? WHERE cwd=?", (_now(), cwd))
    con.commit()


def release(con: sqlite3.Connection, cwd: str) -> None:
    con.execute("DELETE FROM leases WHERE cwd=?", (cwd,))
    con.commit()


def reap_stale(con: sqlite3.Connection) -> list[str]:
    """Remove dead leases; return their session_ids for interruption handling."""
    dead: list[str] = []
    for cwd, session_id, pid, hb in con.execute("SELECT cwd, session_id, pid, heartbeat FROM leases"):
        if not _alive(pid, hb):
            dead.append(session_id)
            con.execute("DELETE FROM leases WHERE cwd=?", (cwd,))
    con.commit()
    return dead


def _alive(pid: int, hb: str) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return datetime.fromisoformat(hb) > datetime.now(tz=timezone.utc) - STALE_AFTER


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
