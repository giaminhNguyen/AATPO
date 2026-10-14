"""Customer-facing delivery report (Markdown, Vietnamese). Built ONLY from recorded state - never from an AI's
own summary - and it states what is NOT verified. Technical identifiers go in a final collapsible-style section."""
from __future__ import annotations

import json
from pathlib import Path

from aatpo.customer.representative import STATE_VI as WO_STATE_VI
from aatpo.domain.models import ROLE_TITLES_VI, utcnow

TASK_VI = {"DONE": "Hoàn thành", "FAILED": "Thất bại", "BLOCKED": "Bị chặn", "REVIEW": "Đang kiểm tra", "READY": "Chưa chạy",
           "BACKLOG": "Chưa chạy", "PAUSED": "Tạm dừng", "REWORK": "Cần làm lại", "RUNNING": "Đang chạy",
           "UNKNOWN_AFTER_CRASH": "Cần xem lại", "CLAIMED": "Đã nhận", "OUTPUT_READY": "Có kết quả"}
INTEGRATION_VI = {"integrated": "Đã tích hợp vào nhánh chính", "ready": "Sẵn sàng tích hợp (chờ bạn bấm)",
                  "conflict": "Cần xử lý xung đột — chưa tích hợp", "not_applicable": "Không có thay đổi tệp để tích hợp",
                  "none": "Chưa xử lý"}
PRIO_VI = {"MUST": "Bắt buộc", "SHOULD": "Nên có", "LATER": "Để sau", "DROP": "Không làm"}


