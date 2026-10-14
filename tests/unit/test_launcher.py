import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aatpo.cli.windows_launcher import LaunchError, MAX_CAPTURE, run_process
from aatpo.telemetry.redaction import redact

FAKE = str(Path(__file__).parents[1] / "fixtures" / "fake_cli.py")
pytestmark = pytest.mark.mock_integration


def go(coro):
    return asyncio.run(coro)


def py(*args, **kw):
    return go(run_process([sys.executable, FAKE, *args], cwd=None, **kw))


def test_ok_and_utf8_roundtrip():
    prompt = 'Sửa nút lưu & "ngoặc" | echo PWNED > x.txt ; $(calc) %PATH% `id`'  # A16 metacharacters
    r = py("echo", stdin_text=prompt)
    d = json.loads(r.stdout)
    assert r.exit_code == 0 and d["text"] == prompt and d["argv"] == ["echo"]
    assert not Path("x.txt").exists()


def test_nonzero_exit_reported():
    r = py("exit3", stdin_text="x")
    assert r.exit_code == 3 and "lỗi giả lập" in r.stderr


def test_timeout_kills_process():
    t = time.time()
    r = py("sleep", stdin_text="x", timeout=1.5)
    assert r.timed_out and not r.cancelled and time.time() - t < 15


def test_output_is_capped_but_drained():
    r = py("big", stdin_text="x")
    assert r.exit_code == 0 and r.truncated and len(r.stdout) == MAX_CAPTURE


def test_cancel_kills_whole_process_tree(tmp_path):
    pidfile = tmp_path / "child.pid"

    async def scenario():
        cancel = asyncio.Event()
        task = asyncio.ensure_future(run_process([sys.executable, FAKE, "tree", str(pidfile)], cwd=None,
                                                  stdin_text="x", cancel=cancel, timeout=60))
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text():
                break
            await asyncio.sleep(0.1)
        child = int(pidfile.read_text())
        assert _alive(child)
        cancel.set()
        res = await task
        return res, child

    res, child = go(scenario())
    assert res.cancelled
    time.sleep(0.5)
    assert not _alive(child), "grandchild survived cancellation"


def _alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def test_missing_executable_is_launch_error():
    with pytest.raises(LaunchError):
        go(run_process(["definitely-not-installed-xyz"], cwd=None))


@pytest.mark.windows_integration
@pytest.mark.skipif(sys.platform != "win32", reason="Windows .cmd semantics")
def test_cmd_wrapper_in_path_with_spaces(tmp_path):
    d = tmp_path / "thư mục có space"  # A15: spaces + Unicode + .cmd
    d.mkdir()
    cmd = d / "fake.cmd"
    cmd.write_text(f'@echo off\r\n"{sys.executable}" "{FAKE}" %*\r\n', encoding="cp1252", errors="replace")
    try:
        r = go(run_process([str(cmd), "ok"], cwd=str(d), stdin_text="hi", timeout=30))
    except Exception as e:  # recorded honestly below
        pytest.fail(f"cmd launch failed: {e}")
    assert r.exit_code == 0 and json.loads(r.stdout)["text"] == "xong"


def test_cmd_rejects_unsafe_args(tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows only")
    cmd = tmp_path / "f.cmd"
    cmd.write_text("@echo off\r\n")
    with pytest.raises(LaunchError):
        go(run_process([str(cmd), "a&calc"], cwd=None))


def test_redaction():
    s = redact("key sk-abcdefghijklmnopqrstuvwxyz123456 and Authorization: Bearer abcdefghijklmnop1234 token=hunter2")
    assert "sk-abc" not in s and "abcdefghijklmnop1234" not in s and "hunter2" not in s
    assert "token=[REDACTED]" in s
