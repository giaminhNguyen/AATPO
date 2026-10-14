# AATPO V4.1 — MASTER INPUT FOR LOCAL CODING AGENT (AUTO-GIT)

**Project:** Autonomous AI Technology Production Office (AATPO)  
**Document type:** Self-contained implementation brief / executable development assignment  
**Date:** 2026-10-14  
**Target:** Windows 11 native, desktop GUI-first, Vietnamese natural-language-first  
**Status:** SPECIFICATION TO BUILD; NOT EVIDENCE OF IMPLEMENTATION  
**Source of requirements:** AATPO Implementation Blueprint V3.1, GUI-first V4.0, and owner's additional automatic-Git decision.  
**Priority:** This V4.1 brief overrides V3.1 where they conflict on user experience, GUI, project registry, automatic local Git workflow and packaging. Preserve all other V3.1 safety, orchestration, session and QA principles.

---

## 0. READ THIS FIRST — DIRECT COMMAND TO THE CODING AGENT

You are the **lead engineering coding agent working locally on the owner's Windows computer**. **IMPLEMENT AATPO**, not merely discuss architecture or produce mockups. Begin with the smallest verifiable working milestone and advance systematically, writing source code, automated tests, sample data, Windows run instructions and implementation reports. Do not claim a milestone passed without actually running its tests. Do not claim Windows/CLI testing if only mocks or another OS were used.

**Required product outcome:** A local **Windows Desktop app** whose primary interface is in **natural Vietnamese** and friendly to people who do not know programming. A user can register/select a project, describe a task in Vietnamese, approve scope if needed, launch work, watch status, handle approvals and receive verifiable results **without typing CLI commands or touching code**. The background engine uses **already-installed, legitimately authenticated official AI CLI programs** (Codex CLI, Claude Code, Gemini CLI, any subset). No separate LLM API key is required by the architecture.

**Immediate instructions:**

1. Inspect OS, repository, Python, Git and the available official AI CLIs without exposing credentials. Check official version-specific `--help`; do not assume flags or schemas from this document always work.
2. Use the exact owner-approved workspace root for AATPO source (e.g. `D:\AATPO`); do not create an unnecessary nested `aatpo/` directory. Detect any existing Git repository first; otherwise initialize a local repository there, add a safe `.gitignore`, create the initial commit when author identity is configured, and use automatic milestone branches/verified commits as required by section 6.3. Never overwrite unrelated files.
3. Follow milestones G0 → G1 → G2 → G3 → G4 → G5 below. Begin coding **G0** immediately; do not stop after generating a proposal. When a milestone passes, continue with the next if permitted by environment and available resources. If blocked, report exactly what is missing and leave a runnable, tested state.
4. Build a **real GUI early**, not a complete backend with a theoretical UI promised for later. The GUI and workflow must use the **same application services**; do not wire the UI directly to CLI shell commands or SQL updates.
5. Keep the original critical invariant: **CLI Provider ≠ Agent Role ≠ Task ≠ Agent Session ≠ Process Run.** Use separate IDs. One logged-in CLI may support multiple logical roles; each `(task, assignment, role, provider)` has its own session. Never use a shared CLI chat history across tasks.
6. Use tests and evidence; the LLM's statement “done” is not evidence. Never use unrestricted approval flags such as `--yolo` or `--dangerously-skip-permissions` by default. Never retrieve/copy provider login tokens or bypass quota/terms.
7. **No sandbox/VM/container isolation implementation in this MVP**, per owner's constraint. Explain the real limitation: native Windows OS privileges cannot be enforced by path allowlists or Git Worktrees alone. Use trusted repositories, lowest practical OS privileges and permission gates.
8. Do not design web UI, public SaaS, multi-tenant service, payment/billing, automatic production deploy, agent subscriptions sharing, or 8 persistent AI worker processes.
9. Record all technical decisions that were not fixed by this document in `docs/decisions.md`. Prefer simple, maintainable solutions. Keep the product's end-user labels non-technical.
10. At the end of each milestone, deliver actual paths, commands, test log, **Git branch and commit hash**, and a truthful list of verified vs unverified functionality; do not merely say “completed”.
11. **Automatic local Git management is a product requirement.** Apply it both when developing AATPO itself and, through GUI-controlled policies, when AATPO later works on customer projects. Safe local init/branches/commits should be automatic after initial project authorization; do not perform remote pushes, history rewriting or destructive Git commands without narrowly scoped approval.

### Starter prompt to use when handing this file to your local coding agent

> Read the entire `AATPO_V4_1_GUI_First_Auto_Git_Coding_Agent_Input.md`. Treat it as the binding self-contained specification for AATPO Desktop GUI-first. Start implementing G0 in the approved local repository immediately, run tests and produce real runnable code. Continue through later milestones only after acceptance passes. Build the Python core and PySide6 desktop GUI with Vietnamese chat, project registry, tasks, approvals and delivery, powered by official logged-in CLI adapters. Do not only generate plans or images. Never claim live Windows/CLI success without tests. Initialize or reuse local Git in the approved root, create a milestone branch, commit only validated changes, and report branch/commit hashes. No automatic push or history rewrite. When a requirement is not implementable safely, report the blocker explicitly and leave a usable checkpoint.

---

## 1. OWNER DECISIONS — FIXED PRODUCT REQUIREMENTS

1. **AATPO is a Windows Desktop application with a normal graphical window**. End users must not have to open PowerShell/Terminal to operate it.
2. **Natural Vietnamese is the primary way of giving work**. Every major action also has an obvious GUI affordance when appropriate: choose/open project, create task, start, pause, resume, approve, see result.
3. The target user **does not know programming**. Do not ask about React/Vue, Redis/SQL, architecture, API, branch names or CLI flags unless they deliberately enter an advanced view.
4. AATPO is a **technology production office**, not just a chat wrapper: it clarifies needs, proposes lean/balanced scope, plans, delegates to logical roles, executes, verifies and delivers.
5. The customer approves scope changes, unusual expense, destructive operations, permissions and production deployment. Non-critical implementation details are chosen internally under policy.
6. AATPO runs locally on **Windows 11** and launches **official installed CLI programs** using the current logged-in user's legitimate authentication. One ready provider is enough; missing providers must degrade gracefully.
7. **8 core logical roles, not 8 resident processes**: `client_representative`, `business_analyst`, `office_manager`, `system_architect`, `frontend_engineer`, `backend_engineer`, `qa_engineer`, `devops_engineer`. Specialist roles are optional profiles.
8. Each project is explicitly registered and isolated logically. Never infer a writable workspace by blind drive-wide scanning. If the natural-language request matches more than one project, ask the user to select.
9. Local durability: reboot/crash must not lose work orders, choices, task states, session mapping, artifacts or evidence. Recovery must not replay potentially destructive actions blindly.
10. Safety, user authorization and providers' terms outrank automation, cost and speed.
11. **Git is managed automatically in the background:** local repository creation (where authorized), work/milestone branches, verified commits, and readable version history. The normal user does not need to understand Git or provide shell commands. Publishing to a remote repository is a separately approved action.

