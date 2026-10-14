"""Test execution as evidence: allowlisted launchers, argv only (no shell), bounded output, every run recorded
with its command, exit code and a hashed output artifact. A test run that errors is NOT a pass."""
from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from aatpo.cli.windows_launcher import LaunchError, run_process
from aatpo.db.connection import Database
from aatpo.domain.models import new_id, utcnow
from aatpo.evidence import artifacts
from aatpo.telemetry.redaction import redact

# First token (file stem) of an approved test command. Anything else needs a P2 approval (not in this MVP).
ALLOWED_LAUNCHERS = {"python", "python3", "py", "pytest", "npm", "yarn", "pnpm", "node", "dotnet", "cargo", "go",
                     "mvn", "gradle", "make"}
_BAD_ARG = re.compile(r"[\r\n\0]")


class CommandRejected(ValueError):
    pass


@dataclass(frozen=True)
class TestResult:
    status: str            # passed | failed | error | timeout
    exit_code: int | None
    duration_ms: int
    output: str
    test_run_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "passed"


def validate_command(argv: list[str]) -> list[str]:
    if not argv or not all(isinstance(a, str) and a and not _BAD_ARG.search(a) for a in argv):
        raise CommandRejected("lệnh kiểm thử trống hoặc có ký tự không hợp lệ")
    if Path(argv[0]).stem.lower() not in ALLOWED_LAUNCHERS:
        raise CommandRejected(f"“{argv[0]}” chưa nằm trong danh sách chương trình kiểm thử được phép")
    return argv


def detect_command(root: Path) -> list[str] | None:
    """Suggestion only; the user confirms it in the GUI before it is ever stored or run."""
    import sys
    if (root / "pytest.ini").exists() or (root / "tests").is_dir() or (root / "pyproject.toml").exists():
        if getattr(sys, "frozen", False):   # packaged AATPO.exe: sys.executable is AATPO itself, never a Python
            exe = shutil.which("python") or shutil.which("py") or "python"
        else:
            exe = sys.executable if sys.platform == "win32" else "python3"
        return [exe, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if (root / "package.json").exists():
        return ["npm", "test"]
    return None


async def run_tests(db: Database, artifacts_root: Path, *, project_id: str, work_order_id: str, task_id: str | None,
                    argv: list[str], cwd: str, timeout: int = 300) -> TestResult:
    argv = validate_command(list(argv))
    t0 = time.monotonic()
    try:
        # no .pyc / pytest cache: a test run must not leave junk that makes the repo look dirty
        r = await run_process(argv, cwd=cwd, stdin_text="", timeout=timeout, env={"PYTHONDONTWRITEBYTECODE": "1"})
        status = "timeout" if r.timed_out else "passed" if r.exit_code == 0 else "failed"
        text, code = (r.stdout + ("\n--- stderr ---\n" + r.stderr if r.stderr.strip() else "")), r.exit_code
    except LaunchError as e:
        status, text, code = "error", f"Không chạy được lệnh kiểm thử: {e}", None
    ms = int((time.monotonic() - t0) * 1000)
    text = redact(text)
    header = f"$ {' '.join(argv)}\n(cwd: {cwd})\nkết quả: {status}, mã thoát: {code}, {ms} ms\n\n"
    aid = artifacts.save_text(db, artifacts_root, project_id=project_id, work_order_id=work_order_id,
                              task_id=task_id or "", run_id=new_id("TEST"), text=header + text, kind="test_output") \
        if task_id else None
    rid = new_id("TRUN")
    with db.tx() as c:
        c.execute("INSERT INTO test_runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (rid, project_id, work_order_id, task_id, json.dumps(argv, ensure_ascii=False), code, status, ms, aid, utcnow()))
    return TestResult(status, code, ms, header + text, rid)
