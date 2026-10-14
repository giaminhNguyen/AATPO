"""Measured run counts / durations per provider (spec G5). Only what was recorded; no cost or quota is invented."""
from __future__ import annotations

from datetime import datetime
from statistics import median


def provider_stats(db) -> dict[str, dict]:
    with db.lock:
        rows = db.conn.execute(
            "SELECT s.provider_id AS provider, r.state, r.started_at, r.finished_at FROM process_runs r "
            "JOIN agent_sessions s USING(session_id)").fetchall()
    stats: dict[str, dict] = {}
    for r in rows:
        s = stats.setdefault(r["provider"], {"runs": 0, "SUCCEEDED": 0, "FAILED": 0, "TIMED_OUT": 0, "CANCELLED": 0,
                                             "UNKNOWN_AFTER_CRASH": 0, "durations": []})
        s["runs"] += 1
        if r["state"] in s:
            s[r["state"]] += 1
        if r["started_at"] and r["finished_at"] and r["state"] == "SUCCEEDED":
            s["durations"].append((datetime.fromisoformat(r["finished_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds())
    for s in stats.values():
        d = s.pop("durations")
        s["median_seconds"] = round(median(d), 1) if d else None
        s["success_rate"] = round(100 * s["SUCCEEDED"] / s["runs"]) if s["runs"] else None
    return stats


def describe(stats: dict[str, dict]) -> str:
    if not stats:
        return "Chưa có lần chạy nào được ghi nhận."
    lines = []
    for p, s in sorted(stats.items()):
        bits = [f"{s['runs']} lần chạy", f"{s['SUCCEEDED']} thành công ({s['success_rate']}%)"]
        for key, label in (("FAILED", "lỗi"), ("TIMED_OUT", "quá giờ"), ("CANCELLED", "bị dừng"), ("UNKNOWN_AFTER_CRASH", "gián đoạn")):
            if s[key]:
                bits.append(f"{s[key]} {label}")
        if s["median_seconds"] is not None:
            bits.append(f"thời gian trung vị {s['median_seconds']} giây")
        lines.append(f"{p}: " + ", ".join(bits))
    return "\n".join(lines)