### Acceptance in one sentence

> On a supported Windows PC with one authenticated AI CLI, a non-developer can open AATPO, select a trusted project, describe a small real coding task in Vietnamese, approve it if appropriate, execute it, watch progress, see test-backed output and safely reopen/continue work after restarting the application — **without touching Terminal**.

---

## 2. PRODUCT EXPERIENCE AND UX PRINCIPLES

### 2.1 Navigation — five primary screens

**A. Văn phòng AI (Home + Chat)**
- Welcome; clear project selector at top; prominently displayed active project name and actual workspace path (path shown in project detail/confirmation, not technical chat text).
- Natural-language chat with `client_representative` as customer-facing voice; history scoped to the selected project/work order.
- Quick actions: `Tạo dự án`, `Mở dự án`, `Giao việc mới`, `Tiếp tục công việc`.
- Status summaries in plain Vietnamese, e.g. `Đang thực hiện`, `Đang kiểm tra`, `Cần bạn xác nhận`, `Hoàn thành`.
- Chat prompts ask **one highest-impact question per turn**, offering `Tôi chưa biết, hãy đề xuất`.

**B. Dự án (Projects)**
- Register an **existing local directory** via a native folder picker; choose a display name and confirm the resolved absolute path.
- Create a **new project** through a folder picker and confirmation; do not overwrite a nonempty directory without explaining and getting explicit approval.
- Project list: name, location, basic state, last activity, select/open/edit metadata/archive (do not physically delete code by archiving).
- Display a simple toggle on project registration: **automatic local version history** (recommended). For a newly created project, enable local Git after project-creation confirmation. For a pre-existing non-Git folder, ask for a one-time explicit opt-in before `git init`. Detect existing repositories and preserve their current branch, history, remotes and dirty changes. Never perform destructive Git actions silently.
- Present human-friendly history (`Version saved`, `Changes awaiting review`, `Restorable previous version`), with branch names and hashes tucked into advanced details.
- Show which project is active; tasks must always be bound to a `project_id` when they affect a repository.
- Support tasks not tied to a code repo (research/analysis) with a registered safe work folder or a clearly designated managed project workspace.

**C. Công việc (Tasks/Work Orders)**
- Human-readable list and detail: purpose, state, progress, pending dependency, responsible logical role, estimated effort **qualitatively**, timestamps.
- Buttons: `Bắt đầu`, `Tạm dừng`, `Tiếp tục`, `Xem chi tiết`, `Xem kết quả` as allowed by state.
- Do not show fake percentage progress; use completed tasks / total tasks or discrete milestone states. Unknown duration remains unknown.
- A small task may use a **Fast Lane**: one execution role plus an evidence-based review, without ceremonially invoking all 8 roles.

**D. Cần bạn quyết định (Approvals Inbox)**
- Dedicated queue with clear action, reason, affected project/files and consequences.
- `Đồng ý` / `Không đồng ý` (and options for lean/balanced proposals), with audit trail and irreversible-action warnings.
- User approval must be linked to the exact action, project and scope version. `No response` never means `yes`.

**E. Kết quả (Delivery)**
- Simple summary of completed work, features delivered, items postponed/blocked, relevant tests and risks.
- Buttons to open output folder, view report, view relevant diff summary, copy/share report and request revisions.
- Do not execute an untrusted deliverable automatically. If preview/runtime would execute code, require explicit opt-in and separate permission check.

**Global UX rules**
- Default language Vietnamese with correct Unicode input/output; avoid unexplained English status and jargon.
- Consistent navigation; visible error recovery; no disappearing work orders after restart.
- Support Windows display scaling (100–150% minimum), keyboard focus and accessible color contrast.
- User-facing conversation stays available while background tasks run. No frozen UI while a CLI is executing.
- No animated “AI is working” indicators unless an actual process/run is active. Distinguish queued vs running vs paused.
- Advanced diagnostics are collapsible: CLI/provider, logs, session IDs, exit codes, JSON parser details.
- An empty-install state guides the user through prerequisites instead of showing raw stack traces.

### 2.2 Natural-language actions and command interpretation

Examples that MUST be supported as intents, not as arbitrary direct shell commands:

| Customer says in Vietnamese | Expected structured action |
|---|---|
| `Tạo dự án quản lý kho` | Propose project creation and choose a folder |
| `Mở dự án bán hàng` | Resolve Project Registry, ask on ambiguity |
| `Sửa lỗi đăng nhập` | Create a work order in the active project; clarify key issue if needed |
| `Làm bản đơn giản, ít chi phí` | Propose lean scope with omissions and ask for approval |
| `Bắt đầu làm` | Start only approved, eligible work for active work order |
| `Dừng việc này` | Request safe pause/cancellation of current run (status shown) |
| `Cho tôi xem đã làm gì` | Show task evidence and customer-friendly report |
| `Sửa lại nút lưu` | New feedback/rework/change request with traceable scope |

Use an LLM to **propose** an intent and structured data, validated with Pydantic. An explicit, deterministic application-service layer decides whether the action is permitted. A message in chat is not a universal authorization token. If a dangerous operation is inferred, ask explicit, scoped approval through GUI.

### 2.3 Interaction sketch (not a demand for pixel-perfect artwork)

```text
+------------------------------------------------------------------+
| AATPO  [Du an: Quan ly ban hang  v]       [Trang thai: San sang]   |
+-----------------+------------------------------------------------+
| Van phong AI    | Xin chao! Ban muon AATPO giup gi?             |
| Du an           |                                                |
| Cong viec       | Khach: Hay sua loi dang nhap                   |
| Can ban quyet   | AI: Toi se kiem tra... Ban co gap thong bao..? |
| dinh            |                                                |
| Ket qua         | [Tiep tuc voi de xuat] [Xem pham vi]          |
|                 |                                                |
|                 | [Mo ta cong viec cua ban...             (Gui)] |
+-----------------+------------------------------------------------+
```

Use native Windows file pickers and simple controls; don't require the user to type paths, work order IDs, or PowerShell commands.

---

## 3. TECHNICAL ARCHITECTURE — DECISIONS FOR THIS BUILD

### 3.1 Tech stack

