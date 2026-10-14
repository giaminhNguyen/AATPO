# Architecture (as built)

```
PySide6 GUI (src/aatpo/gui)  ── pages: Văn phòng AI · Dự án · Công việc · Cần bạn quyết định · Kết quả · Cài đặt
   │  BackgroundJobs: private asyncio thread → Qt signals (UI never blocks)
Application services (src/aatpo)
   ├─ customer/   ChatService (intent → deterministic policy), rule + optional LLM proposer, discovery, scope advisor
   ├─ office/     OfficeManager (plan, schedule, QA gate, rework, finalize), WriteFlow (git/test/commit), ApprovalService,
   │              cli_router, planner, audit, metrics
   ├─ projects/   ProjectRegistry, GitService (allowlisted), git_policies (task branches), history
   ├─ agents/     SessionManager (session ledger, resume/fallback), prompt_builder (fenced data), role profiles (roles/*.md)
   ├─ evidence/   artifacts (SHA-256), tests (allowlisted runner), git_evidence (path/secret scan)
   ├─ delivery/   report (Markdown, from recorded state only)
   └─ cli/        windows_launcher (+Job Object), Codex/Claude/Gemini adapters, strict parsers, probe
Persistence: SQLite (versioned migrations 001-005, WAL, FK ON) + artifact files + the project's own Git repo
```
Five distinct concepts with separate IDs: `CLIProvider` ≠ `AgentRole` ≠ `Task` ≠ `AgentSession` ≠ `ProcessRun` (plus `Project`, `WorkOrder`). One session per (assignment); rework resumes the stored provider session only where verified, otherwise a new generation with a compact brief.

## Control flow of one request
1. Chat → sanitised → intent (rules; LLM optional, validated) → policy → work order + **one** question → scope options (MUST/SHOULD/LATER/DROP).
2. **GUI approval** (action + project + scope version) → plan (validated DAG; Fast Lane / Standard / Full) → tasks.
3. Scheduler (concurrency 1, repo lock) → route provider (preference Claude, Codex, Gemini; only `ready`) → session + run.
4. Write task: Git preflight → task branch → agent edits → path/secret/conflict checks → **AATPO runs the tests** → task commit → artifacts.
5. Independent QA task (own session) sees the real diff + test output; first line `VERDICT: PASS|FAIL`; DONE requires commit + passing test + verified artifact.
6. Final test run → ff-only integration (auto or by click) → report → DELIVERED. Conflicts/failed tests ⇒ not delivered.

Key decisions are in `decisions.md`; safety model in `permission_model.md`; operations in `operations_windows.md`; evidence in `acceptance_matrix.md` and `milestone_reports/`.
