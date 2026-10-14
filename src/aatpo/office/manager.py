"""Office Manager: validated plans, deterministic scheduling, bounded rework, evidence-gated DONE.
LLM output is only ever *data* here: task states change solely through Store transitions this module calls."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from aatpo.agents.prompt_builder import build_task_prompt
from aatpo.agents.session_manager import ScopeNotApproved, SessionManager
from aatpo.config import OfficeConfig
from aatpo.db.repositories import ApprovalRequired, ConflictError, Store
from aatpo.domain.models import Task, TaskState as T, WorkOrder, WorkOrderState as W, new_id, utcnow
from aatpo.domain.plan import PlanRejected, TaskPlan
from aatpo.evidence import artifacts
from aatpo.office import cli_router, planner
from aatpo.office.approvals import ApprovalService
from aatpo.office.write_flow import WriteFlow
from aatpo.projects.git_service import GitService
from aatpo.projects.registry import ProjectRegistry

VERDICT = re.compile(r"^\s*VERDICT:\s*(PASS|FAIL)\s*$", re.I)
RESOURCE = "repo:{}"


class ReplanLimit(RuntimeError):
    pass


@dataclass
class RunSummary:
    outcome: str            # completed | paused | blocked | paused_quota | needs_review | idle
    message: str = ""


def parse_verdict(text: str) -> tuple[str | None, str]:
    """ONLY the first non-empty line counts, and only in the exact form 'VERDICT: PASS|FAIL'."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None, ""
    m = VERDICT.match(lines[0])
    return (m.group(1).lower() if m else None), "\n".join(lines[1:]).strip()


