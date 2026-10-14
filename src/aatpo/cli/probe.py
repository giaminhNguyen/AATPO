"""Local-only provider readiness (no model call, no quota). Persists status to provider_registry."""
from __future__ import annotations

import asyncio

from aatpo.cli.base import ProviderCapabilities
from aatpo.cli.claude_adapter import ClaudeAdapter
from aatpo.cli.codex_adapter import CodexAdapter
from aatpo.cli.gemini_adapter import GeminiAdapter
from aatpo.db.connection import Database
from aatpo.domain.models import utcnow

STATUS_VI = {
    "ready": "Sẵn sàng", "missing": "Chưa cài", "not_authenticated": "Chưa đăng nhập",
    "quota_exhausted": "Hết hạn mức", "unsupported_version": "Không tương thích",
    "unhealthy": "Không xác định", "unknown": "Không xác định",
}


def default_adapters() -> dict:
    return {a.provider_id: a for a in (CodexAdapter(), ClaudeAdapter(), GeminiAdapter())}


async def probe_all(adapters: dict, db: Database) -> dict[str, ProviderCapabilities]:
    caps = dict(zip(adapters, await asyncio.gather(*(a.probe() for a in adapters.values()))))
    with db.tx() as c:
        for pid, cap in caps.items():
            c.execute("UPDATE provider_registry SET version=?, status=?, checked_at=? WHERE provider_id=?",
                      (cap.version, cap.status, utcnow(), pid))
    return caps


def mark_quota_exhausted(db: Database, provider_id: str) -> None:
    with db.tx() as c:
        c.execute("UPDATE provider_registry SET status='quota_exhausted', checked_at=? WHERE provider_id=?",
                  (utcnow(), provider_id))
