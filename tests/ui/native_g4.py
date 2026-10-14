"""Native Windows window (Qt platform 'windows') after a full write workflow on a disposable sample repo
(real git + real pytest, scripted agent). Run: .venv\Scripts\python tests/ui/native_g4.py <out_dir>  (manual_gui)"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from PySide6.QtWidgets import QApplication

from aatpo.gui.main_window import MainWindow
from tests.unit.test_delivery_g4 import Agent, fix, start, world

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
svc, p, root = world(Path(tempfile.mkdtemp()), Agent([fix]))
start(svc, p)
w = MainWindow(svc, auto_probe=False)
w.resize(1100, 760)
w.show()
for key in ("results", "tasks", "projects"):
    w.go(key)
    app.processEvents()
    w.grab().save(str(out / f"{key}.png"))
print("platform:", app.platformName(), "->", sorted(x.name for x in out.glob("*.png")))
w.close()
svc.close()
