from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QTextBrowser,
    QVBoxLayout,
)

from aatpo.customer.representative import STATE_VI
from aatpo.domain.models import WorkOrderState as W
from aatpo.evidence import artifacts
from aatpo.gui.pages.base import Page
from aatpo.gui.widgets.flow_layout import FlowLayout

SHOWN = (W.DELIVERED, W.ACCEPTED, W.PACKAGING)


class ResultsPage(Page):
    """Kết quả: simple report first; open folder / diff summary / save / copy / request revision. Nothing is run."""
    title_vi = "Kết quả"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.empty = QLabel("Chưa có kết quả nào để xem. Khi một công việc hoàn thành, báo cáo sẽ hiện ở đây.")
        self.root.addWidget(self.empty)
        self.list = QListWidget()
        self.list.setMaximumHeight(110)
        self.list.currentRowChanged.connect(self._show)
        self.root.addWidget(self.list)
        self.report = QTextBrowser()
        self.report.setOpenLinks(False)
        self.root.addWidget(self.report, 1)
        bar = FlowLayout()
        self.btn = {}
        for key, text, fn in (("folder", "Mở thư mục dự án", self.open_folder), ("diff", "Xem thay đổi", self.show_diff),
                              ("save", "Lưu báo cáo…", self.save_report), ("copy", "Sao chép báo cáo", self.copy_report),
                              ("revise", "Yêu cầu chỉnh sửa", self.request_revision), ("accept", "Chấp nhận kết quả", self.accept_result)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
            self.btn[key] = b
        bar.addStretch(1)
        self.root.addLayout(bar)
        self.items = []

    # ---- data -------------------------------------------------------------------------------------------
    def refresh(self) -> None:
        p = self.services.registry.selected()
        keep = self.list.currentRow()
        self.items = [w for w in self.services.store.list_work_orders(p.project_id) if w.state in SHOWN and w.kind != "general"] if p else []
        self.list.clear()
        for w in self.items:
            self.list.addItem(f"{w.title[:70]} — {STATE_VI.get(w.state, w.state)}")
        self.empty.setVisible(not self.items)
        for wdg in (self.list, self.report):
            wdg.setVisible(bool(self.items))
        if self.items:
            self.list.setCurrentRow(min(max(keep, 0), len(self.items) - 1))
        else:
            self.report.clear()
            self._buttons(None)

    def current(self):
        r = self.list.currentRow()
        return self.items[r] if 0 <= r < len(self.items) else None

    def report_text(self, wo_id: str) -> str | None:
        for t in reversed(self.services.store.list_work_order_tasks(wo_id)):
            a = artifacts.latest(self.services.db, t.task_id, "report")
            if a:
                return artifacts.read(self.services.db, a["artifact_id"])
        return None

    def _show(self, row: int) -> None:
        wo = self.current()
        self._buttons(wo)
        if wo is None:
            self.report.clear()
            return
        text = self.report_text(wo.work_order_id)
        if text is None:
            text = (f"# {wo.title}\n\nCông việc đang ở trạng thái **{STATE_VI.get(wo.state, wo.state)}**. "
                    f"{wo.integration_note or ''}\n\nBáo cáo bàn giao sẽ có khi mọi việc đã xong và được tích hợp an toàn.")
        self.report.setMarkdown(text)

    def _buttons(self, wo) -> None:
        has = wo is not None
        report = bool(has and self.report_text(wo.work_order_id))
        self.btn["folder"].setEnabled(has)
        self.btn["save"].setEnabled(report)
        self.btn["copy"].setEnabled(report)
        self.btn["revise"].setEnabled(has)
        self.btn["diff"].setEnabled(bool(has and self._range(wo.work_order_id)))
        self.btn["accept"].setEnabled(bool(has and wo.state == W.DELIVERED))

    # ---- actions ---------------------------------------------------------------------------------------------
    def open_folder(self) -> None:
        wo = self.current()
        if wo:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.services.registry.get(wo.project_id).root_path))   # opens Explorer only

    def _range(self, wo_id: str):
        with self.services.db.lock:
            rows = self.services.db.conn.execute("SELECT * FROM git_branches WHERE work_order_id=? ORDER BY created_at, rowid", (wo_id,)).fetchall()
            tip = self.services.db.conn.execute("SELECT sha FROM git_commit_events WHERE branch=? AND status='committed' "
                                                "ORDER BY at DESC, rowid DESC LIMIT 1", (rows[-1]["name"],)).fetchone() if rows else None
        return (rows[0]["base_sha"], tip["sha"]) if rows and tip and rows[0]["base_sha"] else None

    def diff_text(self, wo_id: str) -> str:
        r = self._range(wo_id)
        if not r:
            return "Lần này không có thay đổi tệp nào được lưu (chế độ chỉ đọc hoặc chưa có phiên bản)."
        root = Path(self.services.registry.get(self.services.store.get_work_order(wo_id).project_id).root_path)
        return (self.services.git.diff_range(root, *r, stat=True) + "\n" + self.services.git.diff_range(root, *r))

    def _dialog(self, title: str, text: str) -> None:
        d = QDialog(self)
        d.setWindowTitle(title)
        d.resize(820, 520)
        lay = QVBoxLayout(d)
        box = QPlainTextEdit(text)
        box.setReadOnly(True)
        lay.addWidget(box)
        close = QPushButton("Đóng")
        close.clicked.connect(d.accept)
        lay.addWidget(close)
        self.last_dialog = d
        d.exec()

    def show_diff(self) -> None:
        wo = self.current()
        if wo:
            self._dialog("Các thay đổi đã lưu", self.diff_text(wo.work_order_id))

    def save_report(self) -> None:
        wo = self.current()
        text = self.report_text(wo.work_order_id) if wo else None
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu báo cáo", "bao-cao.md", "Markdown (*.md);;Văn bản (*.txt)")
        if path:
            Path(path).write_text(text, encoding="utf-8")

    def copy_report(self) -> None:
        wo = self.current()
        text = self.report_text(wo.work_order_id) if wo else None
        if text:
            QGuiApplication.clipboard().setText(text)

    def request_revision(self) -> None:
        wo = self.current()
        if wo:
            self.win.go("home")
            self.win.pages["home"].send_text(f"Sửa lại {wo.title[:60]}: ")   # trailing space => prefill for the user to finish

    def accept_result(self) -> None:
        wo = self.current()
        if wo and QMessageBox.question(self, "Chấp nhận kết quả", "Bạn chấp nhận kết quả của công việc này?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.services.store.transition_work_order(wo.work_order_id, W.ACCEPTED, wo.version)
            self.win.refresh_all()
