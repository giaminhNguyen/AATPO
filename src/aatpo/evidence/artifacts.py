"""Output artifacts with SHA-256, stored under the app data dir (not in the project, not in git)."""
from __future__ import annotations

import hashlib
from pathlib import Path

from aatpo.db.connection import Database
from aatpo.domain.models import new_id, utcnow


def save_text(db: Database, root: Path, *, project_id: str, work_order_id: str, task_id: str,
              run_id: str, text: str, kind: str = "agent_output") -> str:
    d = root / project_id / task_id
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{run_id}.md"
    data = text.encode("utf-8")
    f.write_bytes(data)
    aid = new_id("ART")
    with db.tx() as c:
        c.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?)",
                  (aid, project_id, work_order_id, task_id, run_id, str(f), hashlib.sha256(data).hexdigest(), kind, utcnow()))
    return aid


def verify(db: Database, artifact_id: str, task_id: str) -> bool:
    """Evidence is real only if the row belongs to this task, the file exists, is non-empty and hashes the same."""
    with db.lock:
        r = db.conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
    if r is None or r["task_id"] != task_id:
        return False
    f = Path(r["path"])
    try:
        data = f.read_bytes()
    except OSError:
        return False
    return bool(data.strip()) and hashlib.sha256(data).hexdigest() == r["sha256"]


def latest(db: Database, task_id: str) -> dict | None:
    with db.lock:
        r = db.conn.execute("SELECT * FROM artifacts WHERE task_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                            (task_id,)).fetchone()
    return dict(r) if r else None


def read(db: Database, artifact_id: str) -> str:
    with db.lock:
        r = db.conn.execute("SELECT path FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
    return Path(r["path"]).read_text(encoding="utf-8", errors="replace")
