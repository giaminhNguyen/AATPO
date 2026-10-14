from __future__ import annotations

import html

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from aatpo.customer.representative import STATE_VI as WO_STATE_VI
from aatpo.domain.models import ROLE_TITLES_VI, TaskState as T, WorkOrderState as W
from aatpo.evidence import artifacts
from aatpo.gui.pages.base import Page, clear_layout
from aatpo.office.approvals import ApprovalError
from aatpo.gui.widgets.flow_layout import FlowLayout

STATE_VI = {
    "BACKLOG": "Chờ xếp lịch", "READY": "Sẵn sàng", "CLAIMED": "Đã nhận", "RUNNING": "Đang thực hiện",
    "OUTPUT_READY": "Có kết quả", "REVIEW": "Đang kiểm tra", "DONE": "Hoàn thành", "REWORK": "Cần làm lại",
    "BLOCKED": "Bị chặn", "PAUSED": "Tạm dừng", "FAILED": "Thất bại", "UNKNOWN_AFTER_CRASH": "Cần bạn xem lại",
}
PRIO_VI = {"MUST": "Bắt buộc", "SHOULD": "Nên có", "LATER": "Để sau", "DROP": "Không làm"}
NEW_WORK = {W.SCOPE_CONFIRMED, W.PLANNED}
HALTED = {W.PAUSED_QUOTA, W.BLOCKED, W.PAUSED_APPROVAL}


