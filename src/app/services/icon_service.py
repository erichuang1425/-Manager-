from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterable, Optional
from queue import Queue, Empty

from PySide6.QtCore import QSize, Qt, QThread, QObject, Signal
from PySide6.QtWidgets import QFileIconProvider
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QFileInfo
from functools import lru_cache
import time
import threading
from app.logging_utils import get_logger, kv, RateLimiter

_icon_provider = QFileIconProvider()
_log = get_logger("icons")
_rate = RateLimiter()

# Base size for icon cache. 512 is sufficient for max card width of 320px
# while using 1/4 the memory of 1024. Qt SmoothTransformation keeps quality.
_BASE_ICON_SIZE = 512

# ---------------------------------------------------------------------------
#  Async pixmap cache – populated by the background icon loader.
#  Keyed by (path, size); values are QPixmap (may be null for failed loads).
#  This dict is checked FIRST by pixmap_for_path / pixmap_for_game so icons
#  that were loaded asynchronously are available on subsequent sync lookups.
# ---------------------------------------------------------------------------
_async_pixmap_cache: dict[tuple[str, int], QPixmap] = {}
_async_raw_cache: dict[str, QPixmap] = {}  # path -> base-size pixmap


@lru_cache(maxsize=2048)
def _icon_for_path_cached(path: str) -> QIcon:
    start = time.perf_counter()
    if not path:
        return QIcon()
    ico = _icon_provider.icon(QFileInfo(path))
    if _rate.allow("icon_base_miss", 800):
        _log.debug("icon_base_miss %s", kv(path=path, duration_ms=round((time.perf_counter() - start) * 1000, 1)))
    return ico


def icon_for_path(path: str) -> QIcon:
    before = _icon_for_path_cached.cache_info()
    ico = _icon_for_path_cached(path)
    after = _icon_for_path_cached.cache_info()
    hit = after.hits > before.hits
    if _rate.allow(f"icon_cache:{path}", interval_ms=2000):
        _log.debug("icon_cache_%s %s", "hit" if hit else "miss", kv(path=path))
    return ico


@lru_cache(maxsize=2048)
def _raw_pixmap_cached(path: str) -> QPixmap:
    """Highest-quality pixmap we can get for a path."""
    # Check async cache first
    if path in _async_raw_cache:
        return _async_raw_cache[path]
    ico = icon_for_path(path)
    pm = ico.pixmap(QSize(_BASE_ICON_SIZE, _BASE_ICON_SIZE))
    return pm


@lru_cache(maxsize=4096)
def _scaled_pixmap_cached(path: str, size: int) -> QPixmap:
    base = _raw_pixmap_cached(path)
    if base.isNull():
        return QPixmap()
    if max(base.width(), base.height()) <= size:
        return base
    return base.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation)


def pixmap_for_path(path: str, size: int = 32) -> QPixmap:
    # Fast path: check async cache first (populated by background loader)
    key = (path, size)
    cached = _async_pixmap_cache.get(key)
    if cached is not None:
        return cached

    before = _scaled_pixmap_cached.cache_info()
    pm = _scaled_pixmap_cached(path, size)
    if _rate.allow(f"pixmap_cache:{path}:{size}", interval_ms=1200):
        info = _scaled_pixmap_cached.cache_info()
        hit = info.hits > before.hits
        base_ready = not _raw_pixmap_cached(path).isNull()
        _log.debug("pixmap_cache_%s %s", "hit" if hit else "miss", kv(path=path, size=size, base_cached=base_ready))
    if pm.isNull() and _rate.allow(f"pixmap_null:{path}", interval_ms=1500):
        _log.warning("pixmap_null %s", kv(path=path, size=size))
    return pm


# ---- higher-level helpers ----

# Cache Path.exists() results to avoid redundant stat() syscalls.
# Games typically reference the same shortcut/archive paths across renders.
@lru_cache(maxsize=4096)
def _path_exists_cached(p: str) -> bool:
    return Path(p).exists()


