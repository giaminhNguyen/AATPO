"""Deterministic fake provider for tests and provider-less first run. NOT proof of a real CLI."""
from __future__ import annotations

import json

from aatpo.cli.base import AgentRunRequest, AgentRunResult, ProviderCapabilities


class FakeAdapter:
    provider_id = "fake"

    def __init__(self) -> None:
        self.calls: list[AgentRunRequest] = []

    async def probe(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider_id="fake", status="ready", version="fake-1", supports_exact_resume=True)

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        self.calls.append(request)
        return self.parse_output(json.dumps({"session": f"fake-{request.session_id}", "text": "ok"}), "", 0)

    async def resume(self, request: AgentRunRequest, provider_session_id: str) -> AgentRunResult:
        self.calls.append(request)
        return self.parse_output(json.dumps({"session": provider_session_id, "text": "resumed"}), "", 0)

    async def cancel(self, run_id: str) -> bool:
        return True

    def parse_output(self, stdout: str, stderr: str, exit_code: int) -> AgentRunResult:
        """Nonzero exit or malformed JSON is an error, never success (A14)."""
        if exit_code != 0:
            return AgentRunResult(ok=False, exit_code=exit_code, error=stderr[:200] or "nonzero exit")
        try:
            d = json.loads(stdout)
            return AgentRunResult(ok=True, text=str(d["text"]), provider_session_id=d.get("session"))
        except (ValueError, KeyError, TypeError) as e:
            return AgentRunResult(ok=False, error=f"malformed output: {e}")
