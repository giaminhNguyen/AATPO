import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from aatpo.domain.models import WorkOrderState as W  # noqa: E402
from aatpo.gui.main_window import MainWindow  # noqa: E402
from aatpo.gui.pages.projects import join_command, parse_command  # noqa: E402
from tests.unit.test_delivery_g4 import Agent, PYTEST, fix, go, start, world  # noqa: E402

pytestmark = pytest.mark.mock_integration


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def pump(qapp, cond, timeout=20):
    end = time.time() + timeout
    while time.time() < end and not cond():
        qapp.processEvents()
        time.sleep(0.01)
    assert cond(), "timed out"


def yes(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))


def test_results_page_report_diff_save_copy_open_revise_accept(qapp, tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]))
    wo, res = start(svc, p)
    assert res.outcome == "completed"
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["results"]
    page.refresh()
    assert page.list.count() == 1 and "Hoàn thành" in page.list.item(0).text() and not page.empty.isVisibleTo(page)
    md = page.report.toPlainText()
    assert "Báo cáo bàn giao" in md and "Đã tích hợp vào nhánh" in md and "ĐẠT" in md
    assert all(b.isEnabled() for b in page.btn.values())

    opened = []
    monkeypatch.setattr("aatpo.gui.pages.results.QDesktopServices.openUrl", lambda url: opened.append(url.toLocalFile()))
    page.btn["folder"].click()
    assert [o.replace("/", "\\").lower() for o in opened] == [str(root.resolve()).lower()]     # Explorer only; nothing executed

    assert "+    return a + b" in page.diff_text(wo.work_order_id) and "calc.py" in page.diff_text(wo.work_order_id)
    shown = []
    monkeypatch.setattr(type(page), "_dialog", lambda self, t, text: shown.append((t, text)))
    page.btn["diff"].click()
    assert shown and "Các thay đổi" in shown[0][0] and "-    return a - b" in shown[0][1]

    out = tmp_path / "bao-cao.md"
    monkeypatch.setattr("aatpo.gui.pages.results.QFileDialog.getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    page.btn["save"].click()
    assert out.read_text(encoding="utf-8").startswith("# Báo cáo bàn giao")
    copied = []   # the offscreen Qt platform has no real clipboard; the native one is exercised by hand only
    monkeypatch.setattr("aatpo.gui.pages.results.QGuiApplication.clipboard",
                        staticmethod(lambda: type("C", (), {"setText": staticmethod(copied.append)})()))
    page.btn["copy"].click()
    assert copied and copied[0].startswith("# Báo cáo bàn giao")

    page.btn["revise"].click()                                         # request revision -> prefilled chat, not auto-sent
    assert w.pages["home"].input.text().startswith("Sửa lại ") and not w.pages["home"].pending

    yes(monkeypatch)
    page.btn["accept"].click()
    assert svc.store.get_work_order(wo.work_order_id).state == W.ACCEPTED and not page.btn["accept"].isEnabled()
    w.close()
    svc.close()


def test_results_empty_state_and_blocked_work_is_not_shown_as_result(qapp, tmp_path):
    from tests.unit.test_delivery_g4 import wrong
    svc, p, root = world(tmp_path, Agent([wrong]), max_rework_cycles_per_task=0)
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["results"]
    page.refresh()
    assert page.empty.isVisibleTo(page)
    start(svc, p)                                                       # tests fail -> BLOCKED, never a "result"
    page.refresh()
    assert page.list.count() == 0 and page.empty.isVisibleTo(page)
    w.close()
    svc.close()


def test_tasks_page_integration_button_for_ready_branch(qapp, tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]), auto_history=False)
    wo, res = start(svc, p)
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "ready"
    w = MainWindow(svc, auto_probe=False)
    w.go("tasks")
    page = w.pages["tasks"]
    page.refresh()
    page.tree.setCurrentItem(page.tree.topLevelItem(0))
    assert page.btn["integrate"].isEnabled()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    page.btn["integrate"].click()
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "ready"      # "No" changes nothing
    yes(monkeypatch)
    page.btn["integrate"].click()
    assert svc.store.get_work_order(wo.work_order_id).integration_status == "integrated" and not page.btn["integrate"].isEnabled()
    w.close()
    svc.close()


def test_project_test_command_and_identity_dialogs(qapp, tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]), test=False)
    w = MainWindow(svc, auto_probe=False)
    page = w.pages["projects"]
    page.refresh()
    page.table.selectRow(0)
    warned = []
    monkeypatch.setattr(type(page), "_warn", lambda self, msg: warned.append(msg))
    answers = iter(["rm -rf /", f'"{PYTEST[0]}" -m pytest -q'])
    seen_default = []
    monkeypatch.setattr(type(page), "ask_text", lambda self, t, l, d="": seen_default.append(d) or next(answers))
    page.btn_set = page.set_test_command
    page.set_test_command()                                              # rejected: not an approved launcher
    assert warned and svc.registry.get(p.project_id).test_command is None
    page.set_test_command()
    assert svc.registry.get(p.project_id).test_command == [PYTEST[0], "-m", "pytest", "-q"]
    assert "pytest" in seen_default[0]                                   # detected suggestion offered, never auto-applied

    ids = iter(["Chủ dự án", "owner@example.invalid"])
    monkeypatch.setattr(type(page), "ask_text", lambda self, t, l, d="": next(ids))
    page.set_identity()
    from tests.conftest import git as run_git
    assert run_git(root, "config", "--local", "user.email") == "owner@example.invalid"
    w.close()
    svc.close()


def test_command_parsing_has_no_shell_semantics():
    assert parse_command('python -m pytest -q') == ["python", "-m", "pytest", "-q"]
    assert parse_command('"C:/Program Files/py/python.exe" -m pytest') == ["C:/Program Files/py/python.exe", "-m", "pytest"]
    assert parse_command("pytest ; calc") == ["pytest", ";", "calc"]      # `;` is just an argument
    assert parse_command("   ") == [] and join_command(["a b", "c"]) == '"a b" c'
