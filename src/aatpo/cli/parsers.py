"""Provider output parsers. Strict: nonzero exit, invalid JSON, or a provider-reported error is a
failure, never a task completion (A14). Session IDs are accepted only if they look like IDs."""
from __future__ import annotations

import json
import re

from aatpo.cli.base import AgentRunResult

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{7,99}$")
_QUOTA = re.compile(r"(?i)usage limit|quota|rate.?limit|too many requests|\b429\b|credit")


def valid_session_id(s: object) -> str | None:
    return s if isinstance(s, str) and _ID.match(s) else None


def classify_error(text: str) -> str | None:
    return "quota" if _QUOTA.search(text or "") else None


def _fail(msg: str, exit_code: int = 0) -> AgentRunResult:
    return AgentRunResult(ok=False, exit_code=exit_code, error=msg[:500], error_kind=classify_error(msg))


def parse_claude(stdout: str, stderr: str, exit_code: int) -> AgentRunResult:
    """`claude -p --output-format json`: one result object (or an event array containing it)."""
    if exit_code != 0:
        return _fail(stderr.strip() or stdout.strip() or "claude thoát với mã lỗi", exit_code)
    try:
        data = json.loads(stdout)
    except ValueError as e:
        return _fail(f"đầu ra không phải JSON hợp lệ: {e}", exit_code)
    if isinstance(data, list):
        data = next((x for x in reversed(data) if isinstance(x, dict) and x.get("type") == "result"), None)
    if not isinstance(data, dict) or "result" not in data:
        return _fail("thiếu trường 'result' trong đầu ra của claude", exit_code)
    if data.get("is_error"):
        return _fail(str(data.get("result")), exit_code)
    return AgentRunResult(ok=True, text=str(data["result"]), exit_code=exit_code,
                          provider_session_id=valid_session_id(data.get("session_id")))


def parse_codex(stdout: str, stderr: str, exit_code: int, last_message: str | None) -> AgentRunResult:
    """`codex exec --json`: JSONL events. Final text comes from `-o <file>` (last_message) when present,
    else the last agent_message item. thread_id (from thread.started) is the resumable session id."""
    if exit_code != 0:
        return _fail(stderr.strip() or "codex thoát với mã lỗi", exit_code)
    thread, text, err, events = None, None, None, 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue  # banners / non-event lines
        try:
            ev = json.loads(line)
        except ValueError:
            return _fail("một dòng sự kiện JSONL của codex bị hỏng", exit_code)
        events += 1
        kind = ev.get("type")
        if kind == "thread.started":
            thread = valid_session_id(ev.get("thread_id"))
        elif kind in ("error", "turn.failed"):
            err = str(ev.get("message") or ev.get("error") or ev)
        elif kind == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                text = item["text"]
    if err:
        return _fail(err, exit_code)
    final = (last_message or "").strip() or text
    if not events or not final:
        return _fail("codex không trả về nội dung hợp lệ", exit_code)
    return AgentRunResult(ok=True, text=final, exit_code=exit_code, provider_session_id=thread)
