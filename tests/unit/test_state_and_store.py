import sqlite3

import pytest

from aatpo.db.repositories import ConflictError, EvidenceRequired
from aatpo.domain.models import RunState, TaskState, WorkOrderState
from aatpo.domain.state_machine import InvalidTransition


@pytest.fixture
def proj(svc, tmp_path):
    d = tmp_path / "p1"
    d.mkdir()
    return svc.registry.register(d, "P1", auto_history=False)


def _task(svc, proj, title="t"):
    wo = svc.store.create_work_order(proj.project_id, "wo")
    return wo, svc.store.create_task(wo.work_order_id, title)


def test_work_order_transitions(svc, proj):
    wo = svc.store.create_work_order(proj.project_id, "x")
    with pytest.raises(InvalidTransition):
        svc.store.transition_work_order(wo.work_order_id, WorkOrderState.EXECUTING, wo.version)
    wo = svc.store.transition_work_order(wo.work_order_id, WorkOrderState.DISCOVERING, wo.version)
    assert wo.state == WorkOrderState.DISCOVERING and wo.version == 2


def test_task_done_requires_evidence_and_valid_path(svc, proj):
    _, t = _task(svc, proj)
    with pytest.raises(EvidenceRequired):
        svc.store.transition_task(t.task_id, TaskState.DONE, t.version)
    with pytest.raises(InvalidTransition):  # evidence given but BACKLOG -> DONE is still illegal
        svc.store.transition_task(t.task_id, TaskState.DONE, t.version, evidence_id="EV-1")


def test_atomic_claim_rejects_stale_version(svc, proj):
    _, t = _task(svc, proj)
    t2 = svc.store.transition_task(t.task_id, TaskState.READY, t.version)
    svc.store.transition_task(t.task_id, TaskState.CLAIMED, t2.version)
    with pytest.raises(ConflictError):
        svc.store.transition_task(t.task_id, TaskState.CLAIMED, t2.version)  # second claimer loses
    assert len(svc.store.events("task.transition")) == 2  # the lost claim was not journalled


def test_session_isolation_roles_tasks_providers(svc, proj):
    wo = svc.store.create_work_order(proj.project_id, "wo")
    t1, t2 = (svc.store.create_task(wo.work_order_id, n) for n in ("a", "b"))
    s = svc.store
    # same CLI, three roles on one task -> three sessions (A10)
    sess = {r: s.open_session(s.create_assignment(t1.task_id, r, "codex").assignment_id)
            for r in ("backend_engineer", "frontend_engineer", "qa_engineer")}
    assert len({x.session_id for x in sess.values()}) == 3
    # same role+provider on another task -> different session (A11)
    other = s.open_session(s.create_assignment(t2.task_id, "backend_engineer", "codex").assignment_id)
    assert other.session_id != sess["backend_engineer"].session_id
    assert other.task_id == t2.task_id
    # same role, other provider on same task -> different session (A13)
    gem = s.open_session(s.create_assignment(t1.task_id, "backend_engineer", "gemini").assignment_id)
    assert gem.session_id != sess["backend_engineer"].session_id
    # opening twice is idempotent: never a second session for one assignment
    a = s.create_assignment(t2.task_id, "qa_engineer", "claude")
    assert s.open_session(a.assignment_id).session_id == s.open_session(a.assignment_id).session_id
    # duplicate assignment for the same (task, role, provider) is rejected by the schema
    with pytest.raises(sqlite3.IntegrityError):
        s.create_assignment(t1.task_id, "backend_engineer", "codex")
    # every session carries its project via ancestry
    assert all(x.project_id == proj.project_id for x in s.list_sessions())


def test_run_success_does_not_complete_task(svc, proj):
    _, t = _task(svc, proj)
    s = svc.store
    sess = s.open_session(s.create_assignment(t.task_id, "backend_engineer", "fake").assignment_id)
    r = s.create_run(sess.session_id, "idem-1")
    with pytest.raises(sqlite3.IntegrityError):
        s.create_run(sess.session_id, "idem-1")
    s.transition_run(r.run_id, RunState.RUNNING)
    r = s.transition_run(r.run_id, RunState.SUCCEEDED, exit_code=0)
    assert r.state == RunState.SUCCEEDED and r.finished_at
    assert s.get_task(t.task_id).state == TaskState.BACKLOG
    with pytest.raises(InvalidTransition):
        s.transition_run(r.run_id, RunState.RUNNING)


def test_events_append_only(svc, proj):
    with pytest.raises(sqlite3.DatabaseError):
        svc.db.conn.execute("DELETE FROM events")
    with pytest.raises(sqlite3.DatabaseError):
        svc.db.conn.execute("UPDATE events SET kind='x'")


def test_reconcile_marks_running_unknown_not_replayed(svc, proj):
    _, t = _task(svc, proj)
    s = svc.store
    t = s.transition_task(t.task_id, TaskState.READY, t.version)
    t = s.transition_task(t.task_id, TaskState.CLAIMED, t.version)
    t = s.transition_task(t.task_id, TaskState.RUNNING, t.version)
    sess = s.open_session(s.create_assignment(t.task_id, "backend_engineer", "fake").assignment_id)
    r = s.create_run(sess.session_id, "k")
    s.transition_run(r.run_id, RunState.RUNNING)
    assert s.reconcile_after_restart() == 1
    assert s.get_run(r.run_id).state == RunState.UNKNOWN_AFTER_CRASH
    assert s.get_task(t.task_id).state == TaskState.UNKNOWN_AFTER_CRASH


def test_schema_version_and_fk(svc):
    assert svc.db.conn.execute("PRAGMA user_version").fetchone()[0] == 3
    with pytest.raises(sqlite3.IntegrityError):
        svc.store.create_work_order("PRJ-missing", "x")


def test_fake_adapter_errors_are_not_success():
    from aatpo.cli.fake_adapter import FakeAdapter
    a = FakeAdapter()
    assert not a.parse_output("{not json", "", 0).ok
    assert not a.parse_output('{"text":"x"}', "boom", 3).ok
    assert a.parse_output('{"text":"x","session":"s1"}', "", 0).provider_session_id == "s1"
