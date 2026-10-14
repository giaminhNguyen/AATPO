"""TaskPlan contract + validator (A20). A plan is DATA proposed by a planner (rules or LLM);
only a validated plan is persisted."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from aatpo.domain.models import CORE_ROLES

MAX_TASKS = 12


class PlanRejected(ValueError):
    pass


class TaskSpec(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    title: str = Field(min_length=1, max_length=200)
    role: str
    depends_on: list[str] = []
    writes: bool = False
    acceptance: str = Field(min_length=1, max_length=1000)


class TaskPlan(BaseModel):
    mode: Literal["fast_lane", "standard", "full"]
    tasks: list[TaskSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        keys = [t.key for t in self.tasks]
        if len(keys) != len(set(keys)):
            raise ValueError("trùng khóa công việc")
        if len(keys) > MAX_TASKS:
            raise ValueError(f"kế hoạch quá lớn (>{MAX_TASKS} công việc)")
        for t in self.tasks:
            if t.role not in CORE_ROLES:
                raise ValueError(f"vai trò không hợp lệ: {t.role}")
            for d in t.depends_on:
                if d not in keys:
                    raise ValueError(f"công việc '{t.key}' phụ thuộc vào '{d}' không tồn tại")
                if d == t.key:
                    raise ValueError(f"công việc '{t.key}' phụ thuộc vào chính nó")
        _assert_acyclic({t.key: t.depends_on for t in self.tasks})
        qa = [t for t in self.tasks if t.role == "qa_engineer"]
        if not qa:
            raise ValueError("kế hoạch phải có bước kiểm tra (qa_engineer)")
        for t in self.tasks:  # every task that changes things must be reviewed by an independent QA task
            if t.writes and not any(t.key in q.depends_on for q in qa):
                raise ValueError(f"công việc '{t.key}' ghi thay đổi nhưng không có bước kiểm tra phụ thuộc vào nó")
        return self


def _assert_acyclic(graph: dict[str, list[str]]) -> None:
    """Kahn's algorithm; anything left over is on a cycle."""
    indeg = {k: len(v) for k, v in graph.items()}
    ready = [k for k, d in indeg.items() if d == 0]
    seen = 0
    while ready:
        n = ready.pop()
        seen += 1
        for k, deps in graph.items():
            if n in deps:
                indeg[k] -= 1
                if indeg[k] == 0:
                    ready.append(k)
    if seen != len(graph):
        raise ValueError("kế hoạch có vòng phụ thuộc")


def validate_plan(raw: dict | TaskPlan) -> TaskPlan:
    try:
        return raw if isinstance(raw, TaskPlan) else TaskPlan.model_validate(raw)
    except ValidationError as e:
        msg = "; ".join(err["msg"].removeprefix("Value error, ") for err in e.errors())
        raise PlanRejected(msg) from e
