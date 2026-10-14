"""Reconciles what SQLite believes with what the repositories actually contain (spec G5). Read-only: it reports
discrepancies and journals them; it never edits history or task state on its own."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aatpo.projects.git_service import GitError


@dataclass(frozen=True)
class Discrepancy:
    kind: str
    project: str
    task_id: str | None
    detail_vi: str


def audit_git(services) -> list[Discrepancy]:
    db, git, st = services.db, services.git, services.store
    out: list[Discrepancy] = []
    if not git.available:
        return out
    for p in services.registry.list():
        root = Path(p.root_path)
        if not root.is_dir() or not git.detect(root).is_repo:
            continue
        with db.lock:
            commits = db.conn.execute(
                "SELECT ce.*, t.state AS task_state, t.title FROM git_commit_events ce JOIN tasks t USING(task_id) "
                "JOIN work_orders w ON w.work_order_id=t.work_order_id WHERE w.project_id=? AND ce.status='committed'",
                (p.project_id,)).fetchall()
            branches = db.conn.execute(
                "SELECT b.* FROM git_branches b JOIN git_repositories r USING(repo_id) WHERE r.project_id=?",
                (p.project_id,)).fetchall()
            integrated = db.conn.execute(
                "SELECT ce.* FROM git_commit_events ce JOIN git_repositories r USING(repo_id) "
                "WHERE r.project_id=? AND ce.status='integrated'", (p.project_id,)).fetchall()
        try:
            for c in commits:
                if not git.commit_exists(root, c["sha"]):
                    out.append(Discrepancy("commit_missing", p.display_name, c["task_id"],
                                           f"Công việc “{c['title']}” ({c['task_state']}) ghi nhận một phiên bản đã lưu "
                                           "nhưng phiên bản đó không còn trong kho."))
            for b in branches:
                if not git.branch_exists(root, b["name"]):
                    out.append(Discrepancy("branch_missing", p.display_name, b["task_id"],
                                           f"Nhánh làm việc {b['name']} không còn trong kho (có thể đã bị xóa ngoài AATPO)."))
            target = p.git_default_branch
            for i in integrated:
                if target and git.branch_exists(root, target) and git.commit_exists(root, i["sha"]) \
                        and not git.is_ancestor(root, i["sha"], target):
                    out.append(Discrepancy("integration_lost", p.display_name, None,
                                           f"Phiên bản {i['sha'][:8]} từng được tích hợp nhưng nhánh “{target}” hiện không chứa nó."))
        except GitError:
            out.append(Discrepancy("git_error", p.display_name, None, "Không đối chiếu được với kho Git của dự án."))
    with db.tx() as c:
        for d in out:
            st.log_event(c, "audit.mismatch", "task", d.task_id, None, mismatch=d.kind, project=d.project)
    return out
