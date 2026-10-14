"""Application data paths. State lives outside the source repo (spec 6.2)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    home: Path

    @property
    def db_path(self) -> Path:
        return self.home / "data" / "office.db"

    @property
    def backups(self) -> Path:
        return self.home / "backups"

    def ensure(self) -> "AppPaths":
        for sub in ("config", "data", "logs", "artifacts", "backups"):
            (self.home / sub).mkdir(parents=True, exist_ok=True)
        return self


def default_paths() -> AppPaths:
    r"""AATPO_HOME overrides (tests, portable use); else %LOCALAPPDATA%\AATPO."""
    override = os.environ.get("AATPO_HOME")
    if override:
        return AppPaths(Path(override))
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return AppPaths(Path(base) / "AATPO")
