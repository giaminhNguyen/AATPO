from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from aatpo.gui.pages.home_chat import HomePage
from aatpo.gui.bridges.background_jobs import BackgroundJobs
from aatpo.gui.pages.projects import ProjectsPage
from aatpo.gui.pages.settings import SettingsPage
from aatpo.gui.pages.results import ResultsPage
from aatpo.gui.pages.tasks import ApprovalsPage, TasksPage
from aatpo.services import Services

NAV = (("home", "Văn phòng AI", HomePage), ("projects", "Dự án", ProjectsPage),
       ("tasks", "Công việc", TasksPage), ("approvals", "Cần bạn quyết định", ApprovalsPage),
       ("results", "Kết quả", ResultsPage),
       ("settings", "Cài đặt", SettingsPage))

STYLE = """
QWidget { font-size: 11pt; }
QLabel#pageTitle { font-size: 16pt; font-weight: 600; padding-bottom: 6px; }
QListWidget#nav { min-width: 190px; max-width: 230px; }
QListWidget#nav::item { padding: 10px 8px; }
QPushButton { padding: 6px 12px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, services: Services, auto_probe: bool = True):
        super().__init__()
        self.services = services
        self.jobs = BackgroundJobs()
        self.setWindowTitle("AATPO — Văn phòng AI")
        self.resize(1100, 700)
        self.setStyleSheet(STYLE)

        central = QWidget()
        outer = QVBoxLayout(central)
        self.header = QLabel()
        outer.addWidget(self.header)
        body = QHBoxLayout()
        outer.addLayout(body, 1)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.stack = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.keys, self.pages = [], {}
        for key, label, cls in NAV:
            self.nav.addItem(label)
            page = cls(services, self)
            self.pages[key] = page
            self.keys.append(key)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setCurrentRow(0)
        self.refresh_all()
        if auto_probe:
            self.pages["settings"].probe()  # local-only checks; no model call, no quota

    def closeEvent(self, e) -> None:
        self.jobs.shutdown()
        super().closeEvent(e)

    def _on_nav(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        self.pages[self.keys[row]].refresh()

    def go(self, key: str) -> None:
        self.nav.setCurrentRow(self.keys.index(key))

    def refresh_all(self) -> None:
        p = self.services.registry.selected()
        n = len(self.services.approvals.pending())
        state = f"Cần bạn xác nhận ({n})" if n else "Sẵn sàng"
        self.header.setText(f"AATPO   |   Dự án: {p.display_name if p else 'chưa chọn'}   |   Trạng thái: {state}")
        self.nav.item(self.keys.index("approvals")).setText("Cần bạn quyết định" + (f" ({n})" if n else ""))
        for page in self.pages.values():
            page.refresh()
