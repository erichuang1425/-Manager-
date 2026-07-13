"""
GameGrid — thin wrapper around Qt's model/view/delegate library grid.

The heavy lifting lives in:
  * :class:`GameListModel`      (``model.py``)      — holds the games
  * :class:`GameCardDelegate`   (``delegate.py``)   — paints each card
  * :class:`GameGridView`       (``view.py``)       — IconMode QListView + input

This class only wires those together, keeps the empty-state and pagination-bar
UI, and preserves the exact public API the rest of the app consumes (signals
and methods).  There is no per-card widget, no virtual-scroll bookkeeping, no
fade animations and no loading overlay.
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QPushButton, QStackedLayout,
)
from PySide6.QtGui import QColor

from app.models import Game
from app.ui.theme import current_theme, primary_btn_style, secondary_btn_style, ghost_btn_style
from app.ui.icons import AppIcons
from app.logging_utils import get_logger, kv, RateLimiter

from .model import GameListModel
from .view import GameGridView

_log = get_logger("ui.game_grid")


class GameGrid(QWidget):
    """Container for the library grid (model/view/delegate based)."""

    game_selected = Signal(str)          # game_id
    game_play = Signal(str)              # game_id
    context_action = Signal(str, str)    # (game_id, action)
    status_filter_requested = Signal(str)
    updates_requested = Signal(str)
    rating_changed = Signal(str, object)
    tag_filter_requested = Signal(str)
    scan_requested = Signal()            # emitted when user clicks scan from empty state
    import_requested = Signal()          # emitted when user clicks import from empty state
    selection_changed = Signal(list)     # list of selected game_ids
    browse_mode_changed = Signal(str)    # "scroll" or "pages"
    page_changed = Signal(int)           # current page (0-indexed)

    def __init__(self) -> None:
        super().__init__()
        self._rate = RateLimiter()
        self._browse_mode = "scroll"
        self._view_mode = "comfortable"
        self._type_scale = "normal"
        self._pending_games: List[Game] | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._stack = QStackedLayout()

        # 0: empty state
        self._empty_state = self._build_empty_state()
        self._stack.addWidget(self._empty_state)

        # 1: content (view + pagination bar)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.model = GameListModel(self)
        self.view = GameGridView(self.model, self)
        # Keyboard handling (arrows / PageUp / PageDown / Enter / Space) lives on
        # the view.  Callers still focus the wrapper (e.g. grid.setFocus() from
        # the Escape handler), so proxy focus to the view or keyboard nav dies.
        self.setFocusProxy(self.view)
        theme = current_theme()
        self.view.setContentsMargins(
            theme.grid_padding, theme.grid_padding,
            theme.grid_padding, theme.grid_padding,
        )
        content_layout.addWidget(self.view, 1)

        self._pagination_bar = self._build_pagination_bar()
        self._pagination_bar.hide()
        content_layout.addWidget(self._pagination_bar)

        self._stack.addWidget(content)

        stack_widget = QWidget()
        stack_widget.setLayout(self._stack)
        outer.addWidget(stack_widget, 1)

        self._wire_view_signals()

        _log.info("grid_init %s", kv(view_mode=self._view_mode, browse_mode=self._browse_mode))

    # ------------------------------------------------------------------ #
    #  Signal wiring
    # ------------------------------------------------------------------ #

    def _wire_view_signals(self) -> None:
        v = self.view
        v.game_clicked.connect(self.game_selected.emit)
        v.game_activated.connect(self.game_selected.emit)
        v.game_play.connect(self.game_play.emit)
        v.status_filter_requested.connect(self.status_filter_requested.emit)
        v.tag_filter_requested.connect(self.tag_filter_requested.emit)
        v.updates_requested.connect(self.updates_requested.emit)
        v.rating_changed.connect(self.rating_changed.emit)
        v.context_action.connect(self.context_action.emit)
        v.selection_changed.connect(self.selection_changed.emit)
        v.page_flip.connect(self._on_page_flip)

    # ------------------------------------------------------------------ #
    #  Deferred-render tolerance (window.py toggles _render_suppressed)
    # ------------------------------------------------------------------ #

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "_render_suppressed" and value is False:
            pending = getattr(self, "_pending_games", None)
            if pending is not None:
                self._pending_games = None
                self._apply_games(pending)

    # ------------------------------------------------------------------ #
    #  Public API — data
    # ------------------------------------------------------------------ #

    def set_games(self, games: List[Game]) -> None:
        games = games or []
        if self._rate.allow("set_games", interval_ms=500):
            _log.info("set_games %s", kv(count=len(games), mode=self._browse_mode))
        if getattr(self, "_render_suppressed", False):
            self._pending_games = games
            return
        self._apply_games(games)

    def _apply_games(self, games: List[Game]) -> None:
        self.model.set_games(games)
        self._update_empty_state()
        self._update_pagination_bar()

    def set_view_mode(self, mode: str) -> None:
        if mode not in ("comfortable", "compact") or mode == self._view_mode:
            return
        self._view_mode = mode
        self.view.set_view_mode(mode)

    def set_type_scale(self, scale: str) -> None:
        if scale not in ("small", "normal", "large") or scale == self._type_scale:
            return
        self._type_scale = scale
        self.view.set_type_scale(scale)

    def set_browse_mode(self, mode: str) -> None:
        if mode not in ("scroll", "pages") or mode == self._browse_mode:
            return
        _log.info("browse_mode_changed %s", kv(old=self._browse_mode, new=mode))
        self._browse_mode = mode
        paged = mode == "pages"
        self.model.set_page(0)
        self.model.set_paged(paged)
        self.view.set_paged(paged)
        self._pagination_bar.setVisible(paged)
        self.browse_mode_changed.emit(mode)
        self._update_pagination_bar()

    def set_page_size(self, size: int) -> None:
        size = max(6, min(120, int(size)))
        self.model.set_page_size(size)
        self._update_pagination_bar()

    def get_browse_mode(self) -> str:
        return self._browse_mode

    def get_current_page(self) -> int:
        return self.model.page()

    def get_total_pages(self) -> int:
        return self.model.total_pages()

    # ------------------------------------------------------------------ #
    #  Pagination
    # ------------------------------------------------------------------ #

    def go_to_page(self, page: int) -> None:
        tp = self.model.total_pages()
        page = max(0, min(int(page), tp - 1))
        if page == self.model.page():
            return
        self.model.set_page(page)
        self.page_changed.emit(page)
        self._update_pagination_bar()
        self.view.scrollToTop()

    def next_page(self) -> None:
        if self.model.page() < self.model.total_pages() - 1:
            self.go_to_page(self.model.page() + 1)

    def prev_page(self) -> None:
        if self.model.page() > 0:
            self.go_to_page(self.model.page() - 1)

    def _on_page_flip(self, delta: int) -> None:
        if delta > 0:
            self.next_page()
        else:
            self.prev_page()

    def refresh(self) -> None:
        if self._rate.allow("refresh", interval_ms=500):
            _log.debug("grid_refresh")
        self.view.viewport().update()
        self._update_empty_state()
        self._update_pagination_bar()

    # ------------------------------------------------------------------ #
    #  Skeleton loading — kept for API compatibility (inert, no widgets)
    # ------------------------------------------------------------------ #

    def show_skeleton_loading(self, count: int = 8) -> None:
        # No skeleton widgets any more; just make sure the grid surface is shown.
        self._stack.setCurrentIndex(1)

    def hide_skeleton_loading(self) -> None:
        self._update_empty_state()

    # ------------------------------------------------------------------ #
    #  Multi-select
    # ------------------------------------------------------------------ #

    def set_multi_select_mode(self, enabled: bool) -> None:
        self.view.set_multi_select(enabled)

    def is_multi_select_mode(self) -> bool:
        return self.view.is_multi_select()

    def get_selected_game_ids(self) -> List[str]:
        return self.view.selected_ids()

    def select_all(self) -> None:
        self.view.select_all()

    def clear_selection(self) -> None:
        self.view.clear_selection()

    # ------------------------------------------------------------------ #
    #  Keyboard focus
    # ------------------------------------------------------------------ #

    def focus_first(self) -> None:
        self.view.focus_first()

    def clear_focus(self) -> None:
        self.view.clear_focus()

    def reveal_game(self, game_id: str) -> bool:
        """Bring a game into view, including switching to its page if needed."""
        all_games = self.model.all_games()
        absolute_row = next(
            (index for index, game in enumerate(all_games) if game.game_id == game_id),
            -1,
        )
        if absolute_row < 0:
            return False
        if self.model.is_paged():
            self.go_to_page(absolute_row // self.model.page_size())
        row = self.model.row_for_game_id(game_id)
        if row < 0:
            return False
        index = self.model.index(row, 0)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index)
        self.game_selected.emit(game_id)
        self.view.setFocus(Qt.OtherFocusReason)
        return True

    # ------------------------------------------------------------------ #
    #  Empty state
    # ------------------------------------------------------------------ #

    def _update_empty_state(self) -> None:
        if self.model.total_count() == 0:
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(1)

    def _build_empty_state(self) -> QWidget:
        theme = current_theme()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(60, 80, 60, 80)
        layout.setSpacing(12)
        layout.addStretch(2)

        badge = QFrame()
        badge.setFixedSize(132, 132)
        badge.setStyleSheet(
            f"QFrame {{ background: rgba({theme.accent.red()},{theme.accent.green()},"
            f"{theme.accent.blue()},28); border: 1px solid rgba({theme.accent.red()},"
            f"{theme.accent.green()},{theme.accent.blue()},60); border-radius: 66px; }}"
        )
        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(AppIcons.NAV_LIBRARY)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            f"font-size: 64px; color: {theme.accent.name()}; "
            f"background: transparent; border: none;"
        )
        badge_layout.addWidget(icon_label)
        layout.addWidget(badge, 0, Qt.AlignHCenter)

        layout.addSpacing(20)

        title = QLabel("Your library is empty")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {theme.text.name()}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Point the scanner at your shortcuts folder to build your library,\n"
            "or adjust your search filters if you expect to see games."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: 13px; color: {theme.text_muted.name()}; "
            f"line-height: 1.5; max-width: 440px; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(desc)

        layout.addSpacing(24)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)

        scan_btn = QPushButton(f"{AppIcons.ACT_SCAN}  Scan Shortcuts")
        scan_btn.setMinimumWidth(160)
        scan_btn.setStyleSheet(primary_btn_style(theme))
        scan_btn.setCursor(Qt.PointingHandCursor)
        scan_btn.clicked.connect(lambda: self.scan_requested.emit())
        btn_row.addWidget(scan_btn)

        import_btn = QPushButton(f"{AppIcons.ACT_IMPORT}  Import Library")
        import_btn.setMinimumWidth(140)
        import_btn.setStyleSheet(secondary_btn_style(theme))
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setToolTip("Import a previously exported library JSON file")
        import_btn.clicked.connect(lambda: self.import_requested.emit())
        btn_row.addWidget(import_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addStretch(3)
        return widget

    # ------------------------------------------------------------------ #
    #  Pagination bar
    # ------------------------------------------------------------------ #

    def _build_pagination_bar(self) -> QWidget:
        theme = current_theme()
        bar = QFrame()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"QFrame {{ background: {theme.surface.name(QColor.HexArgb)}; "
            f"border-top: 1px solid {theme.outline.name(QColor.HexArgb)}; }}"
        )

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(theme.grid_padding, 4, theme.grid_padding, 4)
        layout.setSpacing(6)
        layout.addStretch(1)

        self._page_prev_btn = QPushButton(f"{AppIcons.UI_ARROW_LEFT}  Prev")
        self._page_prev_btn.setCursor(Qt.PointingHandCursor)
        self._page_prev_btn.setStyleSheet(ghost_btn_style(theme))
        self._page_prev_btn.clicked.connect(self.prev_page)
        layout.addWidget(self._page_prev_btn)

        self._page_btns_layout = QHBoxLayout()
        self._page_btns_layout.setSpacing(4)
        layout.addLayout(self._page_btns_layout)

        self._page_next_btn = QPushButton(f"Next  {AppIcons.UI_ARROW_RIGHT}")
        self._page_next_btn.setCursor(Qt.PointingHandCursor)
        self._page_next_btn.setStyleSheet(ghost_btn_style(theme))
        self._page_next_btn.clicked.connect(self.next_page)
        layout.addWidget(self._page_next_btn)

        layout.addStretch(1)

        self._page_info_label = QLabel("Page 1 of 1")
        self._page_info_label.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._page_info_label)

        return bar

    def _update_pagination_bar(self) -> None:
        # Gate on browse mode, not widget visibility: window.py configures the
        # browse mode and loads games *before* the window is shown, so a saved
        # "pages" mode must populate the bar even while it is not yet visible.
        if self._browse_mode != "pages":
            return
        theme = current_theme()
        current_page = self.model.page()
        total_pages = self.model.total_pages()
        total = self.model.total_count()
        page_size = self.model.page_size()

        self._page_prev_btn.setEnabled(current_page > 0)
        self._page_next_btn.setEnabled(current_page < total_pages - 1)

        if total:
            start = current_page * page_size + 1
            end = min((current_page + 1) * page_size, total)
            self._page_info_label.setText(f"{start}-{end} of {total}")
        else:
            self._page_info_label.setText("No games")

        while self._page_btns_layout.count():
            item = self._page_btns_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        max_visible = 7
        if total_pages <= max_visible:
            pages_to_show = list(range(total_pages))
        else:
            pages_to_show = {0, total_pages - 1}
            for delta in range(-1, 2):
                p = current_page + delta
                if 0 <= p < total_pages:
                    pages_to_show.add(p)
            for delta in range(-2, 3):
                if len(pages_to_show) >= max_visible:
                    break
                p = current_page + delta
                if 0 <= p < total_pages:
                    pages_to_show.add(p)
            pages_to_show = sorted(pages_to_show)

        last_shown = -2
        for p in pages_to_show:
            if p - last_shown > 1:
                ellipsis = QLabel("...")
                ellipsis.setStyleSheet(
                    f"color: {theme.text_muted.name()}; font-size: 11px; "
                    f"background: transparent; border: none; padding: 0 2px;"
                )
                self._page_btns_layout.addWidget(ellipsis)

            btn = QPushButton(str(p + 1))
            btn.setFixedSize(32, 28)
            btn.setCursor(Qt.PointingHandCursor)
            if p == current_page:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {theme.accent.name()}; "
                    f"color: {theme.bg.name()}; border: none; "
                    f"border-radius: {theme.radius_sm}px; font-weight: 600; "
                    f"font-size: 11px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; "
                    f"color: {theme.text_muted.name()}; border: none; "
                    f"border-radius: {theme.radius_sm}px; font-size: 11px; }}"
                    f"QPushButton:hover {{ background: {theme.surface_alt.name(QColor.HexArgb)}; "
                    f"color: {theme.text.name()}; }}"
                )
            btn.clicked.connect(lambda checked=False, pn=p: self.go_to_page(pn))
            self._page_btns_layout.addWidget(btn)
            last_shown = p
