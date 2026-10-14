"""Session ledger driver: one assignment -> session(s) -> process runs.
Resumes the EXACT stored provider session id when the adapter verified support; otherwise records
why and starts a NEW session with a compact brief. Never touches Task state: a finished run is only evidence."""
from __future__ import annotations

from aatpo.cli.base import AgentRunRequest, AgentRunResult
from aatpo.cli.probe import mark_quota_exhausted
from aatpo.db.repositories import Store
from aatpo.domain.models import ProcessRun, RunState, new_id


class SessionManager:
    def __init__(self, store: Store, adapters: dict):
        self.store, self.adapters = store, adapters

    async def execute(self, assignment_id: str, prompt: str, project_root: str, *, brief: str = "",
                      timeout: int = 900, idempotency_key: str | None = None) -> tuple[ProcessRun, AgentRunResult]:
        asg = self.store.get_assignment(assignment_id)
        adapter = self.adapters[asg.provider_id]
        session = self.store.open_session(assignment_id)
        resume_id = session.provider_session_id
        if resume_id and not getattr(adapter, "supports_exact_resume", False):
            session = self.store.start_fallback_session(
                assignment_id, "nhà cung cấp chưa được kiểm chứng hỗ trợ tiếp tục đúng phiên", brief)
            resume_id = None
        run = self.store.create_run(session.session_id, idempotency_key or new_id("IDEM"))
        req = AgentRunRequest(session_id=session.session_id, run_id=run.run_id, project_root=project_root,
                              prompt=(f"{session.handoff_brief}\n\n{prompt}" if session.handoff_brief else prompt),
                              timeout_seconds=timeout)
        self.store.transition_run(run.run_id, RunState.RUNNING)
        try:
            res = await (adapter.resume(req, resume_id) if resume_id else adapter.run(req))
        except Exception as e:  # adapter bug must not leave a run stuck in RUNNING
            res = AgentRunResult(ok=False, error=f"lỗi bộ điều khiển: {type(e).__name__}")
        if resume_id and not res.ok and not (res.timed_out or res.cancelled or res.error_kind == "quota"):
            # exact resume broke (e.g. expired session): fall back once, explicitly
            self.store.transition_run(run.run_id, RunState.FAILED, res.exit_code)
            session = self.store.start_fallback_session(assignment_id, f"tiếp tục phiên thất bại: {res.error}", brief)
            run = self.store.create_run(session.session_id, new_id("IDEM"))
            self.store.transition_run(run.run_id, RunState.RUNNING)
            req = req.model_copy(update={"session_id": session.session_id, "run_id": run.run_id,
                                         "prompt": f"{brief}\n\n{prompt}" if brief else prompt})
            res = await adapter.run(req)
        if res.ok and res.provider_session_id:
            self.store.set_provider_session_id(session.session_id, res.provider_session_id)
        state = (RunState.SUCCEEDED if res.ok else RunState.TIMED_OUT if res.timed_out
                 else RunState.CANCELLED if res.cancelled else RunState.FAILED)
        if res.error_kind == "quota":
            mark_quota_exhausted(self.store.db, asg.provider_id)
        return self.store.transition_run(run.run_id, state, res.exit_code), res

    async def cancel(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        asg = self.store.get_assignment(self.store.get_session(run.session_id).assignment_id)
        await self.adapters[asg.provider_id].cancel(run_id)
