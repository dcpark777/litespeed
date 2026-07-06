"""Nova CLI: up | dev | doctor | reindex."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

NOVA_HOME = Path(os.environ.get("NOVA_HOME", Path.home() / ".nova"))


@app.command()
def up(window: bool = typer.Option(False, help="Open in a pywebview native window"),
       port: int = 8642) -> None:
    """Start the backend and open the UI."""
    import uvicorn
    from nova.server.app import create_app
    if window:
        console.print("[yellow]--window requires nova[window]; falling back if missing.[/]")
    console.print(f"Nova on http://127.0.0.1:{port}")
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


@app.command()
def reindex() -> None:
    """Rebuild the T2 index from T0+T1. Always safe (SPEC §4)."""
    from nova.index.reindex import reindex as _reindex
    stats = _reindex(
        NOVA_HOME / "index.db",
        Path.home() / ".claude" / "projects",
        [NOVA_HOME / "inbox", NOVA_HOME / "memory"],
        events_dir=NOVA_HOME / "events",
        workstreams_dir=NOVA_HOME / "workstreams",
    )
    console.print(f"[green]reindex complete[/] {stats}")


@app.command()
def doctor() -> None:
    """Validate the environment (SPEC §9). Safe to run before anything else —
    this IS the productized Phase 0 smoke test's read-only half."""
    t = Table(title="nova doctor")
    t.add_column("check"); t.add_column("status"); t.add_column("detail")

    claude = shutil.which("claude")
    t.add_row("claude binary", _ok(bool(claude)), claude or "not on PATH")

    mech, detail = _bedrock_mechanism()
    t.add_row("bedrock config mechanism", _ok(mech is not None),
              detail if mech else "none detected — if terminal Claude Code works, "
              "run the live probe; a real turn is the true test")

    try:
        import claude_agent_sdk  # type: ignore  # noqa: F401
        t.add_row("claude-agent-sdk", "[green]ok[/]", "importable")
    except ImportError:
        t.add_row("claude-agent-sdk", "[yellow]missing[/]", "install nova[agent] after smoke test")

    for managed in ("/etc/claude-code/managed-settings.json",
                    "/Library/Application Support/ClaudeCode/managed-settings.json"):
        p = Path(managed)
        if p.exists():
            hint = "check disableAllHooks / forced permissions"
            t.add_row("managed settings", "[yellow]present[/]", f"{managed} — {hint}")

    console.print(t)


def _bedrock_mechanism() -> tuple[str | None, str]:
    """Detect HOW Bedrock is configured (shell env / settings env block / wrapper).
    Diagnostic only — mirrors the Phase 0 feasibility script; a live turn is the
    real test. Shell env is only one of three mechanisms, so its absence is not
    a failure."""
    import json

    if os.environ.get("CLAUDE_CODE_USE_BEDROCK") == "1":
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        return "shell env", f"shell env (region={region})"

    for sp in (Path.home() / ".claude" / "settings.json",
               Path.home() / ".claude" / "settings.local.json",
               Path("/etc/claude-code/managed-settings.json"),
               Path("/Library/Application Support/ClaudeCode/managed-settings.json")):
        if not sp.exists():
            continue
        try:
            env_block = json.loads(sp.read_text()).get("env") or {}
        except Exception:  # noqa: BLE001
            continue
        keys = [k for k in env_block if "BEDROCK" in k or k.startswith("AWS_") or "ANTHROPIC" in k]
        if keys:
            return "settings env block", f"{sp.name}: {sorted(keys)}"

    claude = shutil.which("claude")
    if claude:
        try:
            head = Path(claude).read_bytes()[:512]
            if head.startswith(b"#!") and b"exec" in head:
                return "wrapper script", f"{claude} (shell wrapper)"
        except Exception:  # noqa: BLE001
            pass
    return None, ""


def _ok(cond: bool) -> str:
    return "[green]ok[/]" if cond else "[red]fail[/]"


if __name__ == "__main__":
    app()
