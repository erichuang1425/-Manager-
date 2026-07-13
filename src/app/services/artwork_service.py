"""Managed card artwork storage and non-blocking scaled image loading."""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import time
from typing import Callable, Optional

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal
from PySide6.QtGui import QImage, QImageReader, QImageWriter

from app.logging_utils import get_logger, kv
from app.storage.paths import get_app_dir


_MAX_SAVED_DIMENSION = 1920
_MAX_CACHE_ITEMS = 256
_log = get_logger("artwork")


def card_artwork_dir() -> Path:
    path = get_app_dir() / "card-artwork"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_managed_artwork(path: str) -> bool:
    if not path:
        return False
    try:
        Path(path).resolve(strict=False).relative_to(card_artwork_dir().resolve())
        return True
    except (OSError, ValueError):
        return False


def _remove_managed_file(path: str) -> bool:
    if not _is_managed_artwork(path):
        return False
    try:
        candidate = Path(path)
        if candidate.exists():
            candidate.unlink()
            return True
    except OSError:
        return False
    return False


def save_card_artwork(
    game_id: str,
    image: QImage,
    *,
    previous_path: str = "",
) -> str:
    """Normalize and atomically store a screenshot inside the app data folder."""
    if image is None or image.isNull():
        raise ValueError("The selected image could not be read.")

    normalized = image
    if max(image.width(), image.height()) > _MAX_SAVED_DIMENSION:
        normalized = image.scaled(
            QSize(_MAX_SAVED_DIMENSION, _MAX_SAVED_DIMENSION),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
    normalized = normalized.convertToFormat(QImage.Format_RGB32)

    game_key = hashlib.sha256(str(game_id).encode("utf-8")).hexdigest()[:16]
    destination = card_artwork_dir() / f"{game_key}-{time.time_ns()}.jpg"
    temporary = destination.with_suffix(".tmp.jpg")
    writer = QImageWriter(str(temporary), b"jpeg")
    writer.setQuality(90)
    try:
        written = writer.write(normalized)
        error_message = writer.errorString()
        # QImageWriter keeps the file handle open for its lifetime on Windows.
        # Release it before the atomic rename or os.replace raises WinError 32.
        del writer
        if not written:
            raise ValueError(error_message or "Unable to save card artwork.")
        os.replace(temporary, destination)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

    clear_artwork_cache(previous_path)
    if previous_path and Path(previous_path) != destination:
        _remove_managed_file(previous_path)
    return str(destination)


def import_card_artwork(
    game_id: str,
    source_path: str,
    *,
    previous_path: str = "",
) -> str:
    reader = QImageReader(source_path)
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString() or "The selected image could not be read.")
    return save_card_artwork(game_id, image, previous_path=previous_path)


def remove_card_artwork(path: str) -> bool:
    """Remove app-managed artwork; external paths are never deleted."""
    clear_artwork_cache(path)
    return _remove_managed_file(path)


class _ArtworkLoaderSignals(QObject):
    ready = Signal(str, int, int, object)


class _ArtworkLoader(QThread):
    def __init__(self) -> None:
        super().__init__()
        self.signals = _ArtworkLoaderSignals()
        self._queue: Queue[tuple[str, int, int] | None] = Queue()
        self._pending: set[tuple[str, int, int]] = set()
        self._lock = threading.Lock()
        self._stop_requested = False

    def request(self, key: tuple[str, int, int]) -> bool:
        with self._lock:
            if key in self._pending:
                return False
            self._pending.add(key)
        self._queue.put(key)
        return True

    def stop(self) -> None:
        self._stop_requested = True
        self._queue.put(None)
        self.wait(3000)

    def run(self) -> None:
        while not self._stop_requested:
            try:
                item = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if item is None:
                break
            path, target_width, target_height = item
            try:
                reader = QImageReader(path)
                reader.setAutoTransform(True)
                source_size = reader.size()
                if source_size.isValid():
                    scale = max(
                        target_width / source_size.width(),
                        target_height / source_size.height(),
                    )
                    scale = min(1.0, scale)
                    reader.setScaledSize(QSize(
                        max(1, round(source_size.width() * scale)),
                        max(1, round(source_size.height() * scale)),
                    ))
                image = reader.read()
                self.signals.ready.emit(
                    path,
                    target_width,
                    target_height,
                    None if image.isNull() else image,
                )
            except Exception:
                self.signals.ready.emit(path, target_width, target_height, None)
            finally:
                with self._lock:
                    self._pending.discard(item)


_loader: _ArtworkLoader | None = None
_cache: OrderedDict[tuple[str, int, int], QImage] = OrderedDict()
_failures: set[tuple[str, int, int]] = set()
_subscribers: dict[tuple[str, int, int], list[Callable]] = {}


def _get_loader() -> _ArtworkLoader:
    global _loader
    if _loader is None:
        _loader = _ArtworkLoader()
        _loader.signals.ready.connect(_on_ready)
        _loader.start()
    return _loader


def _on_ready(path: str, width: int, height: int, value: object) -> None:
    key = (path, width, height)
    image = value if isinstance(value, QImage) and not value.isNull() else None
    if image is None:
        _failures.add(key)
    else:
        _cache[key] = image
        _cache.move_to_end(key)
        while len(_cache) > _MAX_CACHE_ITEMS:
            _cache.popitem(last=False)
    callbacks = _subscribers.pop(key, [])
    for callback in callbacks:
        try:
            callback(path, image)
        except Exception:
            # One stale/closed widget must not prevent other cards waiting on
            # the same decoded image from receiving their repaint callback.
            _log.exception("artwork_callback_error %s", kv(path=path))


def request_artwork_async(
    path: str,
    width: int,
    height: int,
    callback: Callable[[str, Optional[QImage]], None],
) -> None:
    width = max(1, int(width))
    height = max(1, int(height))
    key = (path, width, height)
    if not path:
        callback(path, None)
        return
    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        callback(path, cached)
        return
    if key in _failures:
        callback(path, None)
        return
    _subscribers.setdefault(key, []).append(callback)
    _get_loader().request(key)


def clear_artwork_cache(path: str = "") -> None:
    if not path:
        _cache.clear()
        _failures.clear()
        return
    for key in [key for key in _cache if key[0] == path]:
        _cache.pop(key, None)
    failed_keys = {key for key in _failures if key[0] == path}
    _failures.difference_update(failed_keys)


def shutdown_artwork_loader() -> None:
    global _loader
    if _loader is not None:
        _loader.stop()
        _loader = None
