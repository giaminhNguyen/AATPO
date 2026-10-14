"""Dependency wiring shared by GUI and tests. The GUI only talks to these services."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aatpo.agents.session_manager import SessionManager
from aatpo.cli.probe import STATUS_VI, default_adapters
from aatpo.customer.representative import ChatService
from aatpo.db.connection import Database
from aatpo.db.repositories import Store
from aatpo.config import load_config
from aatpo.office.approvals import ApprovalService
from aatpo.office.manager import OfficeManager
from aatpo.projects.git_service import GitService
from aatpo.projects.registry import ProjectRegistry
from aatpo.settings import AppPaths


@dataclass
class Services:
    paths: AppPaths
    db: Database
    store: Store
    git: GitService
    registry: ProjectRegistry
    adapters: dict
    sessions: SessionManager
    approvals: ApprovalService
    chat: ChatService
    manager: OfficeManager

    @classmethod
    def create(cls, paths: AppPaths, git_exe: str | None = None, adapters: dict | None = None,
               write_mode: bool = False) -> "Services":
        paths.ensure()
        db = Database(paths.db_path, backup_dir=paths.backups)
        store = Store(db)
        store.reconcile_after_restart()  # RUNNING work from a previous crash -> UNKNOWN, never replayed
        git = GitService(git_exe)
        adapters = default_adapters() if adapters is None else adapters
        registry = ProjectRegistry(store, git)
        approvals = ApprovalService(store)
        sessions = SessionManager(store, adapters)
        manager = OfficeManager(store, registry, git, sessions, approvals, paths.home / "artifacts",
                                load_config(paths.home / "config" / "office.toml"), write_mode=write_mode)
        chat = ChatService(store, registry, approvals)
        chat.manager = manager
        manager.reconcile_after_restart()   # uncertain work gets an approval request, never an automatic replay
        return cls(paths, db, store, git, registry, adapters, sessions, approvals, chat, manager)

    def provider_statuses(self) -> dict[str, tuple[str, str | None]]:
        """provider_id -> (status, version) as last probed (local checks only)."""
        with self.db.lock:
            rows = self.db.conn.execute("SELECT provider_id,status,version FROM provider_registry").fetchall()
        return {r["provider_id"]: (r["status"], r["version"]) for r in rows if r["provider_id"] in self.adapters}

    def readiness(self) -> list[tuple[str, bool, str]]:
        """First-run checklist in plain Vietnamese: (label, ok, hint)."""
        out = [("Git (lịch sử phiên bản)", self.git.available,
                "Đã sẵn sàng" if self.git.available else "Chưa cài Git for Windows")]
        names = {"codex": "Codex", "claude": "Claude Code", "gemini": "Gemini"}
        for pid, (status, _) in self.provider_statuses().items():
            out.append((f"Trợ lý AI: {names.get(pid, pid)}", status == "ready", STATUS_VI.get(status, status)))
        return out

    def close(self) -> None:
        self.db.close()
