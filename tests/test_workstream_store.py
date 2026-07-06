from datetime import datetime, timezone

from nova.workstreams.models import Gate, Workstream, WorkstreamType
from nova.workstreams.store import WorkstreamStore


def test_roundtrip(tmp_path):
    store = WorkstreamStore(tmp_path)
    ws = Workstream(type=WorkstreamType.repo_pr, title="bump kubekit", cwd="/w",
                    gate=Gate.pr, created=datetime.now(tz=timezone.utc),
                    repo="git@internal:ml/pipeline-a", branch="task/bump")
    store.save(ws)
    loaded = store.load(ws.id)
    assert loaded == ws
    assert store.all() == [ws]


def test_save_is_deterministic(tmp_path):
    store = WorkstreamStore(tmp_path)
    ws = Workstream(type=WorkstreamType.ephemeral, title="t", cwd="/s", gate=Gate.none,
                    created=datetime(2026, 7, 1, tzinfo=timezone.utc))
    p = store.save(ws)
    once = p.read_text()
    store.save(store.load(ws.id))
    assert p.read_text() == once
