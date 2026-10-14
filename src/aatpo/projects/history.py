"""Human-friendly version history: Git log joined with the AATPO ledger so each saved version links back to the
work order / task that produced it (spec 6.3.B.8). Read-only."""
from __future__ import annotations

from pathlib import Path

from aatpo.domain.models import Project


def history_rows(services, project: Project, limit: int = 100) -> list[dict]:
    root = Path(project.root_path)
    if not services.git.available or not root.is_dir() or not services.git.detect(root).is_repo:
        return []
    rows = []
    for sha, subject, date in services.git.log(root, limit):
        with services.db.lock:
            led = services.db.conn.execute(
                "SELECT ce.status, ce.branch, t.title AS task_title, w.title AS wo_title, w.work_order_id, ce.task_id "
                "FROM git_commit_events ce JOIN git_repositories r USING(repo_id) LEFT JOIN tasks t ON t.task_id=ce.task_id "
                "LEFT JOIN work_orders w ON w.work_order_id=t.work_order_id "
                "WHERE ce.sha=? AND r.project_id=? ORDER BY ce.at, ce.rowid", (sha, project.project_id)).fetchall()
        committed = next((x for x in led if x["status"] in ("committed", "reverted")), None)
        rows.append({"sha": sha, "subject": subject, "date": date[:16].replace("T", " "),
                     "ledger": bool(committed), "status": committed["status"] if committed else None,
                     "branch": committed["branch"] if committed else None,
                     "wo_title": committed["wo_title"] if committed else None,
                     "work_order_id": committed["work_order_id"] if committed else None,
                     "task_title": committed["task_title"] if committed else None,
                     "undoable": bool(committed and committed["status"] == "committed")})
    return rows


def friendly(row: dict) -> str:
    if row["status"] == "reverted":
        return f"Đã hoàn tác một phiên bản trước — {row['subject']}"
    return ("Đã lưu phiên bản bởi AATPO — " if row["ledger"] else "Phiên bản của bạn — ") + row["subject"]


def propose_undo(services, project: Project, sha: str) -> None:
    """Creates the reviewed revert PROPOSAL (approval). Executing it is the approval service's job after a GUI click."""
    root = Path(project.root_path)
    row = next((r for r in history_rows(services, project, 500) if r["sha"] == sha), None)
    if row is None or not row["undoable"]:
        raise ValueError("Chỉ đề xuất hoàn tác được các phiên bản do AATPO đã lưu.")
    services.approvals.request_revert(project.project_id, row["work_order_id"], sha, row["subject"],
                                      services.git.commits_after(root, sha), services.git.files_in_commit(root, sha))
