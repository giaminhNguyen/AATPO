"""Append-only, redacted error log under the app data dir (spec A30). Tracebacks only; never user content."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from pathlib import Path

from aatpo.telemetry.redaction import redact


def log_exception(path: Path | None, where: str, exc: BaseException) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 1_000_000:      # rotate: keep one previous file
            path.replace(path.with_suffix(".log.1"))
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z  {where}\n{redact(tb)}")
    except OSError:
        pass   # logging must never become a second failure
