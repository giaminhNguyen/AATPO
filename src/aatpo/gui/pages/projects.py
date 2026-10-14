from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QHeaderView, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
)

from aatpo.gui.pages.base import Page
from aatpo.projects.registry import RegistryError
from aatpo.gui.widgets.flow_layout import FlowLayout


def parse_command(text: str) -> list[str]:
    """Split on spaces, honouring double quotes; no shell is involved anywhere."""
    out, cur, quoted = [], "", False
    for ch in text.strip():
        if ch == '"':
            quoted = not quoted
        elif ch == " " and not quoted:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def join_command(argv: list[str]) -> str:
    return " ".join(f'"{a}"' if " " in a else a for a in argv)


class ConfirmProjectDialog(QDialog):
    """Shows the resolved absolute path and the one-time version-history consent."""

    def __init__(self, parent, path: Path, repo_note: str, default_name: str, ask_history: bool):
        super().__init__(parent)
        self.setWindowTitle("Xác nhận dự án")
        form = QFormLayout(self)
        self.name = QLineEdit(default_name)
        form.addRow("Tên dự án:", self.name)
        loc = QLabel(str(path))
        loc.setWordWrap(True)
        form.addRow("Thư mục:", loc)
        form.addRow("", QLabel(repo_note))
        self.history = QCheckBox("Tự động lưu lịch sử phiên bản (khuyên dùng)")
        self.history.setChecked(ask_history)
        self.history.setVisible(ask_history)
        form.addRow(self.history)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Xác nhận")
        bb.button(QDialogButtonBox.Cancel).setText("Hủy")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)


