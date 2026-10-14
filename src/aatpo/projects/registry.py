"""Project Registry application service: register / create / select / relink / archive.
The GUI calls this; it never touches SQL or git directly."""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

from aatpo.db.connection import Database
from aatpo.db.repositories import Store
from aatpo.domain.models import Project, ProjectStatus, ProjectType, new_id, utcnow
from aatpo.projects.git_service import GitError, GitService

PROFILE = "default"  # one operator profile in the MVP


class RegistryError(ValueError):
    """User-facing (Vietnamese) reason an action was refused."""


def _key(p: Path) -> str:
    return os.path.normcase(str(p))


def fold(text: str) -> str:
    """Lower-case, strip Vietnamese diacritics for fuzzy *candidate* matching."""
    t = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


class ProjectRegistry:
    def __init__(self, store: Store, git: GitService):
        self.store, self.db, self.git = store, store.db, git
        if git.recorder is None:
            git.recorder = self._record_git_op

    def _record_git_op(self, cwd: str, res) -> None:
        with self.db.tx() as c:
            c.execute("INSERT INTO git_operations(op_id,repo_root,argv,exit_code,stdout_tail,stderr_tail,at) "
                      "VALUES(?,?,?,?,?,?,?)", (new_id("GITOP"), cwd, " ".join(res.argv[1:]), res.exit_code,
                                                res.stdout[-500:], res.stderr[-500:], utcnow()))

    # ---- queries ------------------------------------------------------------------------
    def list(self, include_archived: bool = False) -> list[Project]:
        q = "SELECT * FROM projects" + ("" if include_archived else " WHERE status='active'")
        with self.db.lock:
            return [self._row(r) for r in self.db.conn.execute(q + " ORDER BY created_at")]

    def get(self, project_id: str) -> Project:
        with self.db.lock:
            r = self.db.conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if r is None:
            raise KeyError(project_id)
        return self._row(r)

    @staticmethod
    def _row(r) -> Project:
        d = dict(r)
        for k in ("repo_detected", "git_auto_history"):
            d[k] = bool(d[k])
        d["test_command"] = json.loads(d["test_command"]) if d.get("test_command") else None
        return Project(**d)

    def suggest(self, query: str) -> list[Project]:
        """Candidate suggestion only; caller must ask the user when len != 1 (spec 4.2.3)."""
        q = fold(query)
        return [p for p in self.list() if q and (q in fold(p.display_name) or fold(p.display_name) in q)]

    def path_missing(self, p: Project) -> bool:
        return not Path(p.root_path).is_dir()

    # ---- register / create ----------------------------------------------------------------
    def register(self, path: str | Path, display_name: str, *, auto_history: bool,
                 project_type: ProjectType = ProjectType.EXISTING_CODE) -> Project:
        """Register an existing folder. `auto_history=True` is the user's explicit one-time
        consent for `git init` when the folder has no repository (spec 4.1 / 6.3.B.3)."""
        root = self._canonical(path)
        name = display_name.strip()
        if not name:
            raise RegistryError("Vui lòng đặt tên cho dự án.")
        repo = self.git.detect(root) if self.git.available else None
        git_root, created = None, False
        if repo and repo.is_repo:
            git_root = repo.root  # reuse as-is: never switch branch / touch index / init
        elif auto_history:
            if not self.git.available:
                raise RegistryError("Chưa cài Git nên chưa thể bật lưu lịch sử phiên bản tự động.")
            try:
                repo = self.git.init_repo(root, baseline=True)
            except GitError as e:
                raise RegistryError(f"Không thể bật lịch sử phiên bản: {e}") from e
            git_root, created = repo.root, True
        return self._insert(root, name, project_type, auto_history and git_root is not None, repo, git_root, created)

    def create_new(self, path: str | Path, display_name: str, *, auto_history: bool = True,
                   allow_nonempty: bool = False) -> Project:
        """New project: folder must be new/empty unless the user explicitly approved otherwise."""
        p = Path(path)
        if p.exists() and not p.is_dir():
            raise RegistryError("Đường dẫn này là một tệp, không phải thư mục.")
        if p.is_dir() and any(p.iterdir()) and not allow_nonempty:
            raise RegistryError("Thư mục không trống. Hãy chọn thư mục trống hoặc xác nhận rõ ràng để dùng thư mục này.")
        p.mkdir(parents=True, exist_ok=True)
        return self.register(p, display_name, auto_history=auto_history, project_type=ProjectType.NEW_PRODUCT)

    def _canonical(self, path: str | Path) -> Path:
        try:
            root = Path(path).resolve(strict=True)  # follows symlinks/junctions
        except (OSError, RuntimeError) as e:
            raise RegistryError("Không tìm thấy thư mục này.") from e
        if not root.is_dir():
            raise RegistryError("Đường dẫn này không phải thư mục.")
        if root.parent == root:
            raise RegistryError("Không thể đăng ký cả ổ đĩa làm dự án.")
        return root

    def _insert(self, root, name, ptype, auto, repo, git_root, created) -> Project:
        pid, now = new_id("PRJ"), utcnow()
        with self.db.tx() as c:
            if c.execute("SELECT 1 FROM projects WHERE root_key=?", (_key(root),)).fetchone():
                raise RegistryError("Thư mục này đã được đăng ký làm dự án.")
            c.execute("INSERT INTO projects(project_id,display_name,root_path,root_key,project_type,status,"
                      "created_at,updated_at,repo_detected,git_auto_history,git_default_branch) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, name, str(root), _key(root), ptype, ProjectStatus.ACTIVE, now, now,
                       int(bool(repo and repo.is_repo)), int(auto), repo.branch if repo and repo.is_repo else None))
            if git_root:
                c.execute("INSERT INTO git_repositories VALUES(?,?,?,?,?)",
                          (new_id("REPO"), pid, git_root, int(created), now))
            self.store.log_event(c, "project.registered", "project", pid, pid, path=str(root))
        return self.get(pid)

    # ---- selection / lifecycle -------------------------------------------------------------
    def select(self, project_id: str) -> Project:
        p = self.get(project_id)
        if p.status != ProjectStatus.ACTIVE:
            raise RegistryError("Dự án đã được lưu trữ.")
        with self.db.tx() as c:
            c.execute("INSERT INTO app_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (f"selected_project:{PROFILE}", project_id))
            c.execute("UPDATE projects SET selected_at=? WHERE project_id=?", (utcnow(), project_id))
            self.store.log_event(c, "project.selected", "project", project_id, project_id)
        return self.get(project_id)

    def selected(self) -> Project | None:
        with self.db.lock:
            r = self.db.conn.execute("SELECT value FROM app_state WHERE key=?",
                                     (f"selected_project:{PROFILE}",)).fetchone()
        if not r:
            return None
        p = self.get(r["value"])
        return p if p.status == ProjectStatus.ACTIVE else None

    def archive(self, project_id: str) -> None:
        """Archive never touches files on disk."""
        with self.db.tx() as c:
            c.execute("UPDATE projects SET status='archived', updated_at=? WHERE project_id=?", (utcnow(), project_id))
            c.execute("DELETE FROM app_state WHERE key=? AND value=?", (f"selected_project:{PROFILE}", project_id))
            self.store.log_event(c, "project.archived", "project", project_id, project_id)

    def relink(self, project_id: str, new_path: str | Path) -> Project:
        root = self._canonical(new_path)
        with self.db.tx() as c:
            clash = c.execute("SELECT project_id FROM projects WHERE root_key=? AND project_id<>?",
                              (_key(root), project_id)).fetchone()
            if clash:
                raise RegistryError("Thư mục này đã thuộc về một dự án khác.")
            c.execute("UPDATE projects SET root_path=?, root_key=?, updated_at=? WHERE project_id=?",
                      (str(root), _key(root), utcnow(), project_id))
            self.store.log_event(c, "project.relinked", "project", project_id, project_id, path=str(root))
        return self.get(project_id)

    def set_test_command(self, project_id: str, argv: list[str] | None) -> Project:
        """The user-confirmed command AATPO may run as test evidence (P1). None clears it."""
        from aatpo.evidence.tests import validate_command
        if argv is not None:
            validate_command(list(argv))
        with self.db.tx() as c:
            c.execute("UPDATE projects SET test_command=?, updated_at=? WHERE project_id=?",
                      (json.dumps(argv, ensure_ascii=False) if argv else None, utcnow(), project_id))
            self.store.log_event(c, "project.test_command", "project", project_id, project_id, argv=argv)
        return self.get(project_id)

