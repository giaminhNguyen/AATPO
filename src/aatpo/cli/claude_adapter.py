"""Claude Code adapter (headless `-p`). Flags checked against `claude --help` 2.1.299.
Read-only by construction: plan permission mode + only Read/Grep/Glob tools; never --dangerously-skip-permissions."""
from __future__ import annotations

import json
from pathlib import Path

from aatpo.cli.base import AgentRunRequest, AgentRunResult, ProviderCapabilities
from aatpo.cli.parsers import parse_claude
from aatpo.cli.subprocess_adapter import VERIFIED_RESUME, SubprocessAdapter
from aatpo.cli.windows_launcher import ProcResult

REQUIRED_FLAGS = ("--print", "--output-format", "--permission-mode", "--resume", "--tools")
BASE = ["-p", "--output-format", "json", "--permission-mode", "plan", "--tools", "Read,Grep,Glob"]
# Write mode: edits auto-accepted INSIDE the project (cwd); no Bash tool, so the agent cannot run commands -
# tests are run by AATPO itself as independent evidence.
WRITE = ["-p", "--output-format", "json", "--permission-mode", "acceptEdits", "--tools", "Read,Grep,Glob,Edit,Write"]


class ClaudeAdapter(SubprocessAdapter):
    provider_id = "claude"
    exe_name = "claude"

    def run_argv(self, req: AgentRunRequest, scratch: Path) -> list[str]:
        return list(WRITE if req.write else BASE)

    def resume_argv(self, req: AgentRunRequest, sid: str, scratch: Path) -> list[str]:
        return [*(WRITE if req.write else BASE), "--resume", sid]

    def parse(self, proc: ProcResult, scratch: Path) -> AgentRunResult:
        return parse_claude(proc.stdout, proc.stderr, proc.exit_code if proc.exit_code is not None else 1)

    async def probe(self) -> ProviderCapabilities:
        pid = self.provider_id
        if not self.installed():
            return ProviderCapabilities(provider_id=pid, status="missing")
        v, h = await self._quick("--version"), await self._quick("--help")
        if not v or v.exit_code != 0 or not h or h.exit_code != 0:
            return ProviderCapabilities(provider_id=pid, status="unhealthy", detail="không chạy được --version/--help")
        version = v.stdout.strip().splitlines()[0][:80] if v.stdout.strip() else None
        if not all(flag in h.stdout for flag in REQUIRED_FLAGS):
            return ProviderCapabilities(provider_id=pid, status="unsupported_version", version=version,
                                        detail="thiếu cờ cần thiết trong `claude --help`")
        self.supports_exact_resume = pid in VERIFIED_RESUME  # flag exists in --help, but not yet proven
        auth = await self._quick("auth", "status")
        status = "unknown"
        if auth and auth.exit_code is not None:
            try:  # read ONLY the boolean; never keep account details
                status = "ready" if json.loads(auth.stdout).get("loggedIn") is True else "not_authenticated"
            except (ValueError, AttributeError):
                status = "unknown"
        return ProviderCapabilities(provider_id=pid, status=status, version=version,
                                    supports_exact_resume=self.supports_exact_resume)
