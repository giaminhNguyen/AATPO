import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from aatpo.cli.claude_adapter import ClaudeAdapter  # noqa: E402
from aatpo.customer.intent_router import LLMIntentProposer, RuleIntentProposer  # noqa: E402
from aatpo.domain.models import WorkOrderState as W  # noqa: E402
from aatpo.gui.main_window import MainWindow  # noqa: E402
from aatpo.services import Services  # noqa: E402
from aatpo.settings import AppPaths  # noqa: E402

FAKE = str(Path(__file__).parents[1] / "fixtures" / "fake_cli.py")
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


def chips(page):
    return [page.chips.itemAt(i).widget() for i in range(page.chips.count()) if page.chips.itemAt(i).widget()]


def send(qapp, home, text):
    home.input.setText(text)
    home.on_send()
    assert not home.send_btn.isEnabled() and "Đang xử lý" in home.busy.text()   # real job in flight
    pump(qapp, lambda: not home.pending)


def test_full_gui_flow_question_unknown_options_and_click_approval(qapp, tmp_path):
    home_dir, proj = tmp_path / "home", tmp_path / "Kho của tôi"
    proj.mkdir()
    svc = Services.create(AppPaths(home_dir), adapters={})
    p = svc.registry.register(proj, "Kho của tôi", auto_history=False)
    svc.registry.select(p.project_id)
    w = MainWindow(svc, auto_probe=False)
    home = w.pages["home"]

    send(qapp, home, "Tôi cần làm ứng dụng quản lý kho đơn giản")
    assert "quan trọng nhất" in home.transcript.toPlainText()
    assert [b.text() for b in chips(home)] == ["Tôi chưa biết, hãy đề xuất"]
    chips(home)[0].click()                                      # the "I don't know" quick reply
    pump(qapp, lambda: not home.pending and "Cân bằng" in home.transcript.toPlainText())
    txt = home.transcript.toPlainText()
    assert "Tiết kiệm" in txt and "Cân bằng" in txt and "Bắt buộc" in txt

    assert "(1)" in w.nav.item(w.keys.index("approvals")).text() and "Cần bạn xác nhận (1)" in w.header.text()
    ap = w.pages["approvals"]
    ap.refresh()
    assert ap.list.count() == 1 and "Tiết kiệm" in ap.detail.toPlainText() and "Kho của tôi" in ap.detail.toPlainText()
    labels = [ap.btn_row.itemAt(i).widget().text() for i in range(ap.btn_row.count()) if ap.btn_row.itemAt(i).widget()]
    assert labels == ["Đồng ý — Cân bằng", "Đồng ý — Tiết kiệm", "Không đồng ý"] or \
        set(labels) == {"Đồng ý — Cân bằng", "Đồng ý — Tiết kiệm", "Không đồng ý"}

    wo = svc.chat.active_work_order(p.project_id)
    ap.confirm = lambda text: False                              # user hesitates: "Không" in the confirm box
    next(b for b in ap.findChildren(QPushButton) if b.text() == "Đồng ý — Tiết kiệm").click()
    assert svc.store.get_work_order(wo.work_order_id).state == W.SCOPE_PROPOSED
    ap.confirm = lambda text: "Tiết kiệm" in text and "Kho của tôi" in text   # names exact option + project
    next(b for b in ap.findChildren(QPushButton) if b.text() == "Đồng ý — Tiết kiệm").click()
    assert svc.store.get_work_order(wo.work_order_id).state == W.SCOPE_CONFIRMED
    assert "Sẵn sàng" in w.header.text() and "(1)" not in w.nav.item(w.keys.index("approvals")).text()
    assert "bạn đồng ý phương án “Tiết kiệm”" in home.transcript.toPlainText()
    w.close()
    svc.close()

    svc2 = Services.create(AppPaths(home_dir), adapters={})      # restart: history and decisions survive
    w2 = MainWindow(svc2, auto_probe=False)
    assert "bạn đồng ý phương án “Tiết kiệm”" in w2.pages["home"].transcript.toPlainText()
    assert svc2.store.scope_approved(wo.work_order_id)
    assert "Công việc" in w2.pages["tasks"].title_vi and w2.pages["tasks"].tree.topLevelItemCount() == 1
    w2.close()
    svc2.close()


def test_chat_text_cannot_approve_in_gui(qapp, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={})
    svc.registry.select(svc.registry.register(proj, "P", auto_history=False).project_id)
    w = MainWindow(svc, auto_probe=False)
    home = w.pages["home"]
    send(qapp, home, "Tôi cần làm phần mềm bán hàng")
    send(qapp, home, "Tôi chưa biết, hãy đề xuất")
    send(qapp, home, "Đồng ý phương án cân bằng")
    assert "bấm trực tiếp" in home.transcript.toPlainText()
    assert len(svc.approvals.pending()) == 1
    w.close()
    svc.close()


def test_switching_project_shows_only_that_projects_history(qapp, tmp_path):
    svc = Services.create(AppPaths(tmp_path / "home"), adapters={})
    ps = []
    for n in ("a", "b"):
        d = tmp_path / n
        d.mkdir()
        ps.append(svc.registry.register(d, f"DuAn{n}", auto_history=False))
    svc.registry.select(ps[0].project_id)
    w = MainWindow(svc, auto_probe=False)
    send(qapp, w.pages["home"], "Tôi cần làm ứng dụng quản lý kho")
    assert "kho" in w.pages["home"].transcript.toPlainText()
    svc.registry.select(ps[1].project_id)
    w.refresh_all()
    assert "kho" not in w.pages["home"].transcript.toPlainText()
    w.close()
    svc.close()


def test_llm_intent_toggle_needs_consent_and_is_reversible(qapp, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    svc = Services.create(AppPaths(tmp_path / "home"),
                          adapters={"claude": ClaudeAdapter(command=[sys.executable, FAKE, "claude_ok"])})
    svc.registry.select(svc.registry.register(proj, "P", auto_history=False).project_id)
    with svc.db.tx() as c:
        c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='claude'")
    w = MainWindow(svc, auto_probe=False)
    st = w.pages["settings"]
    assert isinstance(svc.chat.proposer, RuleIntentProposer) and not st.llm.isChecked()

    st.confirm_llm_consent = lambda pid: False                  # user declines
    st.llm.setChecked(True)
    assert not st.llm.isChecked() and isinstance(svc.chat.proposer, RuleIntentProposer)

    st.confirm_llm_consent = lambda pid: True
    st.llm.setChecked(True)
    assert st.llm.isChecked() and isinstance(svc.chat.proposer, LLMIntentProposer)
    # "claude_ok" fake returns non-intent JSON text -> validation fails -> rules still drive the reply
    send(qapp, w.pages["home"], "Cho tôi xem đã làm gì")
    assert "Chưa có công việc" in w.pages["home"].transcript.toPlainText()
    assert svc.db.conn.execute("SELECT count(*) FROM process_runs").fetchone()[0] == 1

    st.llm.setChecked(False)
    assert isinstance(svc.chat.proposer, RuleIntentProposer)
    assert svc.db.conn.execute("SELECT count(*) FROM app_state WHERE key='llm_intent_provider'").fetchone()[0] == 0
    w.close()
    svc.close()