- **OS:** Windows 11 native (not WSL as the application runtime).
- **Language:** Python 3.12+; create isolated `.venv` for development.
- **Desktop GUI:** **PySide6 / Qt Widgets** for MVP. The agent may use a light reusable widget/theme layer; avoid a web server/browser to host the GUI. Keep a separation between GUI, presentation controllers and application services. Do not require Electron/Node for this GUI.
- **State/DB:** built-in `sqlite3`, WAL, foreign keys, versioned migrations, transactions.
- **Contracts:** Pydantic v2, JSON Schema where provider output is structured.
- **Execution:** `asyncio.subprocess` or a proven Windows-safe subprocess manager; event bridge to Qt via queued signals/slots or similar safe mechanism. **Do not block Qt UI thread.** Never update Qt widgets directly from a worker thread.
- **CLI runtimes:** official Codex, Claude Code and Gemini CLI; separate provider adapters, independent optional enablement.
- **Workspace:** Git for Windows with mandatory automatic local repository/branch/commit management per section 6.3. Optional worktrees are only for verified isolation of concurrent edits; Worktrees are **not OS isolation**.
- **Tests:** pytest, mock/fake CLI for most tests; separate verified real-Windows integration suite.
- **Packaging:** once the real GUI/core work, create a **Windows `onedir` executable distribution first** (e.g. using PyInstaller); optional installer only if validated. A packaged app must still use the separately installed and logged-in AI CLIs. No false claim that packaged AATPO bundles provider accounts/auth.
- **Configuration/data:** owner-local application data directory (e.g. `%LOCALAPPDATA%\AATPO`) and user-chosen project directories. Keep state and credentials out of the source repository; never store provider login secrets.
- **Optional future:** LangGraph for complex flows only with clear value; it must not replace the SQLite task/session ledger.

### 3.2 Layer boundaries

```text
Desktop GUI (PySide6 Qt Widgets; Vietnamese UX)
    |
Presentation/ViewModels/Qt bridge (safe background events)
    |
Application Services + deterministic state machine/policies
    |---- Customer Gateway: clarify, recommend scope
    |---- Project Registry: register, resolve, select, verify paths
    |---- Office Manager: approve plan, DAG scheduler, handoffs
    |---- Session Ledger + Provider Router + Cost Controller
    |---- Quality Gates / Delivery
    |
Persistence: SQLite + events + file artifacts + automated Git ledger/evidence
    |
Official CLI Adapters -> Windows Process Launcher
    |                         |             |
   Codex CLI              Claude CLI    Gemini CLI
    |
Approved local workspace + test/build tooling
```

**Critical boundary:** GUI calls application services, not subprocesses directly. LLM outputs are proposed commands/data only, and cannot update authoritative task status directly.

### 3.3 Five distinct concepts

| Concept | Description | Example |
|---|---|---|
| `CLIProvider` | Installed executable and auth capability | `codex` |
| `AgentRole` | Stable logical job/profile/policy | `backend_engineer@1` |
| `Task` | Objective with acceptance, dependencies, permitted paths | `TASK-004` |
| `AgentSession` | One role on one task/assignment/provider; own context | `SESS-019` |
| `ProcessRun` | One real subprocess invocation, timeout, logs and exit | `RUN-031` |

`Project` is a separate durable entity and work orders must reference the correct registered project. One CLI can carry out many roles **sequentially**; do not require 8 subscriptions or 8 continuously running processes.

### 3.4 Sessions, rework and provider switching

- Scope a session to `(project_id, work_order_id, task_id, assignment_id, role_id, provider_id)` and versioned role profile.
- On first run, create internal agent session. Persist provider session ID **only if reliably parsed** from provider output.
- For rework on same assignment: resume the **exact provider session ID** if the installed CLI supports it. **Never** use `resume latest` as the orchestrator default.
- If exact resume unsupported/broken: record reason, start a **new session** with a compact stored brief, decisions, code diff and verified findings; never guess an ID or paste raw unrelated chats.
- New task → new session even for same role and provider. QA → different session from developer.
- Switch provider → structured handoff + new provider session; do not pass provider-A session ID into provider B.
- Crash with uncertain side effect → reconcile process/files/external state, mark unknown and request review before any non-idempotent retry.

### 3.5 CLI adapters

Each adapter exposes roughly:

```python
class CLIAdapter(Protocol):
    provider_id: str
    async def probe(self) -> ProviderCapabilities: ...
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult: ...
    async def cancel(self, run_id: str) -> CancelResult: ...
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentRunResult: ...
```

- Check executable path, version, help output and supported modes on the actual machine. Status includes `missing`, `not_authenticated`, `quota_exhausted`, `unsupported_version`, `unhealthy`, `ready`, `unknown`.
- `doctor` defaults to local existence/version/help only. A real read-only AI smoke request requires opt-in because it may consume quota or send repo data to external model services.
- Parse Codex JSONL events vs Claude/Gemini output envelopes according to actual installed CLI version. Nonzero exit or invalid JSON is an error, not task completion.
- Do not interpolate user content in shell command strings. Use controlled argument vectors and stdin/temp prompt files as supported; carefully handle Windows `.exe/.cmd/.bat`, spaces, Vietnamese Unicode and metacharacters. Allowlist provider executable templates.
- Bounded startup/run timeouts; drain stdout/stderr asynchronously; cap logs, redact secrets, terminate process tree on cancellation/timeout according to verified Windows behavior.
- Do not read the CLI's auth files, transfer credentials, bypass quotas, or silently select `--dangerously-skip-permissions`, `--yolo`, or equivalent.
- Do not assume a provider supports all requested capabilities. Disable unsupported features or fall back safely with explicit UI explanations.

**Version-sensitive documentation to verify before coding:**
- Codex: `https://github.com/openai/codex` and installed `codex --help`, `codex exec --help`
- Claude Code: `https://code.claude.com/docs/en/headless` and installed `claude --help`
- Gemini CLI: `https://geminicli.com/docs/cli/headless/`, `https://geminicli.com/docs/cli/session-management/`, installed `gemini --help`
- Qt for Python: `https://doc.qt.io/qtforpython-6/`
- PyInstaller: `https://pyinstaller.org/en/stable/`

Do not treat example flags as a guarantee of compatibility; store actually tested provider/version/capability matrix in `docs/cli_compatibility.md`.

---

## 4. PROJECT REGISTRY — NEW REQUIRED DOMAIN

### 4.1 Data model

Create `projects` as a durable top-level entity with at least:

```text
project_id             UUID/ULID (never name as primary key)
display_name           Unicode text
root_path              canonical absolute Windows path (not blindly trusted)
project_type           existing_code | new_product | research | other
status                 active | archived
selected_at            nullable timestamp
created_at, updated_at ISO-8601 UTC
notes                  optional non-sensitive text
repo_detected          bool, informational only
git_auto_history        bool, explicit project setting
git_default_branch      nullable text, detected not blindly overwritten
```

`work_orders.project_id` references `projects.project_id`, or an explicitly designated non-code workspace for general research. Tasks, sessions, runs, artifacts and file permissions must be traceable to the project through their foreign-key ancestry. **Do not use unverified arbitrary paths from LLM output.**

### 4.2 Project resolution rules

