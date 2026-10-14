"""Native Windows window (Qt platform 'windows') showing the G3 task board after a run driven by the
scripted stand-in provider. Run: .venv\Scripts\python tests/ui/native_g3.py <out_dir>   (manual_gui)"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from PySide6.QtWidgets import QApplication

from aatpo.gui.main_window import MainWindow
from tests.unit.test_manager_g3 import Script, approved, make

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
svc, p = make(Path(tempfile.mkdtemp()), Script())
approved(svc, p)
w = MainWindow(svc, auto_probe=False)
w.resize(1100, 700)
w.show()
w.go("tasks")
page = w.pages["tasks"]
page.btn["start"].click()
end = time.time() + 20
while page.running and time.time() < end:
    app.processEvents()
    time.sleep(0.02)
page.refresh()
app.processEvents()
w.grab().save(str(out / "tasks_after_run.png"))
print("platform:", app.platformName(), "| progress:", page.tree.topLevelItem(0).text(2))
w.close()
svc.close()
