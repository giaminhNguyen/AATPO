"""SQLite connection (WAL, FKs, short explicit transactions) and versioned migrations."""
from __future__ import annotations

import shutil
import sqlite3
import threading
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from aatpo.domain.models import utcnow


def _migrations() -> list[tuple[int, str]]:
    found = []
    for f in resources.files("aatpo.db").joinpath("migrations").iterdir():
        if f.name.endswith(".sql"):
            found.append((int(f.name.split("_", 1)[0]), f.read_text(encoding="utf-8")))
    return sorted(found)


class Database:
    """One shared connection guarded by a re-entrant lock (G0 volume is tiny)."""

    def __init__(self, path: str | Path, backup_dir: Path | None = None):
        self.path = str(path)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self._migrate(backup_dir)

    def _migrate(self, backup_dir: Path | None) -> None:
        current = self.conn.execute("PRAGMA user_version").fetchone()[0]
        pending = [(v, sql) for v, sql in _migrations() if v > current]
        if not pending:
            return
        if current > 0 and backup_dir and self.path != ":memory:":
            backup_dir.mkdir(parents=True, exist_ok=True)
            self.conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(self.path, backup_dir / f"office-v{current}-{utcnow()[:19].replace(':', '')}.db")
        for version, sql in pending:
            self.conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;")

    @contextmanager
    def tx(self):
        """Atomic transaction; rolls back on any exception."""
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def close(self) -> None:
        self.conn.close()
