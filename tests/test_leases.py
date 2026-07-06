import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from nova.index.db import connect
from nova.sessions import leases


@pytest.fixture
def con(tmp_path):
    return connect(tmp_path / "t.db")


def test_single_writer_per_cwd(con):
    leases.acquire(con, "/w1", "s1")
    with pytest.raises(leases.LeaseHeld):
        leases.acquire(con, "/w1", "s2")
    leases.acquire(con, "/w2", "s3")  # different cwd is fine


def test_release_frees_cwd(con):
    leases.acquire(con, "/w1", "s1")
    leases.release(con, "/w1")
    leases.acquire(con, "/w1", "s2")


def test_reap_dead_pid(con):
    con.execute("INSERT INTO leases VALUES(?,?,?,?)",
                ("/w1", "dead", 2**22, datetime.now(tz=timezone.utc).isoformat()))
    con.commit()
    assert leases.reap_stale(con) == ["dead"]
    leases.acquire(con, "/w1", "s2")  # reclaimable after reap


def test_reap_stale_heartbeat(con):
    old = (datetime.now(tz=timezone.utc) - timedelta(minutes=10)).isoformat()
    con.execute("INSERT INTO leases VALUES(?,?,?,?)", ("/w1", "stale", os.getpid(), old))
    con.commit()
    assert leases.reap_stale(con) == ["stale"]
