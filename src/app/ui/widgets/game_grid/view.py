"""
GameGridView — a ``QListView`` in IconMode that renders game cards through
``GameCardDelegate``.  It owns hover / click / keyboard / drag interaction and
translates hit-zones into high-level signals consumed by the ``GameGrid``
wrapper.

No per-card widgets exist: the view paints via the delegate, so scrolling and
resizing allocate nothing.  Item size is recomputed from the viewport width
(same algorithm as the old ``_compute_layout``) on a short debounce.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer, QModelIndex, QPoint, QSize
from PySide6.QtWidgets import QListView, QAbstractItemView, QMenu
from PySide6.QtGui import QDrag

from app.services import pixmap_for_game
from app.ui.theme import current_theme
from app.ui.icons import AppIcons

from .model import GameListModel, GameRole
from .delegate import GameCardDelegate, CardMetrics, build_geometry


class GameGridView(QListView):
    """Icon-mode list view that paints game cards and routes interactions."""

    game_clicked = Signal(str)          # game_id (single click / arrow nav)
    game_activated = Signal(str)        # game_id (double click / Enter)
    game_play = Signal(str)             # game_id (Space / play button)
    status_filter_requested = Signal(str)   # status value (status chip)
    tag_filter_requested = Signal(str)      # tag text
    updates_requested = Signal(str)         # game_id (update badge)
    rating_changed = Signal(str, object)    # game_id, rating or None
    context_action = Signal(str, str)       # game_id, action
    selection_changed = Signal(list)        # list[game_id]
    page_flip = Signal(int)                 # +1 / -1 in pages mode

    def __init__(self, model: GameListModel, parent=None) -> None:
        super().__init__(parent)
        self.setModel(model)
        self._delegate = GameCardDelegate(self)
        self.setItemDelegate(self._delegate)

        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setLayoutMode(QListView.Batched)
        self.setBatchSize(120)
        self.setWrapping(True)
        self.setFlow(QListView.LeftToRight)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setFrameShape(QListView.NoFrame)
        self.setStyleSheet("QListView { background: transparent; border: none; }")

        self._view_mode = "comfortable"
        self._type_scale = "normal"
        self._multi_select = False
        self._paged = False
        self._selected_ids: set[str] = set()

        self._press_pos: Optional[QPoint] = None
        self._press_index: QModelIndex = QModelIndex()

        # Debounced item-size recompute on resize (recompute size only — never
        # rebuild anything).
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(50)
        self._layout_timer.timeout.connect(self._recompute_layout)

        self._recompute_layout()

    # ------------------------------------------------------------------ #
    #  Config
    # ------------------------------------------------------------------ #

    def set_view_mode(self, mode: str) -> None:
        if mode not in ("comfortable", "compact") or mode == self._view_mode:
            return
        self._view_mode = mode
        self._recompute_layout()

    def set_type_scale(self, scale: str) -> None:
        if scale not in ("small", "normal", "large") or scale == self._type_scale:
            return
        self._type_scale = scale
        self._recompute_layout()

    def set_paged(self, paged: bool) -> None:
        self._paged = bool(paged)

    def set_multi_select(self, enabled: bool) -> None:
        self._multi_select = bool(enabled)
        if not enabled:
            self._selected_ids.clear()
        self.viewport().update()
        self.selection_changed.emit(list(self._selected_ids))

    def is_multi_select(self) -> bool:
        return self._multi_select

    def is_selected(self, game_id: str) -> bool:
        return game_id in self._selected_ids

    def selected_ids(self) -> List[str]:
        return list(self._selected_ids)

    # ------------------------------------------------------------------ #
    #  Layout
    # ------------------------------------------------------------------ #

    def _recompute_layout(self) -> None:
        theme = current_theme()
        width = max(240, self.viewport().width())
        preferred_w = 260 if self._view_mode == "comfortable" else 200
        min_w = theme.card_min_width
        max_w = theme.card_max_width
        gap = theme.grid_gap
        padding = theme.grid_padding * 2

        available = width - padding
        cols = max(1, (available + gap) // (preferred_w + gap))
        card_w = max(min_w, min(max_w, (available - gap * (cols - 1)) // cols))
        if card_w < min_w and cols > 1:
            cols -= 1
            card_w = max(min_w, min(max_w, (available - gap * (cols - 1)) // cols))

        metrics = CardMetrics.compute(int(card_w), self._view_mode, self._type_scale)
        self._delegate.set_metrics(metrics)
        # Bake the gap into the grid cell so columns compute from viewport width.
        self.setGridSize(QSize(int(card_w) + gap, metrics.card_h + gap))
        self.setSpacing(0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_timer.start()

    # ------------------------------------------------------------------ #
    #  Hit testing
    # ------------------------------------------------------------------ #

    def _zone_at(self, index: QModelIndex, pos: QPoint):
        game = index.data(GameRole)
        if game is None:
            return None
        rect = self.visualRect(index)
        geo = build_geometry(rect, game, self._delegate.metrics, self._multi_select)
        # Only treat the play button as active when hovering that item.
        for kind, r, payload in geo.zones():
            if kind == "play":
                # play is a small circle — restrict to the ellipse-ish rect
                if r.contains(pos):
                    return (kind, payload)
                continue
            if r.contains(pos):
                return (kind, payload)
        return None

    # ------------------------------------------------------------------ #
    #  Mouse interaction
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        index = self.indexAt(event.pos())
        if not index.isValid():
            # Clear any stale press state so a drag started from here can't
            # reuse a previously clicked card's index.
            self._press_pos = None
            self._press_index = QModelIndex()
            super().mousePressEvent(event)
            return

        self._press_pos = event.pos()
        self._press_index = index
        game = index.data(GameRole)

        zone = self._zone_at(index, event.pos())
        if zone is not None:
            kind, payload = zone
            self._handle_zone(game, kind, payload, index)
            event.accept()
            return

        # Body click.
        self.setCurrentIndex(index)
        if self._multi_select or (event.modifiers() & Qt.ControlModifier):
            self._toggle_select(game.game_id)
        else:
            self.game_clicked.emit(game.game_id)
        event.accept()

    def _handle_zone(self, game, kind: str, payload, index: QModelIndex) -> None:
        if kind == "play":
            self.game_play.emit(game.game_id)
        elif kind == "update":
            self.updates_requested.emit(game.game_id)
        elif kind == "checkbox":
            self._toggle_select(game.game_id)
        elif kind == "rating":
            value = int(payload)
            if game.rating == value:
                game.rating = None
                self.rating_changed.emit(game.game_id, None)
            else:
                game.rating = value
                self.rating_changed.emit(game.game_id, value)
            self._notify_changed(game.game_id)
        elif kind == "status":
            # Chip in the info row filters by that status.
            self.status_filter_requested.emit(str(payload))
        elif kind == "tag":
            self.tag_filter_requested.emit(str(payload))
        elif kind == "strip":
            # Accent strip cycles the game's status (preserved behaviour).
            cycle = ["backlog", "playing", "finished", "dropped"]
            cur = cycle.index(game.status) if game.status in cycle else 0
            nxt = cycle[(cur + 1) % len(cycle)]
            game.status = nxt
            self.context_action.emit(game.game_id, f"set_status_{nxt}")
            self._notify_changed(game.game_id)

    def _notify_changed(self, game_id: str) -> None:
        model = self.model()
        if isinstance(model, GameListModel):
            model.notify_game_changed(game_id)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        index = self.indexAt(event.pos())
        if index.isValid():
            game = index.data(GameRole)
            # A double-click on an interactive zone should defer to that zone.
            if self._zone_at(index, event.pos()) is None:
                self.game_activated.emit(game.game_id)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        # Hover repaint (State_MouseOver is set by Qt; we just ensure repaint).
        super().mouseMoveEvent(event)
        if (event.buttons() & Qt.LeftButton) and self._press_index.isValid():
            if (event.pos() - self._press_pos).manhattanLength() >= 10:
                self._start_drag(self._press_index)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        # A press that never became a drag must not leave its index behind for
        # the next press to pick up.
        self._press_pos = None
        self._press_index = QModelIndex()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.viewport().update()
        super().leaveEvent(event)

    def _start_drag(self, index: QModelIndex) -> None:
        game = index.data(GameRole)
        if game is None:
            return
        model = self.model()
        drag = QDrag(self)
        drag.setMimeData(model.mimeData([index]))
        pm = pixmap_for_game(game, 64)
        if pm is not None and not pm.isNull():
            scaled = pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            drag.setPixmap(scaled)
            drag.setHotSpot(QPoint(scaled.width() // 2, scaled.height() // 2))
        self._press_index = QModelIndex()
        self._press_pos = None
        drag.exec(Qt.CopyAction)

    # ------------------------------------------------------------------ #
    #  Selection helpers
    # ------------------------------------------------------------------ #

    def _toggle_select(self, game_id: str) -> None:
        if game_id in self._selected_ids:
            self._selected_ids.discard(game_id)
        else:
            self._selected_ids.add(game_id)
        self.viewport().update()
        self.selection_changed.emit(list(self._selected_ids))

    def select_all(self) -> None:
        model = self.model()
        if isinstance(model, GameListModel):
            self._selected_ids = {g.game_id for g in model.all_games()}
        self.viewport().update()
        self.selection_changed.emit(list(self._selected_ids))

    def clear_selection(self) -> None:
        self._selected_ids.clear()
        self.viewport().update()
        self.selection_changed.emit([])

    # ------------------------------------------------------------------ #
    #  Keyboard
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        cur = self.currentIndex()

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if cur.isValid():
                game = cur.data(GameRole)
                if game is not None:
                    self.game_activated.emit(game.game_id)
            event.accept()
            return
        if key == Qt.Key_Space:
            if cur.isValid():
                game = cur.data(GameRole)
                if game is not None:
                    self.game_play.emit(game.game_id)
            event.accept()
            return
        if key == Qt.Key_PageDown and self._paged:
            self.page_flip.emit(1)
            event.accept()
            return
        if key == Qt.Key_PageUp and self._paged:
            self.page_flip.emit(-1)
            event.accept()
            return

        super().keyPressEvent(event)

        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                   Qt.Key_Home, Qt.Key_End):
            new = self.currentIndex()
            if new.isValid():
                game = new.data(GameRole)
                if game is not None:
                    self.game_clicked.emit(game.game_id)

    def focus_first(self) -> None:
        model = self.model()
        if model is not None and model.rowCount() > 0:
            idx = model.index(0, 0)
            self.setCurrentIndex(idx)
            self.setFocus()
            game = idx.data(GameRole)
            if game is not None:
                self.game_clicked.emit(game.game_id)

    def clear_focus(self) -> None:
        self.setCurrentIndex(QModelIndex())
        self.viewport().update()

    # ------------------------------------------------------------------ #
    #  Context menu (ported 1:1 from the old GameCard)
    # ------------------------------------------------------------------ #

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        game = index.data(GameRole)
        if game is None:
            return

        menu = QMenu(self)
        a_play = menu.addAction(f"{AppIcons.ACT_PLAY} Play")
        a_edit = menu.addAction("Edit Details")
        menu.addSeparator()

        status_menu = menu.addMenu("Set Status")
        a_status_backlog = status_menu.addAction("Backlog")
        a_status_playing = status_menu.addAction("Playing")
        a_status_finished = status_menu.addAction("Finished")
        a_status_dropped = status_menu.addAction("Dropped")
        status_actions = {
            "backlog": a_status_backlog,
            "playing": a_status_playing,
            "finished": a_status_finished,
            "dropped": a_status_dropped,
        }
        if game.status in status_actions:
            a = status_actions[game.status]
            a.setText(f"✓ {a.text()}")

        rate_menu = menu.addMenu("Rate")
        rating_actions = {}
        for i in range(1, 11):
            filled = i // 2 + i % 2
            stars_text = "★" * filled + "☆" * (5 - filled)
            rating_actions[i] = rate_menu.addAction(f"{stars_text} {i}/10")
        rate_menu.addSeparator()
        a_rate_clear = rate_menu.addAction("Clear rating")
        if game.rating and game.rating in rating_actions:
            a = rating_actions[game.rating]
            a.setText(f"✓ {a.text()}")

        menu.addSeparator()
        a_add = menu.addAction("Add to Collection…")
        menu.addSeparator()
        a_open_folder = menu.addAction("Open Shortcut Folder")
        a_open_file = menu.addAction("Open Shortcut File")
        menu.addSeparator()
        a_rename = menu.addAction("Rename…")
        a_remove = menu.addAction("Remove from Library…")

        chosen = menu.exec(event.globalPos())
        if not chosen:
            return

        if chosen == a_play:
            self.game_play.emit(game.game_id)
        elif chosen == a_edit:
            self.game_clicked.emit(game.game_id)
        elif chosen == a_add:
            self.context_action.emit(game.game_id, "add_to_collection")
        elif chosen == a_open_folder:
            self.context_action.emit(game.game_id, "open_folder")
        elif chosen == a_open_file:
            self.context_action.emit(game.game_id, "open_file")
        elif chosen == a_rename:
            self.context_action.emit(game.game_id, "rename")
        elif chosen == a_remove:
            self.context_action.emit(game.game_id, "remove")
        elif chosen in status_actions.values():
            for st, act in status_actions.items():
                if act == chosen:
                    game.status = st
                    self.context_action.emit(game.game_id, f"set_status_{st}")
                    self._notify_changed(game.game_id)
                    break
        elif chosen == a_rate_clear:
            game.rating = None
            self.rating_changed.emit(game.game_id, None)
            self._notify_changed(game.game_id)
        elif chosen in rating_actions.values():
            for rating, act in rating_actions.items():
                if act == chosen:
                    game.rating = rating
                    self.rating_changed.emit(game.game_id, rating)
                    self._notify_changed(game.game_id)
                    break
