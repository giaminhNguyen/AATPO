from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from aatpo.projects.history import friendly, history_rows, propose_undo


class HistoryDialog(QDialog):
    """Xem lịch sử thay đổi: friendly labels first, hashes/branches behind a 'technical details' switch."""

    def __init__(self, parent, services, project, on_change=None):
        super().__init__(parent)
        self.services, self.project, self.on_change = services, project, on_change
        self.setWindowTitle(f"Lịch sử phiên bản — {project.display_name}")
        self.resize(900, 520)
        lay = QVBoxLayout(self)
        self.rows = history_rows(services, project)
        self.note = QLabel("" if self.rows else "Dự án này chưa có lịch sử phiên bản để hiển thị.")
        lay.addWidget(self.note)
        self.table = QTableWidget(len(self.rows), 5)
        self.table.setHorizontalHeaderLabels(["Thời gian", "Phiên bản", "Công việc liên quan", "Mã", "Nhánh"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        for i, r in enumerate(self.rows):
            for j, v in enumerate((r["date"], friendly(r), r["wo_title"] or "", r["sha"][:10], r["branch"] or "")):
                self.table.setItem(i, j, QTableWidgetItem(v))
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 380)
        self.table.setColumnWidth(2, 220)
        lay.addWidget(self.table, 1)
        self.adv = QCheckBox("Chi tiết kỹ thuật (mã phiên bản, nhánh)")
        self.adv.toggled.connect(self._toggle)
        lay.addWidget(self.adv)
        self._toggle(False)
        bar = QHBoxLayout()
        self.undo = QPushButton("Đề xuất hoàn tác phiên bản đã chọn")
        self.undo.clicked.connect(self.propose)
        close = QPushButton("Đóng")
        close.clicked.connect(self.accept)
        bar.addWidget(self.undo)
        bar.addStretch(1)
        bar.addWidget(close)
        lay.addLayout(bar)

    def _toggle(self, on: bool) -> None:
        self.table.setColumnHidden(3, not on)
        self.table.setColumnHidden(4, not on)

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.rows[rows[0].row()] if rows else None

    def propose(self) -> None:
        r = self.selected()
        if r is None:
            QMessageBox.information(self, "AATPO", "Hãy chọn một phiên bản trong danh sách.")
            return
        try:
            propose_undo(self.services, self.project, r["sha"])
        except Exception as e:
            QMessageBox.warning(self, "AATPO", str(e))
            return
        QMessageBox.information(self, "AATPO", "Đã tạo đề xuất hoàn tác. Hãy xem và quyết định ở mục “Cần bạn quyết định”. "
                                               "Chưa có gì bị thay đổi.")
        if self.on_change:
            self.on_change()
