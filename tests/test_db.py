"""Connection mechanics for the T2 index (kept separate from ingestion tests)."""
from nova.index.db import SCHEMA, connect


def test_connect_creates_missing_parent(tmp_path):
    """Regression: first-run on a fresh machine (no ~/.nova yet) must not fail."""
    con = connect(tmp_path / "not" / "yet" / "index.db")
    con.close()


def test_schema_recorded_in_meta(tmp_path):
    con = connect(tmp_path / "index.db")
    row = con.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
    assert row == (str(SCHEMA),)
    con.close()
