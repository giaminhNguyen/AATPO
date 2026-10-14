"""Codex CLI adapter. Flags checked against `codex exec --help` of codex-cli 0.160.0 (see docs/cli_compatibility.md).
Read-only by construction: `-s read-only`; never --dangerously-bypass-approvals-and-sandbox."""
from __future__ import annotations

from pathlib import Path

from aatpo.cli.base import AgentRunRequest, AgentRunResult, ProviderCapabilities
from aatpo.cli.parsers import parse_codex
from aatpo.cli.subprocess_adapter import VERIFIED_RESUME, SubprocessAdapter
from aatpo.cli.windows_launcher import ProcResult

REQUIRED_RUN_FLAGS = ("--json", "--sandbox", "--output-last-message", "--skip-git-repo-check")


class CodexAdapter(SubprocessAdapter):
    provider_id = "codex"
    exe_name = "codex"

    def run_argv(self, req: AgentRunRequest, scratch: Path) -> list[str]:
        return ["exec", "--json", "-s", "read-only", "--skip-git-repo-check", "-C", req.project_root,
                "-o", str(scratch / "last.txt"), "-"]

    def resume_argv(self, req: AgentRunRequest, sid: str, scratch: Path) -> list[str]:
        # `exec resume` has no -s/-C: sandbox via config override, directory via the process cwd.
        return ["exec", "resume", "--json", "--skip-git-repo-check", "-c", 'sandbox_mode="read-only"',
                "-o", str(scratch / "last.txt"), sid, "-"]

    def parse(self, proc: ProcResult, scratch: Path) -> AgentRunResult:
        f = scratch / "last.txt"
        last = f.read_text(encoding="utf-8", errors="replace") if f.exists() else None
        return parse_codex(proc.stdout, proc.stderr, proc.exit_code if proc.exit_code is not None else 1, last)

    async def probe(self) -> ProviderCapabilities:
        pid = self.provider_id
        if not self.installed():
            return ProviderCapabilities(provider_id=pid, status="missing")
        v = await self._quick("--version")
        h = await self._quick("exec", "--help")
        if not v or v.exit_code != 0 or not h or h.exit_code != 0:
            return ProviderCapabilities(provider_id=pid, status="unhealthy", detail="không chạy được --version/--help")
        version = v.stdout.strip().splitlines()[0][:80] if v.stdout.strip() else None
        if not all(flag in h.stdout for flag in REQUIRED_RUN_FLAGS):
            return ProviderCapabilities(provider_id=pid, status="unsupported_version", version=version,
                                        detail="thiếu cờ cần thiết trong `codex exec --help`")
        r = await self._quick("exec", "resume", "--help")
        self.supports_exact_resume = bool(r and r.exit_code == 0 and "--json" in r.stdout) and pid in VERIFIED_RESUME
        auth = await self._quick("login", "status")
        if auth is None or auth.exit_code is None:
            status = "unknown"
        else:
            status = "ready" if auth.exit_code == 0 else "not_authenticated"
        return ProviderCapabilities(provider_id=pid, status=status, version=version,
                                    supports_exact_resume=self.supports_exact_resume)
