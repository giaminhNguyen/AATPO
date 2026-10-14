from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aatpo.services import Services


def clear_layout(layout) -> None:
    """Remove widgets NOW (hide + unparent), then free them; deleteLater alone leaves ghosts on screen."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()


class Page(QWidget):
    """Base page: has the shared services and a refresh() called on show / data change."""
    title_vi = ""

    def __init__(self, services: Services, window):
        super().__init__()
        self.services, self.win = services, window
        self.root = QVBoxLayout(self)
        h = QLabel(self.title_vi)
        h.setObjectName("pageTitle")
        self.root.addWidget(h)

    def refresh(self) -> None:  # overridden
        pass


class EmptyStatePage(Page):
    message = ""

    def __init__(self, services, window):
        super().__init__(services, window)
        self.note = QLabel(self.message)
        self.note.setWordWrap(True)
        self.note.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.root.addWidget(self.note, 1)
