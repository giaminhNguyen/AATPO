"""Persistence for the core entities. All state changes go through here, validated by the
deterministic state machine, version-checked, and journalled in the append-only events table."""
from __future__ import annotations

import json

from aatpo.db.connection import Database
from aatpo.domain import state_machine as sm
from aatpo.domain.models import (
    CORE_ROLES, PROVIDERS, ROLE_TITLES_VI, AgentSession, Assignment, ProcessRun, RunState,
    Task, TaskState, WorkOrder, WorkOrderState, new_id, utcnow,
)


class ConflictError(RuntimeError):
    """Optimistic-lock failure: someone else changed the row first."""


class EvidenceRequired(ValueError):
    """Task.DONE needs verified evidence, never just a process success or an AI claim."""


class Store:
    def __init__(self, db: Database):
        self.db = db
        self._seed()

    # ---- events -------------------------------------------------------------------------
    def log_event(self, conn, kind: str, entity_type: str | None = None, entity_id: str | None = None,
                  project_id: str | None = None, **detail) -> None:
        conn.execute(
            "INSERT INTO events(at,kind,entity_type,entity_id,project_id,detail) VALUES(?,?,?,?,?,?)",
            (utcnow(), kind, entity_type, entity_id, project_id, json.dumps(detail, ensure_ascii=False)),
        )

    def events(self, kind: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM events", ()
        if kind:
            q, a = q + " WHERE kind=?", (kind,)
        with self.db.lock:
            return [dict(r) for r in self.db.conn.execute(q + " ORDER BY event_id", a)]

    def _seed(self) -> None:
        with self.db.tx() as c:
            for r in CORE_ROLES:
                c.execute("INSERT OR IGNORE INTO agent_roles(role_id,title_vi) VALUES(?,?)",
                          (r, ROLE_TITLES_VI[r]))
            for p in PROVIDERS:
                c.execute("INSERT OR IGNORE INTO provider_registry(provider_id) VALUES(?)", (p,))

    # ---- work orders / tasks ------------------------------------------------------------
    def create_work_order(self, project_id: str, title: str) -> WorkOrder:
        wid, now = new_id("WO"), utcnow()
        with self.db.tx() as c:
            c.execute("INSERT INTO work_orders VALUES(?,?,?,?,1,?,?)",
                      (wid, project_id, title, WorkOrderState.RECEIVED, now, now))
            self.log_event(c, "work_order.created", "work_order", wid, project_id, title=title)
        return self.get_work_order(wid)

    def get_work_order(self, wid: str) -> WorkOrder:
        with self.db.lock:
            row = self.db.conn.execute("SELECT * FROM work_orders WHERE work_order_id=?", (wid,)).fetchone()
        if row is None:
            raise KeyError(wid)
        return WorkOrder(**row)

    def list_work_orders(self, project_id: str) -> list[WorkOrder]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT * FROM work_orders WHERE project_id=? ORDER BY created_at", (project_id,))
            return [WorkOrder(**r) for r in rows]

    def transition_work_order(self, wid: str, to: WorkOrderState, expected_version: int) -> WorkOrder:
        with self.db.tx() as c:
            row = c.execute("SELECT * FROM work_orders WHERE work_order_id=?", (wid,)).fetchone()
            if row is None:
                raise KeyError(wid)
            if row["version"] != expected_version:
                raise ConflictError(f"work order {wid} changed concurrently")
            sm.check(sm.WORK_ORDER, WorkOrderState(row["state"]), to)
            n = c.execute(
                "UPDATE work_orders SET state=?, version=version+1, updated_at=? "
                "WHERE work_order_id=? AND version=?", (to, utcnow(), wid, expected_version)).rowcount
            if n == 0:
                raise ConflictError(f"work order {wid} changed concurrently")
            self.log_event(c, "work_order.transition", "work_order", wid, row["project_id"],
                           src=row["state"], dst=str(to))
        return self.get_work_order(wid)

    def create_task(self, work_order_id: str, title: str) -> Task:
        tid, now = new_id("TASK"), utcnow()
        with self.db.tx() as c:
            pid = c.execute("SELECT project_id FROM work_orders WHERE work_order_id=?",
                            (work_order_id,)).fetchone()["project_id"]
            c.execute("INSERT INTO tasks VALUES(?,?,?,?,1,?,?)",
                      (tid, work_order_id, title, TaskState.BACKLOG, now, now))
            self.log_event(c, "task.created", "task", tid, pid, title=title)
        return self.get_task(tid)

    def get_task(self, tid: str) -> Task:
        with self.db.lock:
            row = self.db.conn.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
        if row is None:
            raise KeyError(tid)
        return Task(**row)

    def list_tasks(self, project_id: str) -> list[Task]:
        with self.db.lock:
            rows = self.db.conn.execute(
                "SELECT t.* FROM tasks t JOIN work_orders w USING(work_order_id) "
                "WHERE w.project_id=? ORDER BY t.created_at", (project_id,))
            return [Task(**r) for r in rows]

    def transition_task(self, tid: str, to: TaskState, expected_version: int,
                        evidence_id: str | None = None) -> Task:
        """`evidence_id` must reference verified evidence (QA/test) to reach DONE (spec 5.3)."""
        if to == TaskState.DONE and not evidence_id:
            raise EvidenceRequired("Task.DONE requires verified evidence")
        with self.db.tx() as c:
            row = c.execute("SELECT t.*, w.project_id FROM tasks t JOIN work_orders w USING(work_order_id) "
                            "WHERE task_id=?", (tid,)).fetchone()
            if row is None:
                raise KeyError(tid)
            if row["version"] != expected_version:
                raise ConflictError(f"task {tid} changed concurrently (atomic claim failed)")
            sm.check(sm.TASK, TaskState(row["state"]), to)
            n = c.execute("UPDATE tasks SET state=?, version=version+1, updated_at=? "
                          "WHERE task_id=? AND version=?", (to, utcnow(), tid, expected_version)).rowcount
            if n == 0:
                raise ConflictError(f"task {tid} changed concurrently (atomic claim failed)")
            self.log_event(c, "task.transition", "task", tid, row["project_id"],
                           src=row["state"], dst=str(to), evidence_id=evidence_id)
        return self.get_task(tid)

    # ---- assignments / sessions / runs --------------------------------------------------
    def create_assignment(self, task_id: str, role_id: str, provider_id: str) -> Assignment:
        aid = new_id("ASG")
        with self.db.tx() as c:
            c.execute("INSERT INTO assignments VALUES(?,?,?,?,?)", (aid, task_id, role_id, provider_id, utcnow()))
        return self.get_assignment(aid)

    def get_assignment(self, aid: str) -> Assignment:
        with self.db.lock:
            return Assignment(**self.db.conn.execute(
                "SELECT * FROM assignments WHERE assignment_id=?", (aid,)).fetchone())

    def open_session(self, assignment_id: str) -> AgentSession:
        """Exactly one session per assignment; scope fields are derived, never caller-supplied,
        so a session cannot be attached to the wrong task/project/role/provider."""
        with self.db.tx() as c:
            row = c.execute(
                "SELECT a.*, t.work_order_id, w.project_id FROM assignments a "
                "JOIN tasks t USING(task_id) JOIN work_orders w USING(work_order_id) "
                "WHERE a.assignment_id=?", (assignment_id,)).fetchone()
            if row is None:
                raise KeyError(assignment_id)
            existing = c.execute("SELECT * FROM agent_sessions WHERE assignment_id=?", (assignment_id,)).fetchone()
            if existing:
                return AgentSession(**existing)
            sid = new_id("SESS")
            c.execute("INSERT INTO agent_sessions(session_id,assignment_id,project_id,work_order_id,task_id,"
                      "role_id,provider_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
                      (sid, assignment_id, row["project_id"], row["work_order_id"], row["task_id"],
                       row["role_id"], row["provider_id"], utcnow()))
            self.log_event(c, "session.opened", "session", sid, row["project_id"], task_id=row["task_id"])
            return AgentSession(**c.execute("SELECT * FROM agent_sessions WHERE session_id=?", (sid,)).fetchone())

    def set_provider_session_id(self, session_id: str, provider_session_id: str) -> None:
        with self.db.tx() as c:
            c.execute("UPDATE agent_sessions SET provider_session_id=? WHERE session_id=?",
                      (provider_session_id, session_id))

    def create_run(self, session_id: str, idempotency_key: str) -> ProcessRun:
        rid = new_id("RUN")
        with self.db.tx() as c:
            c.execute("INSERT INTO process_runs(run_id,session_id,state,idempotency_key,created_at) "
                      "VALUES(?,?,?,?,?)", (rid, session_id, RunState.QUEUED, idempotency_key, utcnow()))
        return self.get_run(rid)

    def get_run(self, rid: str) -> ProcessRun:
        with self.db.lock:
            return ProcessRun(**self.db.conn.execute("SELECT * FROM process_runs WHERE run_id=?", (rid,)).fetchone())

    def transition_run(self, rid: str, to: RunState, exit_code: int | None = None) -> ProcessRun:
        """A run finishing never changes Task state: SUCCEEDED != DONE."""
        with self.db.tx() as c:
            row = c.execute("SELECT * FROM process_runs WHERE run_id=?", (rid,)).fetchone()
            sm.check(sm.RUN, RunState(row["state"]), to)
            now = utcnow()
            c.execute("UPDATE process_runs SET state=?, exit_code=COALESCE(?,exit_code), "
                      "started_at=CASE WHEN ?='RUNNING' THEN ? ELSE started_at END, "
                      "finished_at=CASE WHEN ? IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','UNKNOWN_AFTER_CRASH') "
                      "THEN ? ELSE finished_at END WHERE run_id=?",
                      (to, exit_code, str(to), now, str(to), now, rid))
        return self.get_run(rid)

    def list_sessions(self, task_id: str | None = None) -> list[AgentSession]:
        q, a = "SELECT * FROM agent_sessions", ()
        if task_id:
            q, a = q + " WHERE task_id=?", (task_id,)
        with self.db.lock:
            return [AgentSession(**r) for r in self.db.conn.execute(q, a)]

    def reconcile_after_restart(self) -> int:
        """RUNNING runs after a restart are uncertain: mark UNKNOWN_AFTER_CRASH, never replay."""
        with self.db.tx() as c:
            ids = [r["run_id"] for r in c.execute("SELECT run_id FROM process_runs WHERE state='RUNNING'")]
            for rid in ids:
                c.execute("UPDATE process_runs SET state='UNKNOWN_AFTER_CRASH', finished_at=? WHERE run_id=?",
                          (utcnow(), rid))
                self.log_event(c, "run.unknown_after_crash", "run", rid)
            c.execute("UPDATE tasks SET state='UNKNOWN_AFTER_CRASH', version=version+1, updated_at=? "
                      "WHERE state='RUNNING'", (utcnow(),))
        return len(ids)
