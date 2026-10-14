import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from aatpo.agents.session_manager import SessionManager
from aatpo.cli.base import AgentRunRequest, AgentRunResult
from aatpo.cli.claude_adapter import ClaudeAdapter
from aatpo.cli.codex_adapter import CodexAdapter
from aatpo.cli.gemini_adapter import GeminiAdapter
from aatpo.cli.parsers import classify_error, parse_claude, parse_codex
from aatpo.db.connection import Database
from aatpo.domain.models import RunState, TaskState

FAKE = str(Path(__file__).parents[1] / "fixtures" / "fake_cli.py")
pytestmark = pytest.mark.mock_integration


def go(c):
    return asyncio.run(c)


# ---- parsers (A14) -----------------------------------------------------------------------
def test_claude_parser():
    ok = parse_claude(json.dumps({"type": "result", "result": "hi", "session_id": "11111111-2222"}), "", 0)
    assert ok.ok and ok.text == "hi" and ok.provider_session_id == "11111111-2222"
    assert not parse_claude("{broken", "", 0).ok                               # malformed JSON
    assert not parse_claude(json.dumps({"result": "x"}), "boom", 2).ok         # nonzero exit
    assert not parse_claude(json.dumps({"result": "limit", "is_error": True}), "", 0).ok
    assert not parse_claude(json.dumps({"nothing": 1}), "", 0).ok
    arr = parse_claude(json.dumps([{"type": "system"}, {"type": "result", "result": "r"}]), "", 0)
    assert arr.ok and arr.text == "r"
    assert parse_claude(json.dumps({"result": "r", "session_id": "bad id!"}), "", 0).provider_session_id is None


def test_codex_parser():
    jl = "\n".join(json.dumps(e) for e in (
        {"type": "thread.started", "thread_id": "aaaaaaaa-bbbb"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "mid"}}))
    r = parse_codex(jl, "", 0, "final")
    assert r.ok and r.text == "final" and r.provider_session_id == "aaaaaaaa-bbbb"
    assert parse_codex(jl, "", 0, None).text == "mid"
    assert not parse_codex(jl, "err", 1, "x").ok
    assert not parse_codex("", "", 0, "x").ok                                   # no events at all
    assert not parse_codex(jl + "\n{oops", "", 0, "x").ok                       # corrupted event line
    bad = parse_codex(json.dumps({"type": "error", "message": "usage limit reached"}), "", 0, None)
    assert not bad.ok and bad.error_kind == "quota"
    assert classify_error("HTTP 429 Too Many Requests") == "quota" and classify_error("syntax error") is None


# ---- adapter end-to-end against the fake CLI ----------------------------------------------
def _req(tmp_path, prompt="đọc thư mục"):
    return AgentRunRequest(session_id="S", run_id="R1", project_root=str(tmp_path), prompt=prompt, timeout_seconds=30)


def test_claude_adapter_runs_fake(tmp_path):
    a = ClaudeAdapter(command=[sys.executable, FAKE, "claude_ok"])
    r = go(a.run(_req(tmp_path, "Sửa lỗi & thử | rm -rf")))
    assert r.ok and r.text == "đã đọc xong" and r.provider_session_id.startswith("11111111")


def test_codex_adapter_runs_fake_and_reads_last_message_file(tmp_path):
    a = CodexAdapter(command=[sys.executable, FAKE, "codex_ok"])
    r = go(a.run(_req(tmp_path)))
    assert r.ok and r.text == "câu trả lời cuối" and r.provider_session_id.startswith("aaaaaaaa")


def test_adapter_failure_modes(tmp_path):
    for mode, expect in (("exit3", "lỗi giả lập"), ("badjson", "JSON")):
        r = go(ClaudeAdapter(command=[sys.executable, FAKE, mode]).run(_req(tmp_path)))
        assert not r.ok and expect in r.error
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in (r.error or "")   # redacted (A30)
    t = go(ClaudeAdapter(command=[sys.executable, FAKE, "sleep"]).run(
        _req(tmp_path).model_copy(update={"timeout_seconds": 1})))
    assert t.timed_out and not t.ok                                           # A19
    assert not go(ClaudeAdapter(command=[sys.executable, FAKE, "ok"]).run(
        _req(tmp_path / "nope"))).ok


def test_cancel_through_adapter(tmp_path):
    async def scenario():
        a = ClaudeAdapter(command=[sys.executable, FAKE, "sleep"])
        t = asyncio.ensure_future(a.run(_req(tmp_path).model_copy(update={"timeout_seconds": 60})))
        for _ in range(50):
            await asyncio.sleep(0.1)
            if await a.cancel("R1"):
                break
        return await t
    r = go(scenario())
    assert r.cancelled and not r.ok


