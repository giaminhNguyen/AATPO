"""Child process for the crash drill: starts a real run through AATPO's launcher, announces pids, then waits to be killed."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from aatpo.cli.windows_launcher import run_process

fake, pidfile = sys.argv[1], sys.argv[2]
asyncio.run(run_process([sys.executable, fake, "pids", pidfile], cwd=None, stdin_text="x", timeout=300))
