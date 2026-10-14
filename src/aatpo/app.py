"""Bootstrap: `python -m aatpo` (development) or AATPO.exe (packaged) opens the desktop window.

Developer/CI diagnostics (never needed by end users):
  --smoke-test <file.json>   open the real window, write a self-check report, exit (0 = ok)
  --screenshot <file.png>    open the real window, save a picture of it, exit
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from aatpo import __version__
from aatpo.services import Services
from aatpo.settings import default_paths


def _opt(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def self_check(services: Services, win) -> dict:
    """Facts that prove a packaged build is complete: bundled roles + migrations load, DB opens, window is real."""
    from aatpo.agents.profiles import profile
    from aatpo.domain.models import CORE_ROLES
    return {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "db_schema_version": services.db.conn.execute("PRAGMA user_version").fetchone()[0],
        "roles_loaded": sorted(r for r in CORE_ROLES if profile(r)[1]),
        "nav": [win.nav.item(i).text() for i in range(win.nav.count())],
        "title": win.windowTitle(),
        "data_dir": str(services.paths.home),
        "git_available": services.git.available,
    }


def main(argv: list[str] | None = None) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from aatpo.gui.main_window import MainWindow

    argv = list(sys.argv if argv is None else argv)
    smoke, shot = _opt(argv, "--smoke-test"), _opt(argv, "--screenshot")
    app = QApplication(argv)
    services = Services.create(default_paths(), write_mode=True)
    win = MainWindow(services, auto_probe=not (smoke or shot))
    win.show()
    code = {"v": 0}
    if smoke or shot:
        def finish() -> None:
            try:
                if shot:
                    win.grab().save(shot)
                if smoke:
                    info = self_check(services, win)
                    ok = info["db_schema_version"] >= 5 and len(info["roles_loaded"]) == 8 and len(info["nav"]) == 6
                    Path(smoke).write_text(json.dumps({**info, "ok": ok}, ensure_ascii=False, indent=2), encoding="utf-8")
                    code["v"] = 0 if ok else 2
            except Exception as e:  # a failing self-check must fail loudly (exit code + file), never silently
                if smoke:
                    Path(smoke).write_text(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}), encoding="utf-8")
                code["v"] = 3
            app.quit()
        QTimer.singleShot(1200, finish)
    rc = app.exec()
    services.close()
    return code["v"] or rc
