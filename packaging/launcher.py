"""Entry point used by PyInstaller (AATPO.exe). Equivalent to `python -m aatpo`."""
from aatpo.app import main

raise SystemExit(main())
