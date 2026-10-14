"""Office policy knobs (spec 5.4). Defaults match config/office.example.toml; an optional
`config/office.toml` in the app data dir overrides known keys only. Values are examples, not proven optimal."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass(frozen=True)
class OfficeConfig:
    concurrency: int = 1
    max_replans_per_work_order: int = 3
    max_handoffs_per_task: int = 6
    max_rework_cycles_per_task: int = 2
    max_runs_per_task: int = 4
    run_timeout_seconds: int = 900
    max_total_runs_per_work_order: int = 40
    provider_preference: tuple[str, ...] = ("claude", "codex", "gemini")
    allow_git_auto_local_commit: bool = True
    allow_git_auto_local_fast_forward_merge: bool = True
    allow_git_auto_push: bool = False          # never enabled by code paths in this MVP
    allow_git_history_rewrite: bool = False


def load_config(path: Path | None) -> OfficeConfig:
    if not path or not path.exists():
        return OfficeConfig()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    flat = {k: v for sec in data.values() if isinstance(sec, dict) for k, v in sec.items()}
    known = {f.name for f in fields(OfficeConfig)}
    kw = {k: (tuple(v) if k == "provider_preference" else v) for k, v in flat.items() if k in known}
    kw["allow_git_auto_push"] = False       # hard floor: config cannot turn these on
    kw["allow_git_history_rewrite"] = False
    return OfficeConfig(**kw)
