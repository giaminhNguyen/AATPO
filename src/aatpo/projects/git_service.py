"""Safe, local-only Git operations (spec 6.3). Fixed argv vectors, validated cwd, no shell,
no remotes, no destructive commands. G0 scope: detect, init, baseline commit."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Only these subcommands may ever be executed by this service.
_ALLOWED = {"rev-parse", "status", "init", "add", "commit", "config", "symbolic-ref", "diff", "log", "switch"}
_BRANCH = re.compile(r"^task/[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RepoInfo:
    is_repo: bool
    root: str | None = None
    branch: str | None = None      # None when unborn/detached/not a repo
    has_commits: bool = False
    dirty: bool = False


class GitService:
    def __init__(self, git_exe: str | None = None, recorder=None):
        self.git = git_exe or shutil.which("git")
        self.recorder = recorder  # callable(cwd, GitResult) -> None, for the git_operations ledger

    @property
    def available(self) -> bool:
        return self.git is not None

    def _run(self, cwd: Path, *args: str, check: bool = False) -> GitResult:
        if not self.git:
            raise GitError("Git chưa được cài đặt")
        if args[0] not in _ALLOWED:
            raise GitError(f"git {args[0]} is not allowlisted")
        if not Path(cwd).is_dir():
            raise GitError(f"not a directory: {cwd}")
        p = subprocess.run([self.git, *args], cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL)
        res = GitResult((self.git, *args), p.returncode, p.stdout, p.stderr)
        if self.recorder:
            self.recorder(str(cwd), res)
        if check and p.returncode != 0:
            raise GitError(f"git {args[0]} failed ({p.returncode}): {p.stderr.strip()[:300]}")
        return res

    def detect(self, path: Path) -> RepoInfo:
        """Find the enclosing repository (if any) without modifying anything."""
        top = self._run(path, "rev-parse", "--show-toplevel")
        if top.exit_code != 0:
            return RepoInfo(False)
        root = str(Path(top.stdout.strip()).resolve())
        head = self._run(path, "rev-parse", "--verify", "-q", "HEAD")
        branch = self._run(path, "symbolic-ref", "--short", "-q", "HEAD")
        status = self._run(path, "status", "--porcelain=v1")
        return RepoInfo(True, root, branch.stdout.strip() or None, head.exit_code == 0,
                        bool(status.stdout.strip()))

    def identity(self, path: Path) -> tuple[str, str] | None:
        name = self._run(path, "config", "user.name").stdout.strip()
        email = self._run(path, "config", "user.email").stdout.strip()
        return (name, email) if name and email else None

    def init_repo(self, path: Path, baseline: bool) -> RepoInfo:
        """git init at `path` iff it is NOT already inside a repository (no nesting).
        Baseline commit (empty, so no unreviewed files are swept in) only if identity exists."""
        info = self.detect(path)
        if info.is_repo:
            raise GitError(f"đã nằm trong kho lưu phiên bản tại {info.root}; không tạo kho lồng nhau")
        self._run(path, "init", "-b", "main", check=True)
        if baseline and self.identity(path):
            self._run(path, "commit", "--allow-empty", "-m", "chore: AATPO baseline snapshot", check=True)
        return self.detect(path)

    # ---- task branches (G3) -----------------------------------------------------------------
    def branch_exists(self, path: Path, name: str) -> bool:
        return self._run(path, "rev-parse", "--verify", "-q", f"refs/heads/{name}").exit_code == 0

    def head_sha(self, path: Path) -> str | None:
        r = self._run(path, "rev-parse", "--verify", "-q", "HEAD")
        return r.stdout.strip() if r.exit_code == 0 else None

    def create_task_branch(self, path: Path, name: str) -> str:
        """`git switch -c task/...` from the CURRENT head of a CLEAN repo; returns the base SHA.
        Refuses dirty trees (nothing is stashed/reset/forced) and names outside the task/ namespace."""
        if not _BRANCH.match(name):
            raise GitError(f"tên nhánh không hợp lệ: {name}")
        info = self.detect(path)
        if not info.is_repo or not info.has_commits:
            raise GitError("kho chưa có commit nào")
        if info.dirty:
            raise DirtyRepo("Thư mục dự án có thay đổi chưa được lưu")
        if self.branch_exists(path, name):
            raise GitError(f"nhánh {name} đã tồn tại")
        base = self.head_sha(path)
        self._run(path, "switch", "-c", name, check=True)
        return base


class DirtyRepo(GitError):
    pass
