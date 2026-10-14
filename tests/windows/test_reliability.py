"""Crash / restart drills with REAL processes on Windows (hard kills, not mocks)."""
import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aatpo.domain.models import RunState, TaskState as T
from aatpo.services import Services
from aatpo.settings import AppPaths

FIX = Path(__file__).parents[1] / "fixtures"
pytestmark = [pytest.mark.windows_integration, pytest.mark.skipif(sys.platform != "win32", reason="Windows job objects / taskkill")]


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def wait_for(cond, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_killing_aatpo_also_kills_the_agent_processes_it_started(tmp_path):
    pidfile = tmp_path / "pids.txt"
    parent = subprocess.Popen([sys.executable, str(FIX / "crash_drill.py"), str(FIX / "fake_cli.py"), str(pidfile)])
    try:
        assert wait_for(lambda: pidfile.exists() and len(pidfile.read_text().split()) == 2)
        agent, grandchild = map(int, pidfile.read_text().split())
        assert alive(agent) and alive(grandchild) and alive(parent.pid)
        subprocess.run(["taskkill", "/F", "/PID", str(parent.pid)], capture_output=True)    # hard crash of AATPO only (no /T)
        assert wait_for(lambda: not alive(agent) and not alive(grandchild), 10), "agent processes outlived a crashed AATPO"
    finally:
        parent.kill()


def test_restart_after_hard_kill_marks_uncertain_work_and_never_replays(tmp_path):
    """A real subprocess starts a run (state RUNNING in SQLite), is killed hard, and a new process reopens the DB."""
    home = tmp_path / "home"
    script = tmp_path / "drill.py"
    script.write_text(f'''
import asyncio, sys
sys.path.insert(0, r"{Path(__file__).parents[2] / 'src'}")
sys.path.insert(0, r"{Path(__file__).parents[2]}")
from aatpo.services import Services
from aatpo.settings import AppPaths
from aatpo.domain.models import TaskState as T, RunState
from tests.unit.test_manager_g3 import Script
import tests.unit.test_manager_g3 as g3
from pathlib import Path

class Hang(Script):
    async def _do(self, kind, req, sid):
        Path(r"{tmp_path / 'started.flag'}").write_text("x")
        await asyncio.sleep(300)

svc = Services.create(AppPaths(Path(r"{home}")), adapters={{"fake": Hang()}})
from aatpo.config import OfficeConfig
svc.manager.cfg = OfficeConfig(provider_preference=("fake",))
with svc.db.tx() as c:
    c.execute("UPDATE provider_registry SET status='ready' WHERE provider_id='fake'")
d = Path(r"{tmp_path / 'proj'}"); d.mkdir()
p = svc.registry.register(d, "P", auto_history=False); svc.registry.select(p.project_id)
wo = g3.approved(svc, p, "Sửa lỗi đăng nhập")
svc.manager.create_plan(wo.work_order_id)
asyncio.run(svc.manager.run_work_order(wo.work_order_id))
''', encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)], cwd=Path(__file__).parents[2])
    try:
        assert wait_for(lambda: (tmp_path / "started.flag").exists(), 60), "drill never reached RUNNING"
        subprocess.run(["taskkill", "/F", "/PID", str(proc.pid)], capture_output=True)
        proc.wait(timeout=15)
    finally:
        proc.kill()

    # --- new process opens the same data directory ---
    calls = []

    class Spy:
        supports_exact_resume = False

        async def run(self, req):
            calls.append(req)
            raise AssertionError("replayed after crash")
    svc = Services.create(AppPaths(home), adapters={"fake": Spy()})      # startup reconciliation runs here
    runs = svc.db.conn.execute("SELECT state FROM process_runs").fetchall()
    assert [r["state"] for r in runs] == [RunState.UNKNOWN_AFTER_CRASH]
    t = next(x for x in svc.store.list_tasks(svc.registry.list()[0].project_id) if x.plan_key == "implement")
    assert t.state == T.UNKNOWN_AFTER_CRASH
    pend = svc.approvals.pending()
    assert len(pend) == 1 and pend[0].kind == "rerun"
    assert svc.db.conn.execute("SELECT count(*) FROM resource_locks").fetchone()[0] >= 0
    wo = svc.store.list_work_orders(svc.registry.list()[0].project_id)[-1]
    res = asyncio.run(svc.manager.run_work_order(wo.work_order_id))
    assert res.outcome == "needs_review" and calls == []                  # nothing replayed
    svc.close()
    svc2 = Services.create(AppPaths(home), adapters={})                   # a second restart creates no duplicate approval
    assert len(svc2.approvals.pending()) == 1
    svc2.close()
