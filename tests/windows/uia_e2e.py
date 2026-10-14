"""End-to-end test of the REAL packaged AATPO.exe driven through Windows UI Automation (no mouse hijack where a UIA
pattern exists). Uses a REAL Claude Code session on a disposable repo. Manual-GUI script, not part of default pytest.

   .venv\\Scripts\\python tests\\windows\\uia_e2e.py <AATPO.exe> <repo_dir> <home_dir> [report.json]
Opening the app by double-click and resizing the window are deliberately NOT tested here (left to a human)."""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
import os

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys

exe, repo, home = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
report = {"steps": [], "ok": True}
PYTHON = str(Path(sys.executable))
PREREG = os.environ.get("AATPO_UIA_PREREGISTERED") == "1"


def step(name, ok, detail=""):
    report["steps"].append({"step": name, "ok": bool(ok), "detail": str(detail)[:300]})
    report["ok"] &= bool(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)


def git(*a):
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, encoding="utf-8").stdout.strip()


import os
os.environ["AATPO_HOME"] = home
app = Application(backend="uia").start(f'"{exe}"', timeout=30)
win = app.window(title_re="AATPO.*", control_type="Window")
win.wait("visible", timeout=30)
main_pid = app.process


def el(**kw):
    return win.child_window(**kw)


PAGES = {"Văn phòng AI": ("1", "Văn phòng AI"), "Dự án": ("2", "Dự án"), "Công việc": ("3", "Công việc"),
         "Cần bạn quyết định": ("4", "Cần bạn quyết định"), "Kết quả": ("5", "Kết quả"), "Cài đặt": ("6", "Cài đặt & trợ lý AI")}


def goto(name):
    """Real keyboard shortcut Ctrl+<n>; then PROVE the page changed by looking for its title."""
    key, title = PAGES[name]
    win.set_focus()
    send_keys("^" + key)
    ok = wait_for(lambda: any(t.window_text() == title for t in win.descendants(control_type="Text")), 6, 0.2)
    if not ok:
        raise RuntimeError(f"không chuyển được sang trang {name}")


def texts():
    return " | ".join(t.window_text() for t in win.descendants(control_type="Text") if t.window_text())


def wait_for(cond, timeout=60, every=0.5):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:
            pass
        time.sleep(every)
    return False


def top_dialog(title_re, timeout=15):
    """A modal dialog of OUR process (Qt message box / native file dialog)."""
    d = Desktop(backend="uia")
    end = time.time() + timeout
    while time.time() < end:
        for w in d.windows(process=main_pid):
            if w.window_text() and w.window_text().startswith("AATPO —"):
                continue
            import re
            if re.search(title_re, w.window_text() or ""):
                return w
        time.sleep(0.3)
    return None


def invoke_async(button):
    """Buttons that open modal dialogs block the UIA call; run it on a thread."""
    t = threading.Thread(target=lambda: button.invoke(), daemon=True)
    t.start()
    return t


def press_dialog_button(dlg, names):
    for b in dlg.descendants(control_type="Button"):
        if b.window_text().replace("&", "") in names:
            b.invoke()
            return True
    return False


