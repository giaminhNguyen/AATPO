"""Domain models. Seven distinct entities with separate IDs (spec 3.3):
Project, WorkOrder, CLIProvider, AgentRole, Task, AgentSession, ProcessRun."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ProjectType(StrEnum):
    EXISTING_CODE = "existing_code"
    NEW_PRODUCT = "new_product"
    RESEARCH = "research"
    OTHER = "other"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class WorkOrderState(StrEnum):
    RECEIVED = "RECEIVED"
    DISCOVERING = "DISCOVERING"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    SCOPE_PROPOSED = "SCOPE_PROPOSED"
    SCOPE_CONFIRMED = "SCOPE_CONFIRMED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    PACKAGING = "PACKAGING"
    DELIVERED = "DELIVERED"
    ACCEPTED = "ACCEPTED"
    PAUSED_APPROVAL = "PAUSED_APPROVAL"
    PAUSED_QUOTA = "PAUSED_QUOTA"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"


class TaskState(StrEnum):
    BACKLOG = "BACKLOG"
    READY = "READY"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    OUTPUT_READY = "OUTPUT_READY"
    REVIEW = "REVIEW"
    DONE = "DONE"
    REWORK = "REWORK"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    UNKNOWN_AFTER_CRASH = "UNKNOWN_AFTER_CRASH"


class RunState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"  # process finished - NOT task done
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    UNKNOWN_AFTER_CRASH = "UNKNOWN_AFTER_CRASH"


CORE_ROLES = (
    "client_representative", "business_analyst", "office_manager", "system_architect",
    "frontend_engineer", "backend_engineer", "qa_engineer", "devops_engineer",
)

ROLE_TITLES_VI = {
    "client_representative": "Đại diện khách hàng",
    "business_analyst": "Chuyên viên phân tích nghiệp vụ",
    "office_manager": "Quản lý văn phòng",
    "system_architect": "Kiến trúc sư hệ thống",
    "frontend_engineer": "Kỹ sư giao diện",
    "backend_engineer": "Kỹ sư xử lý dữ liệu",
    "qa_engineer": "Kỹ sư kiểm thử",
    "devops_engineer": "Kỹ sư đóng gói & bàn giao",
}

PROVIDERS = ("codex", "claude", "gemini", "fake")


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class Project(_Row):
    project_id: str
    display_name: str
    root_path: str
    project_type: ProjectType
    status: ProjectStatus
    selected_at: str | None = None
    created_at: str
    updated_at: str
    notes: str | None = None
    repo_detected: bool = False
    git_auto_history: bool = False
    git_default_branch: str | None = None


class WorkOrder(_Row):
    work_order_id: str
    project_id: str
    title: str
    state: WorkOrderState
    version: int
    created_at: str
    updated_at: str
    kind: str = "general"                  # product | change | general
    requires_scope_approval: bool = False
    parent_work_order_id: str | None = None
    brief: str | None = None


class CLIProvider(_Row):
    provider_id: str
    executable: str | None = None
    version: str | None = None
    status: str = "unknown"  # missing|not_authenticated|quota_exhausted|unsupported_version|unhealthy|ready|unknown


class AgentRole(_Row):
    role_id: str
    profile_version: int = 1
    title_vi: str = ""


class Task(_Row):
    task_id: str
    work_order_id: str
    title: str
    state: TaskState
    version: int
    created_at: str
    updated_at: str


class Assignment(_Row):
    assignment_id: str
    task_id: str
    role_id: str
    provider_id: str
    created_at: str


class AgentSession(_Row):
    session_id: str
    assignment_id: str
    project_id: str
    work_order_id: str
    task_id: str
    role_id: str
    provider_id: str
    provider_session_id: str | None = None
    created_at: str
    generation: int = 1
    supersedes_session_id: str | None = None
    fallback_reason: str | None = None
    handoff_brief: str | None = None


class ProcessRun(_Row):
    run_id: str
    session_id: str
    state: RunState
    idempotency_key: str
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str
