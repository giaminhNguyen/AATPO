import asyncio
import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from aatpo.cli.base import AgentRunResult  # noqa: E402
from aatpo.domain.models import TaskState as T, WorkOrderState as W  # noqa: E402
from aatpo.gui.main_window import MainWindow  # noqa: E402
from tests.unit.test_manager_g3 import Script, approved, make, repo_project, tasks_by_key  # noqa: E402

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


def window(svc):
    w = MainWindow(svc, auto_probe=False)
    w.go("tasks")
    return w, w.pages["tasks"]


def test_start_button_runs_plan_to_completion_with_evidence(qapp, tmp_path):
    svc, p = make(tmp_path, Script())
    wo = approved(svc, p)
    w, page = window(svc)
    page.refresh()
    assert page.btn["start"].isEnabled() and not page.btn["pause"].isEnabled() and not page.btn["resume"].isEnabled()
    page.btn["start"].click()
    assert page.running and not page.btn["start"].isEnabled()           # job really in flight
    pump(qapp, lambda: not page.running)
    page.refresh()
    top = page.tree.topLevelItem(0)
    assert "(3/3 việc xong)" in top.text(2) and [top.child(i).text(2) for i in range(3)] == ["Hoàn thành"] * 3
    assert {top.child(i).text(1) for i in range(3)} == {"Chuyên viên phân tích nghiệp vụ", "Kỹ sư xử lý dữ liệu", "Kỹ sư kiểm thử"}
    txt = page.detail_text(wo.work_order_id)
    assert "Kiểm tra: đạt" in txt and "Chế độ làm việc: Tiêu chuẩn" in txt
    assert "kết quả #" in page.results_text(wo.work_order_id)
    assert page.btn["result"].isEnabled() and page.btn["detail"].isEnabled()
    w.close()
    svc.close()


def test_pause_and_resume_buttons(qapp, tmp_path):
    ad = Script()
    started = {"flag": False}

    async def blocker(kind, req, sid, n):
        if n == 1:
            ad.cancel_event = asyncio.Event()
            started["flag"] = True
            await ad.cancel_event.wait()
            return AgentRunResult(ok=False, cancelled=True, error_kind="cancelled", error="x")
    ad.fn = blocker
    svc, p = make(tmp_path, ad)
    wo = approved(svc, p, "Sửa lỗi đăng nhập")
    w, page = window(svc)
    page.refresh()
    page.btn["start"].click()
    pump(qapp, lambda: started["flag"])
    page.refresh()
    assert page.btn["pause"].isEnabled() and "tiến trình thật" in page.live.text()
    page.btn["pause"].click()
    pump(qapp, lambda: not page.running)
    page.refresh()
    assert tasks_by_key(svc, wo)["implement"].state == T.PAUSED
    assert page.tree.topLevelItem(0).child(0).text(2) == "Tạm dừng" and page.live.text() == ""
    assert page.btn["resume"].isEnabled() and not page.btn["pause"].isEnabled()
    page.btn["resume"].click()
    pump(qapp, lambda: not page.running)
    page.refresh()
    assert "(2/2 việc xong)" in page.tree.topLevelItem(0).text(2)
    w.close()
    svc.close()


def test_dirty_repo_message_is_shown_in_plain_vietnamese(qapp, tmp_path):
    svc, p, d = repo_project(tmp_path, {"fake": Script()}, dirty=True)
    wo = approved(svc, p, "Sửa lỗi đăng nhập")
    w, page = window(svc)
    page.refresh()
    page.btn["start"].click()
    pump(qapp, lambda: not page.running)
    page.refresh()
    assert "thay đổi chưa lưu" in page.status.text()
    assert "Bị chặn" in page.tree.topLevelItem(0).child(0).text(2)
    assert (d / "a.txt").read_text() == "dirty edit"
    w.close()
    svc.close()


def test_chat_start_and_pause_commands(qapp, tmp_path):
    ad = Script()
    svc, p = make(tmp_path, ad)
    wo = approved(svc, p, "Sửa lỗi đăng nhập")
    w = MainWindow(svc, auto_probe=False)
    home = w.pages["home"]
    home.input.setText("Bắt đầu làm")
    home.on_send()
    pump(qapp, lambda: not home.pending)
    assert home.chips.count() >= 1
    chip = home.chips.itemAt(0).widget()
    chip.click()                                                         # "Theo dõi công việc" => starts the run
    page = w.pages["tasks"]
    pump(qapp, lambda: not page.running)
    assert svc.store.get_work_order(wo.work_order_id).state == W.DELIVERED and svc.manager.progress(wo.work_order_id) == (2, 2)
    w.close()
    svc.close()


def test_rerun_approval_in_inbox(qapp, tmp_path):
    svc, p = make(tmp_path, Script())
    wo = approved(svc, p, "Sửa lỗi đăng nhập")
    svc.manager.create_plan(wo.work_order_id)
    t = tasks_by_key(svc, wo)["implement"]
    for to in (T.READY, T.CLAIMED, T.RUNNING, T.UNKNOWN_AFTER_CRASH):
        t = svc.store.transition_task(t.task_id, to, svc.store.get_task(t.task_id).version)
    svc.manager.reconcile_after_restart()
    w = MainWindow(svc, auto_probe=False)
    ap = w.pages["approvals"]
    ap.refresh()
    assert ap.list.count() == 1 and "Cảnh báo" in ap.detail.toPlainText() and "ghi trùng" in ap.detail.toPlainText()
    asked = []
    ap.confirm = lambda text: asked.append(text) or True
    next(b for b in ap.findChildren(QPushButton) if b.text() == "Đồng ý — Cho chạy lại").click()
    assert "ghi trùng" in asked[0] and svc.store.get_task(t.task_id).state == T.READY
    w.close()
    svc.close()