1. On creating/registering a project, ask for a directory via GUI file picker; normalize/canonicalize; show the real path in confirmation.
2. Maintain explicit current-project selection per operator profile. Never silently switch the current project from an ambiguous chat mention.
3. Match natural-language project names using a **candidate suggestion only**. If more than one plausible match, ask the user which project is meant.
4. Project creation cannot silently replace an existing project, initialize over important files, or delete a folder.
5. When a task affects files, display the target project prominently before first write and check workspace allowlist/policy.
6. On startup, check missing/offline/moved project paths; show `Không tìm thấy thư mục dự án` with a relink option. Never recreate an unknown path implicitly.
7. Resolve symlinks/junctions/reparse points and check path traversal where possible; **do not claim OS security isolation**, because agents run with ordinary Windows account privileges.
8. Confirm any access to a directory outside the registered workspace. Deny destructive outside-workspace operations by default.
9. When creating or registering a project, detect an enclosing Git repository and its root. Never initialize a nested repository accidentally. Show the owner the exact repository root for the automatic version-history setting.

### 4.3 Examples

```text
Project PRJ-001: "Quản lý bán hàng" -> D:\Projects\QuanLyBanHang
Project PRJ-002: "Quản lý kho"      -> D:\Projects\QuanLyKho
Project PRJ-003: "Website công ty"  -> D:\Projects\WebsiteCongTy
```

A user says "Sửa lỗi đăng nhập dự án bán hàng" → AATPO proposes PRJ-001 and operates in that workspace if unambiguous and allowed. If the user says only "Sửa lỗi đăng nhập" with no active project, show a project picker; **do not search all drives and choose at random**.

---

## 5. ROLES, WORK ORDERS AND OPERATING LOGIC

### 5.1 Core roles

| role_id | Responsibility | Key evidence / limitation |
|---|---|---|
| `client_representative` | Vietnamese customer-facing conversation, options, updates | Never asks jargon, never approves scope for customer |
| `business_analyst` | Clarify needs, MUST/SHOULD/LATER/DROP, acceptance | Does not silently invent must-have features |
| `office_manager` | Plan/route/limit/schedule/escalate | Cannot override approval/QA policies |
| `system_architect` | Architecture, contracts, decision record | Cannot change approved business scope |
| `frontend_engineer` | User interface and relevant tests | Cannot change backend outside assignment |
| `backend_engineer` | Logic/API/data and relevant tests | Cannot access unrelated project data |
| `qa_engineer` | Reviews and verifies against acceptance | `QA says yes` alone is insufficient |
| `devops_engineer` | Build, package and handover docs | Cannot deploy production without explicit approval |

Role profiles stored/versioned in `roles/*.md` or validated config; one provider may execute all of them in separate task sessions. Optional specialists (security, research, UX, data, ML, mobile) are loaded on demand, not persistent processes.

### 5.2 Work order states

```text
RECEIVED -> DISCOVERING -> [WAITING_CUSTOMER] -> SCOPE_PROPOSED
 -> SCOPE_CONFIRMED -> PLANNED -> EXECUTING <-> VERIFYING
 -> PACKAGING -> DELIVERED -> ACCEPTED

Alternatives: PAUSED_APPROVAL | PAUSED_QUOTA | BLOCKED | FAILED | CANCELLED
Post-delivery changes: CHANGE_REQUESTED -> new scope/version or work order
```

### 5.3 Task states

```text
BACKLOG -> READY -> CLAIMED -> RUNNING -> OUTPUT_READY -> REVIEW
                                           |                 |-> DONE (evidence verified)
                                           |                 |-> REWORK -> READY
                                           |-> BLOCKED / PAUSED / FAILED
```

`ProcessRun.SUCCEEDED` **does not** mean `Task.DONE`. Scope and plan are versioned; no overwriting past approvals or evidence.

### 5.4 Budget and scheduling

Default settings (adjustable; **examples**, not proven optimal):

```toml
[office]
language = "vi"
concurrency = 1
max_replans_per_work_order = 3
max_handoffs_per_task = 6
max_rework_cycles_per_task = 2

[limits]
max_runs_per_task = 4
run_timeout_seconds = 900
max_total_runs_per_work_order = 40

[routing]
strategy = "cheapest_capable_available"
provider_preference = ["codex", "gemini", "claude"]

[permissions]
allow_production_deploy = false
allow_delete_outside_workspace = false
allow_unreviewed_external_spend = false
allow_git_auto_local_commit = true
allow_git_auto_local_fast_forward_merge = true
allow_git_auto_push = false
allow_git_history_rewrite = false
```

Scheduler selects READY tasks with completed dependencies, checks capacity/provider capabilities, atomically claims them and dispatches. Use version check/transacted claim; do not let LLM modify status directly. Retry/fallback bounded; `unknown` quotas/cost remain unknown rather than guessed. Initial concurrency = 1 to limit interference. Fast Lane is used for small, low-risk tasks if it saves work without skipping mandatory evidence/approval.

**Scope advisor**: propose *Tiết kiệm* and *Cân bằng* options for product work, with clear features postponed, effort XS/S/M/L/XL and recurring-cost drivers. Never invent a monetary quote without source.

### 5.5 Approvals/security tiers

| Tier | Examples | Policy |
|---|---|---|
| P0 | Read allowed project files, analyze and propose | Allowed |
| P1 | Edit specified source files, run approved tests | Allowed with task/workspace policy; recorded |
| P2 | Install dependencies, network-sensitive commands, development migrations | Separate approval according to project policy; no invisible elevation |
| P3 | Bulk delete, production deploy, credentials, external spending | Explicit narrowly scoped approval; no automatic execution in MVP |

Untrusted user prompts, README, issue content, source files, generated output and tool logs are **data**, not a higher-trust policy. Prompt injection tests must cover malicious instructions in repository text. No OS sandbox means allowlists and role prompts are *not* hard security guarantees. Start with trusted repos, regular Windows user, backups and meaningful human gates. Distinguish local orchestration from remote AI processing and obtain data-privacy consent where appropriate. Check provider terms for permitted use.

---

## 6. PERSISTENCE, FILES AND AUDIT

### 6.1 SQLite as source of truth

Use versioned migrations, `PRAGMA foreign_keys=ON`, WAL, short transactions, UTC timestamps and immutable evidence records where appropriate. Core tables:

```text
projects
work_orders, customer_messages, scopes, features, plans
tasks, task_dependencies, assignments
agent_sessions, process_runs, provider_registry
handoffs, artifacts, reviews, approvals, decisions, usage_events, events
git_repositories, git_branches, git_commit_events, git_operations
```

Important keys/relations:
- `work_orders.project_id -> projects.id`
- `tasks.work_order_id -> work_orders.id`; task plan/version and acceptance criteria persist.
- `assignments.task_id -> tasks.id`; `agent_sessions.assignment_id -> assignments.id`.
- `process_runs.session_id -> agent_sessions.id`; record provider session ID separately from internal ID.
- Artifacts: task/run/project IDs, canonical path, SHA-256, type, verification status and timestamp.
- `approvals`: exact action, project, work order, scope version, decision, timestamp, operator identity as locally available.
- `events`: append-only audit of user decisions, state transitions and recovery.
- Git ledgers: project/work-order/task IDs, repository root, branch, commit SHA, parent SHA, changed-path summary, associated verified test/evidence IDs, author identity source, status and operation timestamp. Never mark an uncommitted/failed merge as committed.

