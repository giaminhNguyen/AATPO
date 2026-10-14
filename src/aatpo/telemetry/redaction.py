"""Best-effort secret redaction for logs/diagnostics (spec A30). Not a guarantee."""
from __future__ import annotations

import re

_RULES = [
    (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}"), "[REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}"), "[REDACTED]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"), "[REDACTED]"),
    (re.compile(r"(?i)\b((?:api[_-]?key|token|secret|password)\s*[=:]\s*)\S+"), r"\1[REDACTED]"),
]


def redact(text: str, limit: int | None = None) -> str:
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text if limit is None or len(text) <= limit else text[:limit] + "…[cắt bớt]"
