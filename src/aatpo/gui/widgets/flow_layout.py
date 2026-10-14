"""A layout that wraps its widgets onto extra rows instead of squeezing/clipping them (small windows, 125-150% scaling)."""
from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._space = spacing
        self.setContentsMargins(QMargins(0, 0, 0, 0))

    def addItem(self, item):
        self._items.append(item)

    def addStretch(self, *_):          # API parity with QBoxLayout; a flow has nothing to stretch
        pass

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test_only):
        m = self.contentsMargins()
        x0, y = rect.x() + m.left(), rect.y() + m.top()
        right = rect.right() - m.right()
        x, row_h = x0, 0
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > right and row_h > 0:
                x, y, row_h = x0, y + row_h + self._space, 0
            if not test_only:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._space
            row_h = max(row_h, hint.height())
        return y + row_h - rect.y() + m.bottom()
