"""
GameListModel — Qt model backing the library grid.

Holds the full ``List[Game]`` and exposes rows to a ``QListView`` via a
``QStyledItemDelegate``.  In *pages* mode only the current page's slice is
exposed as rows; in *scroll* mode every game is a row.  All row-count changes
go through ``begin/endResetModel`` so views relayout correctly.

The ``Game`` object itself is handed to the delegate through ``GameRole`` so the
delegate can paint the whole card without any per-item child widgets.
"""

from __future__ import annotations

import math
from typing import List, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QMimeData

from app.models import Game

from .display_utils import status_label, relative_time


# Custom role used to hand the whole Game object to the delegate.
GameRole = Qt.UserRole + 1

# Mime format used for drag-and-drop onto sidebar collections (must match
# library_sidebar.py's drop handler).
GAME_MIME = "application/x-game-id"


class GameListModel(QAbstractListModel):
    """List model exposing games (optionally a single page's slice) as rows."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._all_games: List[Game] = []
        self._paged: bool = False
        self._page: int = 0
        self._page_size: int = 24

    # ------------------------------------------------------------------ #
    #  Data source management
    # ------------------------------------------------------------------ #

    def set_games(self, games: Optional[List[Game]]) -> None:
        self.beginResetModel()
        self._all_games = list(games) if games else []
        self._clamp_page()
        self.endResetModel()

    def all_games(self) -> List[Game]:
        return self._all_games

    def total_count(self) -> int:
        return len(self._all_games)

    def _visible_games(self) -> List[Game]:
        if self._paged:
            start = self._page * self._page_size
            return self._all_games[start:start + self._page_size]
        return self._all_games

    def game_at(self, row: int) -> Optional[Game]:
        vis = self._visible_games()
        if 0 <= row < len(vis):
            return vis[row]
        return None

    def row_for_game_id(self, game_id: str) -> int:
        for i, g in enumerate(self._visible_games()):
            if g.game_id == game_id:
                return i
        return -1

    def notify_game_changed(self, game_id: str) -> None:
        """Repaint just the row showing ``game_id`` (e.g. after an icon loads)."""
        row = self.row_for_game_id(game_id)
        if row >= 0:
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx)

    # ------------------------------------------------------------------ #
    #  Pagination
    # ------------------------------------------------------------------ #

    def set_paged(self, paged: bool) -> None:
        paged = bool(paged)
        if paged == self._paged:
            return
        self.beginResetModel()
        self._paged = paged
        self._clamp_page()
        self.endResetModel()

    def is_paged(self) -> bool:
        return self._paged

    def set_page(self, page: int) -> None:
        page = max(0, min(int(page), self.total_pages() - 1))
        if page == self._page:
            return
        self.beginResetModel()
        self._page = page
        self.endResetModel()

    def set_page_size(self, size: int) -> None:
        size = max(1, int(size))
        if size == self._page_size:
            return
        self.beginResetModel()
        self._page_size = size
        self._clamp_page()
        self.endResetModel()

    def page(self) -> int:
        return self._page

    def page_size(self) -> int:
        return self._page_size

    def total_pages(self) -> int:
        if not self._all_games:
            return 1
        return max(1, math.ceil(len(self._all_games) / self._page_size))

    def _clamp_page(self) -> None:
        tp = self.total_pages()
        if self._page >= tp:
            self._page = max(0, tp - 1)

    # ------------------------------------------------------------------ #
    #  QAbstractListModel interface
    # ------------------------------------------------------------------ #

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._visible_games())

    def data(self, index, role: int = Qt.DisplayRole):  # noqa: N802
        if not index.isValid():
            return None
        g = self.game_at(index.row())
        if g is None:
            return None
        if role == GameRole:
            return g
        if role == Qt.DisplayRole:
            return g.title
        if role == Qt.ToolTipRole:
            parts = [g.title]
            ver = g.installed_version_raw or g.source_version_raw
            meta = []
            if ver:
                meta.append(f"v{ver}")
            meta.append(status_label(g.status))
            rel = relative_time(g.last_played)
            if rel:
                meta.append(rel)
            if meta:
                parts.append("  ·  ".join(meta))
            return "\n".join(parts)
        return None

    def flags(self, index):  # noqa: N802
        if not index.isValid():
            return Qt.NoItemFlags
        return (
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsDragEnabled
        )

    # ------------------------------------------------------------------ #
    #  Drag-and-drop (game_id onto sidebar collections)
    # ------------------------------------------------------------------ #

    def mimeTypes(self):  # noqa: N802
        return [GAME_MIME, "text/plain"]

    def supportedDragActions(self):  # noqa: N802
        return Qt.CopyAction

    def mimeData(self, indexes):  # noqa: N802
        md = QMimeData()
        for idx in indexes:
            g = self.game_at(idx.row()) if idx.isValid() else None
            if g is not None:
                md.setText(g.game_id)
                md.setData(GAME_MIME, g.game_id.encode())
                break
        return md
