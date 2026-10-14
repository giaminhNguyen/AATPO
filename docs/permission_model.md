# Permission model (what is enforced, what is not)

**There is no sandbox/VM/container in this MVP (owner decision).** AI CLIs run with the *current Windows user's* privileges. Everything below is *policy and guard code*, not an OS security boundary.

## Tiers (spec 5.5) and where they are enforced
| Tier | Examples | Enforcement in code |
|---|---|---|
| P0 read/analyse | Claude `plan` mode + `Read,Grep,Glob`; Codex `read-only` | `ClaudeAdapter.BASE`, `CodexAdapter.run_argv` |
| P1 edit task files, run approved tests | Claude `acceptEdits` + `Edit,Write` (no Bash); Codex `workspace-write`; test command | write only after scope approval + Git preflight (`WriteFlow.preflight`); test command user-confirmed, launcher allowlist |
| P2 install deps, network-sensitive, migrations | – | **not offered**: no tool in write mode can run commands |
| P3 bulk delete, deploy, credentials, spend | – | **no code path exists**; `allow_*` config cannot enable push/history rewrite (`load_config` hard floor) |

## Guards that do exist
- **Consent before data leaves the machine:** each real-provider smoke, the optional LLM intent understanding, and approved work. Stored locally; revocable.
- **Approvals are GUI-only**, bound to action + project + work order + scope version (`ApprovalService`); chat text, silence, or model output can never approve. Approval phrases never reach a model.
- **State machine**: LLM output is data; DONE needs evidence (verified artifact; for write tasks a commit + passing test run + QA verdict).
- **Git**: argv-only, allowlisted subcommands, validated refs/paths, task-namespace branches, clean-tree requirement, explicit-path staging, `merge --ff-only`, `revert` only for ledger commits after approval; **never**: push, fetch, remote edits, reset, clean, stash, forced checkout, rebase.
- **Change policy** after each write run: forbidden paths (`.env`, keys, `.git`), changes outside the project folder (sub-folder projects), secret-looking added lines, conflict markers → rejected before commit.
- **Process hygiene**: no shell, prompts on stdin, output caps, timeouts, process-tree kill, Job Object kill-on-close, secret redaction.
- **Prompt injection**: project text, other tasks' output, briefs and customer text are fenced and labelled DATA; the verdict is parsed only from the QA run's first line.

## Not guaranteed
An agent with Edit/Write can still touch any file the Windows user can reach through symlinks/junctions or absolute paths; AATPO *detects* changes inside the repo it watches and refuses to commit bad ones, but cannot prevent them. Use trusted repositories, back up valuable folders, and do not run AATPO as Administrator.
