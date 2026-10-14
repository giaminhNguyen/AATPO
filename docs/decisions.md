# Technical decisions (not fixed by the V4.1 brief)

| # | Decision | Why |
|---|---|---|
| D1 | Python 3.13 venv (`py -3.13`); `python` on PATH is 3.10, below the 3.12 minimum | Spec requires 3.12+ |
| D2 | Source root is `C:\Users\minhng\Desktop\GIT\AATPO` (the folder the owner opened), flat `src/aatpo` layout, no nested `aatpo/` dir | Spec 0.2; no enclosing repo existed, so `git init -b main` there is not nested |
| D3 | Git identity: reused the owner's existing global `user.name/email`; nothing was written to any Git config | Spec 6.3.A.8 |
| D4 | Baseline commit for registered projects is an **empty** commit (`--allow-empty`), not a snapshot of files | `git add -A` could sweep in secrets or unrelated files; a file snapshot needs a reviewed path list (G4) |
| D5 | GitService allowlists subcommands (`rev-parse status init add commit config symbolic-ref diff log`); push/reset/clean/stash/checkout/remote/rebase/fetch raise `GitError` | Spec 6.3.C; widen deliberately per milestone (branch/merge arrive in G3/G4) |
| D6 | IDs are `PREFIX-<12 hex>` (uuid4), never names | Spec 4.1 |
| D7 | One shared SQLite connection + RLock, `isolation_level=None`, explicit `BEGIN IMMEDIATE` per transaction | G0 volume is tiny; revisit with background workers in G1 |
| D8 | Version is checked **before** transition validity, so a stale claimer gets `ConflictError` | Distinguishes lost races from illegal moves |
| D9 | Chat input on the home page is visibly disabled with a "G2" note rather than faked | Spec 11: no fabricated functionality |
| D10 | Project registration is blocking (a quick `git` subprocess) on the Qt thread in G0 | Sub-second; moves to the background-job bridge when real CLI runs land in G1 |
| D11 | Migration runner turns `foreign_keys` OFF, applies the migration, runs `foreign_key_check`, turns it ON (SQLite's table-rebuild recipe); `defer_foreign_keys` was tried and does not work for DROP of a populated parent | Test with real rows caught it |
| D12 | Fallback session = new `agent_sessions` row (`generation+1`, `supersedes_session_id`, `fallback_reason`, `handoff_brief`) under the SAME assignment; migration 002 | Spec 3.4: new session with brief, never a guessed id |
| D13 | Real-provider smoke is consent-gated in `run_readonly_smoke(consent=...)` (service layer) and also by a GUI dialog; each click creates a new work order/task, hence a new session | Spec G1: opt-in; new task => new session |
| D14 | Provider "ready" = installed + required flags present + the CLI's own local login-status command succeeds. It does NOT prove quota remains | Probe must not call a model |
| D15 | Codex session id is stored only if `thread.started.thread_id` parses; the final text prefers the `-o` file | Spec 3.4/3.5 |
| D16 | Discovery asks exactly ONE question (domain-specific) before proposing scope; more questions would add turns without changing the two options in this MVP | Spec G2: one highest-impact question per turn |
| D17 | Chat text can never approve: approve phrases are intercepted by rules before any model, models may not even propose `approve_attempt`, and `SCOPE_CONFIRMED` is reachable only via `ApprovalService.decide` (GUI buttons) | Spec 2.2 / A07 / A22 |
| D18 | LLM intent understanding is OFF by default, enabled per-user with a consent dialog (stored in `app_state`), re-validated after every probe, preferring Claude then Codex; any LLM failure falls back to rules | Owner preference + spec 2.2 |
| D19 | Every LLM intent call = new task = new session under a per-project "Hội thoại" work order; the prompt carries only the current project name and the fenced user text | Spec 3.4 session isolation, A24 |
| D20 | While a clarification is pending, only housekeeping commands (progress, pause, open/create project) are interpreted as commands; everything else is the answer (data) | Prevents "answer" text acting as a command |
| D21 | `clear_layout()` hides and unparents widgets before `deleteLater()` | Native screenshot showed ghost buttons otherwise |
| D22 | Provider preference default is `claude, codex, gemini` (owner: Claude first); spec default was `codex, gemini, claude`. Config can override, cannot enable push/history rewrite | Owner instruction |
| D23 | Every task that `writes` must be depended on by a QA task (plan validator); non-writing tasks (analysis/design/packaging) reach DONE only via a verified artifact (exists, non-empty, SHA-256, same task) | "QA says yes" or "run succeeded" alone is never evidence |
| D24 | QA tasks may start when their dependencies are in REVIEW (not DONE); QA's verdict is the only thing that moves a writes-task REVIEW→DONE/REWORK. Verdict = first line exactly `VERDICT: PASS|FAIL`, anything else is not a pass | Breaks the DONE↔QA dependency cycle without trusting free text |
| D25 | Rework exhaustion goes REVIEW→FAILED directly (state machine has no REWORK→FAILED) with `rework_count` recorded | Keeps transition table minimal |
| D26 | G3 runs read-only adapters: write tasks yield a concrete PROPOSAL; branch creation for write tasks is implemented and tested (`write_mode=True`) but OFF until G4 enables real writes | Avoids moving the user's checkout for no benefit; real run showed QA correctly rejects "fixes" that were never applied |
| D27 | Restart: CLAIMED→READY, RUNNING→UNKNOWN_AFTER_CRASH + a `rerun` approval; locks of uncertain tasks are kept | Spec 6.1 / A23 |
| D28 | Write mode for Claude = `--permission-mode acceptEdits --tools Read,Grep,Glob,Edit,Write` (NO Bash); Codex = `-s workspace-write`. The agent therefore cannot run commands; AATPO itself runs the tests, as independent evidence | Real run verified for Claude; Codex write mode is UNVERIFIED |
| D29 | Test commands: user-confirmed per project, first token must be an allowlisted launcher (python/py/pytest/npm/yarn/pnpm/node/dotnet/cargo/go/mvn/gradle/make), argv only, `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider` so tests do not dirty the repo | P1 "run approved tests" |
| D30 | Mechanical checks run BEFORE QA and reject straight to bounded rework: no file changed, forbidden path (`.env`, keys, `.git`), secret-looking ADDED line, conflict markers, failing tests. Nothing is committed in those cases (index-only `restore --staged` undoes staging) | Saves QA runs; never commits unreviewed secrets |
| D31 | Preflight for write tasks (blocking, plain-Vietnamese message): Git present, repo with ≥1 commit, commit identity configured (repo-local value only if the user typed it), clean tree for a NEW task branch, still on the task's own branch for rework | Spec 6.3.B; A32/A34/A36 |
| D32 | Task branches chain: a later task's branch starts from the previous task's tip; integration fast-forwards the newest branch after verifying earlier ones are ancestors | Keeps one linear history without merges |
| D33 | Integration is `merge --ff-only` only: automatic when config allows AND the project's history option is on; otherwise `integration_status=ready` plus an explicit "Tích hợp vào nhánh chính" click. Non-fast-forward or dirty tree ⇒ `conflict`, work order stays PACKAGING (not delivered), nothing rebased/forced | Spec 6.3.A.6, A38/A39/A40 |
| D34 | Final verification re-runs the test command before PACKAGING; failure ⇒ BLOCKED, no report, no integration | "Never claims success when a test fails" |
| D35 | Report is built only from recorded state (reviews, test_runs, commits, scope) and always lists what is NOT verified; it is stored as a hashed artifact | Spec 11, 13 |
| D36 | Revert/undo proposals and the version-history view are deferred to G5 (spec G5 lists the history GUI) | Scope control |
| D37 | Windows Job Object (kill-on-close) around every CLI child; best effort, never fatal | A crashed AATPO must not leave an agent editing files |
| D38 | Backups: SQLite online-backup API + integrity_check; restore applied at next start BEFORE the DB opens; pre-restore DB always kept | Never overwrite an open DB |
| D39 | Undo = approval-gated NEW revert commit for ledger commits only; abort on conflict; never reset | Spec 6.3.B.9 |
| D40 | `run_work_order` converts unexpected exceptions into a safe BLOCKED state + redacted log + plain message | A popup with a raw SQL error is not acceptable UX or evidence |
| D41 | Button rows use `FlowLayout`; minimum window 900x600 | Real clipping found at 100/125/150% |
| D42 | Packaged exe is windowed onedir with a `--smoke-test` self-check; no installer/signing | Spec G5: exe first |