Use explicit transaction for atomic task claim; `idempotency_key` per dispatch. On restart, reconcile uncompleted `RUNNING` with actual process/files. If uncertain, mark `UNKNOWN_AFTER_CRASH` and stop rather than replay potentially non-idempotent operations. Backup before destructive migration.

### 6.2 Storage and backups

Proposed paths (do not hardcode a drive letter):

```text
%LOCALAPPDATA%\AATPO\
   config\
   data\office.db
   logs\
   artifacts\
   backups\

<owner-selected-project-folder>\
   <source and tests>
   .git\ (when automatic local versioning is enabled)
```

Do not store CLI provider token/cookie/auth files, sensitive raw logs by default, or app data inside version-controlled source files. Truncate/rotate logs and redact apparent secrets. Large raw outputs are access-controlled files with references and hashes, not unlimited DB blobs. Provide safe migration and restore instructions.

### 6.3 Automatic Git repositories, branches, commits and history — OWNER-APPROVED V4.1 REQUIREMENT

**Purpose:** The local coding agent building AATPO **and** the AATPO application working on authorized customer projects must create and manage local Git history automatically. This is a development safety and traceability mechanism, not a request to publish source code online. Git operations are owned by an application service (`GitService`), not generated shell snippets executed directly from customer chat or raw AI output.

#### A. Git while the local coding agent builds AATPO

1. Before writing source code, inspect the approved project root: `git rev-parse --show-toplevel`, `git status --porcelain`, current branch, repo ownership and `.gitignore`. Do not mistake an enclosing parent repository for an independent AATPO repository.
2. If the owner-designated AATPO workspace **is not already inside an existing repository** and the workspace was explicitly approved for this build, initialize local Git (`git init -b main` when supported; fallback to a version-compatible safe equivalent), set `.gitignore`, and create an initial baseline commit once author identity is available. Do not create a GitHub account, add a remote or push.
3. Never overwrite existing Git history or assume the default branch is `main` in an existing repo. Reuse the actual default/target branch and preserve any user modifications.
4. Create a branch for each development milestone, e.g. `feat/g0-foundation-gui`, `feat/g1-cli-runtime`, `feat/g2-vietnamese-chat`, `feat/g3-orchestration`, `feat/g4-evidence-delivery`, `feat/g5-windows-package`. If an existing branch name conflicts, use a deterministic suffix rather than overwriting it.
5. Within a milestone, make small, meaningful commits **after relevant tests pass**, e.g. `feat(gui): add persistent project picker`, `test(db): verify session isolation`, `fix(cli): parse provider output safely`. Stage **only reviewed and authorized files** using explicit paths; avoid broad `git add -A` when the workspace may include sensitive/unrelated files.
6. After milestone acceptance evidence is verified and the target branch is clean, a **local fast-forward merge** into the approved integration branch may happen automatically if safe and configured. If conflicts/non-fast-forward changes exist, stop and ask for a decision; do not silently rebase or force merge. Record milestone branch and final SHAs.
7. If a test fails, do not create a misleading 'done' commit or merge; preserve the branch/worktree and diagnostics for repair. Optional clearly marked `wip:` checkpoint commits are allowed **only** on the isolated task/milestone branch for crash recovery, never accepted as delivered work.
8. Never alter an existing user's `user.name`/`user.email` globally. If `git config user.name` or `git config user.email` is missing, ask **once** for the local repository commit identity; do not invent a person/email or block unrelated code/test work. Set repo-local identity only if authorized.
9. Maintain a `.gitignore` covering `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.env`, secret-bearing config, database/app runtime files, logs, `build/`, `dist/`, and other generated private state. The Git index must be inspected for accidentally staged credentials before each commit. Do not retroactively erase history without approval.

#### B. Git when the finished AATPO works on user projects

1. **New project:** once the user confirms the project name and folder in GUI, initialize Git locally automatically if the folder is an allowed independent repository root; initialize a baseline commit when safe and author identity exists.
2. **Existing project with Git:** reuse the original repository/branch/history. Never run `git init`, switch branches or modify the index in a way that destroys or hides pre-existing changes. A dirty/uncommitted worktree triggers a safe choice: defer task, use an approved dedicated Git worktree where feasible, or ask the user to resolve the conflict. No automatic `git stash`, `git clean`, `git reset --hard` or `git checkout -f`.
3. **Existing project without Git:** on registration, provide a plain-language, one-time consent option, for example `Tu dong luu lich su phien ban (khuyen dung)`; only after authorization run `git init`, make an approved baseline snapshot and record the repository root. If the folder lies inside a parent repo, do **not** create nested Git by default.
4. **Each write-capable Task:** create a scoped branch using a normalized safe name such as `task/<work-order-id>-<task-id>-<short-slug>`. The branch references the project, work order, task and scope/plan version in SQLite. A task never edits a different project's Git checkout.
5. Prior to the first write, capture base SHA/branch, allowed paths, current status and a local baseline/recovery plan. If concurrent edits are possible, use an authorized task-specific worktree **only when verified compatible**; otherwise serialize work (`concurrency=1`). Separate a worktree from an OS sandbox: it offers no security boundary.
6. For implementation, only stage files actually changed for the authorized task; verify path scope and scan staged files for obvious credentials/private data. Run project-appropriate verified tests, save logs/diff evidence, and create local commits with task-aware messages such as `fix(auth): correct login validation [TASK-004]`.
7. QA reviews the committed task diff and evidence. If rejected, retain work on the same task branch and resume/rework with bounded attempts. If accepted, auto fast-forward merge to the **configured local integration branch** only when it can occur safely and the owner enabled the policy; otherwise show `Ready to integrate` in GUI. Do not label task delivered when merge/checkpoint state is uncertain.
8. GUI should show non-technical messages: `Da luu phien ban`, `Dang kiem tra thay doi`, `Can xu ly xung dot`, `Co the xem lich su`. Advanced detail can show branch, SHA, changed files and test artifacts. Provide a `Xem lich su thay doi` view and link commits to their work orders/tasks.
9. User requests to 'undo' must be turned into a **reviewed revert proposal** (normally a new revert commit where safe), not `reset --hard` or history rewriting. Always warn if undo may affect later edits and seek action-specific confirmation.
10. **Remote operations are OFF by default:** no GitHub/GitLab repository creation, adding/removing remote, fetch from untrusted URL, network push, force-push, remote delete, tag publishing or external deployment without separate explicit owner authorization and relevant provider/network policy checks. A local commit does **not** mean backed up to cloud. Recommend separate backups of valuable project files.

#### C. Safe Git operation boundaries and example implementation

