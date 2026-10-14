"""G5 core: internal-error recovery, backups/restore, git audit, metrics, history + reviewed undo, subfolder projects,
Unicode paths, old-provider detection. Real git/pytest where it matters."""
import asyncio
import sqlite3
import subprocess
import sys

import pytest

from aatpo.cli.claude_adapter import ClaudeAdapter
from aatpo.config import OfficeConfig
from aatpo.db import backup as bk
from aatpo.domain.models import TaskState as T, WorkOrderState as W
from aatpo.office.approvals import ApprovalError
from aatpo.office.audit import audit_git
from aatpo.office.metrics import describe, provider_stats
from aatpo.projects.history import friendly, history_rows, propose_undo
from aatpo.services import Services
from aatpo.settings import AppPaths
from tests.conftest import git as run_git
from tests.unit.test_delivery_g4 import BUGGY, FIXED, PYTEST, Agent, fix, sample_repo, start, wrong, world
from tests.unit.test_manager_g3 import Script, approved, tasks_by_key

from pathlib import Path

FAKE = Path(__file__).parents[1] / "fixtures" / "fake_cli.py"
pytestmark = pytest.mark.unit


def go(c):
    return asyncio.run(c)


def say(svc, text):
    return go(svc.chat.handle(text))


# ===== internal errors never leave half-done work ==========================================================
def test_unexpected_exception_stops_work_safely_logs_traceback_and_recovers(tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]))
    wo = approved(svc, p, "Sửa lỗi hàm cộng hai số")
    svc.manager.create_plan(wo.work_order_id)
    real = svc.manager.flow.collect

    async def boom(*a, **k):
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
    monkeypatch.setattr(svc.manager.flow, "collect", boom)
    res = go(svc.manager.run_work_order(wo.work_order_id))             # does NOT raise
    assert res.outcome == "blocked" and "lỗi nội bộ" in res.message and "IntegrityError" in res.message
    assert svc.store.get_work_order(wo.work_order_id).state == W.BLOCKED
    t = tasks_by_key(svc, wo)["implement"]
    assert t.state in (T.REVIEW, T.UNKNOWN_AFTER_CRASH, T.OUTPUT_READY, T.READY)       # never left CLAIMED/RUNNING
    log = (svc.paths.home / "logs" / "errors.log").read_text(encoding="utf-8")
    assert "Traceback" in log and "FOREIGN KEY constraint failed" in log and "work order" in log
    assert svc.store.events("internal_error")
    assert svc.db.conn.execute("SELECT count(*) FROM resource_locks").fetchone()[0] <= 1


