from __future__ import annotations

import html

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMessageBox, QPushButton, QTextBrowser

from aatpo.customer.representative import STATE_VI as WO_STATE_VI
from aatpo.gui.pages.base import EmptyStatePage, Page, clear_layout
from aatpo.office.approvals import ApprovalError

STATE_VI = {
    "BACKLOG": "Chờ xếp lịch", "READY": "Sẵn sàng", "CLAIMED": "Đã nhận", "RUNNING": "Đang thực hiện",
    "OUTPUT_READY": "Có kết quả", "REVIEW": "Đang kiểm tra", "DONE": "Hoàn thành", "REWORK": "Cần làm lại",
    "BLOCKED": "Bị chặn", "PAUSED": "Tạm dừng", "FAILED": "Thất bại", "UNKNOWN_AFTER_CRASH": "Cần bạn xem lại",
}
PRIO_VI = {"MUST": "Bắt buộc", "SHOULD": "Nên có", "LATER": "Để sau", "DROP": "Không làm"}


class TasksPage(Page):
    title_vi = "Công việc"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.empty = QLabel("Chưa có công việc nào. Hãy mô tả việc bạn cần ở mục “Văn phòng AI”.")
        self.list = QListWidget()
        self.root.addWidget(self.empty)
        self.root.addWidget(self.list, 1)

    def refresh(self) -> None:
        p = self.services.registry.selected()
        wos = [w for w in self.services.store.list_work_orders(p.project_id) if w.kind != "general"] if p else []
        self.list.clear()
        for w in wos:
            self.list.addItem(f"{w.title[:80]} — {WO_STATE_VI.get(w.state, w.state)}")
            for t in self.services.store.list_tasks(p.project_id):
                if t.work_order_id == w.work_order_id:
                    self.list.addItem(f"      • {t.title} — {STATE_VI.get(t.state, t.state)}")
        self.empty.setVisible(not wos)


class ApprovalsPage(Page):
    title_vi = "Cần bạn quyết định"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.empty = QLabel("Hiện không có việc nào cần bạn quyết định.")
        self.root.addWidget(self.empty)
        self.list = QListWidget()
        self.list.setMaximumHeight(130)
        self.list.currentRowChanged.connect(self._show)
        self.root.addWidget(self.list)
        self.detail = QTextBrowser()
        self.root.addWidget(self.detail, 1)
        self.btn_row = QHBoxLayout()
        self.root.addLayout(self.btn_row)
        self.items = []

    def refresh(self) -> None:
        keep = self.list.currentRow()
        self.items = self.services.approvals.pending()
        self.list.clear()
        names = {p.project_id: p.display_name for p in self.services.registry.list(include_archived=True)}
        for a in self.items:
            self.list.addItem(f"[{names.get(a.project_id, '?')}] {a.action_text}")
        self.empty.setVisible(not self.items)
        self.list.setVisible(bool(self.items))
        self.detail.setVisible(bool(self.items))
        if self.items:
            self.list.setCurrentRow(min(max(keep, 0), len(self.items) - 1))
        else:
            self._clear_buttons()

    def _clear_buttons(self) -> None:
        clear_layout(self.btn_row)

    def _show(self, row: int) -> None:
        self._clear_buttons()
        if not (0 <= row < len(self.items)):
            self.detail.clear()
            return
        a = self.items[row]
        proj = self.services.registry.get(a.project_id)
        parts = [f"<h3>{html.escape(a.action_text)}</h3>",
                 f"<p><b>Dự án:</b> {html.escape(proj.display_name)}<br><b>Thư mục:</b> {html.escape(proj.root_path)}</p>",
                 f"<p><b>Điều gì xảy ra nếu bạn đồng ý:</b> {html.escape(a.consequences)}</p>"]
        with self.services.db.lock:
            scopes = self.services.db.conn.execute(
                "SELECT * FROM scopes WHERE work_order_id=? AND version=? ORDER BY option_key DESC",
                (a.work_order_id, a.scope_version)).fetchall()
            for s in scopes:
                feats = self.services.db.conn.execute("SELECT * FROM features WHERE scope_id=?", (s["scope_id"],)).fetchall()
                parts.append(f"<h4>Phương án “{html.escape(s['title_vi'])}” — quy mô {s['effort']}</h4>"
                             f"<p>{html.escape(s['cost_note'])}</p><ul>")
                for prio in ("MUST", "SHOULD", "LATER", "DROP"):
                    for f in feats:
                        if f["priority"] == prio:
                            note = f" ({html.escape(f['note'])})" if f["note"] else ""
                            parts.append(f"<li><b>{PRIO_VI[prio]}:</b> {html.escape(f['name'])}{note}</li>")
                parts.append("</ul>")
        self.detail.setHtml("".join(parts))
        for o in a.options:
            b = QPushButton(f"Đồng ý — {o['title']}")
            b.clicked.connect(lambda _=False, ap=a, key=o["key"], t=o["title"]: self.decide(ap, True, key, t))
            self.btn_row.addWidget(b)
        no = QPushButton("Không đồng ý")
        no.clicked.connect(lambda _=False, ap=a: self.decide(ap, False, None, None))
        self.btn_row.addWidget(no)
        self.btn_row.addStretch(1)

    def confirm(self, text: str) -> bool:
        return QMessageBox.question(self, "Xác nhận quyết định", text, QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No) == QMessageBox.Yes

    def decide(self, a, approve: bool, key: str | None, title: str | None) -> None:
        proj = self.services.registry.get(a.project_id)
        what = (f"Bạn đồng ý phương án “{title}” (phiên bản {a.scope_version}) cho dự án “{proj.display_name}”?"
                if approve else f"Bạn KHÔNG đồng ý phạm vi này cho dự án “{proj.display_name}”?")
        if not self.confirm(what):
            return
        try:
            self.services.approvals.decide(a.approval_id, approve, key)
        except ApprovalError as e:
            QMessageBox.warning(self, "AATPO", str(e))
        else:
            msg = (f"Đã ghi nhận: bạn đồng ý phương án “{title}”. Việc lập kế hoạch sẽ có ở bước phát triển tiếp theo."
                   if approve else "Đã ghi nhận: bạn không đồng ý phạm vi này. Hãy cho tôi biết bạn muốn điều chỉnh gì.")
            self.services.chat.save(a.project_id, "assistant", msg, a.work_order_id, kind="approval_result")
        self.win.refresh_all()


class ResultsPage(EmptyStatePage):
    title_vi = "Kết quả"
    message = "Chưa có kết quả nào để xem."
