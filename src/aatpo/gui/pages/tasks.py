from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget

from aatpo.gui.pages.base import EmptyStatePage, Page

STATE_VI = {
    "BACKLOG": "Chờ xếp lịch", "READY": "Sẵn sàng", "CLAIMED": "Đã nhận", "RUNNING": "Đang thực hiện",
    "OUTPUT_READY": "Có kết quả", "REVIEW": "Đang kiểm tra", "DONE": "Hoàn thành", "REWORK": "Cần làm lại",
    "BLOCKED": "Bị chặn", "PAUSED": "Tạm dừng", "FAILED": "Thất bại", "UNKNOWN_AFTER_CRASH": "Cần bạn xem lại",
}


class TasksPage(Page):
    title_vi = "Công việc"

    def __init__(self, services, window):
        super().__init__(services, window)
        self.empty = QLabel("Chưa có công việc nào. Tính năng giao việc bằng tiếng Việt sẽ có ở bước G2–G3.")
        self.list = QListWidget()
        self.root.addWidget(self.empty)
        self.root.addWidget(self.list, 1)

    def refresh(self) -> None:
        p = self.services.registry.selected()
        tasks = self.services.store.list_tasks(p.project_id) if p else []
        self.list.clear()
        for t in tasks:
            self.list.addItem(f"{t.title} — {STATE_VI.get(t.state, t.state)}")
        self.empty.setVisible(not tasks)


class ApprovalsPage(EmptyStatePage):
    title_vi = "Cần bạn quyết định"
    message = "Hiện không có việc nào cần bạn quyết định."


class ResultsPage(EmptyStatePage):
    title_vi = "Kết quả"
    message = "Chưa có kết quả nào để xem."
