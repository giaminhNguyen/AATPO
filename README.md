# AATPO — Văn phòng AI (Windows Desktop)

Ứng dụng desktop (PySide6) giao việc bằng tiếng Việt cho các trợ lý AI chạy qua CLI chính thức đã đăng nhập.
Đặc tả: `AATPO_V4_1_GUI_First_Auto_Git_Coding_Agent_Input.md`. **Trạng thái: milestone G0 (khung GUI + lõi). Chưa phải MVP hoàn chỉnh.**

## Chạy (phát triển)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m aatpo          # mở cửa sổ
.\.venv\Scripts\python -m pytest -q      # kiểm thử
```

Dữ liệu ứng dụng nằm ở `%LOCALAPPDATA%\AATPO` (đặt biến `AATPO_HOME` để đổi). Không lưu token đăng nhập của CLI.

## Tài liệu
- `docs/decisions.md` — quyết định kỹ thuật
- `docs/git_workflow.md` — chính sách Git tự động (chỉ local, không push)
- `docs/milestone_reports/G0.md` — báo cáo milestone