def test_rerun_decision_releases_the_uncertain_tasks_lock(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    wo = approved(svc, p, "Sửa lỗi hàm cộng hai số")
    svc.manager.create_plan(wo.work_order_id)
    t = tasks_by_key(svc, wo)["implement"]
    for to in (T.READY, T.CLAIMED, T.RUNNING):
        t = svc.store.transition_task(t.task_id, to, svc.store.get_task(t.task_id).version)
    svc.manager._lock(p.project_id, t.task_id)                                 # the crashed run held the repo lock
    svc.store.reconcile_after_restart()
    svc.manager.reconcile_after_restart()
    assert svc.db.conn.execute("SELECT count(*) FROM resource_locks").fetchone()[0] == 1       # kept while uncertain
    svc.approvals.decide(svc.approvals.pending(p.project_id)[0].approval_id, True, "rerun")
    assert svc.db.conn.execute("SELECT count(*) FROM resource_locks").fetchone()[0] == 0        # released on the decision
    assert go(svc.manager.run_work_order(wo.work_order_id)).outcome == "completed"             # and the task can run again


def test_background_job_exception_is_logged(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from aatpo.gui.bridges.background_jobs import BackgroundJobs
    app = QApplication.instance() or QApplication([])
    log = tmp_path / "logs" / "errors.log"
    jobs = BackgroundJobs(log)
    got = []
    jobs.finished.connect(lambda k, r, e: got.append((k, e)))

    async def bad():
        raise RuntimeError("kaboom api_key=sk-abcdefghijklmnopqrstuvwxyz123456")
    jobs.submit("run:WO-1", bad)
    import time
    end = time.time() + 5
    while not got and time.time() < end:
        app.processEvents()
        time.sleep(0.01)
    jobs.shutdown()
    text = log.read_text(encoding="utf-8")
    assert got and "kaboom" in text and "Traceback" in text and "sk-abcdefghijklmnopqrstuvwxyz123456" not in text


# ===== project that is a sub-folder of a repository ==================================================================
def test_subfolder_project_commits_only_inside_its_folder(tmp_path):
    top = tmp_path / "top"
    sample_repo(top)
    sub = top / "app"
    sub.mkdir()
    (sub / "calc.py").write_text(BUGGY, encoding="utf-8")
    run_git(top, "add", "app/calc.py")
    run_git(top, "commit", "-m", "add app")
    ag = Agent([lambda r: (r / "calc.py").write_text(FIXED, encoding="utf-8")])
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={"fake": ag.script}, write_mode=True)
    svc.manager.cfg = OfficeConfig(provider_preference=("fake",))
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    p = svc.registry.register(sub, "App", auto_history=True)
    svc.registry.select(p.project_id)
    wo, res = start(svc, p)
    assert res.outcome == "completed"
    assert run_git(top, "show", "--name-only", "--format=", run_git(top, "rev-parse", "main")).split() == ["app/calc.py"]

    def escape(r):                                     # an agent that edits OUTSIDE its project folder
        (r.parent / "x.txt").write_text("outside")
    ag2 = Agent([escape])
    svc2 = Services.create(AppPaths(tmp_path / "home2"), adapters={"fake": ag2.script}, write_mode=True)
    svc2.manager.cfg = OfficeConfig(provider_preference=("fake",), max_rework_cycles_per_task=0)
    with svc2.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    p2 = svc2.registry.register(sub, "App2", auto_history=True)
    svc2.registry.select(p2.project_id)
    wo2, res2 = start(svc2, p2)
    assert res2.outcome == "blocked" and "NGOÀI thư mục dự án" in res2.message
    assert run_git(top, "diff", "--cached", "--name-only") == ""


# ===== Unicode / spaces paths end to end ===============================================================================
def test_unicode_and_space_path_full_write_workflow(tmp_path):
    ag = Agent([fix])
    root = tmp_path / "Dự án có dấu & khoảng trắng"
    sample_repo(root)
    svc = Services.create(AppPaths(tmp_path / "Dữ liệu AATPO"), adapters={"fake": ag.script}, write_mode=True)
    svc.manager.cfg = OfficeConfig(provider_preference=("fake",))
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    p = svc.registry.register(root, "Máy tính", auto_history=True)
    svc.registry.set_test_command(p.project_id, PYTEST)
    svc.registry.select(p.project_id)
    wo, res = start(svc, svc.registry.get(p.project_id))
    assert res.outcome == "completed" and (root / "calc.py").read_text() == FIXED
    assert run_git(root, "branch", "--show-current") == "main"
    assert [r["status"] for r in svc.db.conn.execute("SELECT status FROM test_runs")] == ["passed", "passed"]


# ===== backups / restore ===============================================================================================
def test_backup_is_verified_daily_pruned_and_restorable(tmp_path):
    home = tmp_path / "home"
    svc = Services.create(AppPaths(home), adapters={})
    d = tmp_path / "a"
    d.mkdir()
    svc.registry.register(d, "A", auto_history=False)
    daily = sorted((home / "backups").glob("office-2*.db"))
    assert len(daily) == 1                                                       # taken at startup, once per day
    assert bk.backup_if_due(svc.db, home / "backups") is None                   # not twice the same day
    for i in range(10):                                                          # fabricate old dailies -> pruned to 7
        (home / "backups" / f"office-2020010{i}.db").write_bytes(daily[0].read_bytes())
    bk.backup_if_due(svc.db, home / "backups")
    assert len(list((home / "backups").glob("office-2*.db"))) == 7
    manual = bk.backup_now(svc.db, home / "backups" / "office-manual-test.db")
    d2 = tmp_path / "b"
    d2.mkdir()
    svc.registry.register(d2, "B", auto_history=False)                           # change AFTER the backup
    bk.schedule_restore(home / "config", manual)
    svc.close()
    svc2 = Services.create(AppPaths(home), adapters={})                          # next start applies the restore
    assert [p.display_name for p in svc2.registry.list()] == ["A"] and "Đã khôi phục" in svc2.restore_note
    kept = next((home / "backups").glob("before-restore-*.db"))                  # pre-restore data is never discarded
    c = sqlite3.connect(kept)
    assert [r[0] for r in c.execute("SELECT display_name FROM projects ORDER BY display_name")] == ["A", "B"]
    c.close()
    assert not (home / "config" / "restore_pending.txt").exists()
    svc2.close()


def test_bad_backups_are_refused_not_applied(tmp_path):
    home = tmp_path / "home"
    svc = Services.create(AppPaths(home), adapters={})
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database at all" * 100)
    with pytest.raises(bk.BackupError):
        bk.schedule_restore(home / "config", junk)
    newer = tmp_path / "newer.db"
    c = sqlite3.connect(newer)
    c.execute("CREATE TABLE projects(x)")
    c.execute("PRAGMA user_version=99")
    c.commit()
    c.close()
    with pytest.raises(bk.BackupError):
        bk.schedule_restore(home / "config", newer)
    assert not (home / "config" / "restore_pending.txt").exists()
    # a marker that was valid when written but whose file later vanished: reported, DB untouched
    (home / "config").mkdir(exist_ok=True)
    (home / "config" / "restore_pending.txt").write_text(str(tmp_path / "gone.db"), encoding="utf-8")
    svc.close()
    svc2 = Services.create(AppPaths(home), adapters={})
    assert svc2.restore_note.startswith("Không khôi phục được") and svc2.db.conn.execute("PRAGMA user_version").fetchone()[0] == 5
    svc2.close()


# ===== git audit ========================================================================================================
def test_git_audit_matches_then_detects_external_tampering(tmp_path):
    svc, p, root = world(tmp_path, Agent([fix]))
    wo, res = start(svc, p)
    assert res.outcome == "completed" and audit_git(svc) == []
    br = svc.db.conn.execute("SELECT name FROM git_branches").fetchone()[0]
    run_git(root, "branch", "-D", br)                                            # someone deletes the task branch
    run_git(root, "reset", "--hard", "HEAD~1")                                   # ...and rewinds main outside AATPO
    kinds = {d.kind for d in audit_git(svc)}
    assert {"branch_missing", "integration_lost"} <= kinds
    assert svc.store.events("audit.mismatch")
    assert svc.store.get_work_order(wo.work_order_id).state == W.DELIVERED       # audit reports, it never edits state


# ===== metrics ===========================================================================================================
def test_metrics_are_measured_counts_only(tmp_path):
    from aatpo.cli.base import AgentRunResult
    seq = iter([AgentRunResult(ok=False, error="boom"), None])

    def fn(kind, req, sid, n):
        if "Kỹ sư kiểm thử" not in req.prompt:
            return next(seq)
    svc, p, root = world(tmp_path / "m", Agent([fix]))
    svc.manager.sessions.adapters["fake"].fn = fn if False else svc.manager.sessions.adapters["fake"].fn
    wo, res = start(svc, p)
    st = provider_stats(svc.db)["fake"]
    assert st["runs"] == 2 and st["SUCCEEDED"] == 2 and st["success_rate"] == 100 and st["median_seconds"] is not None
    text = describe(provider_stats(svc.db))
    assert "2 lần chạy" in text and "100%" in text and "giây" in text and "đồng" not in text and "$" not in text
    assert describe({}) == "Chưa có lần chạy nào được ghi nhận."


# ===== version history + reviewed undo (A40 family) ============================================================================
def test_history_links_commits_to_work_and_undo_is_a_reviewed_new_commit(tmp_path):
    svc, p, root = world(tmp_path, Agent([fix]))
    wo, res = start(svc, p)
    rows = history_rows(svc, p)
    assert [r["subject"][:3] for r in rows][-1] == "ini" and rows[0]["ledger"] and rows[0]["undoable"]
    assert rows[0]["wo_title"].startswith("Sửa lỗi") and not rows[-1]["ledger"]
    assert friendly(rows[0]).startswith("Đã lưu phiên bản bởi AATPO") and friendly(rows[-1]).startswith("Phiên bản của bạn")
    before = run_git(root, "rev-parse", "main")
    reply = say(svc, "Hoàn tác thay đổi vừa rồi")                                # chat 'undo' => proposal only
    assert "chưa hoàn tác ngay" in reply.text and run_git(root, "rev-parse", "main") == before
    assert (root / "calc.py").read_text() == FIXED
    ap = svc.approvals.pending(p.project_id)[0]
    assert ap.kind == "revert" and "đảo ngược" in ap.consequences and "calc.py" in ap.consequences
    with pytest.raises(ApprovalError):
        svc.approvals.request_revert(p.project_id, wo.work_order_id, ap.options[0]["sha"], "x", 0, [])   # no duplicates
    svc.approvals.decide(ap.approval_id, True, "revert")
    assert (root / "calc.py").read_text() == BUGGY                               # change undone...
    assert run_git(root, "rev-list", "--count", "main") == "3"                   # ...by a NEW commit; nothing rewritten
    assert run_git(root, "merge-base", "--is-ancestor", before, "main") == ""
    assert run_git(root, "status", "--porcelain") == ""
    assert svc.db.conn.execute("SELECT count(*) FROM git_commit_events WHERE status='reverted'").fetchone()[0] == 1
    argvs = [r[0] for r in svc.db.conn.execute("SELECT argv FROM git_operations")]
    assert not any(a.startswith(("reset", "push", "clean", "stash")) or "--hard" in a for a in argvs)


def test_undo_refuses_dirty_tree_foreign_commits_and_rejects_cleanly(tmp_path):
    svc, p, root = world(tmp_path, Agent([fix]))
    start(svc, p)
    rows = history_rows(svc, p)
    with pytest.raises(ValueError):
        propose_undo(svc, p, rows[-1]["sha"])                                    # the user's own initial commit: not undoable here
    propose_undo(svc, p, rows[0]["sha"])
    ap = svc.approvals.pending(p.project_id)[0]
    (root / "calc.py").write_text(FIXED + "# my edit\n")                         # user has unsaved edits
    with pytest.raises(ApprovalError) as e:
        svc.approvals.decide(ap.approval_id, True, "revert")
    assert "thay đổi chưa lưu" in str(e.value) and "# my edit" in (root / "calc.py").read_text()
    assert svc.approvals.get(ap.approval_id).status == "pending"                 # nothing consumed
    run_git(root, "checkout", "--", "calc.py")
    svc.approvals.decide(ap.approval_id, False)                                   # "No" leaves history untouched
    assert (root / "calc.py").read_text() == FIXED and svc.approvals.get(ap.approval_id).status == "rejected"


def test_undo_conflict_is_aborted_cleanly(tmp_path):
    svc, p, root = world(tmp_path, Agent([fix]))
    start(svc, p)
    rows = history_rows(svc, p)
    (root / "calc.py").write_text("def add(a, b):\n    return b + a\n")           # a LATER commit touches the same line
    run_git(root, "commit", "-am", "later change by the owner")
    head = run_git(root, "rev-parse", "HEAD")
    propose_undo(svc, p, rows[0]["sha"])
    ap = svc.approvals.pending(p.project_id)[0]
    assert "Đã có 1 phiên bản được lưu sau đó" in ap.consequences
    with pytest.raises(ApprovalError) as e:
        svc.approvals.decide(ap.approval_id, True, "revert")
    assert "Không có gì bị thay đổi" in str(e.value)
    assert run_git(root, "rev-parse", "HEAD") == head and run_git(root, "status", "--porcelain") == ""   # revert --abort worked
    assert svc.approvals.get(ap.approval_id).status == "pending"


# ===== other preconditions ================================================================================================
def test_stuck_git_lock_blocks_without_deleting_it(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    lock = root / ".git" / "index.lock"
    lock.write_text("")
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "index.lock" in res.message and lock.exists() and ag.dev_prompts == []
    lock.unlink()
    svc.manager.resume(wo.work_order_id)
    assert go(svc.manager.run_work_order(wo.work_order_id)).outcome == "completed"


def test_incompatible_old_cli_is_reported_not_used(tmp_path):
    a = ClaudeAdapter(command=[sys.executable, str(FAKE), "probe_old"])
    cap = go(a.probe())
    assert cap.status == "unsupported_version" and cap.version == "0.0.1" and not a.supports_exact_resume
    from aatpo.cli.probe import STATUS_VI
    from aatpo.office import cli_router
    assert STATUS_VI["unsupported_version"] == "Không tương thích"
    assert cli_router.route(("claude",), {"claude": (cap.status, cap.version)}) is None


def test_concurrency_stays_at_one_by_default():
    assert OfficeConfig().concurrency == 1


def test_error_before_any_process_started_leaves_nothing_uncertain(tmp_path, monkeypatch):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    wo = approved(svc, p, "Sửa lỗi hàm cộng hai số")
    svc.manager.create_plan(wo.work_order_id)
    import aatpo.office.manager as m

    def boom(*a, **k):
        raise FileNotFoundError("role profile missing")
    monkeypatch.setattr(m, "build_task_prompt", boom)           # fails after RUNNING, before any run exists
    res = go(svc.manager.run_work_order(wo.work_order_id))
    assert res.outcome == "blocked" and "FileNotFoundError" in res.message
    assert tasks_by_key(svc, wo)["implement"].state == T.READY and svc.approvals.pending() == []     # no needless approval
    assert svc.db.conn.execute("SELECT count(*) FROM process_runs").fetchone()[0] == 0
    monkeypatch.undo()
    svc.manager.resume(wo.work_order_id)
    assert go(svc.manager.run_work_order(wo.work_order_id)).outcome == "completed"
