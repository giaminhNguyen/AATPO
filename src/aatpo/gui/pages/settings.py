from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from aatpo.agents.smoke import run_readonly_smoke
from aatpo.cli.probe import STATUS_VI, probe_all
from aatpo.customer.intent_router import LLMIntentProposer, RuleIntentProposer
from aatpo.customer.llm_ask import make_asker, ready_provider
from aatpo.gui.pages.base import Page

NAMES = {"codex": "Codex", "claude": "Claude Code", "gemini": "Gemini", "fake": "Trợ lý giả lập"}
CONSENT = ("Yêu cầu thử này sẽ gửi nội dung thư mục dự án “{project}” ({path}) tới dịch vụ AI của {provider}.\n\n"
           "• Có thể được tính vào hạn mức sử dụng của bạn.\n"
           "• Trợ lý chỉ được ĐỌC, không được sửa tệp.\n\nBạn đồng ý tiếp tục?")


class SettingsPage(Page):
    title_vi = "Cài đặt & trợ lý AI"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.rows: dict[str, tuple[QLabel, QPushButton]] = {}
        self.running_run: str | None = None
        top = QHBoxLayout()
        self.recheck = QPushButton("Kiểm tra lại")
        self.recheck.clicked.connect(self.probe)
        top.addWidget(self.recheck)
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        top.addWidget(self.stop_btn)
        top.addStretch(1)
        self.root.addLayout(top)
        for pid in services.adapters:
            box = QGroupBox(NAMES.get(pid, pid))
            lay = QHBoxLayout(box)
            label = QLabel("…")
            btn = QPushButton("Thử một yêu cầu chỉ đọc…")
            btn.clicked.connect(lambda _=False, p=pid: self.on_smoke_clicked(p))
            lay.addWidget(label, 1)
            lay.addWidget(btn)
            self.rows[pid] = (label, btn)
            self.root.addWidget(box)
        self.llm = QCheckBox("Dùng trợ lý AI để hiểu câu lệnh phức tạp (tin nhắn của bạn sẽ được gửi tới dịch vụ AI)")
        self.llm.toggled.connect(self.on_llm_toggled)
        self.root.addWidget(self.llm)
        self.busy = QLabel("")
        self.root.addWidget(self.busy)
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("Kết quả thử sẽ hiện ở đây.")
        self.root.addWidget(self.answer, 1)
        self.adv = QGroupBox("Chi tiết kỹ thuật")
        self.adv.setCheckable(True)
        self.adv.setChecked(False)
        al = QVBoxLayout(self.adv)
        self.adv_text = QPlainTextEdit()
        self.adv_text.setReadOnly(True)
        al.addWidget(self.adv_text)
        self.adv_text.setVisible(False)
        self.adv.toggled.connect(self.adv_text.setVisible)
        self.root.addWidget(self.adv)
        self.win.jobs.finished.connect(self._on_job)

    # -- data --
    def refresh(self) -> None:
        stats = self.services.provider_statuses()
        has_project = self.services.registry.selected() is not None
        for pid, (label, btn) in self.rows.items():
            status, version = stats.get(pid, ("unknown", None))
            label.setText(f"{STATUS_VI.get(status, status)}" + (f"  —  {version}" if version else ""))
            btn.setEnabled(status == "ready" and has_project and self.running_run is None)
            btn.setToolTip("" if has_project else "Hãy chọn dự án trước")

    def probe(self) -> None:
        self.recheck.setEnabled(False)
        self.busy.setText("Đang kiểm tra các trợ lý AI trên máy…")
        self.win.jobs.submit("probe", lambda: probe_all(self.services.adapters, self.services.db))

    # -- optional LLM intent understanding (off by default; consent stored locally) --
    KEY = "llm_intent_provider"

    def _stored(self) -> str | None:
        with self.services.db.lock:
            r = self.services.db.conn.execute("SELECT value FROM app_state WHERE key=?", (self.KEY,)).fetchone()
        return r["value"] if r else None

    def _store(self, value: str | None) -> None:
        with self.services.db.tx() as c:
            if value:
                c.execute("INSERT INTO app_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (self.KEY, value))
            else:
                c.execute("DELETE FROM app_state WHERE key=?", (self.KEY,))

    def apply_llm_setting(self) -> None:
        """Called after each probe: enable only if consent is stored AND that provider is ready now."""
        pid = self._stored()
        on = bool(pid) and self.services.provider_statuses().get(pid, ("", None))[0] == "ready"
        self.services.chat.proposer = (LLMIntentProposer(make_asker(self.services, pid)) if on else RuleIntentProposer())
        self.llm.blockSignals(True)
        self.llm.setChecked(on)
        self.llm.blockSignals(False)

    def confirm_llm_consent(self, provider_id: str) -> bool:
        return QMessageBox.question(
            self, "Xác nhận gửi dữ liệu",
            f"Khi bật, mỗi tin nhắn bạn gửi trong ô trò chuyện sẽ được gửi tới dịch vụ AI của {NAMES.get(provider_id, provider_id)} "
            "để hiểu ý bạn, và có thể tính vào hạn mức sử dụng. Trợ lý chỉ được ĐỌC thư mục dự án đang chọn.\n\n"
            "Bạn có thể tắt bất cứ lúc nào. Bạn đồng ý bật?", QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No) == QMessageBox.Yes

    def on_llm_toggled(self, checked: bool) -> None:
        if not checked:
            self._store(None)
            self.apply_llm_setting()
            return
        pid = ready_provider(self.services)
        if pid is None:
            QMessageBox.information(self, "AATPO", "Chưa có trợ lý AI nào sẵn sàng (Claude hoặc Codex).")
        elif self.confirm_llm_consent(pid):
            self._store(pid)
        self.apply_llm_setting()

    # -- smoke --
    def confirm_consent(self, provider_id: str) -> bool:
        p = self.services.registry.selected()
        return QMessageBox.question(
            self, "Xác nhận gửi dữ liệu",
            CONSENT.format(project=p.display_name, path=p.root_path, provider=NAMES.get(provider_id, provider_id)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def on_smoke_clicked(self, provider_id: str) -> None:
        if self.confirm_consent(provider_id):
            self.start_smoke(provider_id, consent=True)

    def start_smoke(self, provider_id: str, *, consent: bool) -> None:
        project = self.services.registry.selected()
        if project is None:
            QMessageBox.information(self, "AATPO", "Hãy chọn dự án trước.")
            return
        self.running_run = "pending"
        self.answer.clear()
        self.busy.setText(f"Đang chạy với {NAMES.get(provider_id, provider_id)}… (đang có tiến trình thật)")
        self.stop_btn.setEnabled(True)
        self.refresh()
        self._provider = provider_id
        self.win.jobs.submit("smoke", lambda: run_readonly_smoke(self.services, provider_id, project, consent=consent))

    def stop(self) -> None:
        # cancel the newest run of the active provider via the session ledger
        with self.services.db.lock:
            row = self.services.db.conn.execute(
                "SELECT run_id FROM process_runs WHERE state='RUNNING' ORDER BY created_at DESC LIMIT 1").fetchone()
        if row:
            self.win.jobs.submit("cancel", lambda: self.services.sessions.cancel(row["run_id"]))
            self.busy.setText("Đang dừng…")

    def _on_job(self, key: str, result, exc) -> None:
        if key == "probe":
            self.recheck.setEnabled(True)
            self.busy.setText("" if exc is None else "Không kiểm tra được trợ lý AI.")
            self.apply_llm_setting()
            self.win.refresh_all()
        elif key == "smoke":
            self.running_run = None
            self.stop_btn.setEnabled(False)
            self.busy.setText("")
            if exc is not None:
                self.answer.setPlainText("Không thể chạy: " + (str(exc) or type(exc).__name__))
            else:
                run, res = result
                if res.ok:
                    self.answer.setPlainText(res.text)
                elif res.timed_out:
                    self.answer.setPlainText("Quá thời gian chờ, đã dừng tiến trình.")
                elif res.cancelled:
                    self.answer.setPlainText("Đã dừng theo yêu cầu của bạn.")
                else:
                    msg = "Hết hạn mức sử dụng của trợ lý này." if res.error_kind == "quota" else f"Không thành công: {res.error}"
                    self.answer.setPlainText(msg)
                self.adv_text.setPlainText(
                    f"run={run.run_id} trạng thái={run.state} exit={run.exit_code}\n"
                    f"phiên nội bộ={run.session_id}\nlỗi={res.error or '-'}\nmã phiên nhà cung cấp={res.provider_session_id or '-'}")
            self.win.refresh_all()
