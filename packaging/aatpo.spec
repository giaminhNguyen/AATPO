# -*- mode: python ; coding: utf-8 -*-
# Build (from the repo root, on Windows):  .venv\Scripts\python -m PyInstaller packaging\aatpo.spec --noconfirm
# Output: dist\AATPO\AATPO.exe  (onedir; no Python needed on the target PC)
from pathlib import Path

root = Path(SPECPATH).parent
src = root / "src"

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(src)],
    datas=[
        (str(src / "aatpo" / "roles" / "*.md"), "aatpo/roles"),
        (str(src / "aatpo" / "db" / "migrations" / "*.sql"), "aatpo/db/migrations"),
    ],
    hiddenimports=[],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
              "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AATPO",
    console=False,                      # no terminal window for end users
    icon=str(root / "packaging" / "aatpo.ico"),
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AATPO")
