"""Bootstrap: `python -m aatpo` opens the desktop window."""
from __future__ import annotations

import sys

from aatpo.services import Services
from aatpo.settings import default_paths


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtWidgets import QApplication

    from aatpo.gui.main_window import MainWindow

    app = QApplication(argv if argv is not None else sys.argv)
    services = Services.create(default_paths(), write_mode=True)
    win = MainWindow(services)
    win.show()
    code = app.exec()
    services.close()
    return code
