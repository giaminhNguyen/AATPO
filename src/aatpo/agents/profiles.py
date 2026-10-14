"""Versioned role profiles (src/aatpo/roles/*.md)."""
from __future__ import annotations

from functools import lru_cache
from importlib import resources

from aatpo.domain.models import CORE_ROLES


@lru_cache
def profile(role_id: str) -> tuple[int, str]:
    """-> (profile_version, prompt body without front matter)."""
    if role_id not in CORE_ROLES:
        raise KeyError(role_id)
    text = resources.files("aatpo").joinpath("roles", f"{role_id}.md").read_text(encoding="utf-8")
    head, body = text.split("---\n", 2)[1:]
    version = int(next(ln.split(":", 1)[1] for ln in head.splitlines() if ln.startswith("profile_version")))
    return version, body.strip()
