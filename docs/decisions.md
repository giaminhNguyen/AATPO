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