def _first_existing(paths: Iterable[str]) -> Optional[str]:
    for p in paths:
        if p and _path_exists_cached(p):
            return p
    return None


@lru_cache(maxsize=2048)
def _best_icon_path_cached(
    executable: str,
    backup: str,
    shortcut: str,
    archive: str,
    compressed: str,
) -> str:
    # Prefer the resolved executable. QFileIconProvider commonly returns the
    # generic .lnk shell glyph for a shortcut, while the target carries the
    # recognizable application icon the user expects.
    ordered = [executable, backup, shortcut, archive, compressed]
    best = _first_existing(ordered) or next((path for path in ordered if path), "")
    return best or ""


def icon_path_candidates(game) -> tuple[str, ...]:
    """Return unique icon-source candidates without touching the filesystem."""
    values = (
        getattr(game, "executable_path", "") or "",
        getattr(game, "backup_target_path", "") or "",
        getattr(game, "shortcut_path", "") or "",
        getattr(game, "archive_folder_path", "") or "",
        getattr(game, "compressed_archive_path", "") or "",
    )
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def icon_path_for_game(game, *, check_exists: bool = True) -> str:
    """Choose an icon source, optionally avoiding synchronous path probes.

    Resolved executables are preferred over shortcuts, followed by archive
    paths. This preserves the recognizable application icon instead of the
    generic Windows shortcut glyph whenever target metadata is available.
    """
    candidates = icon_path_candidates(game)
    if not candidates:
        return ""
    if not check_exists:
        return candidates[0]
    executable = getattr(game, "executable_path", "") or ""
    shortcut = getattr(game, "shortcut_path", "") or ""
    backup = getattr(game, "backup_target_path", "") or ""
    archive = getattr(game, "archive_folder_path", "") or ""
    compressed = getattr(game, "compressed_archive_path", "") or ""
    return _best_icon_path_cached(executable, backup, shortcut, archive, compressed)


def best_icon_path(game) -> str:
    """Backward-compatible filesystem-validated icon path lookup."""
    return icon_path_for_game(game, check_exists=True)


def pixmap_for_game(game, size: int = 32) -> QPixmap:
    """
    Choose and fetch the best available icon for a game, cached at high quality.
    """
    best = best_icon_path(game)
    if not best:
        return QPixmap()
    return pixmap_for_path(best, size=size)


def clear_icon_caches() -> None:
    """Allow manual invalidation (e.g., theme/icon pack changes)."""
    _icon_for_path_cached.cache_clear()
    _raw_pixmap_cached.cache_clear()
    _scaled_pixmap_cached.cache_clear()
    _path_exists_cached.cache_clear()
    _best_icon_path_cached.cache_clear()
    _async_pixmap_cache.clear()
    _async_raw_cache.clear()


# ====================================================================== #
#  Async icon loading – moves QFileIconProvider off the main thread
# ====================================================================== #

class _IconLoaderSignals(QObject):
    """Signals emitted by the background icon loader on the main thread."""
    icon_ready = Signal(str, int, object)  # (path, size, QPixmap or None)


