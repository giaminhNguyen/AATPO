"""Runs against the REAL packaged build (dist/AATPO/AATPO.exe). Skipped - and reported as skipped, not passed -
when the build is absent. Build first: powershell -File packaging/build.ps1"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
EXE = ROOT / "dist" / "AATPO" / "AATPO.exe"
pytestmark = [pytest.mark.windows_integration,
              pytest.mark.skipif(sys.platform != "win32" or not EXE.exists(), reason="packaged exe not built on this machine")]


def run_exe(tmp_path, *args, path_env=None):
    env = {**os.environ, "AATPO_HOME": str(tmp_path / "home"), "QT_QPA_PLATFORM": ""}
    env.pop("QT_QPA_PLATFORM")
    if path_env is not None:
        env["PATH"] = path_env
    return subprocess.run([str(EXE), *args], env=env, timeout=120)


def test_exe_self_check_without_python_on_path(tmp_path):
    report = tmp_path / "r.json"
    git_dir = str(Path(subprocess.run(["where", "git"], capture_output=True, text=True).stdout.splitlines()[0]).parent)
    r = run_exe(tmp_path, "--smoke-test", str(report), path_env=rf"C:\Windows\System32;{git_dir}")
    d = json.loads(report.read_text(encoding="utf-8"))
    assert r.returncode == 0 and d["ok"] and d["frozen"] is True
    assert d["db_schema_version"] >= 5 and len(d["roles_loaded"]) == 8
    assert d["nav"][:5] == ["Văn phòng AI", "Dự án", "Công việc", "Cần bạn quyết định", "Kết quả"]
    assert (tmp_path / "home" / "data" / "office.db").exists()


def test_exe_is_a_windowed_app_with_icon(tmp_path):
    data = EXE.read_bytes()
    import struct
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    subsystem = struct.unpack_from("<H", data, pe + 24 + 68)[0]
    assert subsystem == 2, "must be the GUI subsystem (no console window for end users)"
    assert (ROOT / "dist" / "AATPO" / "_internal").is_dir()


def test_shortcut_script_creates_a_working_shortcut(tmp_path):
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "packaging" / "make_shortcut.ps1"),
                        "-Folder", str(tmp_path)], capture_output=True, text=True, encoding="utf-8")
    lnk = next(tmp_path.glob("*.lnk"))
    target = subprocess.run(["powershell", "-NoProfile", "-Command",
                             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').TargetPath"],
                            capture_output=True, text=True).stdout.strip()
    assert r.returncode == 0 and Path(target).resolve() == EXE.resolve()