class ProjectsPage(Page):
    title_vi = "Dự án"

    def __init__(self, services, window):
        super().__init__(services, window)
        bar = FlowLayout()
        for text, fn in (("Mở dự án có sẵn…", self.add_existing), ("Tạo dự án mới…", self.create_new),
                         ("Chọn làm dự án hiện tại", self.select_current), ("Liên kết lại thư mục…", self.relink),
                         ("Lịch sử phiên bản…", self.show_history), ("Lệnh kiểm thử…", self.set_test_command), ("Tên người lưu phiên bản…", self.set_identity),
                         ("Lưu trữ", self.archive)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch(1)
        self.root.addLayout(bar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Tên dự án", "Thư mục", "Trạng thái", "Lịch sử phiên bản"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.root.addWidget(self.table, 1)
        self.table.doubleClicked.connect(lambda *_: self.select_current())

    # -- helpers --
    def _selected_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(256) if rows else None

    def _warn(self, msg: str) -> None:
        QMessageBox.warning(self, "AATPO", msg)

    def refresh(self) -> None:
        reg, cur = self.services.registry, self.services.registry.selected()
        projects = reg.list()
        self.table.setRowCount(len(projects))
        for i, p in enumerate(projects):
            if reg.path_missing(p):
                state = "Không tìm thấy thư mục dự án"
            else:
                state = "Đang dùng" if cur and cur.project_id == p.project_id else "Sẵn sàng"
            hist = "Bật" if p.git_auto_history else ("Có sẵn (giữ nguyên)" if p.repo_detected else "Tắt")
            for j, v in enumerate((p.display_name, p.root_path, state, hist)):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setData(256, p.project_id)
                self.table.setItem(i, j, it)

    # -- actions --
    def _confirm(self, path: Path, default_name: str, new_project: bool) -> tuple[str, bool] | None:
        git = self.services.git
        info = git.detect(path) if git.available else None
        if info and info.is_repo:
            note, ask = f"Đã có lịch sử phiên bản tại: {info.root}. AATPO sẽ giữ nguyên.", False
        elif not git.available:
            note, ask = "Chưa cài Git nên chưa thể lưu lịch sử phiên bản.", False
        else:
            note, ask = "Thư mục này chưa có lịch sử phiên bản.", True
        dlg = ConfirmProjectDialog(self, path, note, default_name, ask)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.name.text(), (dlg.history.isChecked() if ask else False)

    def add_existing(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục dự án")
        if not d:
            return
        path = Path(d).resolve()
        got = self._confirm(path, path.name, False)
        if got:
            self._do(lambda: self.services.registry.register(path, got[0], auto_history=got[1]))

    def create_new(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Chọn (hoặc tạo) thư mục cho dự án mới")
        if not d:
            return
        path, nonempty = Path(d).resolve(), False
        if any(path.iterdir()):
            nonempty = QMessageBox.question(
                self, "Thư mục không trống",
                "Thư mục này đã có tệp. AATPO sẽ KHÔNG ghi đè tệp có sẵn.\nBạn vẫn muốn dùng thư mục này?"
            ) == QMessageBox.Yes
            if not nonempty:
                return
        got = self._confirm(path, path.name, True)
        if got:
            self._do(lambda: self.services.registry.create_new(
                path, got[0], auto_history=got[1], allow_nonempty=nonempty))

    def _do(self, fn) -> None:
        try:
            p = fn()
            self.services.registry.select(p.project_id)
        except RegistryError as e:
            self._warn(str(e))
        self.win.refresh_all()

    def select_current(self) -> None:
        pid = self._selected_id()
        if pid:
            try:
                self.services.registry.select(pid)
            except RegistryError as e:
                self._warn(str(e))
            self.win.refresh_all()

    def relink(self) -> None:
        pid = self._selected_id()
        d = pid and QFileDialog.getExistingDirectory(self, "Chọn thư mục mới của dự án")
        if d:
            self._do_relink(pid, d)

    def _do_relink(self, pid: str, d: str) -> None:
        try:
            self.services.registry.relink(pid, d)
        except RegistryError as e:
            self._warn(str(e))
        self.win.refresh_all()

    def show_history(self) -> None:
        pid = self._selected_id()
        if pid:
            from aatpo.gui.pages.history import HistoryDialog
            self.last_dialog = HistoryDialog(self, self.services, self.services.registry.get(pid), on_change=self.win.refresh_all)
            self.last_dialog.exec()

    def ask_text(self, title: str, label: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, title, label, QLineEdit.Normal, default)
        return text if ok else None

    def set_test_command(self) -> None:
        """User confirms (or edits) the command AATPO may run as test evidence. Only allowlisted launchers are accepted."""
        pid = self._selected_id()
        if not pid:
            return
        from aatpo.evidence.tests import CommandRejected, detect_command
        p = self.services.registry.get(pid)
        cur = p.test_command or detect_command(Path(p.root_path)) or []
        text = self.ask_text("Lệnh kiểm thử", "Lệnh chạy kiểm thử của dự án (để trống = không có):", join_command(cur))
        if text is None:
            return
        try:
            self.services.registry.set_test_command(pid, parse_command(text) or None)
        except (CommandRejected, ValueError) as e:
            self._warn(str(e))
        self.win.refresh_all()

    def set_identity(self) -> None:
        pid = self._selected_id()
        if not pid:
            return
        p = self.services.registry.get(pid)
        name = self.ask_text("Người lưu phiên bản", "Tên sẽ ghi trong lịch sử phiên bản của dự án này:")
        email = self.ask_text("Người lưu phiên bản", "Email sẽ ghi trong lịch sử phiên bản (chỉ áp dụng cho dự án này):") if name else None
        if name and email:
            from aatpo.projects.git_service import GitError
            try:
                self.services.git.set_local_identity(Path(p.root_path), name, email)
            except GitError as e:
                self._warn(str(e))

    def archive(self) -> None:
        pid = self._selected_id()
        if pid and QMessageBox.question(self, "Lưu trữ dự án",
                                        "Dự án sẽ được ẩn khỏi danh sách. Tệp trên ổ đĩa KHÔNG bị xóa.\nTiếp tục?"
                                        ) == QMessageBox.Yes:
            self.services.registry.archive(pid)
            self.win.refresh_all()