class OfficeManager:
    def __init__(self, store: Store, registry: ProjectRegistry, git: GitService, sessions: SessionManager,
                 approvals: ApprovalService, artifacts_root, cfg: OfficeConfig | None = None,
                 write_mode: bool = False):
        self.store, self.registry, self.git, self.sessions = store, registry, git, sessions
        self.approvals, self.db, self.root = approvals, store.db, artifacts_root
        self.cfg = cfg or OfficeConfig()
        self.write_mode = write_mode  # False: read-only adapters (proposals only). True: real edits on task branches
        self.flow = WriteFlow(self)

    # ===== planning ============================================================================
    def _approved_scope(self, wo_id: str) -> tuple[str, str, list[str], list[str]]:
        with self.db.lock:
            s = self.db.conn.execute("SELECT * FROM scopes WHERE work_order_id=? AND status='approved' "
                                     "ORDER BY version DESC LIMIT 1", (wo_id,)).fetchone()
            if s is None:
                raise ApprovalRequired("Phạm vi chưa được duyệt")
            f = self.db.conn.execute("SELECT name,priority FROM features WHERE scope_id=?", (s["scope_id"],)).fetchall()
        must = [r["name"] for r in f if r["priority"] == "MUST"]
        return s["option_key"], s["effort"], must, [f"{r['priority']}: {r['name']}" for r in f]

    def create_plan(self, wo_id: str, plan: TaskPlan | None = None) -> TaskPlan:
        wo = self.store.get_work_order(wo_id)
        if not self.store.scope_approved(wo_id):
            raise ApprovalRequired("Chỉ được lập kế hoạch sau khi khách duyệt phạm vi")
        _, effort, must, _ = self._approved_scope(wo_id)
        plan = plan or planner.build_plan(wo, planner.choose_mode(wo, effort), must)   # validated either way
        with self.db.lock:
            version = (self.db.conn.execute("SELECT COALESCE(MAX(version),0) FROM plans WHERE work_order_id=?",
                                            (wo_id,)).fetchone()[0]) + 1
        if wo.state == W.SCOPE_CONFIRMED:
            pass
        elif wo.state in (W.PLANNED, W.EXECUTING, W.BLOCKED, W.PAUSED_QUOTA, W.PAUSED_APPROVAL):
            if version - 1 > self.cfg.max_replans_per_work_order:
                raise ReplanLimit("Đã đạt số lần lập lại kế hoạch tối đa")
            self._retire_old_plan(wo_id)
        else:
            raise PlanRejected(f"không thể lập kế hoạch ở trạng thái {wo.state}")
        keys: dict[str, str] = {}
        for spec in self._topo(plan):  # deps may be listed after their dependents
            t = self.store.create_task(wo_id, spec.title, plan_version=version, plan_key=spec.key, role_id=spec.role,
                                       acceptance=spec.acceptance, writes=spec.writes,
                                       depends_on=tuple(keys[d] for d in spec.depends_on))
            keys[spec.key] = t.task_id
        with self.db.tx() as c:
            c.execute("INSERT INTO plans VALUES(?,?,?,?,'active',?)", (new_id("PLAN"), wo_id, version, plan.mode, utcnow()))
            c.execute("UPDATE plans SET status='superseded' WHERE work_order_id=? AND version<>?", (wo_id, version))
            c.execute("UPDATE work_orders SET plan_mode=? WHERE work_order_id=?", (plan.mode, wo_id))
            self.store.log_event(c, "plan.created", "work_order", wo_id, wo.project_id, version=version,
                                 mode=plan.mode, tasks=len(plan.tasks))
        if wo.state == W.SCOPE_CONFIRMED:
            self.store.transition_work_order(wo_id, W.PLANNED, self.store.get_work_order(wo_id).version)
        return plan

    @staticmethod
    def _topo(plan: TaskPlan):
        done, out, pending = set(), [], list(plan.tasks)
        while pending:
            for t in list(pending):
                if all(d in done for d in t.depends_on):
                    out.append(t)
                    done.add(t.key)
                    pending.remove(t)
        return out

    def _retire_old_plan(self, wo_id: str) -> None:
        for t in self.store.list_work_order_tasks(wo_id):
            if t.state in (T.RUNNING, T.CLAIMED, T.OUTPUT_READY, T.REVIEW, T.UNKNOWN_AFTER_CRASH):
                raise PlanRejected("Không thể lập lại kế hoạch khi còn công việc đang chạy hoặc chờ kiểm tra")
        for t in self.store.list_work_order_tasks(wo_id):
            t = self.store.get_task(t.task_id)
            if t.state == T.PAUSED:
                t = self.store.transition_task(t.task_id, T.READY, t.version)
            if t.state in (T.BACKLOG, T.READY):
                self._block(t, "thay bằng kế hoạch mới")

    # ===== scheduling ===========================================================================
    def _deps_satisfied(self, t: Task) -> bool:
        for d in self.store.dependencies(t.task_id):
            if d.state == T.DONE:
                continue
            if t.role_id == "qa_engineer" and d.state == T.REVIEW:   # QA is what lets REVIEW become DONE
                continue
            return False
        return True

    def promote_ready(self, wo_id: str) -> int:
        n = 0
        for t in self.store.list_work_order_tasks(wo_id):
            t = self.store.get_task(t.task_id)
            if t.state == T.BACKLOG and self._deps_satisfied(t):
                self.store.transition_task(t.task_id, T.READY, t.version)
                n += 1
        return n

    def next_task(self, wo_id: str, project_id: str) -> Task | None:
        """Concurrency = cfg.concurrency (1): nothing new while another task of this project is active."""
        active = [t for t in self.store.list_tasks(project_id) if t.state in (T.CLAIMED, T.RUNNING)]
        if len(active) >= self.cfg.concurrency:
            return None
        plan_v = self._current_plan_version(wo_id)
        for t in self.store.list_work_order_tasks(wo_id, plan_v):
            if t.state == T.READY and self._deps_satisfied(t) and (not t.writes or self._lock_free(project_id)):
                return t
        return None

    def _current_plan_version(self, wo_id: str) -> int:
        with self.db.lock:
            return self.db.conn.execute("SELECT COALESCE(MAX(version),1) FROM plans WHERE work_order_id=?",
                                        (wo_id,)).fetchone()[0]

    def _lock_free(self, project_id: str) -> bool:
        with self.db.lock:
            return self.db.conn.execute("SELECT 1 FROM resource_locks WHERE resource=?",
                                        (RESOURCE.format(project_id),)).fetchone() is None

    def _lock(self, project_id: str, task_id: str) -> None:
        with self.db.tx() as c:
            c.execute("INSERT INTO resource_locks VALUES(?,?,?)", (RESOURCE.format(project_id), task_id, utcnow()))

    def _unlock(self, project_id: str, task_id: str) -> None:
        with self.db.tx() as c:
            c.execute("DELETE FROM resource_locks WHERE resource=? AND holder_task_id=?",
                      (RESOURCE.format(project_id), task_id))

    # ===== run loop ================================================================================
    def progress(self, wo_id: str) -> tuple[int, int]:
        ts = self.store.list_work_order_tasks(wo_id, self._current_plan_version(wo_id))
        return sum(t.state == T.DONE for t in ts), len(ts)

    async def run_work_order(self, wo_id: str) -> RunSummary:
        wo = self.store.get_work_order(wo_id)
        if wo.requires_scope_approval and not self.store.scope_approved(wo_id):
            raise ScopeNotApproved("Chưa được duyệt phạm vi nên chưa thể thực hiện")
        if wo.state == W.PLANNED:
            wo = self.store.transition_work_order(wo_id, W.EXECUTING, wo.version)
        elif wo.state in (W.PAUSED_QUOTA, W.BLOCKED, W.PAUSED_APPROVAL):
            wo = self.store.transition_work_order(wo_id, W.EXECUTING, wo.version)
        elif wo.state != W.EXECUTING:
            return RunSummary("idle", f"Công việc đang ở trạng thái {wo.state}")
        with self.db.tx() as c:
            c.execute("UPDATE work_orders SET pause_requested=0 WHERE work_order_id=?", (wo_id,))
        while True:
            wo = self.store.get_work_order(wo_id)
            if self._pause_requested(wo_id):
                return RunSummary("paused", "Đã tạm dừng theo yêu cầu của bạn")
            self.promote_ready(wo_id)
            task = self.next_task(wo_id, wo.project_id)
            if task is None:
                summary = self._idle_summary(wo_id)
                if summary.outcome == "completed" and wo.state == W.EXECUTING:
                    return await self._finalize(wo_id)
                return summary
            res = await self._run_task(wo, task)
            if res is not None:
                return res

    def _pause_requested(self, wo_id: str) -> bool:
        with self.db.lock:
            return bool(self.db.conn.execute("SELECT pause_requested FROM work_orders WHERE work_order_id=?",
                                             (wo_id,)).fetchone()[0])

    def _idle_summary(self, wo_id: str) -> RunSummary:
        ts = self.store.list_work_order_tasks(wo_id, self._current_plan_version(wo_id))
        if ts and all(t.state == T.DONE for t in ts):
            return RunSummary("completed", "Tất cả công việc đã hoàn thành và có bằng chứng")
        if any(t.state == T.UNKNOWN_AFTER_CRASH for t in ts):
            return RunSummary("needs_review", "Có công việc cần bạn xem lại trước khi chạy tiếp")
        if any(t.state in (T.BLOCKED, T.FAILED) for t in ts):
            return RunSummary("blocked", next((t.blocked_reason for t in ts if t.blocked_reason), "Có công việc bị chặn"))
        if any(t.state == T.PAUSED for t in ts):
            return RunSummary("paused", "Công việc đang tạm dừng")
        return RunSummary("idle", "Không có công việc nào sẵn sàng")

    # ---- one task ---------------------------------------------------------------------------------
    def _runs_for(self, *, task_id: str | None = None, wo_id: str | None = None) -> int:
        q = ("SELECT count(*) FROM process_runs r JOIN agent_sessions s USING(session_id) WHERE "
             + ("s.task_id=?" if task_id else "s.work_order_id=?"))
        with self.db.lock:
            return self.db.conn.execute(q, (task_id or wo_id,)).fetchone()[0]

    def _block(self, t: Task, reason: str) -> Task:
        t = self.store.get_task(t.task_id)
        t = self.store.transition_task(t.task_id, T.BLOCKED, t.version)
        with self.db.tx() as c:
            c.execute("UPDATE tasks SET blocked_reason=? WHERE task_id=?", (reason, t.task_id))
        return self.store.get_task(t.task_id)

    def _fail_work_order(self, wo: WorkOrder, why: str, to: W = W.BLOCKED) -> None:
        wo = self.store.get_work_order(wo.work_order_id)
        if wo.state == W.EXECUTING:
            self.store.transition_work_order(wo.work_order_id, to, wo.version)
        with self.db.tx() as c:
            self.store.log_event(c, "work_order.halted", "work_order", wo.work_order_id, wo.project_id, reason=why)

    async def _run_task(self, wo: WorkOrder, task: Task) -> RunSummary | None:
        project = self.registry.get(wo.project_id)
        # 1. atomic claim (version check); losing the race just means someone else has it
        try:
            task = self.store.transition_task(task.task_id, T.CLAIMED, task.version)
        except ConflictError:
            return None
        locked = False
        try:
            if task.writes:
                self._lock(project.project_id, task.task_id)
                locked = True
            # 2. budgets
            if self._runs_for(task_id=task.task_id) >= self.cfg.max_runs_per_task:
                return self._give_up(wo, task, "đã dùng hết số lần chạy cho công việc này")
            if self._runs_for(wo_id=wo.work_order_id) >= self.cfg.max_total_runs_per_work_order:
                return self._give_up(wo, task, "đã dùng hết số lần chạy cho yêu cầu này")
            # 3. provider
            prev = self._previous_provider(task)
            provider = cli_router.route(self.cfg.provider_preference, self._statuses(), prefer=prev)
            if provider is None:
                t = self.store.get_task(task.task_id)
                self.store.transition_task(t.task_id, T.READY, t.version)
                self._fail_work_order(wo, "không có trợ lý AI sẵn sàng", W.PAUSED_QUOTA)
                return RunSummary("paused_quota", "Không có trợ lý AI nào sẵn sàng (chưa đăng nhập hoặc hết hạn mức)")
            if prev and provider != prev and self._handoffs(task) >= self.cfg.max_handoffs_per_task:
                return self._give_up(wo, task, "đã đổi trợ lý quá số lần cho phép")
            # 4. write-capable task: Git safety preflight (repo, identity, clean tree, own branch)
            write = bool(task.writes and self.write_mode)
            if write:
                blk = self.flow.preflight(wo, project, task)
                if blk is not None:
                    t = self.store.get_task(task.task_id)
                    self.store.transition_task(t.task_id, T.READY, t.version)
                    self._block(self.store.get_task(task.task_id), blk.reason)
                    self._fail_work_order(wo, f"git:{blk.code}")
                    return RunSummary("blocked", blk.reason)
            # 5. session + run
            asg = self._assignment(task, provider)
            t = self.store.get_task(task.task_id)
            task = self.store.transition_task(t.task_id, T.RUNNING, t.version)
            brief = self._brief(task, asg.assignment_id)
            prompt = build_task_prompt(wo, task, scope_text=self._scope_text(wo.work_order_id),
                                       inputs=self._inputs(task), brief=brief, read_only=not write)
            run, res = await self.sessions.execute(asg.assignment_id, prompt, project.root_path, brief=brief, write=write,
                                                   timeout=self.cfg.run_timeout_seconds)
            return await self._after_run(wo, project, task, run, res, write)
        finally:
            if locked:
                self._unlock(project.project_id, task.task_id)

    async def _after_run(self, wo: WorkOrder, project, task: Task, run, res, write: bool) -> RunSummary | None:
        t = self.store.get_task(task.task_id)
        if res.ok:
            aid = artifacts.save_text(self.db, self.root, project_id=wo.project_id, work_order_id=wo.work_order_id,
                                      task_id=task.task_id, run_id=run.run_id, text=res.text)
            t = self.store.transition_task(t.task_id, T.OUTPUT_READY, t.version)
            t = self.store.transition_task(t.task_id, T.REVIEW, t.version)
            if t.role_id == "qa_engineer":
                return self._apply_review(wo, t, res.text, aid)
            if not t.writes:
                return self._auto_review(wo, t, aid)   # analysis/design/packaging: DONE only on verified evidence
            if write:   # real edits: check paths/secrets, run tests, commit - failures go straight to bounded rework
                col = await self.flow.collect(wo, project, t)
                if not col.passed:
                    return self._auto_fail(wo, t, aid, col.finding or "Kiểm tra tự động không đạt.")
            return None   # write tasks wait in REVIEW for an independent QA task
        if res.cancelled:
            self.store.transition_task(t.task_id, T.PAUSED, t.version)
            return RunSummary("paused", "Đã dừng theo yêu cầu của bạn")
        if res.error_kind == "quota":     # provider now marked quota_exhausted; the router picks another next loop
            t = self.store.transition_task(t.task_id, T.PAUSED, t.version)
            self.store.transition_task(t.task_id, T.READY, t.version)
            with self.db.tx() as c:
                self.store.log_event(c, "provider.quota", "task", t.task_id, wo.project_id)
            return None
        # failure or timeout: bounded retry
        if self._runs_for(task_id=t.task_id) < self.cfg.max_runs_per_task:
            t = self.store.transition_task(t.task_id, T.PAUSED, t.version)
            self.store.transition_task(t.task_id, T.READY, t.version)
            return None
        t = self.store.transition_task(t.task_id, T.FAILED, t.version)
        self._fail_work_order(wo, res.error or "lỗi không rõ")
        return RunSummary("blocked", f"Công việc “{t.title}” thất bại: {res.error or 'lỗi không rõ'}")

    def _give_up(self, wo: WorkOrder, task: Task, why: str) -> RunSummary:
        t = self.store.get_task(task.task_id)
        t = self.store.transition_task(t.task_id, T.READY, t.version)
        t = self._block(t, why)
        self._fail_work_order(wo, why)
        return RunSummary("blocked", f"Công việc “{t.title}” bị chặn: {why}")

    # ---- QA gate: the only way a task becomes DONE -----------------------------------------------
    def _apply_review(self, wo: WorkOrder, qa: Task, text: str, qa_artifact: str) -> RunSummary | None:
        verdict, findings = parse_verdict(text)
        if verdict is None:   # malformed QA reply is NOT a pass: treat the QA run as failed and retry (bounded)
            qa = self.store.get_task(qa.task_id)
            if self._runs_for(task_id=qa.task_id) < self.cfg.max_runs_per_task:
                qa = self.store.transition_task(qa.task_id, T.REWORK, qa.version)
                self.store.transition_task(qa.task_id, T.READY, qa.version)
                return None
            self.store.transition_task(qa.task_id, T.FAILED, qa.version)
            self._fail_work_order(wo, "kết quả kiểm tra không đúng định dạng")
            return RunSummary("blocked", "Bước kiểm tra không trả về kết luận hợp lệ")
        all_ok = True
        exhausted = None
        for d in self.store.dependencies(qa.task_id):
            d = self.store.get_task(d.task_id)
            if d.state != T.REVIEW:
                continue
            art = artifacts.latest(self.db, d.task_id)
            evidence_ok = bool(art) and artifacts.verify(self.db, art["artifact_id"], d.task_id)
            why = "Không có bằng chứng hợp lệ cho kết quả này."
            if evidence_ok and d.writes and self.write_mode:
                evidence_ok, w2 = self.flow.evidence_ok(d, self.registry.get(wo.project_id))
                why = w2 or why
            passed = verdict == "pass" and evidence_ok
            rid = new_id("REV")
            note = findings if verdict == "fail" else (findings if evidence_ok else why)
            with self.db.tx() as c:
                c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?)", (rid, d.task_id, qa.task_id,
                          "pass" if passed else "fail", note or "(không có ghi chú)", art["artifact_id"] if art else None, utcnow()))
            if passed:
                self.store.transition_task(d.task_id, T.DONE, d.version, evidence_id=rid)
            else:
                all_ok = False
                if self._send_back(d):
                    exhausted = self.store.get_task(d.task_id)
        qa = self.store.get_task(qa.task_id)
        if all_ok and verdict == "pass" and artifacts.verify(self.db, qa_artifact, qa.task_id):
            self.store.transition_task(qa.task_id, T.DONE, qa.version, evidence_id=qa_artifact)
            return None
        if exhausted is not None:
            self.store.transition_task(qa.task_id, T.FAILED, qa.version)
            self._fail_work_order(wo, "vượt quá số lần làm lại")
            return RunSummary("blocked", f"Công việc “{exhausted.title}” không đạt sau nhiều lần làm lại")
        qa = self.store.transition_task(qa.task_id, T.REWORK, qa.version)
        self.store.transition_task(qa.task_id, T.READY, qa.version)
        return None

    def _auto_fail(self, wo: WorkOrder, t: Task, artifact_id: str, finding: str) -> RunSummary | None:
        """Mechanical checks (no changes / forbidden paths / secrets / failing tests) reject BEFORE QA is spent."""
        with self.db.tx() as c:
            c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?)", (new_id("REV"), t.task_id, t.task_id, "fail",
                      finding[:2000], artifact_id, utcnow()))
        if self._send_back(t):
            self._fail_work_order(wo, "vượt quá số lần làm lại")
            return RunSummary("blocked", f"Công việc “{t.title}” không đạt sau nhiều lần làm lại: {finding[:200]}")
        return None

    def _auto_review(self, wo: WorkOrder, t: Task, artifact_id: str) -> RunSummary | None:
        """Non-writing tasks: DONE needs a verified artifact (exists, non-empty, hash matches, same task)."""
        ok = artifacts.verify(self.db, artifact_id, t.task_id)
        rid = new_id("REV")
        with self.db.tx() as c:
            c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?)", (rid, t.task_id, t.task_id, "pass" if ok else "fail",
                      "Kiểm tra tự động: có kết quả hợp lệ, đúng mã băm." if ok else "Kết quả không hợp lệ hoặc đã bị thay đổi.",
                      artifact_id, utcnow()))
        if ok:
            self.store.transition_task(t.task_id, T.DONE, t.version, evidence_id=rid)
            return None
        if self._send_back(t):
            self._fail_work_order(wo, "vượt quá số lần làm lại")
            return RunSummary("blocked", f"Công việc “{t.title}” không đạt sau nhiều lần làm lại")
        return None

    def _send_back(self, t: Task) -> bool:
        """REVIEW -> REWORK -> READY, or REVIEW -> FAILED once the bounded rework cycles are used up.
        Returns True when the task failed for good."""
        t = self.store.get_task(t.task_id)
        count = t.rework_count + 1
        exhausted = count > self.cfg.max_rework_cycles_per_task
        t = self.store.transition_task(t.task_id, T.FAILED if exhausted else T.REWORK, t.version)
        with self.db.tx() as c:
            c.execute("UPDATE tasks SET rework_count=? WHERE task_id=?", (count, t.task_id))
        if not exhausted:
            t = self.store.get_task(t.task_id)
            self.store.transition_task(t.task_id, T.READY, t.version)
        return exhausted

    # ---- helpers ------------------------------------------------------------------------------------
    def _statuses(self) -> dict:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT provider_id,status,version FROM provider_registry").fetchall()
        return {r["provider_id"]: (r["status"], r["version"]) for r in rows}

    def _previous_provider(self, task: Task) -> str | None:
        with self.db.lock:
            r = self.db.conn.execute("SELECT provider_id FROM assignments WHERE task_id=? ORDER BY created_at DESC, rowid DESC "
                                     "LIMIT 1", (task.task_id,)).fetchone()
        return r["provider_id"] if r else None

    def _handoffs(self, task: Task) -> int:
        with self.db.lock:
            return self.db.conn.execute("SELECT count(*) FROM handoffs WHERE to_task_id=?", (task.task_id,)).fetchone()[0]

    def _assignment(self, task: Task, provider: str):
        with self.db.lock:
            r = self.db.conn.execute("SELECT assignment_id FROM assignments WHERE task_id=? AND role_id=? AND provider_id=?",
                                     (task.task_id, task.role_id, provider)).fetchone()
        if r:
            return self.store.get_assignment(r["assignment_id"])
        prev = self._previous_provider(task)
        asg = self.store.create_assignment(task.task_id, task.role_id, provider)
        if prev and prev != provider:     # provider switch => structured handoff + brand-new session
            with self.db.tx() as c:
                c.execute("INSERT INTO handoffs VALUES(?,?,?,?,?,?,?)", (new_id("HO"), task.work_order_id, None, task.task_id,
                          f"đổi trợ lý {prev} -> {provider}", self._compact(task), utcnow()))
        return asg

    def _compact(self, task: Task) -> str:
        art = artifacts.latest(self.db, task.task_id)
        tail = artifacts.read(self.db, art["artifact_id"])[-1200:] if art else "(chưa có kết quả trước đó)"
        return f"Công việc: {task.title}\nTiêu chí: {task.acceptance}\nKết quả gần nhất (đoạn cuối):\n{tail}"

    def _brief(self, task: Task, assignment_id: str) -> str:
        """Compact stored brief for fallback sessions: QA findings + tail of the last output. Never raw chat."""
        with self.db.lock:
            rv = self.db.conn.execute("SELECT findings FROM reviews WHERE task_id=? AND verdict='fail' "
                                      "ORDER BY created_at DESC, rowid DESC LIMIT 1", (task.task_id,)).fetchone()
        if rv is None and task.rework_count == 0 and self._previous_provider(task) is None:
            return ""
        parts = [self._compact(task)]
        if rv:
            parts.append(f"Nhận xét của bước kiểm tra cần sửa:\n{rv['findings']}")
        return "\n\n".join(parts)

    def _scope_text(self, wo_id: str) -> str:
        key, effort, _, feats = self._approved_scope(wo_id)
        return f"Phương án: {key}, quy mô {effort}\n" + "\n".join(feats)

    def _inputs(self, task: Task) -> list[tuple[str, str]]:
        out = []
        for d in self.store.dependencies(task.task_id):
            for kind, label in (("agent_output", "kết quả của công việc"), ("diff", "thay đổi thực tế (diff) của công việc"),
                                ("test_output", "kết quả chạy kiểm thử của công việc")):
                art = artifacts.latest(self.db, d.task_id, kind)
                if art:
                    out.append((f"{label} “{d.title}”", artifacts.read(self.db, art["artifact_id"])))
        return out

    # ===== delivery ====================================================================================
    async def _finalize(self, wo_id: str) -> RunSummary:
        """All tasks DONE with evidence -> final verification -> integration -> report -> DELIVERED."""
        wo = self.store.get_work_order(wo_id)
        project = self.registry.get(wo.project_id)
        write_tasks = [t for t in self.store.list_work_order_tasks(wo_id, self._current_plan_version(wo_id)) if t.writes]
        wo = self.store.transition_work_order(wo_id, W.VERIFYING, wo.version)
        if self.write_mode and write_tasks and project.test_command:
            from aatpo.evidence.tests import run_tests
            r = await run_tests(self.db, self.root, project_id=project.project_id, work_order_id=wo_id,
                                task_id=write_tasks[-1].task_id, argv=project.test_command, cwd=project.root_path,
                                timeout=self.cfg.run_timeout_seconds)
            if not r.ok:
                self.store.transition_work_order(wo_id, W.BLOCKED, self.store.get_work_order(wo_id).version)
                return RunSummary("blocked", f"Kiểm thử cuối cùng KHÔNG đạt ({r.status}); công việc chưa được bàn giao.")
        self.store.transition_work_order(wo_id, W.PACKAGING, self.store.get_work_order(wo_id).version)
        if self.write_mode and write_tasks:
            status, note = self.flow.integrate(wo_id, explicit=False)
        else:
            status, note = "not_applicable", "Chế độ chỉ đọc: không có thay đổi tệp để tích hợp."
        return self._deliver(wo_id, status, note)

    def _deliver(self, wo_id: str, status: str, note: str) -> RunSummary:
        with self.db.tx() as c:
            c.execute("UPDATE work_orders SET integration_status=?, integration_note=? WHERE work_order_id=?", (status, note, wo_id))
            wo = self.store.get_work_order(wo_id)
            self.store.log_event(c, "integration", "work_order", wo_id, wo.project_id, status=status, note=note)
        if status == "conflict":   # uncertain merge state: never label it delivered
            return RunSummary("blocked", note)
        from aatpo.delivery.report import build_report, save_report
        ctx = SimpleNamespace(store=self.store, db=self.db, registry=self.registry, manager=self)
        save_report(ctx, wo_id, build_report(ctx, wo_id, self._diffstat(wo_id)))
        wo = self.store.get_work_order(wo_id)
        if wo.state == W.PACKAGING:
            self.store.transition_work_order(wo_id, W.DELIVERED, wo.version)
        return RunSummary("completed", "Đã hoàn thành, có bằng chứng và báo cáo bàn giao")

    def _diffstat(self, wo_id: str) -> str | None:
        with self.db.lock:
            rows = self.db.conn.execute("SELECT * FROM git_branches WHERE work_order_id=? ORDER BY created_at, rowid",
                                        (wo_id,)).fetchall()
            sha = self.db.conn.execute("SELECT sha FROM git_commit_events WHERE branch=? AND status='committed' "
                                       "ORDER BY at DESC, rowid DESC LIMIT 1", (rows[-1]["name"],)).fetchone() if rows else None
        if not rows or not sha or not rows[0]["base_sha"]:
            return None
        try:
            project = self.registry.get(self.store.get_work_order(wo_id).project_id)
            return self.git.diff_range(Path(project.root_path), rows[0]["base_sha"], sha["sha"], stat=True)
        except Exception:
            return None

    def integrate_now(self, wo_id: str) -> RunSummary:
        """User clicked 'Tích hợp vào nhánh chính' (explicit, action-specific consent). Also the retry after a conflict."""
        wo = self.store.get_work_order(wo_id)
        if wo.state not in (W.PACKAGING, W.DELIVERED):
            return RunSummary("idle", "Công việc chưa sẵn sàng để tích hợp")
        status, note = self.flow.integrate(wo_id, explicit=True)
        return self._deliver(wo_id, status, note)

    # ===== user controls ===============================================================================
    async def pause(self, wo_id: str) -> None:
        with self.db.tx() as c:
            c.execute("UPDATE work_orders SET pause_requested=1 WHERE work_order_id=?", (wo_id,))
        with self.db.lock:
            rows = self.db.conn.execute("SELECT r.run_id FROM process_runs r JOIN agent_sessions s USING(session_id) "
                                        "WHERE s.work_order_id=? AND r.state='RUNNING'", (wo_id,)).fetchall()
        for r in rows:
            await self.sessions.cancel(r["run_id"])

    def resume(self, wo_id: str) -> None:
        """PAUSED tasks become READY. UNKNOWN_AFTER_CRASH ones need an explicit approval instead."""
        with self.db.tx() as c:
            c.execute("UPDATE work_orders SET pause_requested=0 WHERE work_order_id=?", (wo_id,))
        for t in self.store.list_work_order_tasks(wo_id):
            t = self.store.get_task(t.task_id)
            if t.state == T.PAUSED:
                self.store.transition_task(t.task_id, T.READY, t.version)
            elif t.state == T.BLOCKED and t.blocked_reason and "kế hoạch mới" not in t.blocked_reason:
                t = self.store.transition_task(t.task_id, T.READY, t.version)
                with self.db.tx() as c:
                    c.execute("UPDATE tasks SET blocked_reason=NULL WHERE task_id=?", (t.task_id,))
            elif t.state == T.UNKNOWN_AFTER_CRASH:
                self.approvals.request_rerun(t.task_id)

    def reconcile_after_restart(self) -> int:
        """Startup: CLAIMED (never dispatched) -> READY; UNKNOWN tasks get a re-run approval; locks of
        non-uncertain holders are cleared. Nothing is replayed automatically."""
        n = 0
        with self.db.lock:
            claimed = self.db.conn.execute("SELECT task_id FROM tasks WHERE state='CLAIMED'").fetchall()
            unknown = self.db.conn.execute("SELECT task_id FROM tasks WHERE state='UNKNOWN_AFTER_CRASH'").fetchall()
        for r in claimed:
            t = self.store.get_task(r["task_id"])
            self.store.transition_task(t.task_id, T.READY, t.version)
        for r in unknown:
            if self.approvals.request_rerun(r["task_id"]):
                n += 1
        with self.db.tx() as c:
            c.execute("DELETE FROM resource_locks WHERE holder_task_id NOT IN "
                      "(SELECT task_id FROM tasks WHERE state='UNKNOWN_AFTER_CRASH')")
        return n
