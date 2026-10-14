"""When and how a write-capable task gets its own branch (spec 6.3.B.4/5). Never touches a dirty tree."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aatpo.customer.text import fold
from aatpo.db.connection import Database
from aatpo.domain.models import Project, Task, WorkOrder, new_id, utcnow
from aatpo.projects.git_service import DirtyRepo, GitError, GitService


@dataclass(frozen=True)
class BranchResult:
    status: str            # created | skipped | blocked
    branch: str | None = None
    base_sha: str | None = None
    reason: str | None = None


def branch_name(wo: WorkOrder, task: Task) -> str:
    slug = "-".join(fold(task.title).split())[:30].strip("-") or "task"
    return f"task/{wo.work_order_id}-{task.task_id}-{slug}"


def prepare_task_branch(git: GitService, db: Database, project: Project, wo: WorkOrder, task: Task) -> BranchResult:
    if not git.available:
        return BranchResult("skipped", reason="git_missing")
    root = Path(project.root_path)
    info = git.detect(root)
    if not info.is_repo:
        return BranchResult("skipped", reason="no_repo")
    if not info.has_commits:
        return BranchResult("skipped", reason="no_commits")
    name = branch_name(wo, task)
    n = 1
    while git.branch_exists(root, name if n == 1 else f"{name}-{n}"):
        n += 1  # deterministic suffix, never overwrite
    name = name if n == 1 else f"{name}-{n}"
    try:
        base = git.create_task_branch(root, name)
    except DirtyRepo:
        return BranchResult("blocked", reason="dirty_repo")
    except GitError as e:
        return BranchResult("blocked", reason=str(e)[:200])
    with db.tx() as c:
        repo = c.execute("SELECT repo_id FROM git_repositories WHERE project_id=? ORDER BY recorded_at DESC LIMIT 1",
                         (project.project_id,)).fetchone()
        if repo is None:
            rid = new_id("REPO")
            c.execute("INSERT INTO git_repositories VALUES(?,?,?,?,?)", (rid, project.project_id, info.root, 0, utcnow()))
        else:
            rid = repo["repo_id"]
        c.execute("INSERT INTO git_branches VALUES(?,?,?,?,?,?,?)",
                  (new_id("BR"), rid, name, wo.work_order_id, task.task_id, base, utcnow()))
    return BranchResult("created", name, base)
