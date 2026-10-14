"""Runs coroutines on a private asyncio loop thread; results come back to the Qt thread through a
signal (queued connection), so widgets are only ever touched from the GUI thread."""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Callable

from PySide6.QtCore import QObject, Signal


class BackgroundJobs(QObject):
    finished = Signal(str, object, object)  # key, result, exception

    def __init__(self) -> None:
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, name="aatpo-jobs", daemon=True)
        self._thread.start()

    def submit(self, key: str, make_coro: Callable[[], Awaitable[Any]]) -> None:
        async def wrapper():
            return await make_coro()

        fut = asyncio.run_coroutine_threadsafe(wrapper(), self.loop)

        def done(f) -> None:
            exc = f.exception()
            self.finished.emit(key, None if exc else f.result(), exc)

        fut.add_done_callback(done)

    def shutdown(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=5)