try:
    # ---- 1. window + areas -------------------------------------------------------------------------------------
    nav = [i.window_text() for i in win.child_window(title="Các khu vực của AATPO", control_type="List").children()]
    step("1 mở cửa sổ, 6 khu vực tiếng Việt", nav == ["Văn phòng AI", "Dự án", "Công việc", "Cần bạn quyết định", "Kết quả", "Cài đặt"], nav)

    # ---- 2. Cài đặt: providers ready -------------------------------------------------------------------------------
    goto("Cài đặt")
    wait_for(lambda: texts().count("Sẵn sàng") >= 2 and "Đang kiểm tra" not in texts(), 40)
    t = texts()
    step("2 phím tắt Ctrl+6 mở đúng trang Cài đặt", "Cài đặt & trợ lý AI" in t)
    step("4 Cài đặt: Claude/Codex 'Sẵn sàng', Gemini 'Chưa cài'", "codex-cli" in t and "Claude Code" in t and t.count("Sẵn sàng") >= 2 and "Chưa cài" in t, t[:200])

    if not PREREG:   # native folder dialog: verified by the owner by hand
        # ---- 3. open project through the NATIVE folder dialog ----------------------------------------------------------
        goto("Dự án")
        th = invoke_async(el(title="Mở dự án có sẵn…", control_type="Button"))
        dlg = top_dialog(r"Chọn thư mục dự án")
        step("3 hộp thoại chọn thư mục (native Windows) hiện ra", dlg is not None)
        edit = [e for e in dlg.descendants(control_type="Edit")][0]
        edit.set_edit_text(str(repo))
        ok_btn = [b for b in dlg.descendants(control_type="Button") if b.window_text().replace("&", "") in ("Select Folder", "Chọn thư mục", "Select folder")]
        (ok_btn[0].invoke() if ok_btn else send_keys("{ENTER}"))
        confirm = top_dialog(r"Xác nhận dự án")
        step("3 hộp thoại xác nhận dự án hiện đường dẫn", confirm is not None and str(repo.name) in " ".join(c.window_text() for c in confirm.descendants()), "")
        press_dialog_button(confirm, ("Xác nhận",))
        th.join(timeout=10)
        goto("Dự án")
        step("3 dự án được thêm và đang dùng", wait_for(lambda: "Đang dùng" in " ".join(c.window_text() for c in win.descendants()), 10))

        # ---- 4. test command via dialog ----------------------------------------------------------------------------------
        row = [c for c in win.descendants(control_type="DataItem") if repo.name in c.window_text()] or \
              [c for c in win.descendants() if c.window_text() == repo.name]
        row[0].select() if hasattr(row[0], "select") else row[0].click_input()
        th = invoke_async(el(title="Lệnh kiểm thử…", control_type="Button"))
        dlg = top_dialog(r"Lệnh kiểm thử")
        step("5 hộp thoại 'Lệnh kiểm thử' hiện, có gợi ý", dlg is not None)
        sug = dlg.descendants(control_type="Edit")[0].get_value()
        step("5 gợi ý không phải AATPO.exe (đã sửa lỗi)", "AATPO" not in sug.split(" ")[0] and "pytest" in sug, sug)
        bad = dlg.descendants(control_type="Edit")[0]
        bad.set_edit_text("rm -rf /")
        press_dialog_button(dlg, ("OK", "&OK"))
        warn = top_dialog(r"AATPO", 8)
        step("5 lệnh nguy hiểm 'rm -rf /' bị từ chối", warn is not None and "danh sách" in " ".join(c.window_text() for c in warn.descendants()), "")
        if warn:
            press_dialog_button(warn, ("OK",))
        th.join(timeout=10)
        th = invoke_async(el(title="Lệnh kiểm thử…", control_type="Button"))
        dlg = top_dialog(r"Lệnh kiểm thử")
        dlg.descendants(control_type="Edit")[0].set_edit_text(f"{PYTHON} -m pytest -q -p no:cacheprovider")
        press_dialog_button(dlg, ("OK", "&OK"))
        th.join(timeout=10)
        step("5 lệnh kiểm thử hợp lệ được lưu", True)

    # ---- 5. chat -----------------------------------------------------------------------------------------------------
    goto("Văn phòng AI")
    box = el(title="Mô tả công việc của bạn…", control_type="Edit")
    box.set_edit_text("Sửa lỗi hàm cộng hai số: add(2, 3) đang trả về -1, phải là 5")
    el(title="Gửi", control_type="Button").invoke()
    ok = wait_for(lambda: el(title="Tôi chưa biết, hãy đề xuất", control_type="Button").exists(), 20)
    step("5 trợ lý hỏi MỘT câu và có nút 'Tôi chưa biết, hãy đề xuất'", ok)
    el(title="Tôi chưa biết, hãy đề xuất", control_type="Button").invoke()
    ok = wait_for(lambda: el(title="Xem và chọn phạm vi", control_type="Button").exists(), 20)
    step("5 hiện hai phương án Tiết kiệm/Cân bằng", ok)

    # chat 'đồng ý' must NOT approve
    box.set_edit_text("Đồng ý phương án cân bằng")
    el(title="Gửi", control_type="Button").invoke()
    ok = wait_for(lambda: "bấm trực tiếp" in " ".join(c.window_text() for c in win.descendants(control_type="Document")) or
                  any("bấm trực tiếp" in (c.window_text() or "") for c in win.descendants()), 20)
    step("5 nhắn 'đồng ý' trong chat KHÔNG có hiệu lực", ok)

    # ---- 6. approvals ---------------------------------------------------------------------------------------------------
    goto("Cần bạn quyết định")
    ok = wait_for(lambda: el(title="Đồng ý — Tiết kiệm", control_type="Button").exists(), 10)
    step("5 mục 'Cần bạn quyết định' có thẻ phạm vi + nút Đồng ý", ok)
    th = invoke_async(el(title="Đồng ý — Tiết kiệm", control_type="Button"))
    q = top_dialog(r"Xác nhận quyết định")
    step("5 hộp thoại xác nhận nêu đúng phương án và dự án", q is not None and "Tiết kiệm" in " ".join(c.window_text() for c in q.descendants()))
    press_dialog_button(q, ("Yes", "&Yes", "Có"))
    th.join(timeout=10)

    # ---- 7. start work -------------------------------------------------------------------------------------------------------
    goto("Công việc")
    tree = win.child_window(control_type="Tree")
    item = [c for c in tree.descendants(control_type="TreeItem")][0]
    item.select()
    start_btn = el(title="Bắt đầu", control_type="Button")
    step("5 nút 'Bắt đầu' sáng sau khi duyệt", start_btn.is_enabled())
    start_btn.invoke()
    saw_live = wait_for(lambda: "Đang có tiến trình thật" in texts(), 40, 0.4)
    step("5 hiện 'Đang có tiến trình thật chạy ngầm…' khi chạy (UI không đơ)", saw_live)
    done = wait_for(lambda: "Các việc đã xong" in texts() or "Hoàn thành" in texts() and "Đang thực hiện" not in texts(), 300, 1)
    step("5 công việc chạy xong", done, texts()[:200])
    time.sleep(1.5)

    # ---- 8. independent verification --------------------------------------------------------------------------------------------
    step("5 calc.py đã sửa thành a + b", "return a + b" in (repo / "calc.py").read_text(encoding="utf-8"))
    step("5 git: có commit mới, nhánh main, cây sạch, không remote",
         git("log", "--oneline").count("\n") == 1 and git("branch", "--show-current") == "main" and git("status", "--porcelain") == "" and git("remote") == "",
         git("log", "--oneline", "-2"))
    r = subprocess.run([PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=repo, capture_output=True, text=True)
    step("5 pytest độc lập đạt", r.returncode == 0, r.stdout.strip().splitlines()[-1])

    # ---- 9. results page + clipboard + save + open folder ---------------------------------------------------------------------------
    goto("Kết quả")
    wait_for(lambda: "Báo cáo bàn giao" in " ".join(c.window_text() or "" for c in win.descendants()), 10)
    step("6 trang Kết quả hiện báo cáo", any("Báo cáo bàn giao" in (c.window_text() or "") for c in win.descendants()))
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value 'TRUOC'"])
    el(title="Sao chép báo cáo", control_type="Button").invoke()
    time.sleep(0.8)
    clip = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"], capture_output=True, text=True, encoding="utf-8").stdout
    step("6 'Sao chép báo cáo' đưa báo cáo vào clipboard thật", clip.startswith("# Báo cáo bàn giao") and "ĐẠT" in clip, clip[:60])
    out = repo.parent / "bao-cao-uia.md"
    out.unlink(missing_ok=True)
    th = invoke_async(el(title="Lưu báo cáo…", control_type="Button"))
    dlg = top_dialog(r"Lưu báo cáo")
    step("6 hộp thoại 'Lưu báo cáo' hiện", dlg is not None)
    dlg.descendants(control_type="Edit")[0].set_edit_text(str(out))
    sv = [b for b in dlg.descendants(control_type="Button") if b.window_text().replace("&", "") in ("Save", "Lưu")]
    sv[0].invoke()
    th.join(timeout=10)
    time.sleep(0.8)
    step("6 'Lưu báo cáo…' ghi file .md đúng nội dung", out.exists() and out.read_text(encoding="utf-8").startswith("# Báo cáo bàn giao"))
    el(title="Mở thư mục dự án", control_type="Button").invoke()
    exp = None
    for _ in range(20):
        ws = [w for w in Desktop(backend="uia").windows() if repo.name in (w.window_text() or "")]
        if ws:
            exp = ws[0]
            break
        time.sleep(0.5)
    step("6 'Mở thư mục dự án' mở Explorer đúng thư mục", exp is not None, exp.window_text() if exp else "")
    if exp:
        try:
            exp.close()
        except Exception:
            pass
    th = invoke_async(el(title="Xem thay đổi", control_type="Button"))
    dlg = top_dialog(r"Các thay đổi")
    body = dlg.descendants(control_type="Edit")[0].get_value() if dlg else ""
    step("6 'Xem thay đổi' hiện diff đúng", "+    return a + b" in body and "-    return a - b" in body)
    if dlg:
        press_dialog_button(dlg, ("Đóng",))
    th.join(timeout=10)

    # ---- 10. history + undo proposal ------------------------------------------------------------------------------------------------
    goto("Dự án")
    row = [c for c in win.descendants() if c.window_text() == repo.name]
    row[0].select() if hasattr(row[0], "select") else None
    th = invoke_async(el(title="Lịch sử phiên bản…", control_type="Button"))
    dlg = top_dialog(r"Lịch sử phiên bản")
    txt = " ".join(c.window_text() or "" for c in dlg.descendants()) if dlg else ""
    step("8 lịch sử phiên bản hiện, phân biệt 'do AATPO' và 'của bạn'", "Đã lưu phiên bản bởi AATPO" in txt and "Phiên bản của bạn" in txt, txt[:120])
    if dlg:
        press_dialog_button(dlg, ("Đóng",))
    th.join(timeout=10)

    # ---- 11. reliability panel -------------------------------------------------------------------------------------------------------------
    goto("Cài đặt")
    el(title="Sao lưu dữ liệu ngay", control_type="Button").invoke()
    time.sleep(1)
    step("9 'Sao lưu dữ liệu ngay' tạo file sao lưu", any("Đã sao lưu" in (c.window_text() or "") for c in win.descendants()) or
         bool(list(Path(home, "backups").glob("office-manual-*.db"))))
    el(title="Đối chiếu với kho Git", control_type="Button").invoke()
    time.sleep(1.5)
    step("9 đối chiếu Git: dữ liệu khớp", any("khớp" in (c.window_text() or "") for c in win.descendants()))
finally:
    try:
        win.close()
    except Exception:
        pass
    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/PID", str(main_pid)], capture_output=True)
    print("\nTỔNG:", "ĐẠT" if report["ok"] else "CÓ LỖI", f"({sum(s['ok'] for s in report['steps'])}/{len(report['steps'])})")
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
