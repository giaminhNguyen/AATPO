"""Write-capable task flow (G4): preflight, collecting + checking what the agent changed, tests, task commit,
evidence for QA, and safe local fast-forward integration. Every Git action goes through GitService's
allowlisted, fixed-shape commands. Nothing here pushes, rewrites history, stashes, resets the tree or forces."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aatpo.domain.models import Task, WorkOrder, new_id, utcnow
from aatpo.evidence import artifacts, git_evidence
from aatpo.evidence.tests import CommandRejected, run_tests
from aatpo.projects.git_policies import prepare_task_branch
from aatpo.projects.git_service import GitError, MissingIdentity, NotFastForward


@dataclass(frozen=True)
class Block:
    reason: str
    code: str = "blocked"


@dataclass(frozen=True)
class Collected:
    passed: bool
    finding: str | None = None
    commit_sha: str | None = None


class WriteFlow:
    def __init__(self, manager):
        self.m = manager
        self.git, self.db, self.store = manager.git, manager.db, manager.store

    # ---- before the run --------------------------------------------------------------------------------
    def branch_row(self, task_id: str):
        with self.db.lock:
            return self.db.conn.execute("SELECT * FROM git_branches WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                        (task_id,)).fetchone()

    def preflight(self, wo: WorkOrder, project, task: Task) -> Block | None:
        root = Path(project.root_path)
        if not self.git.available:
            return Block("Chưa cài Git nên chưa thể ghi thay đổi một cách an toàn.", "no_git")
        info = self.git.detect(root)
        if not info.is_repo:
            return Block("Dự án chưa có lịch sử phiên bản nên AATPO chưa dám sửa tệp. Hãy bật “lưu lịch sử phiên bản” cho dự án.", "no_repo")
        if not info.has_commits:
            return Block("Kho lịch sử phiên bản chưa có phiên bản nào. Hãy lưu một phiên bản đầu tiên rồi bấm Tiếp tục.", "no_commits")
        if not self.git.identity(root):
            return Block("Chưa có tên và email để ghi lịch sử phiên bản. Hãy thiết lập ở mục Dự án rồi bấm Tiếp tục.", "no_identity")
        existing = self.branch_row(task.task_id)
        if existing:   # rework: must still be on this task's own branch; edits left by a failed attempt are fine
            if self.git.current_branch(root) != existing["name"]:
                return Block(f"Dự án đang ở nhánh khác với nhánh của công việc ({existing['name']}). Hãy chuyển lại rồi bấm Tiếp tục.", "wrong_branch")
            return None
        br = prepare_task_branch(self.git, self.db, project, wo, task)
        if br.status == "blocked":
            if br.reason == "dirty_repo":
                return Block("Thư mục dự án có thay đổi chưa lưu. Hãy lưu hoặc hoàn tác chúng rồi bấm Tiếp tục "
                             "(AATPO không tự cất hay xóa thay đổi của bạn).", "dirty_repo")
            return Block(f"Git: {br.reason}", "git")
        if br.status == "skipped":
            return Block(f"Không thể tạo nhánh làm việc ({br.reason}).", br.reason or "git")
        return None

    # ---- after the run -----------------------------------------------------------------------------------
    async def collect(self, wo: WorkOrder, project, task: Task) -> Collected:
        root = Path(project.root_path)
        try:
            changed = self.git.changed_paths(root)
        except GitError as e:
            return Collected(False, f"Không đọc được trạng thái Git: {e}")
        if not changed:
            return Collected(False, "Không có tệp nào được thay đổi, nên chưa thể coi là đã thực hiện công việc.")
        bad = git_evidence.forbidden_paths(changed)
        if bad:
            return Collected(False, "Trợ lý đã đụng tới tệp không được phép (khóa/bí mật/.git): " + ", ".join(bad[:5])
                             + ". Các tệp này KHÔNG được lưu; hãy hoàn tác chúng.")
        try:
            self.git.stage_paths(root, changed)             # explicit paths only
            hits = git_evidence.scan_added_lines(self.git.staged_diff(root))
            if hits:
                self.git.unstage_paths(root, changed)
                return Collected(False, "Phát hiện nội dung có vẻ là khóa/mật khẩu trong thay đổi (" + "; ".join(hits[:3])
                                 + "). Thay đổi chưa được lưu; hãy bỏ nội dung nhạy cảm.")
            chk = self.git.check_staged(root)
            if "leftover conflict marker" in chk:
                self.git.unstage_paths(root, changed)
                return Collected(False, "Còn sót dấu hiệu xung đột (conflict marker) trong thay đổi.")
            test = None
            if project.test_command:
                test = await run_tests(self.db, self.m.root, project_id=project.project_id, work_order_id=wo.work_order_id,
                                       task_id=task.task_id, argv=project.test_command, cwd=project.root_path,
                                       timeout=self.m.cfg.run_timeout_seconds)
                if not test.ok:
                    self.git.unstage_paths(root, changed)    # keep the edits for the rework, just do not commit them
                    tail = test.output[-1500:]
                    return Collected(False, f"Kiểm thử THẤT BẠI ({test.status}, mã {test.exit_code}). Thay đổi chưa được lưu.\n{tail}")
            kind = "feat" if wo.kind == "product" else "fix"
            sha = self.git.commit_staged(root, f"{kind}: {task.title[:60]} [{task.task_id}]")
        except MissingIdentity as e:
            return Collected(False, str(e))
        except CommandRejected as e:
            self.git.unstage_paths(root, changed)
            return Collected(False, f"Lệnh kiểm thử không hợp lệ: {e}")
        except GitError as e:
            return Collected(False, f"Git báo lỗi khi lưu thay đổi: {str(e)[:200]}")
        br = self.branch_row(task.task_id)
        parent = self.git.parent_sha(root, sha)   # git calls are journalled in their own transaction: keep them outside ours
        with self.db.tx() as c:
            c.execute("INSERT INTO git_commit_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (new_id("GCE"), br["repo_id"], br["name"], sha, parent, task.task_id,
                       test.test_run_id if test else None, "git config (người dùng)", "committed", utcnow()))
        try:
            diff = self.git.diff_range(root, br["base_sha"], sha)
            artifacts.save_text(self.db, self.m.root, project_id=wo.project_id, work_order_id=wo.work_order_id,
                                task_id=task.task_id, run_id=new_id("DIFF"), text=diff or "(không có khác biệt)", kind="diff")
        except GitError:
            pass
        return Collected(True, None, sha)

    # ---- evidence for the QA gate ----------------------------------------------------------------------------
    def evidence_ok(self, task: Task, project) -> tuple[bool, str]:
        """Write-task evidence = a commit that still exists + (if tests are configured) a passing test run."""
        with self.db.lock:
            ce = self.db.conn.execute("SELECT * FROM git_commit_events WHERE task_id=? AND status='committed' "
                                      "ORDER BY at DESC, rowid DESC LIMIT 1", (task.task_id,)).fetchone()
            tr = self.db.conn.execute("SELECT status FROM test_runs WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                      (task.task_id,)).fetchone()
        if ce is None:
            return False, "Không có phiên bản (commit) nào được lưu cho công việc này."
        try:
            if not self.git.commit_exists(Path(project.root_path), ce["sha"]):
                return False, "Phiên bản đã lưu không còn tồn tại trong kho."
        except GitError:
            return False, "Không kiểm tra được phiên bản đã lưu."
        if project.test_command and (tr is None or tr["status"] != "passed"):
            return False, "Chưa có lần chạy kiểm thử đạt cho công việc này."
        return True, ""

    # ---- safe local integration -------------------------------------------------------------------------------
    def integrate(self, wo_id: str, *, explicit: bool) -> tuple[str, str]:
        """Fast-forward the integration branch to the work order's newest task branch. Never rebases/forces."""
        wo = self.store.get_work_order(wo_id)
        project = self.m.registry.get(wo.project_id)
        with self.db.lock:
            rows = self.db.conn.execute("SELECT * FROM git_branches WHERE work_order_id=? ORDER BY created_at, rowid",
                                        (wo_id,)).fetchall()
        if not rows:
            return "not_applicable", "Không có thay đổi tệp nào cần tích hợp."
        root, tip = Path(project.root_path), rows[-1]["name"]
        target = project.git_default_branch
        auto_ok = self.m.cfg.allow_git_auto_local_fast_forward_merge and project.git_auto_history
        if not target:
            return "ready", f"Sẵn sàng tích hợp: nhánh {tip} (chưa xác định nhánh chính để tích hợp)."
        if not (auto_ok or explicit):
            return "ready", f"Sẵn sàng tích hợp vào nhánh “{target}”. Bấm “Tích hợp vào nhánh chính” khi bạn đã xem kết quả."
        try:
            for r in rows[:-1]:
                if not self.git.is_ancestor(root, r["name"], tip):
                    return "conflict", f"Cần xử lý xung đột: nhánh {r['name']} không nằm trong nhánh {tip}."
            info = self.git.detect(root)
            if info.dirty:
                return "conflict", "Cần xử lý: thư mục dự án có thay đổi chưa lưu nên chưa thể tích hợp."
            if self.git.current_branch(root) != target:
                self.git.switch_branch(root, target)
            sha = self.git.merge_ff_only(root, tip)
        except NotFastForward as e:
            return "conflict", f"Cần xử lý xung đột: nhánh “{target}” đã có thay đổi mới nên không thể gộp thẳng ({str(e)[:120]}). Không có gì bị ghi đè."
        except GitError as e:
            return "conflict", f"Cần xử lý: {str(e)[:200]}"
        with self.db.tx() as c:
            c.execute("INSERT INTO git_commit_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (new_id("GCE"), rows[-1]["repo_id"], target, sha, None, None, wo_id, "merge --ff-only", "integrated", utcnow()))
        return "integrated", f"Đã tích hợp vào nhánh “{target}” (phiên bản {sha[:8]})."
