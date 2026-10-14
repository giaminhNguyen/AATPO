import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

from aatpo.gui.main_window import MainWindow  # noqa: E402
from aatpo.services import Services  # noqa: E402
from aatpo.settings import AppPaths  # noqa: E402

pytestmark = pytest.mark.mock_integration


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_five_vietnamese_areas(qapp, svc):
    w = MainWindow(svc)
    labels = [w.nav.item(i).text() for i in range(w.nav.count())]
    assert labels == ["Văn phòng AI", "Dự án", "Công việc", "Cần bạn quyết định", "Kết quả"]
    assert "chưa chọn" in w.header.text()


def test_project_added_via_page_persists_after_restart(qapp, tmp_path):
    home, folder = tmp_path / "home", tmp_path / "Thư mục dự án"
    folder.mkdir()
    s1 = Services.create(AppPaths(home))
    w1 = MainWindow(s1)
    page = w1.pages["projects"]
    page._do(lambda: s1.registry.register(folder, "Quản lý kho", auto_history=False))  # same path as the dialog
    assert page.table.rowCount() == 1 and page.table.item(0, 2).text() == "Đang dùng"
    assert "Quản lý kho" in w1.header.text() and str(folder.resolve()) in w1.pages["home"].active.text()
    s1.close()

    s2 = Services.create(AppPaths(home))  # restart
    w2 = MainWindow(s2)
    assert "Quản lý kho" in w2.header.text()
    assert w2.pages["projects"].table.rowCount() == 1
    s2.close()


def test_missing_folder_shown_in_plain_vietnamese(qapp, svc, tmp_path):
    d = tmp_path / "x"
    d.mkdir()
    svc.registry.register(d, "X", auto_history=False)
    d.rmdir()
    w = MainWindow(svc)
    assert w.pages["projects"].table.item(0, 2).text() == "Không tìm thấy thư mục dự án"