- Git executable and arguments come from allowlisted application code; run subprocess with argument vectors, validated cwd and no user-text shell interpolation. Natural-language requests may propose actions but cannot execute raw `git` commands as trusted instructions.
- Validate repo root and project ID before every mutating Git operation. Capture command, exit code, stdout/stderr references, before/after commit SHA, branch and error in audit/evidence. Do not leak private filenames or secrets into customer-visible reports unnecessarily.
- For local safe actions (authorized init, branch create, stage approved files, verified commit, eligible fast-forward merge), no repeated confirmation is required after a project-wide opt-in. For irreversible/high-impact operations and remote interactions, show the exact effect and require approval.
- Handle repos with no commits (unborn HEAD), detached HEAD, protected branches, existing divergent histories, ignored/untracked files, Git lock files, external tools modifying the repo and Git executable missing. Never silently assume Git succeeded from zero/partial stdout.
- Prefer using `git status --porcelain=v1`, `git rev-parse`, `git diff --check`, `git diff --cached`, `git log`, and `git merge --ff-only` where appropriate; verify command support on installed Git for Windows. A subprocess exit 0 alone is not sufficient to claim task/test success.
- Local branches and commits are NOT backups against disk loss or all agent misbehavior. Keep workspace backups, Windows least-privilege operation and action approval policies.

**Example non-destructive source-build Git sequence (illustrative; validate status/root first):**

```powershell
# In D:\AATPO (owner-approved workspace; no existing parent repo conflict)
git init -b main
git status --short
git switch -c feat/g0-foundation-gui
# Coding agent writes code, runs tests, checks staged paths and secrets
git add -- pyproject.toml README.md .gitignore src tests
git diff --cached --check
git commit -m "feat(core): establish AATPO foundation and GUI shell"
# Only after verified milestone acceptance and safe clean fast-forward conditions:
# git switch main
# git merge --ff-only feat/g0-foundation-gui
```

**Acceptance:** The local agent must demonstrate at least one actual milestone branch plus real test-backed local commit; AATPO must later demonstrate repo initialization (with consent as appropriate), task branch, commit SHA, QA/rework behavior and safe integration in a disposable local sample project. Document skipped/unverified Windows checks truthfully.

---

## 7. DELIVERABLE REPOSITORY STRUCTURE

Suggested layout (adapt only with a documented reason):

```text
aatpo/
  pyproject.toml
  README.md
  CHANGELOG.md
  .gitignore
  config/
    office.example.toml
    providers.example.toml
  roles/
    client_representative.md
    business_analyst.md
    office_manager.md
    system_architect.md
    frontend_engineer.md
    backend_engineer.md
    qa_engineer.md
    devops_engineer.md
  src/aatpo/
    __init__.py
    __main__.py
    app.py                   # bootstrap GUI + dependency wiring
    settings.py
    domain/
      models.py
      state_machine.py
      permissions.py
      contracts.py
    db/
      connection.py
      migrations/
      repositories.py
    projects/
      registry.py
      resolver.py
      workspace.py
      git_service.py            # safe, authorized local Git operations
      git_policies.py           # init/branch/commit/merge guards
    customer/
      representative.py
      analyst.py
      scope_advisor.py
      intent_router.py
    office/
      manager.py
      planner.py
      scheduler.py
      cli_router.py
      quality.py
      cost_controller.py
      handoffs.py
    agents/
      profiles.py
      prompt_builder.py
      session_manager.py
    cli/
      base.py
      windows_launcher.py
      codex_adapter.py
      claude_adapter.py
      gemini_adapter.py
      parsers.py
      probe.py
    evidence/
      git_evidence.py
      git_audit.py               # task/branch/SHA/evidence linkage
      tests.py
      artifacts.py
      reports.py
    gui/
      main_window.py
      navigation.py
      theme.py
      viewmodels/
      widgets/
      pages/
        home_chat.py
        projects.py
        tasks.py
        approvals.py
        results.py
        settings.py
        onboarding.py
      bridges/
        background_jobs.py
        events.py
    telemetry/
      audit.py
      redaction.py
  tests/
    unit/
    integration/
    ui/
    acceptance/
    git/                       # init/dirty/rebase/conflict/commit tests
    fixtures/
      fake_cli.py
  packaging/
    aatpo.spec             # when executable packaging is ready
  docs/
    architecture.md
    user_guide_vi.md
    operations_windows.md
    cli_compatibility.md
    permission_model.md
    acceptance_matrix.md
    decisions.md
    git_workflow.md             # user-facing/technical Git policy
    milestone_reports/
```

Ensure `python -m aatpo` launches the GUI in development. Optional `ato` diagnostic commands may be added for developers/CI but are **not** required for normal customer operations.

---

## 8. MILESTONES — IMPLEMENT IN THIS ORDER

### G0 — Foundational app + REAL GUI SHELL (first code)

Implement:
- Python project/venv/config, Pydantic domain models, SQLite migrations, app data paths.
- **Initialize or reuse Git in the owner-approved AATPO workspace; safe `.gitignore`, author identity check, create `feat/g0-foundation-gui` branch, verified commits and Git evidence (section 6.3).**
- `Project`, `WorkOrder`, `CLIProvider`, `AgentRole`, `Task`, `AgentSession`, `ProcessRun` with distinct IDs.
- Deterministic state transitions, persistence, minimal event journal, fake CLI adapter.
- **Real PySide6 desktop window** with 5 named navigation areas and a first-run onboarding placeholder that is functional for project selection and local configuration even without live providers.
- Project Registry: add existing project with native folder picker, select active project, persist and reopen it.
- Automated tests for DB, transitions, registry and session isolation.

Pass only when:
- Source runs; `python -m aatpo` opens the native Qt window in a supported GUI environment, with visible Vietnamese labels.
- A project can be added from GUI, selected, and is still there after app restart.
- Database and tests pass; different tasks/roles/sessions/runs cannot be conflated.
- Local Git repo status, milestone branch and actual commit SHA are recorded; if identity is missing, provide the precise blocker rather than inventing an author.
- When GUI not available in current CI environment, test non-GUI core and mark actual Windows GUI smoke as **UNVERIFIED**, not passed.

### G1 — Official CLI runtime + GUI provider readiness

Implement:
- Windows CLI launcher with safe argv handling, timeouts, stdout/stderr streaming, cancellation and process-tree cleanup.
- Real probe and read-only opt-in smoke flows; first real provider adapter end-to-end (pick installed one, not always Codex).
- Adapter skeletons for other providers; support missing/unsupported providers without GUI crash.
- Real Session Ledger with exact provider session IDs and fallback on unsupported resume.
- Settings/onboarding page shows status `Sẵn sàng`, `Chưa cài`, `Chưa đăng nhập`, `Hết hạn mức`, `Không tương thích`, `Không xác định` as appropriate.
- Fake CLI fixtures simulate exit error, JSON malformation, timeout and resume.

Pass only when:
- Exactly one logged-in provider can run a simple **read-only** request from the GUI **after consent**; if no provider installed, app explains remedy and cannot pretend success.
- New task uses a new session; rework exact resume only where verified supported.
- `.cmd` executable and Windows path spaces/Unicode are tested, or explicitly marked unverified on non-Windows hosts.

### G2 — Natural-language conversation + UX scope approval

