"""SQLite backups and restore (spec 6.2). Backups use SQLite's online backup API, are integrity-checked, and
restores are applied at the NEXT startup before the database is opened (never by overwriting an open file).
The pre-restore database is always kept."""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aatpo.db.connection import Database

DAILY = re.compile(r"^office-\d{8}\.db$")
MAX_SCHEMA = 5


class BackupError(RuntimeError):
    pass


def _check(path: Path) -> int:
    """Open read-only, run integrity_check, return the schema version; raises BackupError if unusable."""
    try:
        c = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            ok = c.execute("PRAGMA integrity_check").fetchone()[0]
            ver = c.execute("PRAGMA user_version").fetchone()[0]
            c.execute("SELECT count(*) FROM projects").fetchone()
        finally:
            c.close()
    except sqlite3.DatabaseError as e:
        raise BackupError(f"tệp sao lưu không dùng được: {e}") from e
    if ok != "ok":
        raise BackupError("tệp sao lưu bị hỏng (integrity_check không đạt)")
    if ver > MAX_SCHEMA:
        raise BackupError("tệp sao lưu thuộc phiên bản AATPO mới hơn")
    return ver


def backup_now(db: Database, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with db.lock:
        out = sqlite3.connect(dest)
        try:
            db.conn.backup(out)
        finally:
            out.close()
    _check(dest)
    return dest


def backup_if_due(db: Database, backups: Path, keep: int = 7) -> Path | None:
    """One verified backup per UTC day; keeps the newest `keep` daily files."""
    today = backups / f"office-{datetime.now(timezone.utc):%Y%m%d}.db"
    made = None
    if not today.exists():
        made = backup_now(db, today)
    for old in sorted(p for p in backups.glob("office-*.db") if DAILY.match(p.name))[:-keep]:
        old.unlink(missing_ok=True)
    return made


def list_backups(backups: Path) -> list[Path]:
    return sorted((p for p in backups.glob("*.db")), reverse=True)


def schedule_restore(config_dir: Path, backup: Path) -> None:
    """Validate now (so the user learns immediately), apply at next start."""
    _check(backup)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "restore_pending.txt").write_text(str(backup.resolve()), encoding="utf-8")


def apply_pending_restore(home: Path) -> str | None:
    marker = home / "config" / "restore_pending.txt"
    if not marker.exists():
        return None
    src = Path(marker.read_text(encoding="utf-8").strip())
    marker.unlink()
    db_file = home / "data" / "office.db"
    try:
        _check(src)
    except (BackupError, OSError) as e:
        return f"Không khôi phục được: {e}"
    keep = home / "backups" / f"before-restore-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.db"
    keep.parent.mkdir(parents=True, exist_ok=True)
    if db_file.exists():
        shutil.copy2(db_file, keep)
    for ext in ("-wal", "-shm"):
        Path(str(db_file) + ext).unlink(missing_ok=True)
    shutil.copy2(src, db_file)
    return f"Đã khôi phục từ {src.name}; dữ liệu trước đó được giữ tại {keep.name}"
