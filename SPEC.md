# Nova — Platform Specification

**Version:** 0.2.1-draft · **Status:** pre-implementation · **Owner:** Dan
**One-liner:** A lightweight, local-first desktop cockpit for orchestrating Claude Code work — sessions, review gates, curated memory, and fleet campaigns — for a Bedrock-authenticated, sandboxed enterprise environment.

---

## 0. Criticality legend

| Tier | Meaning |
|------|---------|
| **C0 — Contract** | Must be designed correctly before first build. Everything downstream depends on it; retrofit is a migration. |
| **C1 — Foundation** | Build early; retrofit is painful but survivable. |
| **C2 — Iterative** | Build when pulled by need; safe to rewrite. |

---

## 1. Non-goals (explicit)

- **No cloud sync, no shared server, ever.** Nova is per-machine; collaboration flows only through git. (Prevents drift back toward Nimbalyst-with-sync.)
- No mobile, browser-extension, or non-Claude model integrations.
- No WYSIWYG rendered-markdown diff editing in v1. Review is PR-style text diffs. (Lexical vendoring remains a documented future option; see §12.)
- No autonomous background agents. Monitors *propose* work into human-gated queues; nothing runs without a human decision.
- No general workflow engine. Campaign ordering is phased lists, not DAG tooling.
- **No full IDE.** Nova's editor is capable (syntax highlighting, search, multi-file), but LSP servers, debuggers, and refactoring tooling are out of scope — that's what the team's IDEs are for. Documented exit in §12 if demand proves real.
- **Nova never stores secret values at rest.** No credentials in config files, T1, T3/git, logs, or transcripts — only credential *references* resolved at use time (§16).

---

## 2. Architecture summary

```
┌─────────────────────────────────────────────────────────┐
│  pywebview window (or chrome --app / browser tab)       │
│  React + Vite SPA  — pure view over HTTP/WS             │
└───────────────▲─────────────────────────────────────────┘
                │ HTTP / WebSocket (localhost only, token-auth)
┌───────────────┴─────────────────────────────────────────┐
│  FastAPI backend (single Python process)                 │
│  ├─ Workstream manager (worktrees, scratch, local git)   │
│  ├─ Session runner — Python Agent SDK → vetted `claude`  │
│  │   binary (CLAUDE_CODE_USE_BEDROCK=1)                  │
│  ├─ Campaign orchestrator (queue, caps, backoff)         │
│  ├─ Event normalizer (SDK stream + JSONL → Nova schema)  │
│  ├─ Memory pipeline (distiller → inbox → PR promotion)   │
│  ├─ Index service (SQLite FTS5, rebuildable)             │
│  └─ Audit log (append-only)                              │
└───────────────┬─────────────────────────────────────────┘
                │ subprocess / filesystem / git / AWS creds
        vetted claude CLI · git worktrees · ~/.nova · GitHub
```

**Key stack decisions (settled):**
- Backend: **Python + FastAPI**, Python **claude-agent-sdk**, pointed at the vetted binary via `path_to_claude_code_executable`. Rationale: reuse of sessionkit/taskboard, team readability (20 data scientists), pywebview desktop story.
- Frontend: **React + Vite**, communicates only via HTTP/WS. No Electron, no IPC.
- Window: **Tier 1** `chrome --app=` launcher; **Tier 2** pywebview (`nova up --window`). WKWebView (macOS) / WebView2 (Windows — verify runtime presence once).
- Distribution: CI-built wheel (React `dist/` embedded in package static dir). Stage 0: editable install. Stage 1: GitHub release asset + `uv tool install <url>`. Stage 2: Artifactory + `uv tool install nova`. Never commit `dist/` to git.

---

## 3. C0 Contracts (the seven)

These are the load-bearing decisions. Spec each fully before writing feature code.

### 3.1 Normalized event schema — **C0**

All rendering, indexing, and automation consume **Nova events**, never raw SDK messages or raw JSONL. Translation happens once, at the provider boundary.

