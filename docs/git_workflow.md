# Git workflow (local only)

- Milestone branches: `feat/g0-foundation-gui`, `feat/g1-cli-runtime`, … Commits only after tests pass, staged by explicit path.
- No remote, no push, no history rewrite, no reset/clean/stash/forced checkout — enforced in `GitService` by a subcommand allowlist.
- Registered projects: existing repo → reused untouched; no repo → `git init` only after the user ticks the one-time history option; never nested inside a parent repo.
- Local commits are **not** backups.
- Fast-forward integration into `main` happens only after milestone acceptance and only with `--ff-only` (not yet implemented in the product; G0 integration status is in the milestone report).
