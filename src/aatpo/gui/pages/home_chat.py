from __future__ import annotations

import html

from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from aatpo.domain.contracts import ChatReply, UiAction
from aatpo.gui.pages.base import Page, clear_layout

WELCOME = "Xin chào! Bạn muốn AATPO giúp gì hôm nay?"


class HomePage(Page):
    title_vi = "Văn phòng AI"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.active = QLabel()
        self.active.setWordWrap(True)
        self.root.addWidget(self.active)

        quick = QHBoxLayout()
        for text, fn in (("Tạo dự án", lambda: self._go_projects(True)),
                         ("Mở dự án", lambda: self._go_projects(False)),
                         ("Giao việc mới", lambda: self.send_text("Tôi cần làm ")),
                         ("Tiếp tục công việc", lambda: self.send_text("Cho tôi xem đã làm gì"))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            quick.addWidget(b)
        quick.addStretch(1)
        self.root.addLayout(quick)

        self.transcript = QTextBrowser()
        self.transcript.setOpenLinks(False)
        self.root.addWidget(self.transcript, 1)

        self.chips_box = QWidget()
        self.chips = QHBoxLayout(self.chips_box)
        self.chips.setContentsMargins(0, 0, 0, 0)
        self.root.addWidget(self.chips_box)

        self.busy = QLabel("")
        self.root.addWidget(self.busy)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Mô tả công việc của bạn…")
        self.input.returnPressed.connect(self.on_send)
        self.send_btn = QPushButton("Gửi")
        self.send_btn.clicked.connect(self.on_send)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        self.root.addLayout(row)

        box = QGroupBox("Kiểm tra lần đầu")
        self.checks = QVBoxLayout(box)
        self.root.addWidget(box)
        self.pending = False
        self.win.jobs.finished.connect(self._on_job)

    # ---- sending ------------------------------------------------------------------------------
    def on_send(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.send_text(text, autosend=True)

    def send_text(self, text: str, autosend: bool = True) -> None:
        if not autosend or text.endswith(" "):  # prefill templates like "Tôi cần làm " for the user to finish
            self.input.setText(text)
            self.input.setFocus()
            return
        if self.pending:
            return
        self.pending = True
        self.send_btn.setEnabled(False)
        self.busy.setText("Đang xử lý yêu cầu của bạn…")
        self._append("Bạn", text)
        self.win.jobs.submit("chat", lambda: self.services.chat.handle(text))

    def _on_job(self, key: str, result, exc) -> None:
        if key != "chat":
            return
        self.pending = False
        self.send_btn.setEnabled(True)
        self.busy.setText("")
        reply = result if exc is None else ChatReply(text="Xin lỗi, đã có lỗi. Bạn hãy thử lại.")
        self._append("AATPO", reply.text)
        self._show_chips(reply.actions)
        self.win.refresh_all()

    # ---- rendering -------------------------------------------------------------------------------
    def _append(self, who: str, text: str) -> None:
        self.transcript.append(f"<p><b>{html.escape(who)}:</b> {html.escape(text).replace(chr(10), '<br>')}</p>")

    def _show_chips(self, actions: list[UiAction]) -> None:
        clear_layout(self.chips)
        for a in actions:
            b = QPushButton(a.label)
            b.clicked.connect(lambda _=False, act=a: self.run_action(act))
            self.chips.addWidget(b)
        self.chips.addStretch(1)

    def run_action(self, a: UiAction) -> None:
        reg = self.services.registry
        if a.kind == "quick_reply":
            self.send_text(a.payload["text"])
        elif a.kind == "pick_folder_create":
            self.win.go("projects")
            self.win.pages["projects"].create_new()
        elif a.kind == "pick_folder_open":
            self.win.go("projects")
            self.win.pages["projects"].add_existing()
        elif a.kind == "pick_project":
            self.win.go("projects")
        elif a.kind == "switch_project":
            reg.select(a.payload["project_id"])  # explicit user click, never implicit
            self.win.refresh_all()
            if a.payload.get("text"):
                self.send_text(a.payload["text"])
        elif a.kind == "view_scope":
            self.win.go("approvals")
        elif a.kind == "view_progress":
            self.win.go("tasks")

    def _go_projects(self, create: bool) -> None:
        self.win.go("projects")
        (self.win.pages["projects"].create_new if create else self.win.pages["projects"].add_existing)()

    def refresh(self) -> None:
        p = self.services.registry.selected()
        self.active.setText(f"Dự án đang dùng: {p.display_name}\n{p.root_path}" if p
                            else "Chưa chọn dự án. Hãy bấm “Mở dự án” hoặc “Tạo dự án”.")
        self.transcript.clear()
        self.transcript.append(f"<p>{html.escape(WELCOME)}</p>")
        if p:
            for role, text in self.services.chat.history(p.project_id):
                if role in ("customer", "assistant"):
                    self._append("Bạn" if role == "customer" else "AATPO", text)
        clear_layout(self.checks)
        for label, ok, hint in self.services.readiness():
            self.checks.addWidget(QLabel(f"{'✔' if ok else '✖'} {label}: {hint}"))
