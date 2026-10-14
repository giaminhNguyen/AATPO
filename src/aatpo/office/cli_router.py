"""Provider routing: cheapest_capable_available by configured preference. Unknown quota stays unknown."""
from __future__ import annotations


def route(preference: tuple[str, ...], statuses: dict[str, tuple[str, str | None]],
          exclude: frozenset[str] = frozenset(), prefer: str | None = None) -> str | None:
    """First provider in `preference` that is `ready` and not excluded. `prefer` (the task's previous
    provider) wins when still ready so exact session resume stays possible."""
    def ok(p: str) -> bool:
        return p not in exclude and statuses.get(p, ("missing", None))[0] == "ready"
    if prefer and ok(prefer):
        return prefer
    return next((p for p in preference if ok(p)), None)
