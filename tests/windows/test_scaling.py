"""Layout at the window's minimum size on the REAL Windows Qt platform for 100/125/150% display scaling."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
pytestmark = [pytest.mark.windows_integration, pytest.mark.skipif(sys.platform != "win32", reason="Windows display scaling")]


@pytest.mark.parametrize("factor", ["1", "1.25", "1.5"])
def test_no_clipped_or_overflowing_controls(tmp_path, factor):
    env = {**os.environ, "QT_SCALE_FACTOR": factor, "PYTHONIOENCODING": "utf-8"}
    env.pop("QT_QPA_PLATFORM", None)
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "ui" / "native_scaling.py"), str(tmp_path)], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, r.stderr[-500:]
    report = json.loads(r.stdout.strip().splitlines()[-1])
    assert report["scale"] == factor and report["violations"] == [], report["violations"]
    assert len(list(tmp_path.glob(f"{factor}_*.png"))) == 6
