"""G4: real write workflow against disposable sample repos (real git, real pytest) driven by a scripted agent
that really edits files. Real-provider evidence is recorded separately in the milestone report."""
import asyncio
import subprocess
import sys

import pytest

from aatpo.agents.session_manager import ScopeNotApproved  # noqa: F401
from aatpo.cli.base import AgentRunResult
from aatpo.config import OfficeConfig
from aatpo.domain.models import TaskState as T, WorkOrderState as W
from aatpo.evidence import git_evidence
from aatpo.evidence.tests import CommandRejected, detect_command, validate_command
from aatpo.projects.git_service import GitError, NotFastForward
from aatpo.services import Services
from aatpo.settings import AppPaths
from tests.conftest import git as run_git
from tests.unit.test_manager_g3 import Script, approved, tasks_by_key

pytestmark = pytest.mark.unit
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
WRONG = "def add(a, b):\n    return a * b\n"


def go(c):
    return asyncio.run(c)


def say(svc, text):
    return go(svc.chat.handle(text))


def sample_repo(root, *, init=True, commit=True):
    root.mkdir(parents=True)
    (root / "calc.py").write_text(BUGGY, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_calc.py").write_text("from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    if init:
        run_git(root, "init", "-b", "main")
        if commit:
            run_git(root, "add", ".gitignore", "calc.py", "tests/test_calc.py")
            run_git(root, "commit", "-m", "initial sample")


class Agent:
    """Write-capable stand-in: `edits` is a list of per-attempt callables(root) for write runs; QA via verdicts."""

    def __init__(self, edits, verdicts=None):
        self.edits, self.verdicts, self.qa_prompts, self.dev_prompts = list(edits), list(verdicts or []), [], []
        self.script = Script(self._fn)

    def _fn(self, kind, req, sid, n):
        from pathlib import Path
        if "Kỹ sư kiểm thử" in req.prompt:
            self.qa_prompts.append(req.prompt)
            if self.verdicts:
                return AgentRunResult(ok=True, text=self.verdicts.pop(0))
            return None
        if req.write:
            self.dev_prompts.append(req.prompt)
            edit = self.edits.pop(0) if len(self.edits) > 1 else self.edits[0]
            edit(Path(req.project_root))
            return AgentRunResult(ok=True, text="Đã sửa theo yêu cầu.", provider_session_id=f"prov-session-{n:04d}")
        return None


def fix(root):
    (root / "calc.py").write_text(FIXED, encoding="utf-8")


def wrong(root):
    (root / "calc.py").write_text(WRONG, encoding="utf-8")


def world(tmp_path, agent, *, auto_history=True, test=True, git_repo=True, **cfg):
    root = tmp_path / "sample"
    sample_repo(root, init=git_repo)
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={"fake": agent.script}, write_mode=True)
    svc.manager.cfg = OfficeConfig(provider_preference=("fake",), **cfg)
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    p = svc.registry.register(root, "Máy tính", auto_history=auto_history and git_repo)
    if test:
        p = svc.registry.set_test_command(p.project_id, PYTEST)
    svc.registry.select(p.project_id)
    return svc, p, root


def start(svc, p):
    wo = approved(svc, p, "Sửa lỗi hàm cộng hai số")
    svc.manager.create_plan(wo.work_order_id)
    return wo, go(svc.manager.run_work_order(wo.work_order_id))


