"""FastAPI app — localhost-only, per-launch bearer token (SPEC §7 security).

Wiring: T1 stores under NOVA_HOME; sessions stream NovaEvents over WebSocket.
The frontend is a pure view over this API — no other backchannel exists.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nova.events.store import EventStore
from nova.index.db import connect
from nova.workstreams.models import Gate, Status, Workstream, WorkstreamType
from nova.workstreams.store import WorkstreamStore

LAUNCH_TOKEN = os.environ.get("NOVA_TOKEN") or secrets.token_urlsafe(32)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def require_token(request: Request) -> None:
    if request.headers.get("authorization") != f"Bearer {LAUNCH_TOKEN}":
        raise HTTPException(status_code=401, detail="missing or invalid launch token")


class CreateWorkstream(BaseModel):
    type: WorkstreamType
    title: str
    cwd: str
    gate: Gate
    repo: str | None = None
    branch: str | None = None


class StartSession(BaseModel):
    prompt: str
    permission_mode: str = "default"
    resume: str | None = None
    fork: bool = False
    max_turns: int | None = None


def create_app(nova_home: Path | None = None) -> FastAPI:
    home = nova_home or Path(os.environ.get("NOVA_HOME", Path.home() / ".nova"))
    app = FastAPI(title="nova", docs_url=None, redoc_url=None)
    app.state.workstreams = WorkstreamStore(home / "workstreams")
    app.state.events = EventStore(home / "events")
    app.state.db = lambda: connect(home / "index.db")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/workstreams", dependencies=[Depends(require_token)])
    def list_workstreams() -> list[Workstream]:
        return app.state.workstreams.all()

    @app.post("/api/workstreams", dependencies=[Depends(require_token)])
    def create_workstream(body: CreateWorkstream) -> Workstream:
        ws = Workstream(created=datetime.now(tz=timezone.utc), **body.model_dump())
        app.state.workstreams.save(ws)
        return ws

    @app.get("/api/workstreams/{ws_id}", dependencies=[Depends(require_token)])
    def get_workstream(ws_id: str) -> Workstream:
        try:
            return app.state.workstreams.load(ws_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="unknown workstream")

    @app.get("/api/sessions/{session_id}/events", dependencies=[Depends(require_token)])
    def session_events(session_id: str) -> list:
        return [ev.model_dump(mode="json") for ev in app.state.events.read(session_id)]

    @app.websocket("/ws/workstreams/{ws_id}/session")
    async def session_ws(websocket: WebSocket, ws_id: str) -> None:
        """Start (or resume) a session for a workstream; stream NovaEvents as JSON.
        Token via first message: {"token": ..., "start": {StartSession fields}}."""
        await websocket.accept()
        first = await websocket.receive_json()
        if first.get("token") != LAUNCH_TOKEN:
            await websocket.close(code=4401)
            return
        try:
            ws = app.state.workstreams.load(ws_id)
        except FileNotFoundError:
            await websocket.close(code=4404)
            return
        start = StartSession(**first.get("start", {}))
        from nova.sessions.runner import run_session  # deferred: needs nova[agent]
        con = app.state.db()
        try:
            async for ev in run_session(
                con, app.state.events, Path(ws.cwd), start.prompt,
                workstream_id=ws.id, permission_mode=start.permission_mode,
                resume=start.resume, fork=start.fork, max_turns=start.max_turns,
            ):
                await websocket.send_text(ev.canonical_json())
        except Exception as e:  # noqa: BLE001 - surface, don't hide
            await websocket.send_json({"error": type(e).__name__, "detail": str(e)})
        finally:
            con.close()
            await asyncio.shield(websocket.close())

    if STATIC_DIR.exists() and any(p.name != ".gitkeep" for p in STATIC_DIR.iterdir()):
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