def test_resume_rejects_garbage_session_id(tmp_path):
    a = ClaudeAdapter(command=[sys.executable, FAKE, "ok"])
    assert not go(a.resume(_req(tmp_path), "x; calc.exe")).ok


def test_launch_flags_are_read_only(tmp_path):
    scratch = Path(tmp_path)
    cx = CodexAdapter().run_argv(_req(tmp_path), scratch)
    assert cx[cx.index("-s") + 1] == "read-only" and "-" == cx[-1]
    assert "--permission-mode" in ClaudeAdapter().run_argv(_req(tmp_path), scratch)
    for argv in (cx, ClaudeAdapter().run_argv(_req(tmp_path), scratch), CodexAdapter().resume_argv(_req(tmp_path), "abcdefgh12", scratch)):
        assert not any(("dangerous" in a or "yolo" in a or "bypass" in a) for a in argv)


def test_gemini_is_graceful():
    g = GeminiAdapter(command=["definitely-missing-gemini"])
    assert go(g.probe()).status == "missing"
    assert not go(g.run(None)).ok


# ---- session manager ----------------------------------------------------------------------
class Scripted:
    """Adapter whose results are queued by the test."""
    provider_id = "fake"

    def __init__(self, results, resume_ok=True):
        self.results, self.calls, self.supports_exact_resume = list(results), [], resume_ok

    async def run(self, req):
        self.calls.append(("run", req.session_id, req.prompt, None))
        return self.results.pop(0)

    async def resume(self, req, sid):
        self.calls.append(("resume", req.session_id, req.prompt, sid))
        return self.results.pop(0)

    async def cancel(self, run_id):
        return True