def build_report(services, wo_id: str, git_diffstat: str | None = None) -> str:
    st, db = services.store, services.db
    wo = st.get_work_order(wo_id)
    proj = services.registry.get(wo.project_id)
    tasks = st.list_work_order_tasks(wo_id, services.manager._current_plan_version(wo_id))
    with db.lock:
        scope = db.conn.execute("SELECT * FROM scopes WHERE work_order_id=? AND status='approved' ORDER BY version DESC LIMIT 1",
                                (wo_id,)).fetchone()
        feats = db.conn.execute("SELECT name,priority,note FROM features WHERE scope_id=?", (scope["scope_id"],)).fetchall() if scope else []
        tests = db.conn.execute("SELECT * FROM test_runs WHERE work_order_id=? ORDER BY created_at, rowid", (wo_id,)).fetchall()
        commits = db.conn.execute("SELECT * FROM git_commit_events WHERE status='committed' AND task_id IN "
                                  "(SELECT task_id FROM tasks WHERE work_order_id=?) ORDER BY at, rowid", (wo_id,)).fetchall()
        branches = db.conn.execute("SELECT * FROM git_branches WHERE work_order_id=? ORDER BY created_at, rowid", (wo_id,)).fetchall()
        providers = db.conn.execute("SELECT DISTINCT provider_id FROM agent_sessions WHERE work_order_id=?", (wo_id,)).fetchall()
        reviews = {r["task_id"]: r for r in db.conn.execute(
            "SELECT * FROM reviews WHERE reviewer_task_id<>task_id ORDER BY created_at, rowid")}
    modes = {"fast_lane": "Nhanh (1 người làm + 1 người kiểm tra)", "standard": "Tiêu chuẩn (phân tích → thực hiện → kiểm tra)",
             "full": "Đầy đủ (thiết kế → giao diện/dữ liệu → kiểm tra → đóng gói)"}
    read_only = not branches
    L = [f"# Báo cáo bàn giao: {wo.title}", "",
         f"- **Dự án:** {proj.display_name}", f"- **Thư mục:** `{proj.root_path}`",
         f"- **Trạng thái:** {WO_STATE_VI.get(wo.state, wo.state)}", f"- **Lập báo cáo lúc:** {utcnow()[:19].replace('T', ' ')} (UTC)", "",
         "## Yêu cầu của bạn", "", (wo.brief or wo.title), ""]
    if scope:
        L += ["## Phạm vi bạn đã duyệt", "", f"Phương án **{scope['title_vi']}** (quy mô {scope['effort']}). {scope['cost_note']}", ""]
        for prio in ("MUST", "SHOULD", "LATER", "DROP"):
            names = [f"{f['name']}" + (f" ({f['note']})" if f["note"] else "") for f in feats if f["priority"] == prio]
            if names:
                L.append(f"- **{PRIO_VI[prio]}:** " + "; ".join(names))
        L.append("")
    L += ["## Cách thực hiện", "", f"- Chế độ làm việc: {modes.get(wo.plan_mode or '', 'chưa lập kế hoạch')}",
          f"- Trợ lý AI đã dùng: {', '.join(p['provider_id'] for p in providers) or '(chưa chạy)'}", "",
          "## Kết quả từng công việc", "", "| Công việc | Người phụ trách | Kết quả | Kiểm tra độc lập |", "|---|---|---|---|"]
    for t in tasks:
        rv = reviews.get(t.task_id)
        chk = "—" if rv is None else ("Đạt" if rv["verdict"] == "pass" else "Chưa đạt")
        extra = f" (làm lại {t.rework_count} lần)" if t.rework_count else ""
        L.append(f"| {t.title[:70]} | {ROLE_TITLES_VI.get(t.role_id or '', '')} | {TASK_VI.get(t.state, t.state)}{extra} | {chk} |")
    L += ["", "## Kiểm thử", ""]
    if tests:
        for tr in tests:
            L.append(f"- `{' '.join(json.loads(tr['argv']))}` → **{ {'passed': 'ĐẠT', 'failed': 'KHÔNG ĐẠT', 'timeout': 'QUÁ GIỜ', 'error': 'LỖI'}[tr['status']] }** "
                     f"({tr['duration_ms']} ms)")
    else:
        L.append("- **Chưa có lệnh kiểm thử tự động cho dự án này**, nên kết quả chỉ được kiểm tra bằng đối chiếu của bước kiểm tra, chưa được chạy thử.")
    L += ["", "## Phiên bản đã lưu", ""]
    if commits:
        for c in commits:
            L.append(f"- Nhánh `{c['branch']}` — phiên bản `{c['sha'][:10]}`")
        if git_diffstat:
            L += ["", "```", git_diffstat.strip(), "```"]
    elif read_only:
        L.append("- Lần này hệ thống làm ở **chế độ chỉ đọc**: kết quả là đề xuất bằng văn bản, **chưa có tệp nào bị sửa**.")
    else:
        L.append("- Chưa có phiên bản nào được lưu.")
    L += ["", f"**Tích hợp:** {INTEGRATION_VI.get(wo.integration_status, wo.integration_status)}" + (f" — {wo.integration_note}" if wo.integration_note else ""), ""]
    L += ["## Điều chưa làm và rủi ro", ""]
    later = [f["name"] for f in feats if f["priority"] in ("LATER", "DROP")]
    if later:
        L.append("- Hoãn/không làm theo phạm vi đã duyệt: " + "; ".join(later) + ".")
    if not tests:
        L.append("- Chưa có kiểm thử tự động: hãy tự thử các chức năng quan trọng trước khi dùng.")
    if read_only:
        L.append("- Chưa có thay đổi nào được áp dụng vào tệp của dự án.")
    L += ["- Bước kiểm tra do trợ lý AI thực hiện nên **không độc lập hoàn toàn**; độ tin cậy dựa vào bằng chứng (phiên bản đã lưu, kết quả chạy thử).",
          "- Lịch sử phiên bản chỉ lưu trên máy này, **không phải bản sao lưu**. Hãy sao lưu thư mục dự án quan trọng.",
          "- AATPO không triển khai lên môi trường thật và không đẩy mã lên mạng.", ""]
    L += ["## Chi tiết kỹ thuật", "", f"- Mã yêu cầu: `{wo.work_order_id}`"]
    for b in branches:
        L.append(f"- Nhánh `{b['name']}` bắt đầu từ `{(b['base_sha'] or '')[:10]}`")
    return "\n".join(L) + "\n"


def save_report(services, wo_id: str, text: str) -> Path:
    """Stores the report as a hashed artifact (attached to the work order's last task) and returns its path."""
    from aatpo.evidence import artifacts
    st = services.store
    wo = st.get_work_order(wo_id)
    last = st.list_work_order_tasks(wo_id)[-1]
    aid = artifacts.save_text(services.db, services.manager.root, project_id=wo.project_id, work_order_id=wo_id,
                              task_id=last.task_id, run_id=f"report-{utcnow()[:19].replace(':', '')}", text=text, kind="report")
    with services.db.lock:
        return Path(services.db.conn.execute("SELECT path FROM artifacts WHERE artifact_id=?", (aid,)).fetchone()[0])
