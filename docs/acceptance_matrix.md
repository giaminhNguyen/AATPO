# Acceptance matrix (spec section 9) — status as of G5

Legend: **W** = verified on this Windows 11 machine with real components (real git/pytest/processes/Qt platform `windows`); **R** = verified with a *real* authenticated provider (Claude Code); **F** = verified with a fake/scripted provider (logic proven, provider behaviour not); **H** = needs a human at the keyboard — **not verified**; **–** = not verified.

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| A01 | Open desktop GUI, Vietnamese, no terminal | W (window + exe self-check), **H** (human) | `g*_screens/`, `tests/windows/test_packaged_exe.py` |
| A02 | Register local project, persists restart | W; native folder dialog **H** | `test_registry.py`, `test_main_window.py` |
| A03 | Ambiguous project name | W | `test_chat_g2.py::test_open_project_resolution` |
| A04 | Project folder missing | W | `test_registry.py`, GUI "Không tìm thấy thư mục dự án" |
| A05 | New product request → clarifying question | W (+ R intent classification) | `test_chat_g2.py`, G2 report |
| A06 | "Tôi không biết" → default + trade-off | W | same |
| A07 | No approval ⇒ no coding | W | `ScopeNotApproved`, `ApprovalRequired` tests |
| A08 | One provider only | R (Claude) | G3/G4 real runs |
| A09 | Provider missing/not authenticated | W | `test_settings_smoke.py`, probe statuses |
| A10 | Same CLI, 3 roles ⇒ 3 sessions | W | `test_state_and_store.py`, `test_manager_g3.py` |
| A11 | Same role, 2 tasks ⇒ different sessions | W | same |
| A12 | QA return ⇒ exact resume or fresh session | F (resume), W (fallback); **real exact resume –** | `test_manager_g3.py`; disabled for real providers until verified |
| A13 | Switch providers ⇒ handoff + new session | F | `test_quota_switches_provider_with_handoff_and_new_session` |
| A14 | Malformed JSON / nonzero exit | W | parser/adapter/manager tests; real Claude format R |
| A15 | Windows path spaces/Unicode + `.cmd` | W (fake CLI; no real npm `.cmd` CLI installed) | `test_launcher.py`, `test_unicode_and_space_path_full_write_workflow` |
| A16 | Shell metacharacters are data | W | `test_launcher.py`, `test_chat_g2.py` |
| A17 | Access to unrelated project | W | switch-confirmation test, project-scoped prompts |
| A18 | Prompt injection in README/source | F (fencing, QA-verdict parsing, rule-layer approval filter); not tried against a real model with a hostile repo | `test_untrusted_text_is_fenced…`, G2 real injection phrase caught by rules |
| A19 | Provider quota/timeout | F, W (timeouts, kill) | `test_launcher.py`, `test_manager_g3.py` |
| A20 | Plan cycle/missing dependency | W | 8 validator cases |
| A21 | Tests fail / QA rejects ⇒ bounded rework | W (real pytest) + F (QA verdicts); R (QA FAIL observed on a read-only proposal, G3) | `test_delivery_g4.py` |
| A22 | Destructive/paid action needs explicit approval | W: scope, re-run after crash, undo/revert, integration click; no deploy/spend/delete features exist | approvals tests |
| A23 | Crash during run | **W** (real hard kill of a process holding a RUNNING task) | `tests/windows/test_reliability.py` |
| A24 | New work order in another project | W | `test_history_and_work_orders_are_per_project` |
| A25 | Real coding task, verifiable tests | **R** (Claude fixed `calc.py`; pytest independent re-run) | G4 report |
| A26 | Packaged app, double-click | W (automated launch of `dist\AATPO\AATPO.exe`, no Python on PATH); **H** (real double-click) | `test_packaged_exe.py` |
| A27 | Final result screen | W | `test_results_gui.py`, `g4_screens/results.png` |
| A28 | No provider at all | W | GUI still works, execution blocked with message |
| A29 | Cancel/pause, UI responsive, child cleanup | W (process tree + Job Object kill-on-close with control experiment) | `test_launcher.py`, `test_reliability.py` |
| A30 | Logs without credentials | W | redaction tests, `errors.log` test |
| A31 | G0 Git init in approved root | W | `git log` (baseline `088c9c9`) |
| A32 | Git identity missing | W | `test_missing_commit_identity_blocks_then_user_supplied_identity_works` |
| A33 | Milestone branch + verified commit + SHA | W | every milestone report |
| A34 | Dirty repo preserved | W | G3/G4 tests |
| A35 | New project local Git | W | `test_new_project_inits_git_with_baseline` |
| A36 | Unversioned project needs consent | W | `test_unversioned_project_requires_consent_for_git` |
| A37 | Task branch + path-scoped commit + evidence link | W, R | G4 |
| A38 | QA fail / merge conflict ⇒ isolated, not DONE | W | `test_non_fast_forward_is_reported_not_forced` |
| A39 | ff-only integration | W, R | G4 |
| A40 | No push/force/rewrite without approval | W (allowlist + recorded-argv inspection); undo is a new revert commit after approval | `test_git_allowlist_blocks_…`, `test_history_links_commits…` |

## Spec section 12 — "Final done definition"
Items 1–10 and 12 have the evidence above **except the human-in-the-loop parts**; item 11 (packaged app runs by double-click) is verified by automated launch only.
**Therefore this is labelled: engineering-complete partial implementation — NOT an accepted complete MVP until a person completes the manual checklist in `docs/milestone_reports/G5.md`.**
