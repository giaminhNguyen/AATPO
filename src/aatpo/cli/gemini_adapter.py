"""Gemini CLI adapter skeleton (G1): detection only. Running is not implemented until a Gemini CLI
is installed and its headless flags can be verified on this machine; the GUI says so plainly."""
from __future__ import annotations

from aatpo.cli.base import AgentRunRequest, AgentRunResult, ProviderCapabilities
from aatpo.cli.subprocess_adapter import SubprocessAdapter

NOT_SUPPORTED = AgentRunResult(ok=False, error="Gemini CLI chưa được hỗ trợ chạy trong phiên bản này")


class GeminiAdapter(SubprocessAdapter):
    provider_id = "gemini"
    exe_name = "gemini"

    async def probe(self) -> ProviderCapabilities:
        if not self.installed():
            return ProviderCapabilities(provider_id=self.provider_id, status="missing")
        return ProviderCapabilities(provider_id=self.provider_id, status="unsupported_version",
                                    detail="Đã cài nhưng chưa có bộ điều khiển được kiểm chứng")

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        return NOT_SUPPORTED

    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult:
        return NOT_SUPPORTED
