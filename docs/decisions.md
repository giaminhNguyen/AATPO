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
