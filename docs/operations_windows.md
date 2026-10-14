# Operations on Windows 11

## Run / build
| Goal | Command (from the repo root) |
|---|---|
| Development app | `.\.venv\Scripts\python -m aatpo` |
| Tests | `.\.venv\Scripts\python -m pytest -q` (178 at G5; `tests\windows` needs a built exe for the packaged-exe tests, otherwise they are *skipped*) |
| Build the app | `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` → `dist\AATPO\AATPO.exe` (onedir, windowed, ~130 MB) |
| Desktop shortcut | `powershell -ExecutionPolicy Bypass -File packaging\make_shortcut.ps1` |
| Built-in self-check | `AATPO.exe --smoke-test out.json` (opens the window, checks roles/migrations/DB, exit 0 = ok) |

The packaged app needs **no Python**. It still needs **Git for Windows** and an installed + logged-in **Claude Code / Codex** (the app never stores their credentials).

## Where data lives (`%LOCALAPPDATA%\AATPO`, override with `AATPO_HOME`)
`data\office.db` (SQLite, WAL) · `artifacts\` (agent outputs, diffs, test output, reports; SHA-256 in DB) · `backups\` · `logs\errors.log` (redacted tracebacks, rotated at 1 MB) · `config\office.toml` (optional overrides, see `config\office.example.toml`).

## Backups and restore
- A verified backup is taken once per day at startup (`backups\office-YYYYMMDD.db`, newest 7 kept) and before every schema migration.
- GUI: **Cài đặt → Dữ liệu và độ tin cậy**: *Sao lưu dữ liệu ngay*, *Khôi phục từ bản sao lưu…* (applied at the NEXT start; the current database is kept as `backups\before-restore-*.db`), *Đối chiếu với kho Git*.
- Manual restore: close AATPO, copy a backup over `data\office.db`, delete `office.db-wal`/`-shm`.
- Project folders are **not** backed up by AATPO; local Git history is not a backup.

## Crash behaviour
Child CLI processes die with AATPO (Windows Job Object). On the next start, a task that was RUNNING becomes "Cần bạn xem lại" with a re-run approval; nothing is replayed automatically.

## Troubleshooting
| Symptom | Meaning / action |
|---|---|
| "Gặp lỗi nội bộ …" | work was stopped safely; send `logs\errors.log` |
| Task "Bị chặn: thay đổi chưa lưu" | commit/revert your own edits, then **Tiếp tục** |
| "index.lock" | another Git process/crash left `.git\index.lock`; close it and delete the file yourself |
| "Chưa có tên và email" | Dự án → **Tên người lưu phiên bản…** |
| Provider "Không tương thích" | CLI flags changed; see `docs\cli_compatibility.md`, update AATPO or the CLI |
| Display scaling | validated at 100/125/150% at the 900×600 minimum size |

## Known limits
Concurrency is 1 by design (2 only after locks are proven under load — not done). Real exact-resume with Claude/Codex is disabled until verified. Gemini CLI is detection-only. No code signing (SmartScreen may warn on first run).