class TasksPage(Page):
    title_vi = "Công việc"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.empty = QLabel("Chưa có công việc nào. Hãy mô tả việc bạn cần ở mục “Văn phòng AI”.")
        self.root.addWidget(self.empty)
        bar = FlowLayout()
        self.btn = {}
        for key, text, fn in (("start", "Bắt đầu", self.start_selected), ("pause", "Tạm dừng", self.pause_selected),
                              ("resume", "Tiếp tục", self.resume_selected), ("detail", "Xem chi tiết", self.show_detail),
                              ("result", "Xem kết quả", self.show_result),
                              ("integrate", "Tích hợp vào nhánh chính", self.integrate_selected)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
            self.btn[key] = b
        bar.addStretch(1)
        self.root.addLayout(bar)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.live = QLabel("")
        self.root.addWidget(self.live)
        self.root.addWidget(self.status)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Công việc", "Người phụ trách", "Trạng thái"])
        hh = self.tree.header()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self._update_buttons)
        self.root.addWidget(self.tree, 1)
        self.running: set[str] = set()      # work orders with a live background job
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.win.jobs.finished.connect(self._on_job)

    # ---- selection / rendering ---------------------------------------------------------------------
    def selected_wo(self) -> str | None:
        it = self.tree.currentItem()
        if it is None:
            return None
        return it.data(0, 256) if it.parent() is None else it.parent().data(0, 256)

    def refresh(self) -> None:
        p = self.services.registry.selected()
        keep = self.selected_wo()
        st, mgr = self.services.store, self.services.manager
        wos = [w for w in st.list_work_orders(p.project_id) if w.kind != "general"] if p else []
        self.tree.clear()
        for w in wos:
            plan_v = mgr._current_plan_version(w.work_order_id)
            tasks = [t for t in st.list_work_order_tasks(w.work_order_id) if t.plan_version == plan_v]
            prog = f"  ({sum(t.state == T.DONE for t in tasks)}/{len(tasks)} việc xong)" if tasks else ""
            label = WO_STATE_VI.get(w.state, w.state)
            if w.state == W.EXECUTING and tasks and all(t.state == T.DONE for t in tasks) and w.work_order_id not in self.running:
                label = "Các việc đã xong, chờ đóng gói báo cáo"   # report/delivery arrives with G4
            top = QTreeWidgetItem([w.title[:80], "", label + prog])
            top.setData(0, 256, w.work_order_id)
            self.tree.addTopLevelItem(top)
            for t in tasks:
                top.addChild(QTreeWidgetItem([t.title, ROLE_TITLES_VI.get(t.role_id or "", ""), self._task_state(t)]))
            top.setExpanded(True)
            if w.work_order_id == keep or (keep is None and w is wos[-1]):
                self.tree.setCurrentItem(top)
        self.empty.setVisible(not wos)
        self.tree.setVisible(bool(wos))
        self._update_buttons()
        if self.running and not self.timer.isActive():
            self.timer.start()
        elif not self.running:
            self.timer.stop()
        self.live.setText("Đang có tiến trình thật chạy ngầm…" if self._any_running_run() else "")

    @staticmethod
    def _task_state(t) -> str:
        s = STATE_VI.get(t.state, t.state)
        return f"{s} — {t.blocked_reason}" if t.state == T.BLOCKED and t.blocked_reason else s

    def _any_running_run(self) -> bool:
        with self.services.db.lock:
            return self.services.db.conn.execute("SELECT 1 FROM process_runs WHERE state='RUNNING' LIMIT 1").fetchone() is not None

    def _update_buttons(self) -> None:
        wid = self.selected_wo()
        wo = self.services.store.get_work_order(wid) if wid else None
        live = bool(wid) and wid in self.running
        tasks = self.services.store.list_work_order_tasks(wid) if wid else []
        stuck = any(t.state in (T.PAUSED, T.BLOCKED, T.UNKNOWN_AFTER_CRASH) for t in tasks)
        self.btn["start"].setEnabled(bool(wo and not live and wo.state in NEW_WORK))
        self.btn["pause"].setEnabled(live)
        self.btn["resume"].setEnabled(bool(wo and not live and (wo.state in HALTED or (wo.state == W.EXECUTING and stuck))))
        self.btn["detail"].setEnabled(wo is not None)
        self.btn["integrate"].setEnabled(bool(wo and wo.state in (W.PACKAGING, W.DELIVERED)
                                              and wo.integration_status in ("ready", "conflict")))
        self.btn["result"].setEnabled(bool(wid and any(artifacts.latest(self.services.db, t.task_id) for t in tasks)))

    # ---- actions ------------------------------------------------------------------------------------
    def start_selected(self) -> None:
        wid = self.selected_wo()
        if wid:
            self.start(wid)

    def start(self, wid: str) -> None:
        """Safe start: the manager refuses anything whose scope is not approved."""
        mgr, wo = self.services.manager, self.services.store.get_work_order(wid)
        try:
            if wo.state == W.SCOPE_CONFIRMED:
                mgr.create_plan(wid)
        except Exception as e:
            QMessageBox.warning(self, "AATPO", str(e))
            return
        if wid in self.running:
            return
        self.running.add(wid)
        self.status.setText("")
        self.win.jobs.submit(f"run:{wid}", lambda: mgr.run_work_order(wid))
        self.refresh()

    def pause_selected(self) -> None:
        wid = self.selected_wo()
        if wid:
            self.status.setText("Đang yêu cầu dừng an toàn…")
            self.win.jobs.submit(f"pause:{wid}", lambda: self.services.manager.pause(wid))

    def resume_selected(self) -> None:
        wid = self.selected_wo()
        if wid:
            self.services.manager.resume(wid)
            self.start(wid)

    def integrate_selected(self) -> None:
        wid = self.selected_wo()
        if not wid:
            return
        wo = self.services.store.get_work_order(wid)
        proj = self.services.registry.get(wo.project_id)
        if QMessageBox.question(self, "Tích hợp vào nhánh chính",
                                f"AATPO sẽ gộp các thay đổi đã kiểm tra vào nhánh “{proj.git_default_branch or 'chính'}” của dự án "
                                f"“{proj.display_name}” theo kiểu gộp thẳng (không ghi đè, không xóa lịch sử). Bạn đồng ý?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        res = self.services.manager.integrate_now(wid)
        self.status.setText("" if res.outcome == "completed" else res.message)
        self.win.refresh_all()

    def _on_job(self, key: str, result, exc) -> None:
        if key.startswith("run:"):
            self.running.discard(key[4:])
            if exc is not None:
                QMessageBox.warning(self, "AATPO", f"Không thể thực hiện: {exc}\n\nChi tiết kỹ thuật đã được ghi vào:\n"
                                    f"{self.services.paths.home / 'logs' / 'errors.log'}")
            elif result is not None:
                self.status.setText(result.message if result.outcome in ("blocked", "paused_quota", "needs_review") else "")
            self.win.refresh_all()
        elif key.startswith("pause:"):
            self.win.refresh_all()

    # ---- detail / results ---------------------------------------------------------------------------
    def detail_text(self, wid: str) -> str:
        st, db = self.services.store, self.services.db
        wo = st.get_work_order(wid)
        modes = {"fast_lane": "Nhanh", "standard": "Tiêu chuẩn", "full": "Đầy đủ"}
        out = [wo.title, f"Trạng thái: {WO_STATE_VI.get(wo.state, wo.state)}",
               f"Chế độ làm việc: {modes.get(wo.plan_mode or '', 'chưa lập kế hoạch')}", ""]
        for t in st.list_work_order_tasks(wid):
            line = f"• {t.title} — {self._task_state(t)}"
            if t.rework_count:
                line += f" (làm lại {t.rework_count} lần)"
            out.append(line)
            with db.lock:
                rv = db.conn.execute("SELECT verdict,findings FROM reviews WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                                     (t.task_id,)).fetchone()
                br = db.conn.execute("SELECT name FROM git_branches WHERE task_id=?", (t.task_id,)).fetchone()
            if rv:
                out.append(f"    Kiểm tra: {'đạt' if rv['verdict'] == 'pass' else 'chưa đạt'} — {rv['findings'][:160]}")
            if br:
                out.append(f"    Đã lưu phiên bản trên nhánh: {br['name']}")
        return "\n".join(out)

    def _dialog(self, title: str, text: str) -> None:
        d = QDialog(self)
        d.setWindowTitle(title)
        d.resize(720, 480)
        lay = QVBoxLayout(d)
        box = QPlainTextEdit(text)
        box.setReadOnly(True)
        lay.addWidget(box)
        close = QPushButton("Đóng")
        close.clicked.connect(d.accept)
        lay.addWidget(close)
        self.last_dialog = d
        d.exec()

    def show_detail(self) -> None:
        wid = self.selected_wo()
        if wid:
            self._dialog("Chi tiết công việc", self.detail_text(wid))

    def results_text(self, wid: str) -> str:
        parts = []
        for t in self.services.store.list_work_order_tasks(wid):
            a = artifacts.latest(self.services.db, t.task_id)
            if a:
                parts.append(f"=== {t.title} ({STATE_VI.get(t.state, t.state)}) ===\n{artifacts.read(self.services.db, a['artifact_id'])}")
        return "\n\n".join(parts)

    def show_result(self) -> None:
        wid = self.selected_wo()
        if wid:
            self._dialog("Kết quả đã lưu", self.results_text(wid))


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
        self.btn_row = FlowLayout()
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
        if a.kind == "rerun":
            parts.append("<p><b>Cảnh báo:</b> thao tác này có thể ghi trùng lên tệp. Hãy kiểm tra thư mục dự án trước.</p>")
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
        if a.kind == "revert":
            what = (f"Bạn đồng ý tạo MỘT phiên bản mới đảo ngược thay đổi này trong dự án “{proj.display_name}”? "
                    "Lịch sử cũ được giữ nguyên." if approve else "Bạn KHÔNG muốn hoàn tác thay đổi này?")
        elif a.kind == "rerun":
            what = (f"Bạn cho chạy lại công việc bị gián đoạn trong dự án “{proj.display_name}”? Thao tác có thể ghi trùng lên tệp."
                    if approve else "Bạn KHÔNG cho chạy lại công việc này (sẽ đánh dấu thất bại)?")
        else:
            what = (f"Bạn đồng ý phương án “{title}” (phiên bản {a.scope_version}) cho dự án “{proj.display_name}”?"
                    if approve else f"Bạn KHÔNG đồng ý phạm vi này cho dự án “{proj.display_name}”?")
        if not self.confirm(what):
            return
        try:
            self.services.approvals.decide(a.approval_id, approve, key)
        except ApprovalError as e:
            QMessageBox.warning(self, "AATPO", str(e))
        else:
            if a.kind == "scope":
                msg = (f"Đã ghi nhận: bạn đồng ý phương án “{title}”. Bấm “Bắt đầu” ở mục Công việc (hoặc nhắn “Bắt đầu làm”)."
                       if approve else "Đã ghi nhận: bạn không đồng ý phạm vi này. Hãy cho tôi biết bạn muốn điều chỉnh gì.")
                self.services.chat.save(a.project_id, "assistant", msg, a.work_order_id, kind="approval_result")
        self.win.refresh_all()