```yaml
# NovaEvent (stored as JSONL in T1 per session; also streamed over WS)
schema_version: 1            # REQUIRED on every record
event_id: ulid
session_id: string           # Claude Code session id
workstream_id: ulid
ts: iso8601
kind: enum                   # session_started | user_message | assistant_text |
                             # tool_call | tool_result | subagent_started |
                             # subagent_finished | permission_request |
                             # permission_decision | session_interrupted |
                             # session_result | error
payload: object              # kind-specific, versioned with schema_version
provenance:
  source: enum               # sdk_stream | jsonl_replay
  provider: claude-code
  sdk_version: string
  cli_version: string
```

Rules:
- Live SDK stream and historical JSONL replay MUST produce identical NovaEvents for the same session (tested with golden fixtures).
- Unknown SDK message types are preserved as `kind: error`-free passthrough events with raw payload — never dropped silently.
- Bump `schema_version` on any breaking change; readers must support N and N−1.

### 3.2 Concurrency invariants — **C0**

- **Single writer per cwd:** at most one active session per workstream working directory. Enforced by the session runner, not by convention.
- **Global cap:** configurable max concurrent sessions (default 4). Campaigns get per-campaign caps ≤ global.
- **Leases:** running sessions hold a lease record (pid, started_at, heartbeat) in SQLite. On backend start, stale leases are reaped and workstreams marked `interrupted`, then reattached via SDK `resume` where possible.
- **Bedrock backoff:** throttling errors trigger exponential backoff with jitter at the queue level (library: `tenacity`), not inside agent prompts.

### 3.3 Permission & audit model — **C0**

- Permission mode is a **workstream-type default**, overridable per workstream via config precedence (§3.5):
  - Type 1 (repo/PR): standard tool gating; write access scoped to the worktree.
  - Type 2 (ephemeral): permissive within scratch dir.
  - Type 3 (maintained): file edits permissive within its repo; **external side-effects always gated** (change-plan review before apply).
