"""Safe, local-only Git operations (spec 6.3). Fixed argv vectors, validated cwd, no shell,
no remotes, no destructive commands. G0 scope: detect, init, baseline commit."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Only these subcommands may ever be executed by this service.
_ALLOWED = {"rev-parse", "status", "init", "add", "commit", "config", "symbolic-ref", "diff", "log", "switch",
            "merge", "merge-base", "restore"}
_BRANCH = re.compile(r"^task/[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,120}$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")


class GitError(RuntimeError):
    pass


class DirtyRepo(GitError):
    pass


class MissingIdentity(GitError):
    pass


class NotFastForward(GitError):
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


    # ---- G4: write workflow (every command is fixed-shape; refs/paths are validated) -----------------------
    def current_branch(self, path: Path) -> str | None:
        r = self._run(path, "symbolic-ref", "--short", "-q", "HEAD")
        return r.stdout.strip() or None

    def changed_paths(self, path: Path) -> list[str]:
        """Paths changed in the working tree (porcelain v1, NUL-separated so any filename is safe)."""
        r = self._run(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", check=True)
        out, parts = [], r.stdout.split("\0")
        i = 0
        while i < len(parts):
            e = parts[i]
            i += 1
            if len(e) < 4:
                continue
            code, name = e[:2], e[3:]
            if "R" in code or "C" in code:   # rename/copy carries the source path as the next field
                i += 1
            out.append(name)
        return out

    def stage_paths(self, path: Path, paths: list[str]) -> None:
        """Stage ONLY the given paths (never -A). Paths are passed after `--` so they cannot become options."""
        if not paths:
            raise GitError("không có tệp nào để lưu")
        self._run(path, "add", "--", *paths, check=True)

    def unstage_paths(self, path: Path, paths: list[str]) -> None:
        """Index-only undo of `add` (`restore --staged`); the working tree is never touched."""
        if paths:
            self._run(path, "restore", "--staged", "--", *paths, check=True)

    def commit_exists(self, path: Path, sha: str) -> bool:
        return bool(_SHA.match(sha)) and self._run(path, "rev-parse", "--verify", "-q", f"{sha}^{{commit}}").exit_code == 0

    def parent_sha(self, path: Path, sha: str) -> str | None:
        if not _SHA.match(sha):
            return None
        r = self._run(path, "rev-parse", "--verify", "-q", f"{sha}^")
        return r.stdout.strip() if r.exit_code == 0 else None

    def staged_paths(self, path: Path) -> list[str]:
        r = self._run(path, "diff", "--cached", "--name-only", "-z", check=True)
        return [p for p in r.stdout.split("\0") if p]

    def staged_diff(self, path: Path, limit: int = 400_000) -> str:
        return self._run(path, "diff", "--cached", "--no-color", check=True).stdout[:limit]

    def check_staged(self, path: Path) -> str:
        """`git diff --cached --check` output ('' when clean). Callers decide what blocks."""
        r = self._run(path, "diff", "--cached", "--check")
        return (r.stdout + r.stderr).strip()

    def commit_staged(self, path: Path, message: str) -> str:
        if not self.identity(path):
            raise MissingIdentity("Chưa có tên/email để ghi vào lịch sử phiên bản")
        self._run(path, "commit", "-m", message, check=True)
        return self.head_sha(path)

    def set_local_identity(self, path: Path, name: str, email: str) -> None:
        """Repo-local only, and only with values the user typed (never global, never invented)."""
        name, email = name.strip(), email.strip()
        if not name or "@" not in email or any(c in name + email for c in "\n\r\0"):
            raise GitError("tên hoặc email không hợp lệ")
        self._run(path, "config", "--local", "user.name", name, check=True)
        self._run(path, "config", "--local", "user.email", email, check=True)

    def diff_range(self, path: Path, base: str, head: str, stat: bool = False, limit: int = 400_000) -> str:
        if not (_SHA.match(base) and _SHA.match(head)):
            raise GitError("mã phiên bản không hợp lệ")
        args = ["diff", "--no-color", *(["--stat"] if stat else []), f"{base}..{head}"]
        return self._run(path, *args, check=True).stdout[:limit]

    def is_ancestor(self, path: Path, ancestor: str, descendant: str) -> bool:
        for ref in (ancestor, descendant):
            if not _REF.match(ref):
                raise GitError("tên nhánh không hợp lệ")
        return self._run(path, "merge-base", "--is-ancestor", ancestor, descendant).exit_code == 0

    def switch_branch(self, path: Path, name: str) -> None:
        """Plain `git switch <existing branch>` (no -f, no -c). Fails, untouched, if it would lose edits."""
        if not _REF.match(name) or not self.branch_exists(path, name):
            raise GitError(f"nhánh không tồn tại: {name}")
        self._run(path, "switch", name, check=True)

    def merge_ff_only(self, path: Path, branch: str) -> str:
        """The ONLY merge this service performs. Non-fast-forward => GitError, history untouched."""
        if not _REF.match(branch):
            raise GitError("tên nhánh không hợp lệ")
        r = self._run(path, "merge", "--ff-only", branch)
        if r.exit_code != 0:
            raise NotFastForward((r.stderr or r.stdout).strip()[:300])
        return self.head_sha(path)
