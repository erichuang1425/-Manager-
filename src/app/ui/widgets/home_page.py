"""Home landing page: at-a-glance library overview and quick jumps."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea,
)
from PySide6.QtGui import QColor

from app.models import Game
from app.ui.icons import AppIcons
from app.ui.theme import (
    current_theme, primary_btn_style, secondary_btn_style, ghost_btn_style,
)
from app.ui.widgets.game_artwork import GameArtwork


class HomePage(QWidget):
    """Landing page shown on launch.

    Surfaces a quick library summary, continue-playing / recently-added tiles,
    and Updates / Health jump cards. The whole body is rebuilt on `refresh` so
    the page always mirrors the live library without stale widgets lingering.
    """

    # Emits a game_id; wired to the same launch path the grid uses.
    game_play_requested = Signal(str)
    game_reveal_requested = Signal(str)
    pick_requested = Signal()
    # Emits a sidebar nav key (e.g. "import", "updates"); wired to set_selected.
    navigate_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        theme = current_theme()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self._scroll)

        body = QWidget()
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(
            theme.spacing_sm, theme.spacing_sm, theme.spacing_xl, theme.spacing_xl
        )
        self._body.setSpacing(theme.section_gap)
        self._scroll.setWidget(body)

        self._games: List[Game] = []
        self._columns = 3
        self._resize_refresh_pending = False
        self._fingerprint = None
        self.refresh([])

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #
    def refresh(self, games) -> None:
        """Rebuild the page body from the current library."""
        incoming = list(games or [])
        fingerprint = (
            self._columns,
            tuple(self._game_signature(game) for game in incoming),
        )
        if fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        self._games = incoming
        scroll_position = self._scroll.verticalScrollBar().value()
        self.setUpdatesEnabled(False)
        self._clear_layout(self._body)
        theme = current_theme()

        self._body.addWidget(self._build_header(theme))

        if not self._games:
            self._body.addWidget(self._build_empty_state(theme), 1)
            self._body.addStretch(1)
            self.setUpdatesEnabled(True)
            return

        continuing = sorted(
            [
                g for g in self._games
                if getattr(g, "last_played", None)
                and getattr(getattr(g, "status", ""), "value", getattr(g, "status", ""))
                not in {"finished", "dropped"}
            ],
            key=lambda g: (
                getattr(getattr(g, "status", ""), "value", getattr(g, "status", ""))
                == "playing",
                g.last_played,
            ),
            reverse=True,
        )[:6]
        if continuing:
            self._body.addWidget(self._section_label("Continue playing", theme))
            self._body.addWidget(self._tile_grid(
                [self._continue_tile(g, theme) for g in continuing]
            ))

        # No creation timestamp exists on Game; the repository appends new games,
        # so the tail of the list is the most-recently-added. Reverse it.
        recent = list(reversed(self._games))[:6]
        if recent:
            self._body.addWidget(self._section_label("Recently added", theme))
            self._body.addWidget(self._tile_grid(
                [self._recent_tile(g, theme) for g in recent]
            ))

        self._body.addWidget(self._section_label("At a glance", theme))
        self._body.addWidget(self._summary_row(theme))
        self._body.addStretch(1)
        self.setUpdatesEnabled(True)
        QTimer.singleShot(
            0,
            lambda value=scroll_position: self._scroll.verticalScrollBar().setValue(value),
        )

    # ------------------------------------------------------------------ #
    #  Builders
    # ------------------------------------------------------------------ #
    def _build_header(self, theme) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.spacing_lg)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(theme.spacing_xs)
        title = QLabel(f"{AppIcons.NAV_LIBRARY}  Game Library")
        title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {theme.text.name()};")
        playing = sum(1 for g in self._games if getattr(g, "status", "") == "playing")
        total = len(self._games)
        if total:
            stats = f"{total} games in your library · {playing} currently playing"
        else:
            stats = "No games yet"
        subtitle = QLabel(stats)
        subtitle.setStyleSheet(f"font-size: 13px; color: {theme.text_muted.name()};")
        col.addWidget(title)
        col.addWidget(subtitle)
        row.addLayout(col, 1)

        pick_btn = QPushButton(f"{AppIcons.UI_DICE}  Pick for me")
        pick_btn.setMinimumHeight(40)
        pick_btn.setEnabled(bool(self._games))
        pick_btn.setStyleSheet(primary_btn_style(theme))
        pick_btn.setCursor(Qt.PointingHandCursor)
        pick_btn.setToolTip("Choose a playable game from your library (Ctrl+P)")
        pick_btn.clicked.connect(lambda _=False: self.pick_requested.emit())
        row.addWidget(pick_btn, 0, Qt.AlignVCenter)
        return wrap

    def _build_empty_state(self, theme) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {theme.card.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.card_border.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_lg}px; }}"
            "QFrame QLabel { background: transparent; border: none; }"
        )
        col = QVBoxLayout(frame)
        col.setContentsMargins(theme.spacing_xl, theme.spacing_xl, theme.spacing_xl, theme.spacing_xl)
        col.setSpacing(theme.spacing_md)
        col.setAlignment(Qt.AlignCenter)
        headline = QLabel("Your library is empty")
        headline.setAlignment(Qt.AlignCenter)
        headline.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {theme.text.name()};")
        explainer = QLabel(
            "Add shortcut files, scan a folder, or import a backup to start "
            "building your library."
        )
        explainer.setWordWrap(True)
        explainer.setAlignment(Qt.AlignCenter)
        explainer.setStyleSheet(f"font-size: 13px; color: {theme.text_muted.name()};")
        add_btn = QPushButton(f"{AppIcons.ACT_ADD}  Add Games")
        add_btn.setStyleSheet(primary_btn_style(theme))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(lambda: self.navigate_requested.emit("import"))
        col.addWidget(headline)
        col.addWidget(explainer)
        col.addWidget(add_btn, 0, Qt.AlignCenter)
        return frame

    def _section_label(self, text: str, theme) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {theme.text.name()}; "
            f"background: transparent; border: none;"
        )
        return lbl

    def _tile_grid(self, tiles: List[QWidget]) -> QWidget:
        theme = current_theme()
        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(theme.spacing_md)
        grid.setVerticalSpacing(theme.spacing_md)
        for index, tile in enumerate(tiles):
            grid.addWidget(tile, index // self._columns, index % self._columns)
        for c in range(self._columns):
            grid.setColumnStretch(c, 1)
        return wrap

    def _tile_frame(self, theme) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setMinimumHeight(112)
        frame.setStyleSheet(
            f"QFrame {{ background: {theme.card.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.card_border.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_lg}px; }}"
            "QFrame QLabel { background: transparent; border: none; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(theme.spacing_md, theme.spacing_md, theme.spacing_lg, theme.spacing_md)
        row.setSpacing(theme.spacing_md)
        col = QVBoxLayout()
        row.addLayout(col, 1)
        col.setSpacing(theme.spacing_sm)
        return frame, col

    def _continue_tile(self, game: Game, theme) -> QFrame:
        frame, col = self._tile_frame(theme)
        frame.layout().insertWidget(0, GameArtwork(game, width=82, height=82))
        title = QLabel(game.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {theme.text.name()};")
        play = QPushButton(f"{AppIcons.ACT_PLAY}  Play")
        play.setStyleSheet(primary_btn_style(theme))
        play.setCursor(Qt.PointingHandCursor)
        gid = game.game_id
        play.clicked.connect(lambda _=False, g=gid: self.game_play_requested.emit(g))
        col.addWidget(title, 1)
        col.addWidget(play, 0, Qt.AlignLeft)
        return frame

    def _recent_tile(self, game: Game, theme) -> QFrame:
        frame, col = self._tile_frame(theme)
        frame.layout().insertWidget(0, GameArtwork(game, width=82, height=82))
        title = QLabel(game.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {theme.text.name()};")
        open_btn = QPushButton("Open in library")
        open_btn.setStyleSheet(ghost_btn_style(theme))
        open_btn.setCursor(Qt.PointingHandCursor)
        gid = game.game_id
        open_btn.clicked.connect(lambda _=False, g=gid: self.game_reveal_requested.emit(g))
        col.addWidget(title, 1)
        col.addWidget(open_btn, 0, Qt.AlignLeft)
        return frame

    def _summary_row(self, theme) -> QWidget:
        wrap = QWidget()
        row = QVBoxLayout(wrap) if self._columns == 1 else QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.spacing_md)

        update_games = [
            g for g in self._games
            if getattr(g, "source_version_raw", "")
            and getattr(g, "installed_version_raw", "")
            and g.source_version_raw != g.installed_version_raw
        ]
        if update_games:
            update_body = f"{len(update_games)} updates available to review."
        else:
            update_body = "No tracked updates available right now."
        row.addWidget(self._summary_card(
            "Updates", AppIcons.NAV_UPDATES, update_body, "View updates", "updates", theme
        ), 1)

        missing_shortcuts = sum(1 for g in self._games if not getattr(g, "shortcut_path", ""))
        missing_sources = sum(1 for g in self._games if not getattr(g, "source_url", ""))
        issues = missing_shortcuts + missing_sources
        if issues:
            health_body = (
                f"{issues} items need attention "
                f"({missing_shortcuts} missing shortcuts, {missing_sources} missing sources)."
            )
        else:
            health_body = f"All {len(self._games)} games look healthy."
        row.addWidget(self._summary_card(
            "Health", AppIcons.NAV_HEALTH, health_body, "View health", "health", theme
        ), 1)
        return wrap

    def _summary_card(
        self, title: str, icon: str, body_text: str,
        button_text: str, nav_key: str, theme,
    ) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(118)
        frame.setStyleSheet(
            f"QFrame {{ background: {theme.card.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.card_border.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_lg}px; }}"
            "QFrame QLabel { background: transparent; border: none; }"
        )
        col = QVBoxLayout(frame)
        col.setContentsMargins(theme.spacing_lg, theme.spacing_md, theme.spacing_lg, theme.spacing_md)
        col.setSpacing(theme.spacing_xs)
        header = QLabel(f"{icon}  {title}")
        header.setStyleSheet(
            f"font-size: 12px; font-weight: 700; letter-spacing: 1px; "
            f"color: {theme.text.name()}; text-transform: uppercase;"
        )
        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setStyleSheet(f"font-size: 13px; color: {theme.text_muted.name()}; line-height: 130%;")
        btn = QPushButton(button_text)
        btn.setStyleSheet(secondary_btn_style(theme))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, k=nav_key: self.navigate_requested.emit(k))
        col.addWidget(header)
        col.addWidget(body, 1)
        col.addWidget(btn, 0, Qt.AlignLeft)
        return frame

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        width = self._scroll.viewport().width()
        columns = 1 if width < 560 else (2 if width < 900 else 3)
        if columns == self._columns:
            return
        self._columns = columns
        if self._resize_refresh_pending:
            return
        self._resize_refresh_pending = True
        QTimer.singleShot(0, self._refresh_for_width)

    def _refresh_for_width(self) -> None:
        self._resize_refresh_pending = False
        self.refresh(self._games)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    HomePage._clear_layout(sub)

    @staticmethod
    def _game_signature(game: Game) -> tuple:
        """Fields that materially affect Home, used to skip hidden rebuilds."""
        status = getattr(game.status, "value", game.status)
        last_played = game.last_played.isoformat() if game.last_played else ""
        return (
            game.game_id,
            game.title,
            status,
            game.rating,
            tuple(game.tags or ()),
            last_played,
            game.launch_count,
            game.shortcut_path,
            game.backup_target_path,
            game.executable_path,
            game.card_artwork_path,
            game.installed_version_raw,
            game.source_version_raw,
            game.source_url,
        )