class IconLoaderThread(QThread):
    """Background thread that loads icons via QFileIconProvider.

    On Windows/macOS Qt 6, QPixmap is backed by QImage and is safe to
    create from non-GUI threads.  This thread processes a queue of
    (path, size) requests and emits ``icon_ready`` on the main thread
    when each icon is done.
    """

    def __init__(self) -> None:
        super().__init__()
        self.signals = _IconLoaderSignals()
        self._queue: Queue[tuple[str, int] | None] = Queue()
        self._stop = False
        # Track exact requests so a 64px preview cannot accidentally consume a
        # simultaneous 256px card request for the same path (or vice versa).
        self._pending: set[tuple[str, int]] = set()
        self._lock = threading.Lock()

    def request(self, path: str, size: int) -> bool:
        """Enqueue an icon load request.  Returns False if already pending."""
        key = (path, size)
        with self._lock:
            if key in self._pending:
                return False
            self._pending.add(key)
        self._queue.put((path, size))
        return True

    def stop(self) -> None:
        self._stop = True
        self._queue.put(None)
        self.wait(3000)

    def run(self) -> None:
        # Each thread gets its own QFileIconProvider instance
        provider = QFileIconProvider()
        while not self._stop:
            try:
                item = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if item is None:
                break
            path, size = item
            start = time.perf_counter()
            try:
                ico = provider.icon(QFileInfo(path))
                base_pm = ico.pixmap(QSize(_BASE_ICON_SIZE, _BASE_ICON_SIZE))
                if base_pm.isNull():
                    self.signals.icon_ready.emit(path, size, None)
                else:
                    # Scale to requested size
                    if max(base_pm.width(), base_pm.height()) > size:
                        pm = base_pm.scaled(
                            QSize(size, size), Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    else:
                        pm = base_pm
                    # Store the base pixmap for cache population on main thread
                    _async_raw_cache[path] = base_pm
                    self.signals.icon_ready.emit(path, size, pm)
                duration = (time.perf_counter() - start) * 1000
                if _rate.allow("async_icon_load", 400):
                    _log.debug(
                        "async_icon_loaded %s",
                        kv(path=path, duration_ms=round(duration, 1),
                           null=base_pm.isNull()),
                    )
            except Exception:
                _log.exception("async_icon_error %s", kv(path=path))
                self.signals.icon_ready.emit(path, size, None)
            finally:
                with self._lock:
                    self._pending.discard((path, size))


# Singleton loader + subscriber registry
_icon_loader: IconLoaderThread | None = None
# (path, size) -> callbacks; callback signature: (path, QPixmap | None) -> None
_icon_subscribers: dict[tuple[str, int], list[Callable]] = {}


def _get_icon_loader() -> IconLoaderThread:
    global _icon_loader
    if _icon_loader is None:
        _icon_loader = IconLoaderThread()
        _icon_loader.signals.icon_ready.connect(_on_icon_ready)
        _icon_loader.start()
    return _icon_loader


def _on_icon_ready(path: str, size: int, pm: object) -> None:
    """Slot called on the main thread when a background icon load completes."""
    pixmap = pm if isinstance(pm, QPixmap) and not pm.isNull() else None
    if pixmap is not None:
        _async_pixmap_cache[(path, size)] = pixmap
        # Also populate the async raw cache so sync lookups work on re-render
        if path not in _async_raw_cache:
            _async_raw_cache[path] = pixmap
    callbacks = _icon_subscribers.pop((path, size), [])
    for cb in callbacks:
        try:
            cb(path, pixmap)
        except Exception:
            _log.exception("icon_callback_error %s", kv(path=path))


def request_icon_async(
    path: str, size: int, callback: Callable[[str, Optional[QPixmap]], None],
) -> None:
    """Request an icon to be loaded in the background.

    If the icon is already cached, *callback* is invoked synchronously.
    Otherwise the request is queued and *callback* is called on the main
    thread when the icon is ready.

    Args:
        path: File path to extract the icon from.
        size: Desired pixmap size (square).
        callback: ``callback(path, pixmap_or_none)`` – called on the main
            thread when the icon is available.
    """
    if not path:
        callback(path, None)
        return
    # Check async cache first
    cached = _async_pixmap_cache.get((path, size))
    if cached is not None:
        callback(path, cached)
        return
    # Register callback and submit to background thread
    _icon_subscribers.setdefault((path, size), []).append(callback)
    loader = _get_icon_loader()
    loader.request(path, size)


def shutdown_icon_loader() -> None:
    """Stop the background icon loader thread (call on app exit)."""
    global _icon_loader
    if _icon_loader is not None:
        _icon_loader.stop()
        _icon_loader = None
