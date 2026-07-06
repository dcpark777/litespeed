#!/usr/bin/env python3
"""Nova Phase 0 feasibility test.

Usage:
    python3 nova_feasibility.py            # diagnostics + the one true gate (check 4)
    python3 nova_feasibility.py --full     # adds file-edit, hook, and resume checks

Run from the SAME shell where terminal Claude Code works. Stdlib-only until the
SDK checks; `pip install claude-agent-sdk` when check 3 tells you to.

Design notes (learned the hard way):
- Environment checks are DIAGNOSTIC, never gating. Bedrock can be configured via
  shell env, a settings.json env block, or a wrapper script — the script detects
  which, but only check 4 (a real turn) decides feasibility.
- Python SDK option is `cli_path` (TS SDK calls it pathToClaudeCodeExecutable);
  fields are introspected so version renames degrade gracefully.
- Verified against claude-agent-sdk 0.2.110: cli_path, cwd, permission_mode,
  resume, fork_session, hooks/HookMatcher all present.

Exit code 0 = check 4 passed (Nova as designed is feasible here).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GREEN, RED, YELLOW, CYAN, END = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[0m"
RESULTS: list[tuple[str, bool, str]] = []


def report(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    mark = f"{GREEN}PASS{END}" if ok else f"{RED}FAIL{END}"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def info(label: str, value: str) -> None:
    print(f"       {CYAN}info{END}: {label}: {value}")


# ---------------------------------------------------------------- check 1
def check_1_binary() -> bool:
    """The only hard prerequisite: a runnable claude binary."""
    claude = shutil.which("claude")
    ok = report("1a. claude binary on PATH", bool(claude), claude or "not found")
    if claude:
        try:
            v = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=15)
            ok &= report("1b. claude --version", v.returncode == 0,
                         v.stdout.strip() or v.stderr.strip())
        except Exception as e:  # noqa: BLE001
            ok &= report("1b. claude --version", False, str(e))
    return ok


# ---------------------------------------------------------------- check 2
def check_2_bedrock_mechanism() -> None:
    """DIAGNOSTIC: detect how (or whether) Bedrock is configured. Never gates —
    the real test of auth is check 4. Three known mechanisms:
      (a) shell env vars   (b) settings.json/managed "env" block   (c) wrapper script
    """
    print(f"\n{CYAN}-- Bedrock configuration mechanism (diagnostic) --{END}")
    mechanisms: list[str] = []

    # (a) shell env
    shell_flag = os.environ.get("CLAUDE_CODE_USE_BEDROCK")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if shell_flag == "1":
        mechanisms.append("shell env")
    info("shell env", f"CLAUDE_CODE_USE_BEDROCK={shell_flag!r} region={region!r}")

    # (b) settings files with env blocks
    settings_paths = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.local.json",
        Path("/etc/claude-code/managed-settings.json"),
        Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    ]
    for p in settings_paths:
        if not p.exists():
            continue
        try:
            cfg = json.loads(p.read_text())
        except Exception as e:  # noqa: BLE001
            info(str(p), f"unreadable: {e}")
            continue
        env_block = cfg.get("env") or {}
        bedrock_keys = {k: v for k, v in env_block.items()
                        if "BEDROCK" in k or k.startswith("AWS_") or "ANTHROPIC" in k}
        if bedrock_keys:
            mechanisms.append(f"settings env block ({p.name})")
            info(str(p), f"env keys: {sorted(bedrock_keys)}")
        if cfg.get("disableAllHooks"):
            report("2x. disableAllHooks not set", False,
                   f"{p} — POLICY DISABLES HOOKS: Layer-2 interception off; "
                   "Layer-1 (own-the-loop) unaffected")
        if cfg.get("permissions"):
            info(str(p), f"forced permissions present: {list(cfg['permissions'])[:5]}")

    # (c) wrapper script
    claude = shutil.which("claude")
    if claude:
        try:
            head = Path(claude).read_bytes()[:512]
            if head.startswith(b"#!") and b"exec" in head:
                mechanisms.append("wrapper script")
                info("wrapper", f"{claude} is a shell wrapper (likely exports env, then execs)")
        except Exception:  # noqa: BLE001
            pass

    for var in ("NODE_EXTRA_CA_CERTS", "HTTPS_PROXY", "AWS_PROFILE", "ANTHROPIC_BEDROCK_BASE_URL"):
        info(var, repr(os.environ.get(var)))

    if mechanisms:
        print(f"       {GREEN}detected{END}: {', '.join(dict.fromkeys(mechanisms))} — "
              "the SDK-spawned CLI inherits this; check 4 will confirm")
    else:
        print(f"       {YELLOW}none detected{END}: no shell env, settings env block, or "
              "wrapper found. Terminal Claude Code may use subscription auth here; "
              "check 4 still decides.")


# ---------------------------------------------------------------- check 3
def check_3_sdk_import() -> bool:
    try:
        import claude_agent_sdk  # type: ignore  # noqa: F401
        ver = getattr(claude_agent_sdk, "__version__", "unknown")
        return report("3. claude-agent-sdk importable", True, f"version {ver}")
    except ImportError:
        return report(
            "3. claude-agent-sdk importable", False,
            "run: pip install claude-agent-sdk — if the internal mirror 404s, that's an "
            "Artifactory request, not a design blocker; rerun after",
        )


# ---------------------------------------------------------------- SDK turn helper
async def _single_turn(prompt: str, opts_extra: dict) -> tuple[bool, str, str | None]:
    import dataclasses

    from claude_agent_sdk import ClaudeAgentOptions, query  # type: ignore

    kwargs = dict(max_turns=opts_extra.pop("max_turns", 1))
    binary = shutil.which("claude")
    if binary:
        fields = {f.name for f in dataclasses.fields(ClaudeAgentOptions)}
        for candidate in ("cli_path", "path_to_claude_code_executable"):
            if candidate in fields:
                kwargs[candidate] = binary  # vetted/wrapped binary, not the SDK bundle
                break
        else:
            print(f"       {YELLOW}note{END}: no CLI-path option in this SDK version; "
                  "bundled CLI will be used — flag this")
    kwargs.update(opts_extra)
    session_id, texts = None, []
    async for msg in query(prompt=prompt, options=ClaudeAgentOptions(**kwargs)):
        name = type(msg).__name__
        session_id = getattr(msg, "session_id", session_id)
        if hasattr(msg, "result"):
            texts.append(str(msg.result))
        if "Error" in name or getattr(msg, "is_error", False):
            return False, f"{name}: {getattr(msg, 'result', msg)!r}", session_id
    return True, " ".join(texts)[-200:], session_id


# ---------------------------------------------------------------- check 4
def check_4_live_turn() -> tuple[bool, str | None]:
    """THE gate: SDK spawns the CLI, auth resolves (however configured), turn completes."""
    try:
        ok, detail, sid = asyncio.run(_single_turn("Reply with exactly: SDK_OK", {}))
        passed = ok and "SDK_OK" in detail
        report("4. live single turn (SDK_OK)", passed,
               detail if not passed else f"session {sid}")
        if not passed:
            low = detail.lower()
            if any(s in detail for s in ("AccessDenied", "ExpiredToken")) or "credential" in low:
                print(f"       {YELLOW}hint{END}: IAM/auth — bedrock:InvokeModel* on the model "
                      "IDs, region vs `claude /status`, SSO token freshness")
            if "haiku" in low or "inference profile" in low:
                print(f"       {YELLOW}hint{END}: small/fast (Haiku) model access missing "
                      "from the role/inference profiles")
            if "enoent" in low or "spawn" in low:
                print(f"       {YELLOW}hint{END}: subprocess spawn — PATH from the launching "
                      "env, or NODE_EXTRA_CA_CERTS missing behind corporate proxy; diff "
                      "this script's env against your working terminal's")
            if "tool" in low and "search" in low:
                print(f"       {YELLOW}hint{END}: Bedrock tool-search incompatibility — "
                      "disable tool search via env for Nova sessions")
        return passed, sid
    except Exception as e:  # noqa: BLE001
        report("4. live single turn", False, f"{type(e).__name__}: {e}")
        return False, None


# ---------------------------------------------------------------- check 5
def check_5_file_edit() -> bool:
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "hello.txt"
        target.write_text("hello\n")
        try:
            ok, detail, _ = asyncio.run(_single_turn(
                f"Replace the word hello with goodbye in {target}. Only edit that file.",
                {"max_turns": 5, "cwd": td, "permission_mode": "acceptEdits"},
            ))
            edited = target.read_text().strip() == "goodbye"
            return report("5. file-edit turn (scoped cwd)", ok and edited,
                          detail if not (ok and edited) else "file edited correctly")
        except Exception as e:  # noqa: BLE001
            return report("5. file-edit turn (scoped cwd)", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- check 6
def check_6_hook_fires() -> bool:
    fired = {"v": False}

    async def hook(*a, **k):  # tolerant signature across SDK versions
        fired["v"] = True
        return {}

    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "x.txt").write_text("x\n")
        try:
            from claude_agent_sdk import HookMatcher  # type: ignore
            hooks = {"PreToolUse": [HookMatcher(hooks=[hook])]}
        except ImportError:
            hooks = {"PreToolUse": [{"hooks": [hook]}]}
        try:
            asyncio.run(_single_turn(
                f"Read the file {td}/x.txt and tell me its contents.",
                {"max_turns": 3, "cwd": td, "hooks": hooks},
            ))
        except Exception as e:  # noqa: BLE001
            return report("6. PreToolUse hook fires", False, f"{type(e).__name__}: {e}")
    return report("6. PreToolUse hook fires", fired["v"],
                  "" if fired["v"] else "hook never ran — if a managed-settings file above "
                  "sets disableAllHooks, this is policy (caveat, not blocker); otherwise "
                  "inspect this SDK version's hook API")


# ---------------------------------------------------------------- check 7
def check_7_resume(prev_session: str | None) -> bool:
    if not prev_session:
        return report("7. resume prior session", False, "no session id from check 4")
    try:
        ok, detail, _ = asyncio.run(_single_turn(
            "What exact string did I ask you to reply with earlier? Answer with just it.",
            {"resume": prev_session, "max_turns": 1},
        ))
        passed = ok and "SDK_OK" in detail
        return report("7. resume prior session", passed, detail[-120:])
    except Exception as e:  # noqa: BLE001
        return report("7. resume prior session", False, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true",
                    help="also run file-edit, hook, and resume checks")
    ap.add_argument("--no-bedrock", action="store_true",
                    help="deprecated no-op (env checks are diagnostic-only now)")
    args = ap.parse_args()

    print("== Nova Phase 0 feasibility ==\n")
    binary_ok = check_1_binary()
    check_2_bedrock_mechanism()
    print()
    sdk_ok = check_3_sdk_import()

    turn_ok, session_id = (False, None)
    if binary_ok and sdk_ok:
        turn_ok, session_id = check_4_live_turn()
    else:
        print(f"\n{YELLOW}Skipping live checks — need the binary (1) and the SDK (3).{END}")

    if args.full and turn_ok:
        check_5_file_edit()
        check_6_hook_fires()
        check_7_resume(session_id)
    elif args.full:
        print(f"{YELLOW}Skipping --full checks: check 4 must pass first.{END}")

    print("\n== Verdict ==")
    failures = [name for name, ok, _ in RESULTS if not ok]
    if turn_ok and not failures:
        print(f"{GREEN}FEASIBLE{END} — Nova as designed works in this environment. "
              "Next: git init the scaffold, commit SPEC.md, install nova[agent], Phase 1.")
    elif turn_ok:
        print(f"{YELLOW}FEASIBLE WITH CAVEATS{END} — the core loop works; address: "
              f"{', '.join(failures)}. A hook-only failure = Layer-2 interception off; "
              "the design otherwise stands.")
    else:
        print(f"{RED}BLOCKED{END} — the SDK-driven core loop failed. Diagnose via the "
              "hints and the mechanism diagnostic above; if the cause is unfixable policy, "
              "the fallback is the PTY/JSONL architecture we ruled out — a design change, "
              "so stop and reassess before writing Nova code.")
    return 0 if turn_ok else 1


if __name__ == "__main__":
    sys.exit(main())
