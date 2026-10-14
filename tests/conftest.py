import os
import subprocess

import pytest

from aatpo.services import Services
from aatpo.settings import AppPaths


@pytest.fixture(autouse=True)
def hermetic_git(tmp_path_factory, monkeypatch):
    """Never touch the real user git config: identity comes from a throwaway global file."""
    cfg = tmp_path_factory.mktemp("gitcfg") / "gitconfig"
    cfg.write_text("[user]\n\tname = Test User\n\temail = test@example.invalid\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    return cfg


@pytest.fixture
def svc(tmp_path):
    s = Services.create(AppPaths(tmp_path / "home"), adapters={})
    yield s
    s.close()


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
