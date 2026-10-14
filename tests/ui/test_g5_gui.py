import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QLineEdit  # noqa: E402

from aatpo.gui.main_window import MainWindow  # noqa: E402
from aatpo.gui.pages.history import HistoryDialog  # noqa: E402
from tests.unit.test_delivery_g4 import BUGGY, Agent, fix, start, world  # noqa: E402
from tests.unit.test_manager_g3 import Script, make  # noqa: E402

pytestmark = pytest.mark.mock_integration


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_keyboard_shortcuts_focus_and_accessible_names(qapp, tmp_path):
    svc, p = make(tmp_path, Script())
    w = MainWindow(svc, auto_probe=False)
    w.show()
    w.activateWindow()
    QTest.qWaitForWindowActive(w)
    for i, key in enumerate(w.keys, start=1):
        QTest.keyClick(w, getattr(Qt, f"Key_{i}"), Qt.ControlModifier)
        assert w.keys[w.nav.currentRow()] == key, f"Ctrl+{i} should open {key}"
    w.go("home")
    for k in w.keys:                                                     # visit every page so all controls exist
        w.go(k)
    unnamed = [b.text() for b in w.findChildren(QPushButton) if not b.accessibleName()]
    unfocusable = [b.text() for b in w.findChildren(QPushButton) if b.focusPolicy() == Qt.NoFocus]
    assert unnamed == [] and unfocusable == []
    assert all(e.accessibleName() for e in w.findChildren(QLineEdit) if e.parent() is not None and e.isEnabled())
    home = w.pages["home"]
    home.input.setText("Cho tôi xem đã làm gì")
    QTest.keyClick(home.input, Qt.Key_Return)                           # Enter sends; no mouse needed
    end = time.time() + 10
    while home.pending and time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)
    assert "Chưa có công việc" in home.transcript.toPlainText()
    w.close()
    svc.close()


def test_history_dialog_and_undo_through_the_inbox(qapp, tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]))
    start(svc, p)
    w = MainWindow(svc, auto_probe=False)
    dlg = HistoryDialog(w, svc, p, on_change=w.refresh_all)
    assert dlg.table.rowCount() == 2 and "Đã lưu phiên bản bởi AATPO" in dlg.table.item(0, 1).text()
    assert "Phiên bản của bạn" in dlg.table.item(1, 1).text()
    assert dlg.table.isColumnHidden(3) and dlg.table.isColumnHidden(4)         # hashes tucked away
    dlg.adv.setChecked(True)
    assert not dlg.table.isColumnHidden(3) and len(dlg.table.item(0, 3).text()) == 10
    infos = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: infos.append(a[2])))
    dlg.propose()                                                       # nothing selected
    assert "chọn một phiên bản" in infos[-1]
    dlg.table.selectRow(1)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: infos.append(a[2])))
    dlg.propose()                                                       # user's own commit: refused
    assert "do AATPO đã lưu" in infos[-1] and not svc.approvals.pending()
    dlg.table.selectRow(0)
    dlg.propose()
    assert "Chưa có gì bị thay đổi" in infos[-1] and (root / "calc.py").read_text() != BUGGY
    ap = w.pages["approvals"]
    ap.refresh()
    assert ap.list.count() == 1 and "Hoàn tác phiên bản" in ap.list.item(0).text()
    asked = []
    ap.confirm = lambda text: asked.append(text) or True
    next(b for b in ap.findChildren(QPushButton) if b.text() == "Đồng ý — Tạo bản hoàn tác").click()
    assert "Lịch sử cũ được giữ nguyên" in asked[0] and (root / "calc.py").read_text() == BUGGY
    w.close()
    svc.close()


def test_settings_backup_restore_audit_and_stats(qapp, tmp_path, monkeypatch):
    svc, p, root = world(tmp_path, Agent([fix]))
    start(svc, p)
    w = MainWindow(svc, auto_probe=False)
    st = w.pages["settings"]
    st.refresh()
    assert "fake: 2 lần chạy" in st.rel_text.toPlainText() and "chi phí" in st.rel_text.toPlainText()
    st.do_backup()
    assert "Đã sao lưu" in st.rel_text.toPlainText() and list((svc.paths.backups).glob("office-manual-*.db"))
    st.do_audit()
    assert "khớp" in st.rel_text.toPlainText()
    target = next(svc.paths.backups.glob("office-manual-*.db"))
    monkeypatch.setattr(type(st), "choose_backup", lambda self: str(target))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    st.do_restore()
    assert not (svc.paths.home / "config" / "restore_pending.txt").exists()      # "No" schedules nothing
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    st.do_restore()
    assert (svc.paths.home / "config" / "restore_pending.txt").exists() and "mở lại AATPO" in st.rel_text.toPlainText()
    w.close()
    svc.close()
