"""Shared plumbing for official-CLI adapters. Executable templates are fixed in code; user text
only ever travels on stdin. Subclasses supply argv and parsing for their CLI version."""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path

from aatpo.cli.base import AgentRunRequest, AgentRunResult, ProviderCapabilities
from aatpo.cli.parsers import valid_session_id
from aatpo.cli.windows_launcher import LaunchError, ProcResult, resolve_executable, run_process
from aatpo.telemetry.redaction import redact


# Exact resume is only trusted for providers whose resume was exercised end to end on this machine
# (spec 3.4 / G1). Empty until verified; unverified providers fall back to a fresh session + brief.
VERIFIED_RESUME: set[str] = set()


class SubprocessAdapter:
    provider_id = ""
    exe_name = ""

    def __init__(self, command: list[str] | None = None):
        """`command` overrides the executable prefix (tests point it at a fake CLI)."""
        self.command = command or [self.exe_name]
        self.supports_exact_resume = False
        self._cancels: dict[str, asyncio.Event] = {}

    # -- hooks --------------------------------------------------------------------------
    def run_argv(self, req: AgentRunRequest, scratch: Path) -> list[str]:
        raise NotImplementedError

    def resume_argv(self, req: AgentRunRequest, sid: str, scratch: Path) -> list[str]:
        raise NotImplementedError

    def parse(self, proc: ProcResult, scratch: Path) -> AgentRunResult:
        raise NotImplementedError

    async def probe(self) -> ProviderCapabilities:
        raise NotImplementedError

    # -- common -------------------------------------------------------------------------
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentRunResult:
        return self.parse(ProcResult(exit_code, stdout, stderr), Path(tempfile.gettempdir()))

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        return await self._execute(request, None)

    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult:
        sid = valid_session_id(provider_session_id)
        if not sid:
            return AgentRunResult(ok=False, error="mã phiên của nhà cung cấp không hợp lệ")
        return await self._execute(request, sid)

    async def cancel(self, run_id: str) -> bool:
        ev = self._cancels.get(run_id)
        if ev:
            ev.set()
        return ev is not None

    async def _execute(self, req: AgentRunRequest, sid: str | None) -> AgentRunResult:
        root = Path(req.project_root)
        if not root.is_dir():
            return AgentRunResult(ok=False, error="Không tìm thấy thư mục dự án")
        cancel = self._cancels[req.run_id] = asyncio.Event()
        try:
            with tempfile.TemporaryDirectory(prefix="aatpo_") as scratch:
                scratch_dir = Path(scratch)
                argv = self.command + (self.resume_argv(req, sid, scratch_dir) if sid
                                       else self.run_argv(req, scratch_dir))
                try:
                    proc = await run_process(argv, cwd=str(root), stdin_text=req.prompt,
                                             timeout=req.timeout_seconds, cancel=cancel)
                except LaunchError as e:
                    return AgentRunResult(ok=False, error=str(e))
                if proc.timed_out:
                    return AgentRunResult(ok=False, timed_out=True, error_kind="timeout",
                                          error="Quá thời gian chờ; đã dừng tiến trình")
                if proc.cancelled:
                    return AgentRunResult(ok=False, cancelled=True, error_kind="cancelled",
                                          error="Đã dừng theo yêu cầu")
                res = self.parse(proc, scratch_dir)
                if res.error:
                    res = res.model_copy(update={"error": redact(res.error, 500)})
                return res.model_copy(update={"text": redact(res.text)})
        finally:
            self._cancels.pop(req.run_id, None)

    async def _quick(self, *args: str) -> ProcResult | None:
        """Short local command for probing; None if it cannot run."""
        try:
            return await run_process(self.command + list(args), cwd=None, stdin_text="", timeout=20)
        except LaunchError:
            return None

    def installed(self) -> bool:
        try:
            resolve_executable(self.command[0])
            return True
        except LaunchError:
            return False
