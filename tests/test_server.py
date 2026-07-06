from fastapi.testclient import TestClient

from nova.server import app as app_module
from nova.server.app import create_app


def _client(tmp_path):
    return TestClient(create_app(nova_home=tmp_path))


def _auth():
    return {"authorization": f"Bearer {app_module.LAUNCH_TOKEN}"}


def test_health_open(tmp_path):
    assert _client(tmp_path).get("/api/health").json() == {"ok": True}


def test_token_required(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/workstreams").status_code == 401
    assert c.get("/api/workstreams", headers=_auth()).status_code == 200


def test_workstream_crud(tmp_path):
    c = _client(tmp_path)
    body = {"type": "repo_pr", "title": "bump kubekit", "cwd": "/w", "gate": "pr"}
    created = c.post("/api/workstreams", json=body, headers=_auth()).json()
    assert created["title"] == "bump kubekit"
    got = c.get(f"/api/workstreams/{created['id']}", headers=_auth()).json()
    assert got == created
    assert c.get("/api/workstreams", headers=_auth()).json() == [created]
    assert c.get("/api/workstreams/nope", headers=_auth()).status_code == 404


def test_session_events_endpoint_empty(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/sessions/unknown/events", headers=_auth()).json() == []
