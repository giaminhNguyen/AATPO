"""Input hygiene. Chat text is DATA: normalized, bounded, never executed or interpolated into commands."""
from __future__ import annotations

import re
import unicodedata

MAX_LEN = 4000
UNKNOWN_QUICK = "Tôi chưa biết, hãy đề xuất"
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_UNKNOWN = ("chua biet", "khong biet", "de xuat", "tuy ban", "tuy ong", "sao cung duoc", "chua ro", "khong ro")


def sanitize(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "")
    t = _CTRL.sub("", t).replace("\r\n", "\n").strip()
    return t[:MAX_LEN]


def fold(text: str) -> str:
    """Lower-case, no diacritics (đ -> d), single spaces: for tolerant keyword matching only."""
    t = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def is_unknown_answer(text: str) -> bool:
    f = fold(text)
    return any(p in f for p in _UNKNOWN)
