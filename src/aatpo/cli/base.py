"""CLI adapter contract (spec 3.5). G0 ships the protocol plus a fake adapter only; real
provider adapters arrive in G1 and must be validated against the installed CLI versions."""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class AgentRunRequest(BaseModel):
    session_id: str
    run_id: str
    project_root: str
    prompt: str
    timeout_seconds: int = 900


class AgentRunResult(BaseModel):
    ok: bool
    text: str = ""
    provider_session_id: str | None = None  # only when reliably parsed
    exit_code: int = 0
    error: str | None = None
    error_kind: str | None = None  # quota | timeout | cancelled | None
    timed_out: bool = False
    cancelled: bool = False


class ProviderCapabilities(BaseModel):
    provider_id: str
    status: str  # missing|not_authenticated|quota_exhausted|unsupported_version|unhealthy|ready|unknown
    version: str | None = None
    supports_exact_resume: bool = False
    detail: str | None = None


class CLIAdapter(Protocol):
    provider_id: str

    async def probe(self) -> ProviderCapabilities: ...
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...
    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult: ...
    async def cancel(self, run_id: str) -> bool: ...
    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentRunResult: ...
