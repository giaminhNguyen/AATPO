import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from aatpo.agents.smoke import run_readonly_smoke  # noqa: E402
from aatpo.cli.claude_adapter import ClaudeAdapter  # noqa: E402
from aatpo.gui.main_window import MainWindow  # noqa: E402
from aatpo.services import Services  # noqa: E402
from aatpo.settings import AppPaths  # noqa: E402

FAKE = str(Path(__file__).parents[1] / "fixtures" / "fake_cli.py")
pytestmark = pytest.mark.mock_integration


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def pump(qapp, cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end and not cond():
        qapp.processEvents()
        time.sleep(0.02)
    assert cond(), "timed out waiting for background job"


def make(tmp_path, command):
    proj = tmp_path / "Dự án thử"
    proj.mkdir()
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={"claude": ClaudeAdapter(command=command)})
    p = svc.registry.register(proj, "Dự án thử", auto_history=False)
    svc.registry.select(p.project_id)
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='claude'")
    return svc, p


def test_no_consent_no_run(tmp_path):
    svc, p = make(tmp_path, [sys.executable, FAKE, "claude_ok"])
    import asyncio
    with pytest.raises(PermissionError):
        asyncio.run(run_readonly_smoke(svc, "claude", p, consent=False))
    assert svc.db.conn.execute("SELECT count(*) FROM process_runs").fetchone()[0] == 0
    assert svc.store.list_work_orders(p.project_id) == []
    svc.close()


def test_smoke_from_gui_after_consent_and_declined(qapp, tmp_path):
    svc, p = make(tmp_path, [sys.executable, FAKE, "claude_ok"])
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["settings"]
    page.refresh()
    label, btn = page.rows["claude"]
    assert "Sẵn sàng" in label.text() and btn.isEnabled()

    page.confirm_consent = lambda pid: False          # user clicks "Không"
    page.on_smoke_clicked("claude")
    assert svc.db.conn.execute("SELECT count(*) FROM process_runs").fetchone()[0] == 0

    page.confirm_consent = lambda pid: True           # user clicks "Có"
    page.on_smoke_clicked("claude")
    assert page.running_run is not None and page.stop_btn.isEnabled() and "đang có tiến trình thật" in page.busy.text()
    pump(qapp, lambda: page.running_run is None)
    assert page.answer.toPlainText() == "đã đọc xong"
    assert not page.stop_btn.isEnabled() and page.busy.text() == ""
    page.on_smoke_clicked("claude")                   # second click => new task => new session
    pump(qapp, lambda: page.running_run is None)
    sessions = svc.store.list_sessions()
    assert len(sessions) == 2 and len({s.task_id for s in sessions}) == 2
    assert svc.db.conn.execute("SELECT count(*) FROM process_runs WHERE state='SUCCEEDED'").fetchone()[0] == 2
    assert all(t.state == "BACKLOG" for t in svc.store.list_tasks(p.project_id))   # run success != DONE
    w.close()
    svc.close()


def test_failure_is_shown_in_plain_vietnamese(qapp, tmp_path):
    svc, p = make(tmp_path, [sys.executable, FAKE, "exit3"])
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["settings"]
    page.confirm_consent = lambda pid: True
    page.on_smoke_clicked("claude")
    pump(qapp, lambda: page.running_run is None)
    assert page.answer.toPlainText().startswith("Không thành công")
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in page.answer.toPlainText() + page.adv_text.toPlainText()
    w.close()
    svc.close()


def test_missing_provider_shows_remedy_not_success(qapp, tmp_path):
    svc = Services.create(AppPaths(tmp_path / "home"),
                          adapters={"claude": ClaudeAdapter(command=["definitely-not-installed-xyz"])})
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["settings"]
    page.probe()
    pump(qapp, lambda: page.recheck.isEnabled())
    label, btn = page.rows["claude"]
    assert label.text().startswith("Chưa cài") and not btn.isEnabled()
    assert "✖" in w.pages["home"].checks.itemAt(1).widget().text()      # A09/A28: GUI still works
    w.close()
    svc.close()
