"""Validated contracts between the (untrusted) language layer and the deterministic services."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentAction = Literal[
    "create_project", "open_project", "new_work_order", "start_work", "pause_work",
    "show_progress", "change_request", "approve_attempt", "prefer_lean", "unknown",
]


class Intent(BaseModel):
    """Proposal only. Nothing here is authority: the policy layer decides what actually happens."""
    action: IntentAction
    project_hint: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    kind: Literal["product", "change", "general"] = "general"
    source: Literal["rules", "llm"] = "rules"


class UiAction(BaseModel):
    kind: Literal["quick_reply", "pick_folder_create", "pick_folder_open", "switch_project",
                  "pick_project", "view_scope", "view_progress"]
    label: str
    payload: dict = {}


class ChatReply(BaseModel):
    text: str
    actions: list[UiAction] = []