Implement:
- Customer chat with saved message history per project/work order.
- Intent proposal + Pydantic validation + deterministic action policy; input sanitization and user-visible error fallback.
- Discovery asks one meaningful question at a time and permits `Tôi chưa biết, hãy đề xuất`.
- Scope proposals MUST/SHOULD/LATER/DROP, `Tiết kiệm` vs `Cân bằng`, scope version/approval.
- User clicks approval in GUI; forbidden actions cannot be approved implicitly through fabricated AI output.

Pass only when:
- Vietnamese request for simple inventory app → meaningful question → `không biết` response → two scope options → explicit GUI approval.
- Without approval, no coding task for new product scope starts.
- Text sent to assistant in one project is not leaked into unrelated project sessions.

### G3 — Manager, scheduler, task list, approvals

Implement:
- Validated TaskPlan DAG, dependencies, no cycles, versioned plan.
- Deterministic scheduler with project-scoped routing and resource locks.
- Automatic task-to-Git-branch assignment policy integrated with project/work-order/task identifiers; branch conflicts/dirty repo pause safely.
- Three work modes by policy: Fast Lane (small), Standard (BA/Dev/QA as needed), Full Project (Architect/FE/BE/QA/DevOps as needed). **Not all roles every time.**
- Task details/real-time status in GUI; safe start, pause, resume and pending-approval queue.
- Structured handoffs and bounded retry/replan/review cycles.
- Clear customer-facing progress events; log only verified state.

Pass only when:
- One simple task can be started by clicking a GUI button, scheduled, executed by fake or real CLI, and reviewed with evidence.
- Multi-task work respects dependency order. Quota/unavailable provider pauses accurately.
- Nothing writes `Task.DONE` based solely on the AI's claim.

### G4 — Real coding workflow, evidence, delivery

Implement:
- Project workspace access validation, **automatic authorized repo init + task branches + test-backed local commits + safe fast-forward integration**, Git status/diff, limited authorized writes, actual test execution with recorded commands and outputs.
- QA verifies acceptance; rework with exact-session resume or verified fallback.
- `Kết quả` screen: deliverable, tests, summary, known limitations, open folder, request revision.
- Real repo end-to-end test under a trusted, isolated **test project folder**, no production deploy.
- Report export as Markdown/text (PDF optional later); full user guide in Vietnamese.

Pass only when:
- User opens GUI, registers a trusted sample repo, writes a Vietnamese request, approves, starts execution using one authenticated official CLI, and obtains **real modified source + test evidence + readable report**.
- QA rejects at least one deliberate failure and rework flow is bounded.
- Disposable sample repo shows a task branch, task-specific commit, verified QA link and safe local integration; no unauthorized remote push or destructive Git operation.
- The software never claims production deployment or success when a test fails.

### G5 — Windows packaging, reliability, usability validation

Implement:
- PyInstaller **onedir** Windows packaging, icon/shortcut or documented quick launch, no terminal needed for end user.
- DB backups, restart/crash recovery tests, run reconciliation, old provider schema error handling.
- Git crash/conflict recovery, user-friendly version-history GUI and audit reconciliation of SQLite task state with actual repo SHA/branch.
- GUI keyboard, scaling, Unicode path and responsive behavior validation.
- Measured run counts/time and provider success/failure diagnostics; no invented actual costs.
- Optional concurrency=2 only after locks and reliability tests; remain at 1 otherwise.

Pass only when:
- A non-developer can launch the packaged `.exe` on Windows, register/select a project, provide instructions in Vietnamese and inspect outcome, **without installing a separate Python environment**. Provider CLI must still be installed/authenticated separately.
- Restart keeps work state; uncertain write operations are not replayed blindly.
- Packaging and UI tests are **actually run on Windows** and recorded. Never pass G5 based on a Linux-generated build.

### Delivery discipline

At each milestone update `docs/milestone_reports/Gx.md` with:
- Implemented behavior and files; exactly how to launch it.
- Test commands, number passed/failed/skipped, current OS, Python and provider versions.
- Screenshots or actual GUI observations for Windows UX tests where available, not substitute mock art.
- Demo workflow, validated evidence references and unresolved risks.
- Exact Git repository root, working/integration branch names, commit SHA(s), merge status and whether any Git action awaits the owner.
- Next milestone entry conditions. Do not move forward assuming the preceding milestone works.

---

## 9. ACCEPTANCE TEST MATRIX — MUST IMPLEMENT

| ID | Scenario | Required outcome |
|---|---|---|
| A01 | Open desktop GUI | Vietnamese UI loads, responsive, no terminal for end user |
| A02 | Register local project | Native picker, canonical path shown, persists restart |
| A03 | Same name/ambiguous project | Ask user; never silently choose target |
| A04 | Existing project directory missing | Explain and offer relink; no silent recreation |
| A05 | Customer asks for new product in Vietnamese | Clarify highest-impact missing detail without jargon |
| A06 | User says `Tôi không biết` | Safe suggested default with trade-offs |
| A07 | Scope lean/balanced not approved | No coding execution for new product scope |
| A08 | One installed/authenticated provider only | Usable; no requirement for other providers |
| A09 | Provider missing/not authenticated | Friendly GUI guidance, no fake success |
| A10 | Same CLI, 3 roles | Three distinct sessions with appropriate profiles |
| A11 | Same role, 2 tasks | Different sessions, no cross-task conversation |
| A12 | Same task returned by QA | Resume **exact** ID when supported; else explicit fresh session |
| A13 | Switch providers | Structured handoff, new session, preserved evidence |
| A14 | Malformed JSON/nonzero exit | Run failed/parse error; never Task.DONE |
| A15 | Windows path with spaces/Unicode and `.cmd` | Safe execution or explicit unsupported state |
| A16 | User prompt contains shell metacharacters | Treated as data, no shell execution |
| A17 | User asks to access unrelated project | Guard/approval flow; no implicit access |
| A18 | README or source contains prompt injection | Does not become trusted policy |
| A19 | Provider quota/timeout | Bounded pause/error/fallback as configured |
| A20 | Planner returns cycle/missing dependency | Plan rejected by validator |
| A21 | Tests fail or QA rejects | Bounded rework, not marked complete |
| A22 | Approval needed for destructive/paid action | Explicit action-specific GUI approval |
| A23 | Restart/crash during run | Durable state, reconciliation, no blind duplicate write |
| A24 | New work order in another project | Correct target, project memory isolation |
| A25 | Real coding task | Actual source change, independently verifiable tests, evidence |
| A26 | Package Windows app | Double-click GUI works; no developer Terminal required |
| A27 | User requests final result | Open folder, friendly summary, unresolved items visible |
| A28 | No CLI provider at all | GUI/project management still works; execution correctly blocked |
| A29 | Cancel/pause from GUI | UI remains responsive; child process cleanup is checked |
| A30 | App logs | No intentional credential collection; diagnostics are redacted |
| A31 | Coding agent starts G0 without Git | Initializes in exact approved root (not nested) and checks `.gitignore` |
| A32 | Git identity missing | Requests one-time repository-local author identity; never invents an author |
| A33 | Milestone source passes tests | Creates feature branch, verified local commit and reports SHA |
| A34 | Existing repository dirty | Preserves uncommitted edits; no reset/clean/stash/forced checkout |
| A35 | New project local Git enabled | Initializes authorized new repository and baseline safely |
| A36 | Existing unversioned project | GUI one-time approval before Git initialization |
| A37 | Coding task in registered project | Task-specific branch, allowed-path commit, evidence linked to SHA |
| A38 | QA fails or merge conflict | Keeps work isolated; no false DONE/merge; reports actionable issue |
| A39 | Successful local integration | Fast-forward-only on configured clean branch; preserves history |
| A40 | Unrequested remote/destructive Git action | No push/force-push/rewrite/remote delete; scoped approval required |

