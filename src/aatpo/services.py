"""Dependency wiring shared by GUI and tests. The GUI only talks to these services."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aatpo.db.connection import Database
from aatpo.db.repositories import Store
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

    @classmethod
    def create(cls, paths: AppPaths, git_exe: str | None = None) -> "Services":
        paths.ensure()
        db = Database(paths.db_path, backup_dir=paths.backups)
        store = Store(db)
        store.reconcile_after_restart()  # RUNNING work from a previous crash -> UNKNOWN, never replayed
        git = GitService(git_exe)
        return cls(paths, db, store, git, ProjectRegistry(store, git))

    def readiness(self) -> list[tuple[str, bool, str]]:
        """First-run checklist in plain Vietnamese: (label, ok, hint). Local checks only."""
        import shutil
        out = [("Git (lịch sử phiên bản)", self.git.available,
                "Đã sẵn sàng" if self.git.available else "Chưa cài Git for Windows")]
        for exe, label in (("codex", "Codex"), ("claude", "Claude Code"), ("gemini", "Gemini")):
            found = shutil.which(exe)
            out.append((f"Trợ lý AI: {label}", bool(found),
                        "Đã cài (chưa kiểm tra đăng nhập)" if found else "Chưa cài"))
        return out

    def close(self) -> None:
        self.db.close()
