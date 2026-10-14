"""Rule-based planner: picks a work mode by policy and emits a TaskPlan that must pass validate_plan.
Not every role runs every time (spec G3): Fast Lane = 1 executor + review; Standard = BA/Dev/QA; Full = Architect/FE+BE/QA/DevOps."""
from __future__ import annotations

import json
import re

from aatpo.customer.text import fold
from aatpo.domain.models import WorkOrder
from aatpo.domain.plan import PlanRejected, TaskPlan, validate_plan

_UI = ("giao dien", "nut", "man hinh", "trang", "form", "bieu mau", "mau sac", "hien thi")


def choose_mode(wo: WorkOrder, effort: str) -> str:
    if wo.kind == "change" and effort in ("XS", "S"):
        return "fast_lane"
    return "standard" if effort in ("XS", "S", "M") else "full"


def _dev_role(wo: WorkOrder) -> str:
    f = fold(f"{wo.title} {wo.brief or ''}")
    return "frontend_engineer" if wo.kind == "change" and any(k in f for k in _UI) else "backend_engineer"


def build_plan(wo: WorkOrder, mode: str, must: list[str]) -> TaskPlan:
    goal = "; ".join(must) if must else wo.title
    acc = f"Đáp ứng các mục bắt buộc đã duyệt: {goal}"
    t = wo.title[:80]
    dev = _dev_role(wo)
    if mode == "fast_lane":
        tasks = [dict(key="implement", title=f"Thực hiện: {t}", role=dev, writes=True, acceptance=acc),
                 dict(key="review", title="Kiểm tra kết quả theo bằng chứng", role="qa_engineer",
                      depends_on=["implement"], acceptance="Kết quả khớp tiêu chí nghiệm thu và có bằng chứng.")]
    elif mode == "standard":
        tasks = [dict(key="analyze", title=f"Làm rõ tiêu chí nghiệm thu: {t}", role="business_analyst",
                      acceptance="Danh sách tiêu chí nghiệm thu cụ thể, kiểm chứng được."),
                 dict(key="implement", title=f"Thực hiện: {t}", role=dev, writes=True, depends_on=["analyze"], acceptance=acc),
                 dict(key="review", title="Kiểm tra kết quả theo bằng chứng", role="qa_engineer",
                      depends_on=["implement"], acceptance="Kết quả khớp tiêu chí nghiệm thu và có bằng chứng.")]
    else:
        tasks = [dict(key="design", title=f"Thiết kế tổng thể: {t}", role="system_architect",
                      acceptance="Kiến trúc và hợp đồng giữa các phần rõ ràng."),
                 dict(key="frontend", title="Làm phần giao diện", role="frontend_engineer", writes=True,
                      depends_on=["design"], acceptance=acc),
                 dict(key="backend", title="Làm phần xử lý dữ liệu", role="backend_engineer", writes=True,
                      depends_on=["design"], acceptance=acc),
                 dict(key="review", title="Kiểm tra kết quả theo bằng chứng", role="qa_engineer",
                      depends_on=["frontend", "backend"], acceptance="Kết quả khớp tiêu chí nghiệm thu và có bằng chứng."),
                 dict(key="package", title="Đóng gói và viết hướng dẫn bàn giao", role="devops_engineer",
                      depends_on=["review"], acceptance="Có hướng dẫn chạy và bàn giao; không triển khai lên môi trường thật.")]
    return validate_plan({"mode": mode, "tasks": tasks})


def parse_plan_json(raw: str) -> TaskPlan:
    """For an optional LLM planner: extract JSON, validate. Raises PlanRejected on anything off."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise PlanRejected("không có JSON kế hoạch")
    try:
        return validate_plan(json.loads(m.group(0)))
    except ValueError as e:
        raise PlanRejected(str(e)) from e
