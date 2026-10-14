"""Customer Gateway (client_representative voice). Deterministic policy over proposed intents:
saves history per project, asks one question at a time, proposes scope, never approves anything itself."""
from __future__ import annotations

import json

from aatpo.customer import analyst, scope_advisor
from aatpo.customer.intent_router import IntentProposer, RuleIntentProposer
from aatpo.customer.text import UNKNOWN_QUICK, is_unknown_answer, sanitize
from aatpo.db.repositories import Store
from aatpo.domain.contracts import ChatReply, Intent, UiAction
from aatpo.domain.models import Project, WorkOrder, WorkOrderState as W, new_id, utcnow
from aatpo.office.approvals import ApprovalService
from aatpo.projects.registry import ProjectRegistry

STATE_VI = {
    "RECEIVED": "Đã nhận", "DISCOVERING": "Đang tìm hiểu yêu cầu", "WAITING_CUSTOMER": "Đang chờ bạn trả lời",
    "SCOPE_PROPOSED": "Cần bạn xác nhận phạm vi", "SCOPE_CONFIRMED": "Đã duyệt phạm vi", "PLANNED": "Đã lên kế hoạch",
    "EXECUTING": "Đang thực hiện", "VERIFYING": "Đang kiểm tra", "PACKAGING": "Đang đóng gói",
    "DELIVERED": "Hoàn thành", "ACCEPTED": "Đã nghiệm thu", "PAUSED_APPROVAL": "Cần bạn xác nhận",
    "PAUSED_QUOTA": "Tạm dừng (hết hạn mức)", "BLOCKED": "Bị chặn", "FAILED": "Thất bại", "CANCELLED": "Đã hủy",
    "CHANGE_REQUESTED": "Có yêu cầu thay đổi",
}
META_WHILE_WAITING = {"show_progress", "pause_work", "open_project", "create_project"}
OPEN_STATES = {W.RECEIVED, W.DISCOVERING, W.WAITING_CUSTOMER, W.SCOPE_PROPOSED, W.SCOPE_CONFIRMED, W.PLANNED,
               W.EXECUTING, W.VERIFYING, W.PACKAGING, W.PAUSED_APPROVAL, W.PAUSED_QUOTA, W.BLOCKED}


