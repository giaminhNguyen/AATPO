"""Pre-commit safety checks on what an agent changed: path policy + obvious-credential scan of ADDED lines."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

_FORBIDDEN_PATH = re.compile(
    r"(^|/)(\.git(/|$)|\.env($|\.)|id_rsa|id_ed25519|.*\.(pem|key|p12|pfx|jks|kdbx)$|"
    r"(credentials|secrets?)(\.[a-z]+)?$|\.aws/|\.ssh/)", re.I)
_SECRET_LINE = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*['\"][^'\"\s]{12,}['\"]"),
]


def forbidden_paths(paths: list[str]) -> list[str]:
    """Paths an agent may never change/commit (secrets, .git internals). Windows separators normalised."""
    bad = []
    for p in paths:
        q = PurePosixPath(p.replace("\\", "/")).as_posix()
        if q.startswith("/") or ".." in PurePosixPath(q).parts or _FORBIDDEN_PATH.search(q):
            bad.append(p)
    return bad


def scan_added_lines(diff: str) -> list[str]:
    """Descriptions (never the secret itself) of suspicious ADDED lines in a unified diff."""
    hits, current = [], "?"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for rx in _SECRET_LINE:
                if rx.search(line):
                    hits.append(f"{current}: dòng có vẻ chứa khóa/mật khẩu")
                    break
    return hits