- **Audit log:** append-only JSONL in `~/.nova/audit/`, one record per: tool permission decision, gate decision (accept/reject/revise), external apply, campaign launch, memory promotion. Fields: audit_version (REQUIRED, currently 1; readers support N and N−1), ts, actor (user|policy), action, subject, workstream_id?, session_id?, decision?, rationale?. The typed model in `nova.audit.log.AuditRecord` is the normative shape — callers construct it, never free-form dicts. Never stored in shared git; exportable on demand.
- SDK `PreToolUse` hooks implement interception; keep hook bodies fast (they sit on the agent's critical path). Verify org managed-settings does not set `disableAllHooks` (see §13 smoke test).

### 3.4 Extension seams — **C0**

Exactly four, all versioned interfaces:

1. **Artifact panel registry** — `(filetype | content-matcher) → React panel component` + optional backend companion (e.g., CSV canonical serializer). Panels may read workstream files via API and propose edits; they cannot spawn sessions or bypass gates. The **default panel is the text/code editor** (§5.6) — every file is editable; richer panels override per filetype.
2. **Selection-context → scoped-agent-call primitive** — generic contract:
   `{artifact_path, selection: {ids|ranges, labels}, instruction} → scoped query() (single turn budget, file-edit tool only, cwd-scoped) → deterministic validator gate → write | retry-once-with-error | surface failure`.
   Mermaid click-to-edit is the first client; CSV cell-selection is the second.
3. **Versioned prompt/skill artifacts** — distillers, playbooks, classifiers, edit-templates are files in git with frontmatter `{id, version, inputs, model_hint}`. Never string literals in code. Every use records `{artifact_id, version}` in the audit/provenance trail.
4. **External connectors** — versioned plugins for external systems (Jira, Jenkins, Snowflake, GitHub API, Slack…). Interface contract in §15: typed `pull` (read → local snapshot), `plan` (proposed changes → reviewable artifact), `apply(plan)` (gated execution), `health()`, and a declared credential-requirements manifest. Connector *reads* may be exposed to agents as tools; connector *writes* are never agent-callable — only plan generation is, and apply is human-gated in core.

Hard rule: **nothing behind an extension boundary may create workstreams, start sessions, or alter concurrency/permission state.** Campaigns, queue, gates live in core only.

### 3.5 Config precedence — **C0**

`org (managed) → commons defaults → team → user → workstream`, later wins except org-managed keys marked `locked`. Stored as YAML; resolved config viewable in UI ("effective config" panel). Config schema carries `config_version`; Nova releases declare which versions they read (support N, N−1).

Configurable at minimum: model ids (main + small/fast), permission presets per workstream type, concurrency caps, distiller artifact id/version, memory source list, campaign defaults.

### 3.6 Memory & note contract — **C0**

Every note (inbox candidate or curated):

```yaml
---
id: ulid                # stable; ALL links are by id, never path/title
note_version: 1
type: decision | distillate | standard | playbook | entity
title: string
created: iso8601
source:                 # provenance, REQUIRED
  session_id: string?
  workstream_id: ulid?
  repo: string?
  distiller: {id, version}?
entities: [ids]         # typed links
status: inbox | curated
---
(markdown body)
```

- Byte-deterministic serialization (canonical key order, LF, trailing newline) so git diffs are always meaningful. Library: `ruamel.yaml` (round-trip mode) or `python-frontmatter` with a canonical dumper.
- Raw transcripts NEVER enter shared git. The inbox → PR gate is the DLP boundary.

### 3.7 Multi-team federation & trajectory — **C0 (decision), C2 (build)**

- Repos: `nova` (platform), `nova-commons` (org knowledge + default team-config templates), `nova-memory-<team>` (spokes; GitHub permissions = access control), per-workstream maintained-state repos.
- Memory sources are an **ordered list** in config; T2 merges at reindex with precedence (team overrides commons). Build the list mechanism now; stand up spokes lazily.
- Promotion ladder: local inbox → team repo (PR) → commons (PR), CODEOWNERS at each rung.
- Written decision: multi-user NEVER means shared server or shared DB.

---

## 4. Storage layers

| Tier | What | Where | Truth? | Notes |
|------|------|-------|--------|-------|
| **T0** | Claude Code JSONL transcripts | `~/.claude/projects/…` | Runtime truth (external) | Read-only feed. Never migrated, copied to git, or edited. |
| **T1** | Nova canonical files | `~/.nova/` + per-project `.nova/` | **Yes** | Workstreams, NovaEvent logs, gate decisions, memory inbox, audit. Deterministic markdown/YAML/JSONL, ULIDs. |
| **T2** | SQLite | `~/.nova/index.db` | No — derived | FTS5 (transcripts, notes, playbooks), session catalog, entity/link tables, leases, metrics. `nova reindex` rebuilds fully from T0+T1. No migrations discipline needed — delete on schema change. |
| **T3** | Git/GitHub | hub-and-spoke repos (§3.7) | Yes (curated) | Only human-reviewed content. |

**T2 sketch (indicative, disposable):**

```sql
CREATE VIRTUAL TABLE fts USING fts5(doc_id, kind, title, body, tokenize='porter');
CREATE TABLE sessions(session_id PRIMARY KEY, workstream_id, started, ended,
                      status, title, cost_usd, turns, playbook_id, playbook_ver);
CREATE TABLE workstreams(id PRIMARY KEY, type, status, cwd, repo, branch,
                         pr_url, campaign_id, created, archived);
CREATE TABLE entities(id PRIMARY KEY, type, name);         -- repos, services, datasets…
CREATE TABLE links(src, dst, rel);                          -- imports, references, mentions
CREATE TABLE leases(cwd PRIMARY KEY, session_id, pid, heartbeat);
CREATE TABLE metrics(ts, session_id, key, value);
```

Agents read memory through **one query tool** (Nova MCP tool or injected context, §11.1) over T2 — never by grepping folders. Gives ranking, scoping, per-source filtering, and one choke point for access control.

---

## 5. Domain model

### 5.1 Workstream — the universal unit

```yaml
id: ulid
type: repo_pr | ephemeral | maintained
title: string
status: inbox | active | gating | done | interrupted | archived
cwd: path
sessions: [session_id]
gate: pr | local_diff | change_plan | none
lifecycle:
  archive_after_days: int?     # ephemeral default 7
  recurrence: rrule?           # maintained only (library: APScheduler)
campaign_id: ulid?
# type-specific
repo: {url, base_branch, task_branch, worktree_path, pr_url}?      # repo_pr
state_repo: {path}?                                                 # maintained
```

### 5.2 The three types

| | **Type 1: repo_pr** | **Type 2: ephemeral** | **Type 3: maintained** |
|---|---|---|---|
| Backing | `git worktree add` per task branch | `~/.nova/scratch/<ulid>` | Nova-managed **local git repo** |
| Gate | local diff (triage) → **GitHub PR** (real review) | none (unless files produced) | **change-plan before external apply** |
| Lifecycle | auto-archive on PR merge; prune worktree | distill → move outputs → auto-archive N days | recurrence-capable; auto-commit after each session with session_id in message |
| External systems | — | — | via **deterministic edge scripts** (`jira-sync pull` / `apply changes.yaml`) — agent produces reviewable artifacts, never freehand API calls |

Worktrees (not clones) for Type 1: parallel tasks per repo, cheap cleanup, and Claude Code keys transcripts by cwd → naturally scoped session history. Git operations via `git` CLI subprocess (deterministic, matches vetted tooling); `pygit2` only if perf demands.

### 5.3 Sessions

- Started/resumed exclusively through the session runner: Python `claude_agent_sdk.query()` with `options.resume` / `options.fork_session` for resume/branching.
- Persistent chats/tabs = frontend state over the T2 session catalog; transcripts render from NovaEvents (live stream and JSONL replay are indistinguishable to the UI).
- Titles: cheap small-model call on first exchange.
- Lifecycle automation: **Layer 1** (own-the-loop code before/after/around the stream) for observation and post-session work — cannot be policy-disabled, never slows the agent. **Layer 2** (SDK in-process hook callbacks) only for genuine interception.

### 5.4 Campaigns — **core object, C1**

Map-reduce with human gates, for multi-repo work (single sessions degrade: context compaction, error propagation, needless serialization).

- **Plan:** pilot 2–3 repos interactively → extract **playbook** (versioned artifact). Calibration bar: a fresh session must complete pilot repo #3 from the playbook alone.
- **Map:** one Type-1 workstream per repo, fresh session per repo, deterministic queue honoring caps + Bedrock backoff. Phased ordering via simple dependency lists (`phase 1: [shared-lib]; phase 2: [rest]`).
- **Reduce:** dashboard lane — merged / PR-open / failed-retryable / needs-human. Failure triage: small-model classifier (versioned artifact) bucketing transcripts into `flaky-retry | assumptions-mismatch | playbook-bug`.
- Every run records `{playbook_id, playbook_version}`; mid-campaign playbook fixes bump the version, enabling "which repos ran v1?" re-run decisions.
- Not subagents: teammates/subagents parallelize *within* one repo's task; cross-repo isolation demands separate sessions.
- UI: no new panel class — a kanban lane grouping + one campaign detail route + creation form. Repo-set *selectors* may become pluggable (read-only queries) later.

### 5.5 Review model

- Primary: **PR-style text diffs**. Library: `@codemirror/merge` (per-hunk accept/reject built in) or Monaco diff editor. Build per-hunk since it's free, but design the workflow around **accept-all / reject-and-revise**: a one-click "revise with feedback" that reopens the session with the comment is the 10× feature.
- **Gate granularity is a UI concern, not a data concern** — persist decisions at file/change-set level (store full proposed content), so a future richer editor is a component swap, not a schema migration. No line-number-keyed records anywhere persistent.
- Diff view pairs with the **session transcript** for the same change-set (the reasoning trail is half the review).
- Filetype-aware rendering at the edges: notebooks via `nbdime`-style rendering or preview (raw JSON diffs are unreadable); compiled KFP `PipelineSpec` reviewed at source, generated JSON ignored by convention.

### 5.6 Direct editing (code / CSV / text) — **C1**

Nova is also a lightweight editor: every workstream file can be opened and edited directly, not only reviewed.

**Editing model:**
- **Disk is truth; the editor is a view.** Open = read via API; save = explicit write via API (Cmd+S; optional debounced autosave per user config). No second document store, no browser-side persistence.
- **Optimistic concurrency via mtime/content-hash.** Every buffer carries the hash it was loaded from. Save with a stale hash is rejected; the UI responds with a 3-way merge view (`@codemirror/merge` again — same component as the gate) between base, user buffer, and current disk. No hard file locks.
- **Agent/user coexistence.** The single-writer invariant (§3.2) governs *sessions*, not humans. When a session is active in the workstream: clean buffers live-reload on file-watcher events (user sees the agent typing, effectively); dirty buffers show a conflict banner instead of silently reloading. A per-workstream "pause agent writes while I edit" toggle uses the interrupt mechanism for the heavy-handed case.
- **Provenance:** user saves in Type 3 workstreams are captured by the existing auto-commit (attributed `user-edit` rather than a session id); Type 1 user edits are ordinary working-tree changes visible in the same diff gate. File saves are recorded in the audit log (path + hash, never content).

**Editor surface (all CodeMirror 6 — one ecosystem for edit, diff, and merge):**
- Syntax highlighting via `@codemirror/lang-*` (python, yaml, json, sql, markdown…) with `@codemirror/language-data` for lazy loading
- Search/replace (`@codemirror/search`), multiple cursors, bracket matching, folding — built-ins
- File tree in the *Changes/Files* tab of the right panel; open-in-editor from anywhere a path appears (diff view, transcript tool-call chips, search results)
- CSV: the grid panel (§7) is read-write — cell edits write through the canonical serializer, so a human edit and an agent edit produce byte-identical formatting
- Explicit non-goal (§1): no LSP, no debugger. If real demand emerges, the documented exit is CodeMirror's LSP client packages — the editor surface doesn't change.

---

## 6. Memory pipeline — **C1**

```
session ends ──▶ distiller (versioned artifact, scoped small-model call)
            ──▶ ~/.nova/inbox/<ulid>.md  (frontmatter per §3.6, status: inbox)
            ──▶ human triage in UI: promote | edit | discard
            ──▶ promote = write into nova-memory-<team> + open PR
            ──▶ optional later: PR team → commons
```

- The PR gate = quality filter **and** DLP boundary (fraud-case data must never reach shared repos).
- Per-repo knowledge lives in that repo's own `docs/`; cross-cutting knowledge in memory repos.
- Obsidian is an optional read-mostly *viewer* pointed at the folders — never the store, never a format dependency. (Chosen over Logseq: plain `.md` round-trips cleanly with an agent author; no block-UUID/outliner conventions to conform to.)

---

## 7. UI specification

Three regions; mental model: **left = what exists, center = what's happening, right = what it touched.**

- **Left rail:** workstream board (kanban by status; campaign lanes collapsible; type badges PR/⚡/♻); global FTS search (transcripts, memory, playbooks).
- **Center:** browser-style session tabs; transcript from NovaEvents (tool-call chips, subagent progress, streaming text); interrupt / revise-with-feedback bar.
- **Right (per-workstream tabs):** *Changes* (file list + merge view + gate controls) · *Artifact* (panel-registry-resolved viewer: CSV grid, Mermaid, …) · *Info* (branch, worktree, PR link, playbook version, audit trail).
- **Secondary routes:** campaign detail (progress header, triage buckets, batch retry/approve) · memory inbox (promote/edit/discard — make this *pleasant* or curation dies) · settings (effective-config viewer) · doctor report.
- Aesthetic: dense, keyboard-driven (Linear/trading-terminal, not Notion). Unit of interaction: glance → decide → next.

**Frontend libraries (C2, swappable):**

| Concern | Recommendation |
|---|---|
| Data fetching / cache | TanStack Query |
| Routing | TanStack Router (or React Router) |
| Client state | zustand (thin; server is the truth) |
| Diff view | `@codemirror/merge` (first choice) / `monaco-editor` diff |
| Terminal panel (optional) | `xterm.js` + backend PTY over WS |
| Mermaid | `mermaid` (pin version), `svg-pan-zoom`; SVG node-id click mapping per diagram type (start: flowchart, sequence) |
| CSV grid | Glide Data Grid or RevoGrid (Nimbalyst uses RevoGrid) + `papaparse`; keyed table diffs: `daff` |
| Markdown render | `react-markdown` + `remark-gfm`; code highlight: `shiki` |
| Kanban DnD | `dnd-kit` |
| Components/styling | Tailwind + Radix primitives (or shadcn/ui) |
| API client | generated from OpenAPI (`openapi-typescript` + `openapi-fetch`) — pins the FE/BE contract |

**Backend libraries (C2, swappable):**

| Concern | Recommendation |
|---|---|
| Framework | FastAPI + uvicorn; Pydantic v2 models = single schema source (OpenAPI → TS types) |
| Agent | `claude-agent-sdk` (Python) |
| File watching | `watchfiles` |
| SQLite | stdlib `sqlite3` (+ FTS5) or `aiosqlite`; `sqlite-utils` for ergonomics |
| IDs | `python-ulid` |
| YAML/frontmatter | `ruamel.yaml` (canonical round-trip) / `python-frontmatter` |
| Retry/backoff | `tenacity` |
| Scheduling (Type 3 recurrence) | `APScheduler` |
| CLI | `typer` + `rich` (doctor output) |
| Window | `pywebview` |
| Packaging | `hatchling` backend; `uv` for tooling; CI embeds Vite `dist/` in wheel |

**Localhost security (C1):** bind 127.0.0.1 only; per-launch bearer token handed to the frontend; strict CORS; no `js_api` bridge (all FE↔BE over HTTP/WS so browser-tab mode stays free).

---

## 8. Hooks & lifecycle automation

| Need | Mechanism |
|---|---|
| Session start context injection | Layer 1 (before `query()`) — see §11.1 |
| Kanban/status updates, file-change sidebar, notifications | Layer 1 (message stream) |
| Post-session distillation, auto-commit (Type 3) | Layer 1 (after stream close) |
| Tool blocking/rewriting, permission gating | Layer 2 — SDK `PreToolUse` / `PostToolUse` / `PermissionDenied` in-process callbacks |
| Full event set available | SessionStart/End, Stop, SubagentStop, UserPromptSubmit, PreCompact, Notification |

Day-one verify: managed settings don't set `disableAllHooks` (applies to SDK-spawned CLI too).

---

## 9. Distribution & environment

- **Install:** `uv tool install nova` (isolated venv, PATH entrypoint, `uv tool upgrade nova`); `install.sh` one-liner for bootstrap. Brew/npx rejected (wrong ecosystem, extra infra).
- **Stages:** 0 editable → 1 GitHub release wheel → 2 Artifactory. CI builds React, embeds `dist/`, `uv build`, publishes.
- **`nova doctor` (C1):** validates vetted `claude` binary on PATH, `CLAUDE_CODE_USE_BEDROCK` + AWS cred chain + region, model access (incl. small/fast model inference profile), managed-settings landmines (`disableAllHooks`, forced permissions), WebView2 presence (Windows), package/build version. Prints exactly what a bug report needs.
- **Env parity rule:** Nova must launch from (or replicate) the shell profile where terminal Claude Code works — `AWS_*`, proxy, `NODE_EXTRA_CA_CERTS` (corporate TLS interception).

---

## 10. Metrics — **C1 (instrument early; history is unrecoverable)**

Land per-session records in T2: cost, duration, turns, outcome, playbook id/version, workstream type, campaign id. Surface: Bedrock spend by team/campaign, playbook success rates, campaign time-to-merge. This is the management-facing artifact and the empirical playbook-quality signal.

---

## 11. Enhancement roadmap (post-v1, in leverage order)

1. **Auto-injected context packs (build immediately after memory exists).** SessionStart → T2 query by workstream repo/entities → inject relevant standards/decisions/distillates. RAG over *human-curated* knowledge only; without this, memory is write-only. Anti-goal: auto-summarizing everything into every prompt.
2. **Playbook flywheel.** Distiller flags recurring session patterns → proposes playbook candidates into inbox; campaign triage feeds playbook revisions. Anti-goal: agents editing playbooks without PR.
3. **Fleet intelligence.** codegraph AST analysis fleet-wide → T2 entity/link graph → campaign selectors as queries ("all repos importing kubekit.retry"), dependency-aware context packs, impact analysis.
4. **Monitors.** Event-driven intake (Mend issue → proposed vuln workstream; CI failure → proposed triage session) into a human-gated inbox lane. vuln-remediator becomes the first resident monitor. Anti-goal: auto-run.
5. **Selection-primitive clients.** Mermaid click-to-edit (Tier 2 of §7 table), CSV cell-selection → instruction; later KFP DAG views.

---

## 12. Deferred options (documented exits)

- **Lexical WYSIWYG diff review:** Nimbalyst's editor (`packages/runtime/src/editor`, MIT) is ~77K LOC of Lexical+React with minimal Electron coupling; vendoring = copy + host shim + component swap. Viable *because* gate records are change-set-level (§5.5). Trigger: reviewers demonstrably need in-document review.
- **Excalidraw panel:** embeddable React component; one-way `mermaid-to-excalidraw` if freeform diagram editing is ever demanded.
- **Node sidecar:** only if large TS server-code vendoring ever becomes necessary (not currently anticipated).

---

## 13. Build order

**Phase 0 — Proof (days):** SDK smoke test in sandbox (package reachable via internal index → `claude /status` baseline → managed-settings inspection → `SDK_OK` single-turn with vetted binary → file-edit turn → hook fires → `resume` works). Any failure here changes the plan; nothing else starts until this passes.

**Phase 1 — Contracts (1–2 wks):** NovaEvent schema + dual-source normalizer with golden-fixture tests · T1 layouts + canonical serializers · T2 + `nova reindex` · config precedence resolver · audit log · lease/queue skeleton · **credential-reference resolver + redaction filter (§16)** · **connector interface definition (§15.1, no implementations yet)**.

**Phase 2 — Core loop (2–3 wks):** workstream CRUD (3 types) · session runner (start/resume/fork/interrupt) · transcript UI + tabs · worktree lifecycle · CodeMirror gate + revise-with-feedback · **direct editor with mtime-conflict merge (§5.6)** · FTS search · `nova doctor` (incl. connector health + STS identity) · Stage-1 packaging.

**Phase 3 — Memory + metrics (1–2 wks):** distiller artifact + inbox + triage UI + PR promotion · metrics capture + minimal dashboard · context packs (roadmap #1).

**Phase 4 — Campaigns (2 wks):** campaign object, queue integration, phases, triage buckets, batch actions · first real campaign as validation (candidate: a fleet dependency bump).

**Phase 5 — Panels & connectors:** CSV grid panel (read-write) · Mermaid panel (+ selection primitive) · first connectors: `github` → `jira` → `jenkins` (§15.3) · recurrence.

---

## 14. Definition of "designed right" (self-checks)

- `rm -rf ~/.nova/index.db && nova reindex` is always safe.
- `git log` on any curated fact explains its origin (session → distiller version → PR).
- A backend crash mid-session loses nothing that `resume` + JSONL can't recover.
- A new artifact panel ships without touching core.
- A second team onboards by adding one repo URL to a config list.
- Every "which version did X?" question has a recorded answer.

---

## 15. External connectors — **C0 (interface) / C2 (individual connectors)**

The fourth extension seam (§3.4.4), in detail. Design principle: **deterministic edges** — external side-effects are produced as reviewable artifacts by vetted code, never freehanded by agents.

### 15.1 Connector interface

Each connector is a Python plugin registered via entry point (`nova.connectors`), packaged either in-tree or as its own wheel (`nova-connector-jira`):

```python
class Connector(Protocol):
    id: str                      # "jira", "jenkins", "snowflake", ...
    version: str                 # interface conformance is versioned (connector_api: 1)
    credentials: list[CredRef]   # declared requirements, resolved per §16 — never values

    def health(self) -> HealthReport: ...
    def pull(self, scope: PullScope) -> SnapshotResult: ...       # read → local files
    def plan(self, intent: dict, snapshot: Path) -> PlanArtifact: ...  # → changes.yaml
    def apply(self, plan: PlanArtifact) -> ApplyResult: ...       # gated execution
```

- **`pull`** writes canonical local snapshot files (deterministic serialization) into the workstream — typically a Type 3 state repo, so external state becomes git-diffable history.
- **`plan`** emits a `changes.yaml` artifact: human-readable, schema-validated, idempotency-keyed. This is what the diff/change-plan gate reviews.
- **`apply`** executes a reviewed plan, records per-item results, and re-pulls to confirm convergence. Apply is invoked only by core after a gate decision — connectors expose it, but nothing at the edge can call it.
- **`health`** feeds `nova doctor` (reachability, auth validity, API version).

### 15.2 Agent access rules

| Operation | Agent-callable? | How |
|---|---|---|
| `pull` / reads | Yes | Exposed as tools (SDK MCP tool or vetted CLI script the agent runs). Read-only, safe. |
| `plan` | Yes | Agent produces/edits the intent and can invoke plan generation — output is inert until gated. |
| `apply` | **Never** | Core-only, post-gate. Not registered as a tool; `PreToolUse` hook additionally denies any attempt at direct external mutation (belt and suspenders). |

Secrets never enter agent context: connectors resolve credentials themselves at execution time (§16), so prompts and transcripts see only connector names and non-secret outputs.

### 15.3 Modularity properties

- Interface version (`connector_api`) is a C0 contract; Nova releases declare supported versions (N, N−1) like every other schema.
- Config (per team/user layer) declares enabled connectors + credential references + pull scopes; enabling a connector is a config change, not a code change.
- **Monitors** (roadmap #4) are connectors' `pull` on a schedule + a rule that maps snapshot deltas to proposed workstreams — no new integration surface.
- First implementations, in order of existing need: `github` (API beyond git — PR status for campaign reduce), `jira` (the standing Type 3 use case), `jenkins` (CI status), `snowflake` (read-only first).

---

## 16. Secrets, credentials & auth — **C0**

Governing rule (also §1): **Nova never stores secret values at rest.** Config, T1, T3, logs, metrics, and audit records contain only credential *references*; values are resolved at use time and held in memory only.

### 16.1 Resolution chain

Credential references use a scheme prefix, resolved in this order:

| Scheme | Backend | Use |
|---|---|---|
| `env:NAME` | Process environment | CI, power users, anything already env-managed |
| `keyring:service/name` | OS keychain via `keyring` (macOS Keychain, Windows Credential Locker, Secret Service on Linux) | Default for user-held tokens (Jira, GitHub PAT). First use prompts once in-UI, stores to keychain. |
| `aws-sm:secret-id` / `aws-ssm:param` | AWS Secrets Manager / SSM Parameter Store via the ambient IAM role (`boto3`) | Team-managed secrets — no new auth surface, since AWS creds already exist for Bedrock |

### 16.2 Auth patterns by system

- **Bedrock / AWS:** ambient credential chain only (SSO/role). Nova never touches, stores, or proxies AWS credentials; it inherits exactly what the terminal Claude Code session uses (env-parity rule, §9). `nova doctor` reports identity via STS and flags imminent SSO token expiry.
- **Git / GitHub:** delegate entirely — system git credential helper and/or `gh` CLI auth. Nova shells out; it never handles the token. PR creation goes through `gh pr create` or the `github` connector using a `keyring:`/`aws-sm:` reference.
- **Connectors:** declared `CredRef`s resolved per §16.1 at `pull`/`apply` execution time, inside connector code, outside any agent context.
- **Localhost API:** per-launch random bearer token (§7), 127.0.0.1 bind, strict CORS — unchanged.

### 16.3 Leak prevention (defense in depth)

1. **Structural:** secrets are never injected into prompts, session env beyond what Claude Code itself requires, or tool outputs — connectors are the only code that sees values, and they run in the deterministic layer.
2. **Transcript redaction filter** on NovaEvent ingestion: pattern-based scrubbing (AWS key shapes, JWT/PAT prefixes, `Authorization:` headers) applied before events reach T1/T2. Belt-and-suspenders for the day something leaks into a tool result.
3. **Promotion-gate scan:** memory-inbox → PR promotion runs the same secret patterns (plus entropy heuristic) and blocks promotion on hit — protecting the shared repos specifically.
4. **Audit:** credential *use* is logged (connector id, cred ref, purpose) — never the value.

### 16.4 Self-check additions (extends §14)

- A secrets-pattern scan across `~/.nova/`, all state repos, and all memory repos returns zero hits — continuously true, enforceable in CI for shared repos (`gitleaks` or `trufflehog` as the scanner).
- Revoking one token requires touching exactly one keychain/secret entry — never a config file, never a redeploy.