Tag tests `unit`, `mock_integration`, `windows_integration`, `real_provider`, `manual_gui`. Fake CLI passing is not proof that Windows/authenticated provider integration passed.

---

## 10. INITIAL SETUP THE OWNER MAY NEED TO DO

**Keep this simple; do not ask the owner to learn programming.** At startup, show a first-run checklist that can diagnose the following and explain missing items in Vietnamese:

1. A **Windows 11** computer and a **trusted folder** where AATPO source can be built; plus one or more folders containing the projects they want AATPO to work with.
2. **Python 3.12+** available to the coding agent for building; after packaged GUI is delivered, the ordinary end user should not need to manage Python separately.
3. **Git for Windows** available; automatic local version history is required for build milestones and code-editing tasks. GitHub/GitLab account, remote and network push are **not** required. Git commit author name/email may need a one-time configuration if missing (do not guess personal details).
4. At least **one official AI CLI** installed and logged in legitimately: Codex, Claude Code, or Gemini CLI. It is not necessary to buy/install all three; a coding agent can begin mock-based G0 before any real CLI is ready.
5. Internet connectivity when required by the chosen AI provider, package installation or updates. **Local CLI execution does not imply offline model inference.**
6. Before enabling real file edits, back up valuable project folders and ensure the Windows user is **not running AATPO as Administrator**. Only use trusted repos at first.
7. The owner must consent to installing project dependencies into an isolated `.venv` (not system/global Python), and separately approve other P2/P3 activities per policy.

### Useful Windows read-only checks for developer / coding agent

```powershell
python --version
py --version
git --version
Get-Command codex,claude,gemini -ErrorAction SilentlyContinue
```

These are optional **diagnostic checks for developer setup**, not normal end-user commands. No need for separate API keys by default. Do not ask the owner for credentials in chat or configuration files; let official CLIs manage their own login.

### What is not a prerequisite

- No web server, domain, hosting, cloud account, Redis, Postgres, Docker/WSL, vector database.
- No 8 provider accounts or continuously running worker instances.
- No API token copied out of a CLI provider's login folder.

---

## 11. NON-GOALS AND IMPORTANT HONEST LIMITATIONS

- Not a web app or remotely hosted SaaS in this version.
- No public auto-deploy or autonomous payment/spending; these require separate explicit scope and permission.
- No installer/service that auto-starts 24/7 by default; GUI launches locally and workflow pauses/resumes durably. An always-on background service would require future design.
- No claim of complete security isolation. A CLI operating under the user's Windows credentials can have OS privileges beyond the app's logical path permissions.
- No claim that two QA/developer sessions using the same model are fully independent; acceptance is anchored in executable tests and artifacts.
- No claim of known monetary cost/quota when provider does not expose reliable information.
- No fabricated test logs, screenshots, file paths or `.exe` bundles.
- No copying auth data or violating provider subscription/CLI usage policies.

---

## 12. FINAL DONE DEFINITION — COMPLETE GUI-FIRST MVP

AATPO is accepted as **complete MVP** only when the following **all** have real evidence on Windows:

1. Native GUI opens with ordinary Windows launch; five primary areas and clear Vietnamese language.
2. Nontechnical owner registers/selects an existing project through GUI, with unambiguous target path.
3. Owner describes a task in Vietnamese; Agent receives/clarifies it and presents scope if necessary.
4. Explicit customer scope/permission decisions persist, cannot be bypassed by LLM output.
5. Planner creates a valid, appropriately sized task DAG and selects role/CLI.
5a. Project and task changes use authorized **automatic local Git branches and test-backed commits**, with visible version history; no remote push or history rewrite without approval.
6. An actual authenticated official CLI runs at least one real task **from the GUI**, using the registered project.
7. Sessions of different roles/tasks are demonstrably separate; correct resume/fallback is evidenced.
8. Source/artifacts and test outputs are validated; QA can request bounded rework.
9. GUI shows real progress, errors, pauses, approvals and user-friendly delivery reports.
10. Closing/restarting the application preserves tasks, decisions and reports, with safe crash reconciliation.
11. Packaged Windows GUI runs via double-click (with provider installed/authenticated separately).
12. Test reports differentiate `passed on Windows`, `passed with fake provider`, `skipped` and `not verified`.

If any item is unverified, the agent must label the output **partial implementation, not accepted complete MVP**.

---

## 13. FINAL RESPONSE CONTRACT FOR CODING AGENT

When reporting work back to the owner, use Vietnamese and this structure:

1. **Đã xây dựng:** brief factual completed features.
2. **Cách mở phần mềm:** actual tested path or commands, distinguish development app vs packaged `.exe`.
3. **Cách dùng thử:** a concrete GUI scenario, named project and task.
4. **Kiểm thử:** environment, explicit test command, pass/fail/skip and actual evidence.
5. **CLI:** what providers were really detected, authenticated-tested (or not) and session/resume support.
5a. **Git:** repo root, milestone/task branch, latest verified commit SHA, integration status, pending conflicts and whether remote publishing was disabled.
6. **Còn thiếu/rủi ro:** truthful limitations and unverified Windows behaviors.
7. **Bước tiếp theo:** next milestone or exact reason blocked, without claiming background work.

**DO NOT end with only a design. Build code. DO NOT mark a task done without evidence. DO NOT ask the owner to choose a programming framework: use this approved stack.**

---

## 14. OPTIONAL CONTEXT / SOURCE PRIORITY

`AATPO_Implementation_Blueprint_V3.1.md` is the original detailed implementation blueprint. If it is available in the repository, read it for the additional domain definitions, state semantics, example contracts, tests and policy detail. If missing, **this V4.1 brief is self-contained** and sufficient to start and continue development.

Conflict rule: **Owner's GUI-first/natural-language-first decision documented in V4.1 > V3.1 terminal-only MVP requirement**. Preserve V3.1's Windows native/official authenticated CLI, task-scoped sessions, no shared chat history, SQLite source of truth, evidence, approvals, no sandbox design and no unrestricted bypass flags.

**End of V4.1 implementation input. Start implementing milestone G0 with automatic local Git setup now.**
