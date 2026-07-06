"""T2 index — SQLite + FTS5, strictly derived (SPEC §4).

Contract: `nova reindex` rebuilds this database entirely from T0 (Claude Code
JSONL) + T1 (~/.nova canonical files). Deleting index.db is always safe; there is
deliberately no migration machinery — schema change = bump SCHEMA + reindex.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = 1

DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(doc_id, kind, title, body, tokenize='porter');
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  session_id TEXT PRIMARY KEY, workstream_id TEXT, started TEXT, ended TEXT,
  status TEXT, title TEXT, cost_usd REAL, turns INTEGER,
  playbook_id TEXT, playbook_ver TEXT);
CREATE TABLE IF NOT EXISTS workstreams(
  id TEXT PRIMARY KEY, type TEXT, status TEXT, cwd TEXT, repo TEXT, branch TEXT,
  pr_url TEXT, campaign_id TEXT, created TEXT, archived TEXT);
CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, type TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS links(src TEXT, dst TEXT, rel TEXT);
CREATE TABLE IF NOT EXISTS leases(cwd TEXT PRIMARY KEY, session_id TEXT, pid INTEGER, heartbeat TEXT);
CREATE TABLE IF NOT EXISTS metrics(ts TEXT, session_id TEXT, key TEXT, value REAL);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.execute("INSERT OR REPLACE INTO meta VALUES('schema', ?)", (str(SCHEMA),))
    return con


def reindex(db_path: Path, nova_home: Path, claude_projects: Path) -> None:
    """Full rebuild from T0+T1. TODO(phase-1): walk transcripts via
    events.jsonl_replayer and notes via memory inbox; populate fts + catalogs."""
    if db_path.exists():
        db_path.unlink()
    con = connect(db_path)
    con.commit()
    con.close()
