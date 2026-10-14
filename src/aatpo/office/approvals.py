"""Approval service: the ONLY path to SCOPE_CONFIRMED. A decision is tied to the exact action,
project, work order and scope version; chat text, silence, or AI output can never produce one."""
from __future__ import annotations

import getpass
import json
from dataclasses import dataclass

from aatpo.db.repositories import Store
from aatpo.domain.models import WorkOrderState, new_id, utcnow


class ApprovalError(ValueError):
    pass


@dataclass(frozen=True)
class Approval:
    approval_id: str
    kind: str
    project_id: str
    work_order_id: str
    scope_version: int | None
    action_text: str
    consequences: str
    options: list[dict]
    status: str
    chosen_option: str | None


def _row(r) -> Approval:
    return Approval(r["approval_id"], r["kind"], r["project_id"], r["work_order_id"], r["scope_version"],
                    r["action_text"], r["consequences"], json.loads(r["options"]), r["status"], r["chosen_option"])


class ApprovalService:
    def __init__(self, store: Store):
        self.store, self.db = store, store.db

    def request_scope_approval(self, work_order_id: str, version: int) -> Approval:
        """Create a pending approval for this scope version; older pending ones are superseded."""
        with self.db.tx() as c:
            wo = c.execute("SELECT * FROM work_orders WHERE work_order_id=?", (work_order_id,)).fetchone()
            scopes = c.execute("SELECT * FROM scopes WHERE work_order_id=? AND version=? ORDER BY option_key",
                               (work_order_id, version)).fetchall()
            if not scopes:
                raise ApprovalError("Chưa có phạm vi để duyệt")
            c.execute("UPDATE approvals SET status='superseded' WHERE work_order_id=? AND kind='scope' "
                      "AND status='pending'", (work_order_id,))
            opts = [{"key": s["option_key"], "title": s["title_vi"], "effort": s["effort"]} for s in scopes]
            aid = new_id("APR")
            c.execute("INSERT INTO approvals(approval_id,kind,project_id,work_order_id,scope_version,action_text,"
                      "consequences,options,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (aid, "scope", wo["project_id"], work_order_id, version,
                       f"Duyệt phạm vi (phiên bản {version}) cho: {wo['title']}",
                       "Sau khi đồng ý, AATPO mới được lập kế hoạch và thực hiện đúng phạm vi đã chọn. "
                       "Thay đổi phạm vi về sau cần bạn duyệt lại.",
                       json.dumps(opts, ensure_ascii=False), utcnow()))
            self.store.log_event(c, "approval.requested", "approval", aid, wo["project_id"], version=version)
        return self.get(aid)

    def get(self, approval_id: str) -> Approval:
        with self.db.lock:
            r = self.db.conn.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
        if r is None:
            raise KeyError(approval_id)
        return _row(r)

    def pending(self, project_id: str | None = None) -> list[Approval]:
        q, a = "SELECT * FROM approvals WHERE status='pending'", ()
        if project_id:
            q, a = q + " AND project_id=?", (project_id,)
        with self.db.lock:
            return [_row(r) for r in self.db.conn.execute(q + " ORDER BY created_at, rowid", a)]

    def decide(self, approval_id: str, approve: bool, chosen_option: str | None = None,
               operator: str | None = None) -> Approval:
        """Called only by GUI button handlers. Re-validates everything deterministically."""
        with self.db.tx() as c:
            r = c.execute("SELECT * FROM approvals WHERE approval_id=?", (approval_id,)).fetchone()
            if r is None:
                raise KeyError(approval_id)
            if r["status"] != "pending":
                raise ApprovalError("Yêu cầu này đã được xử lý hoặc không còn hiệu lực")
            latest = c.execute("SELECT MAX(version) FROM scopes WHERE work_order_id=?",
                               (r["work_order_id"],)).fetchone()[0]
            if r["kind"] == "scope" and latest != r["scope_version"]:
                raise ApprovalError("Phạm vi đã thay đổi; hãy xem lại phiên bản mới")
            wo = c.execute("SELECT * FROM work_orders WHERE work_order_id=?", (r["work_order_id"],)).fetchone()
            if wo["project_id"] != r["project_id"]:
                raise ApprovalError("Dự án không khớp với yêu cầu duyệt")
            if approve:
                keys = {o["key"] for o in json.loads(r["options"])}
                if chosen_option not in keys:
                    raise ApprovalError("Hãy chọn một trong các phương án đang đề xuất")
            now = utcnow()
            op = operator or getpass.getuser()
            c.execute("UPDATE approvals SET status=?, chosen_option=?, decided_at=?, operator=? WHERE approval_id=?",
                      ("approved" if approve else "rejected", chosen_option if approve else None, now, op, approval_id))
            c.execute("UPDATE scopes SET status=CASE WHEN ?=1 AND option_key=? THEN 'approved' ELSE 'rejected' END "
                      "WHERE work_order_id=? AND version=?",
                      (int(approve), chosen_option, r["work_order_id"], r["scope_version"]))
            dst = WorkOrderState.SCOPE_CONFIRMED if approve else WorkOrderState.DISCOVERING
            self.store.transition_work_order_in_tx(c, r["work_order_id"], dst, wo["version"])
            self.store.log_event(c, "approval.decided", "approval", approval_id, r["project_id"],
                                 approve=approve, option=chosen_option, scope_version=r["scope_version"],
                                 work_order_id=r["work_order_id"], operator=op)
        return self.get(approval_id)
