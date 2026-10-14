"""Layout check on the REAL Windows Qt platform at the window's minimum size, under the display scale given by
QT_SCALE_FACTOR. Prints a JSON list of violations (widgets spilling outside the window / text clipped) and saves
a screenshot per page. Run:  set QT_SCALE_FACTOR=1.5 && .venv\\Scripts\\python tests/ui/native_scaling.py <out_dir>"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from aatpo.gui.main_window import MainWindow
from tests.unit.test_delivery_g4 import Agent, fix, start, world

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
scale = os.environ.get("QT_SCALE_FACTOR", "1")
app = QApplication([])
svc, p, root = world(Path(tempfile.mkdtemp()), Agent([fix]))
start(svc, p)                                   # realistic content on every page
w = MainWindow(svc, auto_probe=False)
w.resize(w.minimumSize())
w.show()
app.processEvents()
bad = []
for key in w.keys:
    w.go(key)
    app.processEvents()
    win = w.rect()
    for wd in w.findChildren(QPushButton) + w.findChildren(QLabel):
        if not wd.isVisibleTo(w) or wd.width() == 0:
            continue
        tl = wd.mapTo(w, QPoint(0, 0))
        right, bottom = tl.x() + wd.width(), tl.y() + wd.height()
        if right > win.width() + 1:
            bad.append({"page": key, "widget": (wd.text() or wd.objectName())[:40], "problem": f"spills {right - win.width()}px right"})
        if isinstance(wd, QPushButton) and wd.fontMetrics().horizontalAdvance(wd.text()) > wd.width():
            bad.append({"page": key, "widget": wd.text()[:40], "problem": "button text clipped"})
    w.grab().save(str(out / f"{scale}_{key}.png"))
print(json.dumps({"scale": scale, "window": [w.width(), w.height()], "violations": bad}, ensure_ascii=False))
w.close()
svc.close()
