from __future__ import annotations
from PySide6.QtCore import QObject, Signal, Slot
from typing import List

from app.models import Game
from app.services import scan_shortcut_files, scan_shortcut_root
from app.logging_utils import get_logger, kv

_log = get_logger("worker.scan")

class ScanWorker(QObject):
    # progress(text, current, total)
    progress = Signal(str, int, int)
    finished = Signal(list)   # List[Game]
    failed = Signal(str)

    def __init__(self, root_path: str = "", paths: list[str] | None = None) -> None:
        super().__init__()
        self.root_path = root_path
        self.paths = list(paths or [])
        self._stop = False
        self.cancelled = False

    def stop(self) -> None:
        self._stop = True

    @Slot()
    def run(self) -> None:
        try:
            _log.info("scan_worker_start %s", kv(path=self.root_path))
            if self.paths:
                games = scan_shortcut_files(
                    self.paths,
                    progress=lambda msg, i, total: self.progress.emit(msg, i, total),
                    should_stop=lambda: self._stop,
                    source_label="selected shortcut files",
                )
            else:
                games = scan_shortcut_root(
                    self.root_path,
                    progress=lambda msg, i, total: self.progress.emit(msg, i, total),
                    should_stop=lambda: self._stop,
                )
            self.cancelled = self._stop
            self.finished.emit(games)
        except Exception as e:
            _log.exception("scan_worker_error %s", kv(path=self.root_path))
            self.failed.emit(str(e))
