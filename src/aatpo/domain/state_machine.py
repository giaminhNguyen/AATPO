"""Deterministic transition tables (spec 5.2, 5.3). LLM output never sets state directly."""
from __future__ import annotations

from aatpo.domain.models import RunState as R
from aatpo.domain.models import TaskState as T
from aatpo.domain.models import WorkOrderState as W


class InvalidTransition(ValueError):
    pass


_PAUSE_FAIL = {W.PAUSED_APPROVAL, W.PAUSED_QUOTA, W.BLOCKED, W.FAILED, W.CANCELLED}
WORK_ORDER: dict[W, set[W]] = {
    W.RECEIVED: {W.DISCOVERING, W.CANCELLED},
    W.DISCOVERING: {W.WAITING_CUSTOMER, W.SCOPE_PROPOSED} | _PAUSE_FAIL,
    W.WAITING_CUSTOMER: {W.DISCOVERING, W.CANCELLED},
    W.SCOPE_PROPOSED: {W.SCOPE_CONFIRMED, W.DISCOVERING, W.CANCELLED},
    W.SCOPE_CONFIRMED: {W.PLANNED} | _PAUSE_FAIL,
    W.PLANNED: {W.EXECUTING} | _PAUSE_FAIL,
    W.EXECUTING: {W.VERIFYING, W.PACKAGING} | _PAUSE_FAIL,
    W.VERIFYING: {W.EXECUTING, W.PACKAGING} | _PAUSE_FAIL,
    W.PACKAGING: {W.DELIVERED} | _PAUSE_FAIL,
    W.DELIVERED: {W.ACCEPTED, W.CHANGE_REQUESTED},
    W.ACCEPTED: {W.CHANGE_REQUESTED},
    W.PAUSED_APPROVAL: {W.EXECUTING, W.PLANNED, W.CANCELLED},
    W.PAUSED_QUOTA: {W.EXECUTING, W.PLANNED, W.CANCELLED},
    W.BLOCKED: {W.PLANNED, W.EXECUTING, W.CANCELLED},
    W.FAILED: set(),
    W.CANCELLED: set(),
    W.CHANGE_REQUESTED: {W.DISCOVERING, W.SCOPE_PROPOSED, W.CANCELLED},
}

TASK: dict[T, set[T]] = {
    T.BACKLOG: {T.READY, T.BLOCKED},
    T.READY: {T.CLAIMED, T.BLOCKED, T.PAUSED},
    T.CLAIMED: {T.RUNNING, T.READY},
    T.RUNNING: {T.OUTPUT_READY, T.BLOCKED, T.PAUSED, T.FAILED, T.UNKNOWN_AFTER_CRASH},
    T.OUTPUT_READY: {T.REVIEW},
    T.REVIEW: {T.DONE, T.REWORK, T.FAILED},
    T.REWORK: {T.READY},
    T.BLOCKED: {T.READY},
    T.PAUSED: {T.READY},
    T.FAILED: set(),
    T.DONE: set(),
    T.UNKNOWN_AFTER_CRASH: {T.READY, T.FAILED},  # only after human review
}

RUN: dict[R, set[R]] = {
    R.QUEUED: {R.RUNNING, R.CANCELLED},
    R.RUNNING: {R.SUCCEEDED, R.FAILED, R.TIMED_OUT, R.CANCELLED, R.UNKNOWN_AFTER_CRASH},
    R.SUCCEEDED: set(), R.FAILED: set(), R.TIMED_OUT: set(),
    R.CANCELLED: set(), R.UNKNOWN_AFTER_CRASH: set(),
}


def check(table: dict, src, dst) -> None:
    if dst not in table[src]:
        raise InvalidTransition(f"{src} -> {dst} is not allowed")
