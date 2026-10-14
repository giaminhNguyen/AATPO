# CLI compatibility matrix (tested on this machine only)

Host: Windows 11 Pro 10.0.26200. Rows describe what was **actually run**; "UNVERIFIED" means not exercised against the real CLI.

| Provider | Version | Local probe (`--version`, `--help`, auth status) | Real model request | Exact session resume |
|---|---|---|---|---|
| Codex | codex-cli 0.160.0 (`.exe`) | verified: `ready` (`codex login status` exit 0) | **UNVERIFIED** | flags present in `codex exec resume --help`; **UNVERIFIED** end to end → disabled |
| Claude Code | 2.1.299 (`.exe`) | verified: `ready` (`claude auth status` → `loggedIn: true`; only the boolean is read) | **verified 2026-10-14** (read-only, scratch folder; `result` text + `session_id` UUID parsed; files untouched) | `--resume <id>` in `--help`; **UNVERIFIED** end to end → disabled |
| Gemini CLI | not installed | verified: `missing`; adapter is a skeleton (cannot run) | n/a | n/a |

## Command templates (fixed in code; prompt only on stdin)
- Codex run: `codex exec --json -s read-only --skip-git-repo-check -C <project> -o <tmp>/last.txt -`
- Codex resume: `codex exec resume --json --skip-git-repo-check -c sandbox_mode="read-only" -o <tmp>/last.txt <thread_id> -` (cwd = project; `resume` has no `-s`/`-C`)
- Claude run: `claude -p --output-format json --permission-mode plan --tools Read,Grep,Glob` (cwd = project); resume adds `--resume <session_id>`
- Never used: `--dangerously-bypass-approvals-and-sandbox`, `--dangerously-skip-permissions`, `--yolo`.

## Parser status
- Claude JSON: **confirmed against a real run**. Codex JSONL: still an assumption.

## Parser assumptions (Codex still unconfirmed)
- Codex JSONL: `thread.started{thread_id}`, `item.completed{item:{type:"agent_message",text}}`, `error` / `turn.failed`. Final text prefers the `-o` file. If `thread_id` is absent, **no session id is stored** and rework starts a new session (safe fallback).
- Claude JSON: object (or event array) with `result`, `session_id`, `is_error`.
These come from CLI help and general knowledge of the formats, **not** from a captured real run; fake-CLI tests prove parsing logic, not format accuracy.

## Windows launch behaviour
- `.exe`: `create_subprocess_exec`, prompt via stdin (UTF-8), `CREATE_NO_WINDOW`.
- `.cmd/.bat`: only through `cmd.exe` with an argument allowlist (`[A-Za-z0-9_.:=,/\-]`); tested with a path containing spaces and Vietnamese characters (fake CLI) — passed.
- Timeout/cancel: `taskkill /T /F`; a spawned grandchild process was verified dead after cancel.