# ======================================================================================================
def test_real_fix_branch_commit_tests_qa_integration_report(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    base = run_git(root, "rev-parse", "main")
    wo, res = start(svc, p)
    assert res.outcome == "completed" and svc.store.get_work_order(wo.work_order_id).state == W.DELIVERED
    ts = tasks_by_key(svc, wo)
    assert all(t.state == T.DONE for t in ts.values())

    # real source change, committed on a task branch, then fast-forwarded into main
    assert (root / "calc.py").read_text() == FIXED
    br = svc.db.conn.execute("SELECT * FROM git_branches").fetchone()
    assert br["name"].startswith("task/WO-") and br["base_sha"] == base and br["task_id"] == ts["implement"].task_id
    ce = svc.db.conn.execute("SELECT * FROM git_commit_events WHERE status='committed'").fetchone()
    assert ce["task_id"] == ts["implement"].task_id and ce["parent_sha"] == base and ce["evidence_ref"]
    assert run_git(root, "rev-parse", br["name"]) == ce["sha"] == run_git(root, "rev-parse", "main")
    assert run_git(root, "branch", "--show-current") == "main" and run_git(root, "status", "--porcelain") == ""
    assert run_git(root, "log", "-1", "--format=%s", "main").endswith(f"[{ts['implement'].task_id}]")
    assert run_git(root, "show", "--name-only", "--format=", ce["sha"]).split() == ["calc.py"]   # only the changed file
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "integrated"
    assert svc.db.conn.execute("SELECT status FROM git_commit_events ORDER BY at DESC, rowid DESC LIMIT 1").fetchone()[0] == "integrated"

    # independently re-runnable evidence
    tr = svc.db.conn.execute("SELECT * FROM test_runs").fetchall()
    assert [r["status"] for r in tr] == ["passed", "passed"]              # per-task and final verification
    assert subprocess.run(PYTEST, cwd=root, capture_output=True).returncode == 0

    # QA saw the REAL diff and the REAL test output (fenced), and its PASS is linked to the commit
    qa = ag.qa_prompts[0]
    assert "-    return a - b" in qa and "+    return a + b" in qa and "1 passed" in qa
    rv = svc.db.conn.execute("SELECT * FROM reviews WHERE reviewer_task_id=?", (ts["review"].task_id,)).fetchone()
    assert rv["verdict"] == "pass" and rv["task_id"] == ts["implement"].task_id

    # no remote, no destructive/remote git ever issued
    assert run_git(root, "remote") == ""
    argvs = [r[0] for r in svc.db.conn.execute("SELECT argv FROM git_operations")]
    assert argvs and not any(a.split()[0] in ("push", "reset", "clean", "stash", "checkout", "rebase", "fetch", "remote", "pull")
                             for a in argvs)
    assert not any("--force" in a or "--hard" in a or " -f" in a for a in argvs)

    # report
    from aatpo.evidence import artifacts
    rep = artifacts.read(svc.db, artifacts.latest(svc.db, ts["review"].task_id, "report")["artifact_id"])
    for needle in ("# Báo cáo bàn giao", "Sửa lỗi hàm cộng hai số", "ĐẠT", "Đã tích hợp vào nhánh “main”", "calc.py", "không phải bản sao lưu",
                   "không độc lập hoàn toàn"):
        assert needle in rep, needle


def test_failing_tests_block_commit_then_rework_succeeds(tmp_path):
    ag = Agent([wrong, fix])
    svc, p, root = world(tmp_path, ag)
    wo, res = start(svc, p)
    assert res.outcome == "completed"
    t = tasks_by_key(svc, wo)["implement"]
    assert t.rework_count == 1
    # the failed attempt produced NO commit; exactly one commit (the good one) sits on the task branch
    assert svc.db.conn.execute("SELECT count(*) FROM git_commit_events WHERE status='committed'").fetchone()[0] == 1
    assert [r["status"] for r in svc.db.conn.execute("SELECT status FROM test_runs ORDER BY created_at, rowid")] == ["failed", "passed", "passed"]
    assert "Kiểm thử THẤT BẠI" in ag.dev_prompts[1] and "assert" in ag.dev_prompts[1]      # failure output fed to the rework
    assert (root / "calc.py").read_text() == FIXED


def test_qa_rejection_triggers_bounded_rework_on_same_branch(tmp_path):
    def improve(root):
        (root / "calc.py").write_text(FIXED + "\n# validated\n", encoding="utf-8")
    ag = Agent([fix, improve], verdicts=["VERDICT: FAIL\ncần thêm chú thích", "VERDICT: PASS\nđạt"])
    svc, p, root = world(tmp_path, ag)
    wo, res = start(svc, p)
    assert res.outcome == "completed"
    br = svc.db.conn.execute("SELECT count(*) FROM git_branches").fetchone()[0]
    commits = svc.db.conn.execute("SELECT count(*) FROM git_commit_events WHERE status='committed'").fetchone()[0]
    assert br == 1 and commits == 2                                           # same task branch, second commit
    assert "cần thêm chú thích" in ag.dev_prompts[1]
    assert run_git(root, "rev-list", "--count", "main") == "3"                # initial + 2 task commits (fast-forward kept history)


def test_always_wrong_is_bounded_never_delivered_never_integrated(tmp_path):
    ag = Agent([wrong])
    svc, p, root = world(tmp_path, ag, max_rework_cycles_per_task=2)
    base = run_git(root, "rev-parse", "main")
    wo, res = start(svc, p)
    t = tasks_by_key(svc, wo)["implement"]
    assert res.outcome == "blocked" and t.state == T.FAILED and t.rework_count == 3
    assert len(ag.dev_prompts) == 3
    assert svc.store.get_work_order(wo.work_order_id).state == W.BLOCKED
    assert svc.db.conn.execute("SELECT count(*) FROM git_commit_events").fetchone()[0] == 0     # nothing committed
    assert run_git(root, "rev-parse", "main") == base                          # integration branch untouched
    assert svc.db.conn.execute("SELECT count(*) FROM artifacts WHERE kind='report'").fetchone()[0] == 0   # no success report
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "none"


def test_no_changes_is_not_progress(tmp_path):
    ag = Agent([lambda root: None])
    svc, p, root = world(tmp_path, ag, max_rework_cycles_per_task=0)
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "Không có tệp nào được thay đổi" in res.message


def test_secret_files_and_secret_content_are_never_committed(tmp_path):
    def sneaky(root):
        fix(root)
        (root / ".env").write_text("API_KEY=abcdefghijklmnop123456\n", encoding="utf-8")
    ag = Agent([sneaky], )
    svc, p, root = world(tmp_path, ag, max_rework_cycles_per_task=0)
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and ".env" in res.message
    assert svc.db.conn.execute("SELECT count(*) FROM git_commit_events").fetchone()[0] == 0
    assert run_git(root, "diff", "--cached", "--name-only") == ""            # nothing staged either

    def leak(root):
        (root / "calc.py").write_text(FIXED + "KEY = 'sk-abcdefghijklmnopqrstuvwxyz123456'\n", encoding="utf-8")
    ag2 = Agent([leak])
    svc2, p2, root2 = world(tmp_path / "b", ag2, max_rework_cycles_per_task=0)
    wo2, res2 = start(svc2, p2)
    assert res2.outcome == "blocked" and "khóa/mật khẩu" in res2.message and "sk-abcdefgh" not in res2.message
    assert run_git(root2, "diff", "--cached", "--name-only") == "" and svc2.db.conn.execute("SELECT count(*) FROM git_commit_events").fetchone()[0] == 0


def test_path_policy_and_secret_scanner_units():
    assert git_evidence.forbidden_paths([".env", "src/.env.local", "a/b.pem", ".git/config", "id_rsa", "../x", "ok.py", "sub/credentials.json"]) \
        == [".env", "src/.env.local", "a/b.pem", ".git/config", "id_rsa", "../x", "sub/credentials.json"]
    d = "+++ b/a.py\n+x = 1\n+TOKEN = 'abcdefghijklmnopqrstuvwxyz'\n-old = 'sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaa'\n"
    assert git_evidence.scan_added_lines(d) == ["a.py: dòng có vẻ chứa khóa/mật khẩu"]     # removed lines ignored


# ===== preconditions (A32, A34, A36) ==================================================================================
def test_missing_commit_identity_blocks_then_user_supplied_identity_works(tmp_path, monkeypatch):
    empty = tmp_path / "empty.cfg"
    empty.write_text("")
    ag = Agent([fix])
    root = tmp_path / "sample"
    sample_repo(root, init=False)
    run_git(root, "init", "-b", "main")
    run_git(root, "-c", "user.name=T", "-c", "user.email=t@e.x", "add", ".")
    run_git(root, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-m", "init")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={"fake": ag.script}, write_mode=True)
    svc.manager.cfg = OfficeConfig(provider_preference=("fake",))
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    p = svc.registry.register(root, "S", auto_history=True)
    svc.registry.select(p.project_id)
    svc.registry.set_test_command(p.project_id, PYTEST)
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "tên và email" in res.message and ag.dev_prompts == []   # agent never invoked
    svc.git.set_local_identity(root, "Chủ dự án", "owner@example.invalid")                        # the user typed it
    assert run_git(root, "config", "--local", "user.name") == "Chủ dự án"
    svc.manager.resume(wo.work_order_id)
    assert go(svc.manager.run_work_order(wo.work_order_id)).outcome == "completed"
    assert "Chủ dự án" in run_git(root, "log", "-1", "--format=%an", "main")
    with pytest.raises(GitError):
        svc.git.set_local_identity(root, "x", "not-an-email")


def test_project_without_version_history_is_not_edited(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag, git_repo=False, test=False)
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "lịch sử phiên bản" in res.message
    assert (root / "calc.py").read_text() == BUGGY and ag.dev_prompts == [] and not (root / ".git").exists()


def test_existing_edits_are_preserved_and_block_the_task(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    (root / "calc.py").write_text(BUGGY + "# my own unsaved note\n", encoding="utf-8")
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "thay đổi chưa lưu" in res.message
    assert "my own unsaved note" in (root / "calc.py").read_text() and ag.dev_prompts == []
    assert run_git(root, "stash", "list") == "" and run_git(root, "branch", "--show-current") == "main"


# ===== integration safety (A38/A39/A40) ================================================================================
def test_non_fast_forward_is_reported_not_forced(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    orig_integrate = svc.manager.flow.integrate

    def main_moves_first(wo_id, *, explicit):          # someone commits on main while the task branch was being built
        run_git(root, "switch", "main")
        (root / "other.txt").write_text("someone else\n")
        run_git(root, "add", "other.txt")
        run_git(root, "commit", "-m", "work on main")
        return orig_integrate(wo_id, explicit=explicit)
    svc.manager.flow.integrate = main_moves_first
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "xung đột" in res.message
    w = svc.store.get_work_order(wo.work_order_id)
    assert w.state == W.PACKAGING and w.integration_status == "conflict"       # NOT delivered
    assert run_git(root, "log", "-1", "--format=%s", "main") == "work on main"  # main kept its own history
    assert run_git(root, "rev-list", "--merges", "--count", "main") == "0"      # no merge commit, no rebase
    assert svc.db.conn.execute("SELECT count(*) FROM artifacts WHERE kind='report'").fetchone()[0] == 0
    # retrying while still diverged stays a conflict and destroys nothing
    svc.manager.flow.integrate = orig_integrate
    assert svc.manager.integrate_now(wo.work_order_id).outcome == "blocked"
    assert "calc.py" in run_git(root, "show", "--name-only", "--format=", svc.db.conn.execute("SELECT sha FROM git_commit_events "
                                "WHERE status='committed'").fetchone()[0])


def test_ready_to_integrate_when_auto_history_is_off_then_explicit_click(tmp_path):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag, auto_history=False)
    wo, res = start(svc, p)
    w = svc.store.get_work_order(wo.work_order_id)
    assert res.outcome == "completed" and w.state == W.DELIVERED and w.integration_status == "ready"
    assert run_git(root, "rev-parse", "main") != run_git(root, "rev-parse", "HEAD")          # main untouched
    assert "Sẵn sàng tích hợp" in w.integration_note
    out = svc.manager.integrate_now(wo.work_order_id)
    assert out.outcome == "completed" and svc.store.get_work_order(wo.work_order_id).integration_status == "integrated"
    assert run_git(root, "rev-parse", "main") == run_git(root, "rev-parse", "HEAD") and run_git(root, "branch", "--show-current") == "main"


def test_final_verification_failure_blocks_delivery(tmp_path, monkeypatch):
    ag = Agent([fix])
    svc, p, root = world(tmp_path, ag)
    import aatpo.evidence.tests as et
    real = et.run_tests
    calls = {"n": 0}

    async def flaky(*a, **k):
        calls["n"] += 1
        r = await real(*a, **k)
        return r if calls["n"] == 1 else et.TestResult("failed", 1, 1, "final regression", r.test_run_id)
    monkeypatch.setattr(et, "run_tests", flaky)
    monkeypatch.setattr("aatpo.office.write_flow.run_tests", flaky)
    wo, res = start(svc, p)
    assert res.outcome == "blocked" and "KHÔNG đạt" in res.message
    assert svc.store.get_work_order(wo.work_order_id).state == W.BLOCKED
    assert svc.db.conn.execute("SELECT count(*) FROM artifacts WHERE kind='report'").fetchone()[0] == 0
    assert run_git(root, "rev-parse", "main") != run_git(root, "rev-parse", "HEAD")           # nothing integrated


def test_git_service_refuses_unsafe_refs_and_non_ff(tmp_path):
    root = tmp_path / "r"
    sample_repo(root)
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={})
    g = svc.git
    for bad in ("--abort", "x y", "-D", "a;b", ""):
        with pytest.raises(GitError):
            g.merge_ff_only(root, bad)
    run_git(root, "switch", "-c", "task/a")
    (root / "x.txt").write_text("1")
    run_git(root, "add", "x.txt")
    run_git(root, "commit", "-m", "a")
    run_git(root, "switch", "main")
    (root / "y.txt").write_text("2")
    run_git(root, "add", "y.txt")
    run_git(root, "commit", "-m", "m")
    head = run_git(root, "rev-parse", "main")
    with pytest.raises(NotFastForward):
        g.merge_ff_only(root, "task/a")
    assert run_git(root, "rev-parse", "main") == head and run_git(root, "status", "--porcelain") == ""
    with pytest.raises(GitError):
        g.create_task_branch(root, "feature/x")                   # outside the task/ namespace
    with pytest.raises(GitError):
        g.diff_range(root, "HEAD", "--output=x")                  # only hex SHAs
    svc.close()


# ===== test command policy + report for read-only mode ====================================================================
def test_test_command_policy(tmp_path):
    for bad in (["rm", "-rf", "/"], ["powershell", "-c", "x"], ["cmd", "/c", "dir"], [], [""], ["python", "a\nb"], ["bash", "x"]):
        with pytest.raises(CommandRejected):
            validate_command(bad)
    assert validate_command(["python", "-m", "pytest"]) and validate_command(["C:/x/Python313/python.exe", "-m", "pytest"]) \
        and validate_command(["npm", "test"])
    (tmp_path / "tests").mkdir()
    assert detect_command(tmp_path)[1:3] == ["-m", "pytest"] and detect_command(tmp_path / "tests") is None
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={})
    d = tmp_path / "pp"
    d.mkdir()
    pr = svc.registry.register(d, "P", auto_history=False)
    with pytest.raises(CommandRejected):
        svc.registry.set_test_command(pr.project_id, ["curl", "http://x"])
    assert svc.registry.set_test_command(pr.project_id, ["npm", "test"]).test_command == ["npm", "test"]
    assert svc.registry.set_test_command(pr.project_id, None).test_command is None
    svc.close()


def test_read_only_delivery_report_is_honest(tmp_path):
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={"fake": Script()})   # write_mode False
    svc.manager.cfg = OfficeConfig(provider_preference=("fake",))
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
    d = tmp_path / "p"
    d.mkdir()
    p = svc.registry.register(d, "P", auto_history=False)
    svc.registry.select(p.project_id)
    wo = approved(svc, p, "Sửa lỗi đăng nhập")
    svc.manager.create_plan(wo.work_order_id)
    assert go(svc.manager.run_work_order(wo.work_order_id)).outcome == "completed"
    from aatpo.evidence import artifacts
    last = svc.store.list_work_order_tasks(wo.work_order_id)[-1]
    rep = artifacts.read(svc.db, artifacts.latest(svc.db, last.task_id, "report")["artifact_id"])
    assert "chế độ chỉ đọc" in rep and "chưa có tệp nào bị sửa" in rep and "Chưa có lệnh kiểm thử tự động" in rep
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "not_applicable"


def test_detect_command_in_packaged_exe_never_suggests_the_exe_itself(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\AATPO\AATPO.exe")
    cmd = detect_command(tmp_path)
    assert "AATPO" not in cmd[0] and cmd[1:3] == ["-m", "pytest"]
    validate_command(cmd)                       # and the suggestion itself is acceptable to the policy
