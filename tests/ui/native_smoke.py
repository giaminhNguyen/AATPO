"""Manual/CI-adjacent smoke: shows the REAL native Windows Qt window (not offscreen),
registers a project through the same service the GUI uses, saves screenshots, exits.
Run:  .venv\\Scripts\\python tests\\ui\\native_smoke.py <out_dir>
Tagged manual_gui: it proves the window renders natively; it is not a human usability test."""
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aatpo.gui.main_window import MainWindow
from aatpo.services import Services
from aatpo.settings import AppPaths

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
out.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp())
proj = tmp / "Quản lý bán hàng"
proj.mkdir()

app = QApplication([])
svc = Services.create(AppPaths(tmp / "home"))
win = MainWindow(svc)
win.show()


def step():
    p = svc.registry.register(proj, "Quản lý bán hàng", auto_history=True)
    svc.registry.select(p.project_id)
    win.refresh_all()
    for i, key in enumerate(win.keys):
        win.go(key)
        app.processEvents()
        win.grab().save(str(out / f"{i}_{key}.png"))
    print("platform:", app.platformName(), "| screenshots:", sorted(x.name for x in out.glob("*.png")))
    app.quit()


QTimer.singleShot(300, step)
app.exec()
svc.close()