@pytest.fixture
def world(svc, tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    p = svc.registry.register(d, "P", auto_history=False)
    wo = svc.store.create_work_order(p.project_id, "wo")
    return svc, p, wo, str(d)


def _asg(svc, wo, title="t", role="backend_engineer"):
    t = svc.store.create_task(wo.work_order_id, title)
    return t, svc.store.create_assignment(t.task_id, role, "fake")


def ok(sid="sess-0001-aaaa"):
    return AgentRunResult(ok=True, text="ok", provider_session_id=sid)


def test_first_run_stores_exact_provider_id_and_does_not_finish_task(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)
    ad = Scripted([ok("sess-0001-aaaa")])
    run, res = go(SessionManager(svc.store, {"fake": ad}).execute(a.assignment_id, "việc 1", root))
    assert run.state == RunState.SUCCEEDED
    assert svc.store.open_session(a.assignment_id).provider_session_id == "sess-0001-aaaa"
    assert svc.store.get_task(t.task_id).state == TaskState.BACKLOG


def test_rework_resumes_exact_id_when_supported(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)
    ad = Scripted([ok("sess-0001-aaaa"), ok("sess-0001-aaaa")])
    m = SessionManager(svc.store, {"fake": ad})
    go(m.execute(a.assignment_id, "lần 1", root))
    go(m.execute(a.assignment_id, "sửa lại", root))
    assert ad.calls[1][0] == "resume" and ad.calls[1][3] == "sess-0001-aaaa"      # A12
    assert len(svc.store.list_sessions(t.task_id)) == 1


def test_unsupported_resume_records_reason_and_starts_new_session(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)
    ad = Scripted([ok("sess-0001-aaaa"), ok("sess-0002-bbbb")], resume_ok=False)
    m = SessionManager(svc.store, {"fake": ad})
    go(m.execute(a.assignment_id, "lần 1", root))
    go(m.execute(a.assignment_id, "sửa lại", root, brief="TÓM TẮT: đã làm X"))
    assert ad.calls[1][0] == "run" and "TÓM TẮT: đã làm X" in ad.calls[1][2]
    sess = svc.store.list_sessions(t.task_id)
    assert len(sess) == 2 and sess[1].generation == 2 and sess[1].supersedes_session_id == sess[0].session_id
    assert sess[1].fallback_reason and ad.calls[1][3] is None                     # never a guessed ID
    assert svc.store.events("session.fallback")


def test_broken_resume_falls_back_once_explicitly(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)
    ad = Scripted([ok("sess-0001-aaaa"), AgentRunResult(ok=False, error="session expired"), ok("sess-0003-cccc")])
    m = SessionManager(svc.store, {"fake": ad})
    go(m.execute(a.assignment_id, "lần 1", root))
    run, res = go(m.execute(a.assignment_id, "sửa lại", root, brief="brief"))
    assert res.ok and run.state == RunState.SUCCEEDED
    assert [c[0] for c in ad.calls] == ["run", "resume", "run"]
    assert "session expired" in svc.store.open_session(a.assignment_id).fallback_reason


def test_new_task_new_session_and_qa_separate(world):
    svc, p, wo, root = world
    ad = Scripted([ok("sess-aaaa-0001"), ok("sess-bbbb-0002"), ok("sess-cccc-0003")])
    m = SessionManager(svc.store, {"fake": ad})
    _, a1 = _asg(svc, wo, "t1")
    _, a2 = _asg(svc, wo, "t2")
    t1b = svc.store.create_task(wo.work_order_id, "t3")
    qa = svc.store.create_assignment(t1b.task_id, "qa_engineer", "fake")
    for a in (a1, a2, qa):
        go(m.execute(a.assignment_id, "x", root))
    assert len({c[1] for c in ad.calls}) == 3 and all(c[0] == "run" for c in ad.calls)


def test_failures_are_runs_not_task_progress(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)
    ad = Scripted([AgentRunResult(ok=False, error="x", exit_code=2),
                   AgentRunResult(ok=False, timed_out=True, error_kind="timeout"),
                   AgentRunResult(ok=False, cancelled=True, error_kind="cancelled"),
                   AgentRunResult(ok=False, error="HTTP 429", error_kind="quota")])
    m = SessionManager(svc.store, {"fake": ad})
    states = [go(m.execute(a.assignment_id, "x", root))[0].state for _ in range(4)]
    assert states == [RunState.FAILED, RunState.TIMED_OUT, RunState.CANCELLED, RunState.FAILED]
    assert svc.store.get_task(t.task_id).state == TaskState.BACKLOG
    assert svc.db.conn.execute("SELECT status FROM provider_registry WHERE provider_id='fake'").fetchone()[0] \
        == "quota_exhausted"


def test_adapter_crash_does_not_leave_run_running(world):
    svc, p, wo, root = world
    t, a = _asg(svc, wo)

    class Boom(Scripted):
        async def run(self, req):
            raise RuntimeError("boom")
    run, res = go(SessionManager(svc.store, {"fake": Boom([])}).execute(a.assignment_id, "x", root))
    assert run.state == RunState.FAILED and not res.ok


# ---- migration 001 -> 002 keeps data ------------------------------------------------------
def test_migration_preserves_existing_sessions(tmp_path):
    from aatpo.db import connection
    db_path = tmp_path / "old.db"
    first = connection._migrations()[0]
    conn = sqlite3.connect(db_path)
    conn.executescript(first[1] + "PRAGMA user_version=1;")
    conn.executescript("""
      INSERT INTO projects(project_id,display_name,root_path,root_key,project_type,created_at,updated_at)
        VALUES('P','n','r','r','other','t','t');
      INSERT INTO provider_registry(provider_id) VALUES('fake');
      INSERT INTO agent_roles(role_id) VALUES('backend_engineer');
      INSERT INTO work_orders VALUES('W','P','t','RECEIVED',1,'t','t');
      INSERT INTO tasks VALUES('T','W','t','BACKLOG',1,'t','t');
      INSERT INTO assignments VALUES('A','T','backend_engineer','fake','t');
      INSERT INTO agent_sessions VALUES('S','A','P','W','T','backend_engineer','fake','prov-1','t');
      INSERT INTO process_runs(run_id,session_id,state,idempotency_key,created_at) VALUES('R','S','QUEUED','k','t');
    """)
    conn.close()
    db = Database(db_path, backup_dir=tmp_path / "bk")
    row = db.conn.execute("SELECT provider_session_id, generation FROM agent_sessions WHERE session_id='S'").fetchone()
    assert tuple(row) == ("prov-1", 1)
    assert db.conn.execute("SELECT session_id FROM process_runs WHERE run_id='R'").fetchone()[0] == "S"
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert list((tmp_path / "bk").glob("office-v1-*.db"))                      # backup before migrating
    db.close()


def test_real_adapters_do_not_claim_unverified_resume():
    from aatpo.cli.subprocess_adapter import VERIFIED_RESUME
    assert VERIFIED_RESUME == set()
    assert ClaudeAdapter().supports_exact_resume is False and CodexAdapter().supports_exact_resume is False