class ChatService:
    def __init__(self, store: Store, registry: ProjectRegistry, approvals: ApprovalService,
                 proposer: IntentProposer | None = None):
        self.store, self.registry, self.approvals = store, registry, approvals
        self.db = store.db
        self.proposer = proposer or RuleIntentProposer()

    # ---- history (scoped per project) ------------------------------------------------------
    def save(self, project_id: str, role: str, text: str, work_order_id: str | None = None, **meta) -> None:
        with self.db.tx() as c:
            c.execute("INSERT INTO customer_messages VALUES(?,?,?,?,?,?,?)",
                      (new_id("MSG"), project_id, work_order_id, role, text,
                       json.dumps(meta, ensure_ascii=False) if meta else None, utcnow()))

    def history(self, project_id: str, limit: int = 200) -> list[tuple[str, str]]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT role,text FROM customer_messages WHERE project_id=? ORDER BY created_at, rowid LIMIT ?",
                (project_id, limit)).fetchall()
        return [(r["role"], r["text"]) for r in rows]

    def active_work_order(self, project_id: str) -> WorkOrder | None:
        for wo in reversed(self.store.list_work_orders(project_id)):
            if wo.state in OPEN_STATES and wo.kind != "general":
                return wo
        return None

    # ---- entry point ------------------------------------------------------------------------
    async def handle(self, text: str) -> ChatReply:
        text = sanitize(text)
        project = self.registry.selected()
        if not text:
            return ChatReply(text="Bạn hãy nhập nội dung muốn giao cho AATPO.")
        if project:
            self.save(project.project_id, "customer", text)
        try:
            reply = await self._route(text, project)
        except Exception:  # user-visible fallback; details stay in logs/events, not in the chat
            reply = ChatReply(text="Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu này. Dữ liệu của bạn vẫn an toàn; "
                                   "bạn hãy thử diễn đạt lại hoặc dùng các nút bên dưới.")
        if project:
            self.save(project.project_id, "assistant", reply.text, kind="reply")
        return reply

    async def _route(self, text: str, project: Project | None) -> ChatReply:
        wo = self.active_work_order(project.project_id) if project else None
        # 1) a pending clarification question: the next message is its answer (data, not a command)
        intent = None
        if wo and wo.state == W.WAITING_CUSTOMER:
            meta = await RuleIntentProposer().propose(text, None)   # clear housekeeping commands still work
            if meta.action not in META_WHILE_WAITING:
                return self._answer(wo, text)
            intent = meta
        intent = intent or await self.proposer.propose(text, project.display_name if project else None)
        return self._act(intent, text, project, wo)

    # ---- deterministic action policy --------------------------------------------------------
    def _act(self, intent: Intent, text: str, project: Project | None, wo: WorkOrder | None) -> ChatReply:
        a = intent.action
        if a == "approve_attempt":
            return self._approval_hint(project, wo)
        if a == "create_project":
            name = intent.title or ""
            return ChatReply(text=f"Tôi sẽ giúp bạn tạo dự án{(' “' + name + '”') if name else ''}. "
                                  "Hãy chọn thư mục để lưu dự án.",
                             actions=[UiAction(kind="pick_folder_create", label="Chọn thư mục…", payload={"name": name})])
        if a == "open_project":
            return self._open_project(intent.project_hint or "")
        if project is None:
            return ChatReply(text="Bạn chưa chọn dự án nên tôi chưa thể giao việc. Hãy chọn một dự án trước.",
                             actions=[UiAction(kind="pick_project", label="Chọn dự án"),
                                      UiAction(kind="pick_folder_open", label="Mở dự án có sẵn…")])
        other = self._other_project_mentioned(text, project)
        if other:  # never operate on, or even read, another project without an explicit switch
            return ChatReply(text=f"Có vẻ bạn đang nói tới dự án “{other.display_name}”, nhưng dự án đang chọn là "
                                  f"“{project.display_name}”. Bạn muốn chuyển sang dự án đó không?",
                             actions=[UiAction(kind="switch_project", label=f"Chuyển sang “{other.display_name}”",
                                               payload={"project_id": other.project_id, "text": text})])
        if a in ("new_work_order", "change_request"):
            return self._new_work_order(intent, text, project, wo)
        if a == "start_work":
            return self._start(project, wo)
        if a == "pause_work":
            return ChatReply(text="Hiện chưa có tiến trình nào đang chạy để tạm dừng. "
                                  "Khi có công việc đang chạy, tôi sẽ yêu cầu dừng an toàn và báo lại trạng thái.")
        if a == "show_progress":
            return self._progress(project)
        if a == "prefer_lean":
            if wo and wo.state == W.SCOPE_PROPOSED:
                return ChatReply(text="Phương án “Tiết kiệm” phù hợp với yêu cầu này. Hãy xem phạm vi và bấm chọn ở mục "
                                      "“Cần bạn quyết định” — tôi không tự chọn thay bạn.",
                                 actions=[UiAction(kind="view_scope", label="Xem phạm vi")])
            return ChatReply(text="Bạn muốn làm bản đơn giản cho việc gì? Hãy mô tả ngắn, ví dụ: “Tạo ứng dụng quản lý kho”.")
        return ChatReply(text="Tôi chưa hiểu rõ ý bạn. Bạn muốn tạo ứng dụng mới, sửa một lỗi, hay xem tiến độ?",
                         actions=[UiAction(kind="quick_reply", label="Xem tiến độ", payload={"text": "Cho tôi xem đã làm gì"})])

    def _other_project_mentioned(self, text: str, current: Project) -> Project | None:
        hits = [p for p in self.registry.suggest(text) if p.project_id != current.project_id]
        cur_hit = any(p.project_id == current.project_id for p in self.registry.suggest(text))
        return hits[0] if len(hits) == 1 and not cur_hit else None

    def _open_project(self, hint: str) -> ChatReply:
        c = self.registry.suggest(hint) if hint else []
        if len(c) == 1:
            self.registry.select(c[0].project_id)
            return ChatReply(text=f"Đã mở dự án “{c[0].display_name}”.")
        if not c:
            return ChatReply(text="Tôi không tìm thấy dự án nào khớp. Bạn hãy chọn từ danh sách hoặc mở một thư mục.",
                             actions=[UiAction(kind="pick_project", label="Chọn dự án"),
                                      UiAction(kind="pick_folder_open", label="Mở dự án có sẵn…")])
        return ChatReply(text="Có nhiều dự án phù hợp, bạn muốn mở dự án nào?",
                         actions=[UiAction(kind="switch_project", label=p.display_name,
                                           payload={"project_id": p.project_id}) for p in c])

    def _new_work_order(self, intent: Intent, text: str, project: Project, wo: WorkOrder | None) -> ChatReply:
        if wo and wo.state in (W.SCOPE_PROPOSED, W.DISCOVERING, W.RECEIVED):
            return ChatReply(text="Bạn đang có một yêu cầu chưa chốt phạm vi. Hãy xử lý nó ở mục “Cần bạn quyết định” "
                                  "trước khi giao việc mới.", actions=[UiAction(kind="view_scope", label="Xem phạm vi")])
        kind = "product" if intent.kind == "product" else "change"
        parent = None
        if intent.action == "change_request":
            done = [w for w in self.store.list_work_orders(project.project_id)
                    if w.state in (W.DELIVERED, W.ACCEPTED, W.SCOPE_CONFIRMED, W.EXECUTING)]
            parent = done[-1].work_order_id if done else None
        new = self.store.create_work_order(project.project_id, (intent.title or text)[:120], kind=kind,
                                          requires_scope_approval=True, parent=parent, brief=text)
        new = self.store.transition_work_order(new.work_order_id, W.DISCOVERING, new.version)
        q, domain = analyst.question_for(kind, text)
        new = self.store.transition_work_order(new.work_order_id, W.WAITING_CUSTOMER, new.version)
        self.save(project.project_id, "system", f"Đã ghi nhận yêu cầu mới: {new.title}", new.work_order_id, domain=domain)
        return ChatReply(text=q, actions=[UiAction(kind="quick_reply", label=UNKNOWN_QUICK, payload={"text": UNKNOWN_QUICK})])

    def _answer(self, wo: WorkOrder, text: str) -> ChatReply:
        wo = self.store.transition_work_order(wo.work_order_id, W.DISCOVERING, wo.version)
        domain = analyst.domain_of(wo.brief or wo.title) if wo.kind != "change" else "change"
        if is_unknown_answer(text):
            note = analyst.DEFAULT_ASSUMPTION[domain]
            detail = f"{note}\n\n"
        else:
            detail = f"Cảm ơn bạn, tôi đã ghi nhận: “{text[:200]}”.\n\n"
        self.save(wo.project_id, "system", f"Câu trả lời của khách cho yêu cầu {wo.work_order_id}", wo.work_order_id)
        drafts = scope_advisor.propose(domain)
        version = self._store_scopes(wo, drafts)
        wo = self.store.get_work_order(wo.work_order_id)
        wo = self.store.transition_work_order(wo.work_order_id, W.SCOPE_PROPOSED, wo.version)
        self.approvals.request_scope_approval(wo.work_order_id, version)
        return ChatReply(text=detail + self._describe(drafts) + "\nHãy chọn phương án ở mục “Cần bạn quyết định”. "
                         "Tôi sẽ không bắt đầu làm khi bạn chưa đồng ý.",
                         actions=[UiAction(kind="view_scope", label="Xem và chọn phạm vi")])

    def _store_scopes(self, wo: WorkOrder, drafts) -> int:
        with self.db.tx() as c:
            v = (c.execute("SELECT COALESCE(MAX(version),0) FROM scopes WHERE work_order_id=?",
                           (wo.work_order_id,)).fetchone()[0]) + 1
            c.execute("UPDATE scopes SET status='superseded' WHERE work_order_id=? AND status='proposed'",
                      (wo.work_order_id,))
            for d in drafts:
                sid = new_id("SCP")
                c.execute("INSERT INTO scopes(scope_id,work_order_id,version,option_key,title_vi,effort,cost_note,created_at)"
                          " VALUES(?,?,?,?,?,?,?,?)", (sid, wo.work_order_id, v, d.option_key, d.title_vi, d.effort,
                                                       d.cost_note, utcnow()))
                for name, prio, note in d.features:
                    c.execute("INSERT INTO features VALUES(?,?,?,?,?)", (new_id("FT"), sid, name, prio, note))
        return v

    @staticmethod
    def _describe(drafts) -> str:
        label = {"MUST": "Bắt buộc", "SHOULD": "Nên có", "LATER": "Để sau", "DROP": "Không làm"}
        out = []
        for d in drafts:
            out.append(f"■ Phương án “{d.title_vi}” — quy mô {d.effort} (XS nhỏ … XL lớn). {d.cost_note}")
            for prio in ("MUST", "SHOULD", "LATER", "DROP"):
                names = [n for n, p, _ in d.features if p == prio]
                if names:
                    out.append(f"   {label[prio]}: " + "; ".join(names))
        return "\n".join(out)

    def _approval_hint(self, project: Project | None, wo: WorkOrder | None) -> ChatReply:
        # A chat "đồng ý" is NOT an approval token (spec 2.2): only the GUI button can approve.
        if project and self.approvals.pending(project.project_id):
            return ChatReply(text="Để đảm bảo đúng ý bạn, việc đồng ý phải được bấm trực tiếp ở mục “Cần bạn quyết định” "
                                  "(tôi không thể nhận lời đồng ý bằng tin nhắn).",
                             actions=[UiAction(kind="view_scope", label="Mở mục quyết định")])
        return ChatReply(text="Hiện chưa có gì cần bạn đồng ý.")

    def _start(self, project: Project, wo: WorkOrder | None) -> ChatReply:
        if wo is None:
            return ChatReply(text="Chưa có công việc nào để bắt đầu. Hãy mô tả việc bạn muốn giao.")
        if wo.requires_scope_approval and not self.store.scope_approved(wo.work_order_id):
            return ChatReply(text="Tôi chưa thể bắt đầu vì phạm vi chưa được bạn duyệt. Hãy chọn phương án ở mục "
                                  "“Cần bạn quyết định”.", actions=[UiAction(kind="view_scope", label="Xem phạm vi")])
        return ChatReply(text="Phạm vi đã được duyệt. Việc lập kế hoạch và thực hiện sẽ có ở bước phát triển tiếp theo "
                              "(G3); hiện tôi chưa tự chạy công việc.")

    def _progress(self, project: Project) -> ChatReply:
        wos = self.store.list_work_orders(project.project_id)
        wos = [w for w in wos if w.kind != "general"]
        if not wos:
            return ChatReply(text="Chưa có công việc nào trong dự án này.")
        lines = [f"• {w.title[:60]} — {STATE_VI.get(w.state, w.state)}" for w in wos[-5:]]
        return ChatReply(text="Tình hình công việc:\n" + "\n".join(lines))
