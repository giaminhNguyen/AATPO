import subprocess

import pytest

from aatpo.projects.git_service import GitError
from aatpo.projects.registry import RegistryError
from aatpo.services import Services
from aatpo.settings import AppPaths
from tests.conftest import git


def test_register_select_and_persist_across_restart(tmp_path):
    home, proj = tmp_path / "home", tmp_path / "Dự án có dấu & khoảng trắng"
    proj.mkdir()
    s1 = Services.create(AppPaths(home))
    p = s1.registry.register(proj, "Quản lý bán hàng", auto_history=False)
    s1.registry.select(p.project_id)
    assert p.root_path == str(proj.resolve())
    s1.close()
    s2 = Services.create(AppPaths(home))  # "restart"
    assert [x.display_name for x in s2.registry.list()] == ["Quản lý bán hàng"]
    assert s2.registry.selected().project_id == p.project_id
    s2.close()


def test_duplicate_and_bad_paths_rejected(svc, tmp_path):
    d = tmp_path / "a"
    d.mkdir()
    svc.registry.register(d, "A", auto_history=False)
    with pytest.raises(RegistryError):
        svc.registry.register(d, "A again", auto_history=False)
    with pytest.raises(RegistryError):
        svc.registry.register(tmp_path / "nope", "X", auto_history=False)
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(RegistryError):
        svc.registry.register(f, "F", auto_history=False)
    e = tmp_path / "e"
    e.mkdir()
    with pytest.raises(RegistryError):
        svc.registry.register(e, " ", auto_history=False)


def test_ambiguous_names_return_candidates_not_a_choice(svc, tmp_path):
    for n, name in (("a", "Quản lý bán hàng"), ("b", "Quản lý kho"), ("c", "Website công ty")):
        (tmp_path / n).mkdir()
        svc.registry.register(tmp_path / n, name, auto_history=False)
    got = svc.registry.suggest("Sửa lỗi đăng nhập dự án quản lý bán hàng")
    assert [p.display_name for p in got] == ["Quản lý bán hàng"]
    assert svc.registry.suggest("quan ly kho")[0].display_name == "Quản lý kho"  # diacritics-insensitive
    assert svc.registry.suggest("Sửa lỗi đăng nhập") == []  # no match -> caller must ask the user
    assert svc.registry.selected() is None  # a suggestion never changes selection (spec 4.2.2)


def test_missing_folder_flagged_and_relink_no_recreation(svc, tmp_path):
    d = tmp_path / "gone"
    d.mkdir()
    p = svc.registry.register(d, "G", auto_history=False)
    d.rmdir()
    assert svc.registry.path_missing(p)
    assert not d.exists()  # never silently recreated
    n = tmp_path / "moved"
    n.mkdir()
    p = svc.registry.relink(p.project_id, n)
    assert not svc.registry.path_missing(p)


def test_archive_keeps_files(svc, tmp_path):
    d = tmp_path / "keep"
    d.mkdir()
    (d / "x.txt").write_text("data")
    p = svc.registry.register(d, "K", auto_history=False)
    svc.registry.select(p.project_id)
    svc.registry.archive(p.project_id)
    assert (d / "x.txt").read_text() == "data"
    assert svc.registry.list() == [] and svc.registry.selected() is None


def test_create_new_refuses_nonempty_without_approval(svc, tmp_path):
    d = tmp_path / "new"
    d.mkdir()
    (d / "x.txt").write_text("mine")
    with pytest.raises(RegistryError):
        svc.registry.create_new(d, "N")
    p = svc.registry.create_new(d, "N", allow_nonempty=True)
    assert (d / "x.txt").read_text() == "mine" and p.git_auto_history


def test_new_project_inits_git_with_baseline(svc, tmp_path):
    d = tmp_path / "fresh"
    p = svc.registry.create_new(d, "Fresh")
    assert (d / ".git").is_dir() and p.git_auto_history and p.git_default_branch == "main"
    assert git(d, "rev-list", "--count", "HEAD") == "1"
    assert git(d, "ls-files") == ""  # baseline is empty: no unreviewed files swept in
    assert svc.db.conn.execute("SELECT count(*) FROM git_repositories WHERE created_by_aatpo=1").fetchone()[0] == 1
    assert svc.db.conn.execute("SELECT count(*) FROM git_operations").fetchone()[0] >= 3


def test_unversioned_project_requires_consent_for_git(svc, tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    p = svc.registry.register(d, "Plain", auto_history=False)
    assert not (d / ".git").exists() and not p.git_auto_history  # A36: no init without opt-in
    d2 = tmp_path / "plain2"
    d2.mkdir()
    svc.registry.register(d2, "Plain2", auto_history=True)
    assert (d2 / ".git").is_dir()


def test_existing_dirty_repo_preserved(svc, tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    git(d, "init", "-b", "trunk")
    (d / "a.txt").write_text("1")
    git(d, "add", "a.txt")
    git(d, "commit", "-m", "c1")
    (d / "a.txt").write_text("dirty")
    (d / "new.txt").write_text("untracked")
    head, status = git(d, "rev-parse", "HEAD"), git(d, "status", "--porcelain")
    p = svc.registry.register(d, "Repo", auto_history=True)
    assert p.repo_detected and p.git_default_branch == "trunk"  # detected, not assumed 'main'
    assert git(d, "rev-parse", "HEAD") == head and git(d, "status", "--porcelain") == status  # A34
    assert (d / "a.txt").read_text() == "dirty"


def test_no_nested_repo_inside_parent_repo(svc, tmp_path):
    git(tmp_path, "init", "-b", "main")
    sub = tmp_path / "sub"
    sub.mkdir()
    p = svc.registry.register(sub, "Sub", auto_history=True)
    assert not (sub / ".git").exists() and p.repo_detected


def test_missing_identity_makes_no_commit_with_invented_author(svc, tmp_path, monkeypatch):
    empty = tmp_path / "empty.cfg"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    d = tmp_path / "noid"
    d.mkdir()
    svc.registry.register(d, "NoId", auto_history=True)
    assert (d / ".git").is_dir()
    r = subprocess.run(["git", "rev-list", "--all", "--count"], cwd=d, capture_output=True, text=True)
    assert r.stdout.strip() == "0"


def test_git_allowlist_blocks_destructive_and_remote(svc, tmp_path):
    for bad in ("push", "reset", "clean", "stash", "checkout", "remote", "rebase", "fetch"):
        with pytest.raises(GitError):
            svc.git._run(tmp_path, bad)
