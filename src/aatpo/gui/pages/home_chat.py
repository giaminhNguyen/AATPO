from __future__ import annotations

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from aatpo.gui.pages.base import Page


class HomePage(Page):
    title_vi = "Văn phòng AI"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.welcome = QLabel("Xin chào! Bạn muốn AATPO giúp gì hôm nay?")
        self.root.addWidget(self.welcome)
        self.active = QLabel()
        self.active.setWordWrap(True)
        self.root.addWidget(self.active)

        quick = QHBoxLayout()
        for text, fn in (("Tạo dự án", lambda: self._go_projects(True)),
                         ("Mở dự án", lambda: self._go_projects(False)),
                         ("Giao việc mới", lambda: self.win.go("tasks")),
                         ("Tiếp tục công việc", lambda: self.win.go("tasks"))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            quick.addWidget(b)
        quick.addStretch(1)
        self.root.addLayout(quick)

        box = QGroupBox("Kiểm tra lần đầu")
        self.checks = QVBoxLayout(box)
        self.root.addWidget(box)

        # Honest placeholder: conversation is milestone G2, not faked here.
        self.chat = QLineEdit()
        self.chat.setPlaceholderText("Mô tả công việc của bạn… (tính năng trò chuyện sẽ có ở bước G2)")
        self.chat.setEnabled(False)
        self.root.addStretch(1)
        self.root.addWidget(self.chat)

    def _go_projects(self, create: bool) -> None:
        self.win.go("projects")
        (self.win.pages["projects"].create_new if create else self.win.pages["projects"].add_existing)()

    def refresh(self) -> None:
        p = self.services.registry.selected()
        self.active.setText(f"Dự án đang dùng: {p.display_name}\n{p.root_path}" if p
                            else "Chưa chọn dự án. Hãy bấm “Mở dự án” hoặc “Tạo dự án”.")
        while self.checks.count():
            self.checks.takeAt(0).widget().deleteLater()
        for label, ok, hint in self.services.readiness():
            self.checks.addWidget(QLabel(f"{'✔' if ok else '✖'} {label}: {hint}"))
