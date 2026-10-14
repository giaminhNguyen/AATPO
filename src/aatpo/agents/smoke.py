"""Opt-in read-only smoke request. Policy lives here (deterministic), not in the GUI."""
from __future__ import annotations

from aatpo.cli.base import AgentRunResult
from aatpo.domain.models import ProcessRun, Project

SMOKE_PROMPT = ("Chỉ đọc: tuyệt đối không sửa, tạo hay xóa tệp và không chạy lệnh. "
                "Hãy trả lời tối đa 5 dòng bằng tiếng Việt: thư mục làm việc hiện tại chủ yếu chứa loại tệp nào?")


async def run_readonly_smoke(services, provider_id: str, project: Project, *, consent: bool,
                             timeout: int = 180) -> tuple[ProcessRun, AgentRunResult]:
    if not consent:  # a chat message or a default can never stand in for this
        raise PermissionError("Cần sự đồng ý của người dùng trước khi gửi dữ liệu tới dịch vụ AI")
    if provider_id not in services.adapters:
        raise KeyError(provider_id)
    if services.registry.path_missing(project):
        raise FileNotFoundError("Không tìm thấy thư mục dự án")
    st = services.store
    wo = st.create_work_order(project.project_id, "Kiểm tra kết nối trợ lý AI (chỉ đọc)")
    task = st.create_task(wo.work_order_id, f"Thử yêu cầu chỉ đọc với {provider_id}")
    asg = st.create_assignment(task.task_id, "client_representative", provider_id)  # new task => new session
    with services.db.tx() as c:
        st.log_event(c, "smoke.consented", "task", task.task_id, project.project_id, provider=provider_id)
    return await services.sessions.execute(asg.assignment_id, SMOKE_PROMPT, project.root_path, timeout=timeout)
