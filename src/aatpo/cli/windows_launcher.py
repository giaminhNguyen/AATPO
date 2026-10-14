"""Windows-safe subprocess launcher: argv vectors only, prompt via stdin, bounded output,
timeout + cancel with process-TREE termination. Never builds shell strings from user text."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from dataclasses import dataclass
from typing import Callable

IS_WIN = sys.platform == "win32"
_SAFE_CMD_ARG = re.compile(r"^[A-Za-z0-9_.:=,/\\\-]+$")  # the only args allowed through cmd.exe for .cmd/.bat
MAX_CAPTURE = 2_000_000


class LaunchError(RuntimeError):
    pass


@dataclass
class ProcResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False
    truncated: bool = False


def resolve_executable(name_or_path: str) -> str:
    found = shutil.which(name_or_path)
    if not found:
        raise LaunchError(f"không tìm thấy chương trình: {name_or_path}")
    return found


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if IS_WIN:
        killer = await asyncio.create_subprocess_exec(
            "taskkill", "/PID", str(proc.pid), "/T", "/F",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await killer.wait()
    else:  # shortcut: POSIX hosts only kill the direct child; Windows is the supported target
        proc.kill()


async def run_process(argv: list[str], *, cwd: str | None, stdin_text: str | None = None, timeout: float = 900,
                      cancel: asyncio.Event | None = None,
                      on_line: Callable[[str], None] | None = None) -> ProcResult:
    exe = resolve_executable(argv[0])
    args = argv[1:]
    kw = dict(cwd=cwd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
              stderr=asyncio.subprocess.PIPE)
    if IS_WIN:
        import subprocess
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    if IS_WIN and exe.lower().endswith((".cmd", ".bat")):
        bad = [a for a in args if not _SAFE_CMD_ARG.match(a)]
        if bad:
            raise LaunchError(f"đối số không an toàn cho .cmd: {bad[0]!r}")
        proc = await asyncio.create_subprocess_shell(" ".join([f'"{exe}"', *args]), **kw)
    else:
        proc = await asyncio.create_subprocess_exec(exe, *args, **kw)

    out, err, truncated = bytearray(), bytearray(), False

    async def drain(stream, buf: bytearray, stream_lines: bool) -> None:
        nonlocal truncated
        pending = b""
        while chunk := await stream.read(65536):
            if len(buf) < MAX_CAPTURE:
                buf.extend(chunk[: MAX_CAPTURE - len(buf)])
            else:
                truncated = True  # keep draining so the child never blocks on a full pipe
            if stream_lines and on_line:
                pending += chunk
                *lines, pending = pending.split(b"\n")
                for ln in lines:
                    on_line(ln.decode("utf-8", "replace").rstrip("\r"))

    async def feed() -> None:
        try:
            if stdin_text is not None:
                proc.stdin.write(stdin_text.encode("utf-8"))
                await proc.stdin.drain()
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass  # child exited before reading; its exit code tells the story

    async def drive() -> None:
        await asyncio.gather(feed(), drain(proc.stdout, out, True), drain(proc.stderr, err, False), proc.wait())

    main = asyncio.ensure_future(drive())
    watchers = {main}
    if cancel is not None:
        watchers.add(asyncio.ensure_future(cancel.wait()))
    done, pending_tasks = await asyncio.wait(watchers, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
    timed_out = cancelled = False
    if main not in done:
        cancelled = cancel is not None and cancel.is_set()
        timed_out = not cancelled
        await _kill_tree(proc)
        try:
            await asyncio.wait_for(main, 10)
        except asyncio.TimeoutError:
            main.cancel()
    for t in pending_tasks:
        if t is not main:
            t.cancel()
    return ProcResult(proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"),
                      timed_out, cancelled, truncated)
