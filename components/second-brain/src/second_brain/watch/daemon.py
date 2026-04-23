from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest
from second_brain.log import EventKind, append_event
from second_brain.watch.queue import SerialQueue

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver


Worker = Callable[[Path], None]
Clock = Callable[[], float]

_DEBOUNCE_SECONDS = 1.5
_POLL_INTERVAL = 0.25


def _default_worker(cfg: Config) -> Worker:
    def run(path: Path) -> None:
        try:
            source = IngestInput.from_path(path)
            folder = ingest(source, cfg=cfg)
            append_event(
                kind=EventKind.WATCH,
                op="watch.ingest.ok",
                subject=folder.root.name,
                value=str(path),
                home=cfg.home,
            )
        except (IngestError, Exception) as exc:  # noqa: BLE001
            append_event(
                kind=EventKind.ERROR,
                op="watch.ingest.failed",
                subject=str(path),
                value=str(exc),
                home=cfg.home,
            )

    return run


class Watcher:
    def __init__(
        self,
        cfg: Config,
        *,
        queue: SerialQueue | None = None,
        worker: Worker | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.cfg = cfg
        self.queue = queue or SerialQueue()
        self._worker = worker or _default_worker(cfg)
        self._clock = clock or time.monotonic
        self._observer: Any | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _handle_event(self, src_path: str) -> None:
        path = Path(src_path)
        if not path.exists() or path.is_dir():
            return
        if path.name.startswith("."):
            return
        if ".processed" in path.parts:
            return
        self.queue.enqueue(
            key=str(path),
            fn=lambda p=path: self._worker(p),
            debounce=_DEBOUNCE_SECONDS,
            now=self._clock(),
        )

    def start(self) -> None:
        from watchdog.observers import Observer

        handler = _InboxHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.cfg.inbox_dir), recursive=False)
        observer.start()
        self._observer = observer

        self._stop.clear()
        self._thread = threading.Thread(target=self._worker_loop, name="sb-watch", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=timeout)
            self._observer = None
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            self.queue.drain_until_empty(now=self._clock())
            time.sleep(_POLL_INTERVAL)


try:
    from watchdog.events import FileSystemEventHandler as _BaseHandler
except ImportError:  # watchdog optional at import time; start() will re-import
    _BaseHandler = object  # type: ignore[assignment,misc]


class _InboxHandler(_BaseHandler):  # type: ignore[misc]
    def __init__(self, watcher: Watcher) -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
        self._watcher._handle_event(event.src_path)

    def on_moved(self, event) -> None:  # type: ignore[no-untyped-def]
        self._watcher._handle_event(event.dest_path)
