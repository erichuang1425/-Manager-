"""Redesigned details panel with clear sections and interactive controls."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QScrollArea,
    QFrame, QSizePolicy,
)
from PySide6.QtGui import QColor

from app.models import Game
from app.ui.theme import (
    current_theme, primary_btn_style, secondary_btn_style, ghost_btn_style,
    section_header_style, collapsible_header_style, status_color,
)
from app.ui.icons import AppIcons
from app.ui.typography import get_scale, title_style, caption_style, label_style
from app.ui.widgets.game_grid.display_utils import relative_time
from app.ui.widgets.game_artwork import GameArtwork
from app.ui.widgets.controls import StarRating, StatusChips, TagEditor


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M")


class DetailsPanel(QWidget):
    play_clicked = Signal(str)
    game_changed = Signal(str)
    artwork_capture_requested = Signal(str)
    artwork_paste_requested = Signal(str)
    artwork_choose_requested = Signal(str)
    artwork_remove_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._game: Optional[Game] = None
        self._loading = False
        theme = current_theme()
        scale = get_scale()

        # Scrollable panel
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(theme.spacing_md, theme.spacing_md, theme.spacing_md, theme.spacing_lg)
        layout.setSpacing(theme.spacing_sm)

        # == Title + subtitle ==
        self.title = QLabel("Select a game")
        self.title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {theme.text.name()}; "
            f"background: transparent; border: none;"
        )
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.subtitle = QLabel("")
        self.subtitle.setStyleSheet(
            f"font-size: 12px; color: {theme.text_muted.name()}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self.subtitle)

        self.hint = QLabel("")
        self.hint.setStyleSheet(
            f"color: {theme.accent.name()}; font-size: 12px; font-weight: 500; "
            f"background: transparent; border: none;"
        )
        self.hint.setWordWrap(True)
        self.hint.hide()
        layout.addWidget(self.hint)

        layout.addSpacing(theme.spacing_sm)

        # == Play button (prominent) ==
        self.play_btn = QPushButton(f"{AppIcons.ACT_PLAY}  Play")
        self.play_btn.setStyleSheet(primary_btn_style(theme))
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setEnabled(False)
        self.play_btn.setMinimumHeight(36)
        self.play_btn.clicked.connect(self._emit_play)
        layout.addWidget(self.play_btn)

        layout.addSpacing(theme.spacing_lg)

        # == Section: Card artwork ==
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("CARD ARTWORK", theme))

        artwork_container = QFrame()
        artwork_container.setStyleSheet(
            f"QFrame {{ background: {theme.surface_alt.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_sm}px; border: none; }}"
        )
        artwork_layout = QVBoxLayout(artwork_container)
        artwork_layout.setContentsMargins(
            theme.spacing_sm, theme.spacing_sm, theme.spacing_sm, theme.spacing_sm,
        )
        artwork_layout.setSpacing(theme.spacing_sm)

        self.artwork_preview = GameArtwork(width=184, height=104)
        artwork_layout.addWidget(self.artwork_preview, 0, Qt.AlignHCenter)

        artwork_help = QLabel(
            "Capture opens Windows Snipping Tool. Select the game area and it "
            "will become this card's background."
        )
        artwork_help.setWordWrap(True)
        artwork_help.setStyleSheet(
            f"font-size: 11px; color: {theme.text_muted.name()}; "
            "background: transparent; border: none;"
        )
        artwork_layout.addWidget(artwork_help)

        artwork_primary = QHBoxLayout()
        artwork_primary.setSpacing(theme.spacing_xs)
        self.capture_artwork_btn = QPushButton("Capture")
        self.paste_artwork_btn = QPushButton("Paste")
        self.capture_artwork_btn.setStyleSheet(primary_btn_style(theme))
        self.paste_artwork_btn.setStyleSheet(secondary_btn_style(theme))
        artwork_primary.addWidget(self.capture_artwork_btn, 1)
        artwork_primary.addWidget(self.paste_artwork_btn, 1)
        artwork_layout.addLayout(artwork_primary)

        artwork_secondary = QHBoxLayout()
        artwork_secondary.setSpacing(theme.spacing_xs)
        self.choose_artwork_btn = QPushButton("Choose image")
        self.remove_artwork_btn = QPushButton("Remove")
        self.choose_artwork_btn.setStyleSheet(ghost_btn_style(theme))
        self.remove_artwork_btn.setStyleSheet(ghost_btn_style(theme))
        artwork_secondary.addWidget(self.choose_artwork_btn, 1)
        artwork_secondary.addWidget(self.remove_artwork_btn, 1)
        artwork_layout.addLayout(artwork_secondary)

        for button in (
            self.capture_artwork_btn, self.paste_artwork_btn,
            self.choose_artwork_btn, self.remove_artwork_btn,
        ):
            button.setCursor(Qt.PointingHandCursor)
            button.setEnabled(False)
        self.capture_artwork_btn.setToolTip("Minimize the library and capture a game area")
        self.paste_artwork_btn.setToolTip("Use an image currently on the clipboard")
        self.choose_artwork_btn.setToolTip("Choose a PNG, JPEG, WebP, or BMP image")
        self.remove_artwork_btn.setToolTip("Return to the generated title background")
        self.capture_artwork_btn.clicked.connect(
            lambda: self._emit_artwork_request(self.artwork_capture_requested)
        )
        self.paste_artwork_btn.clicked.connect(
            lambda: self._emit_artwork_request(self.artwork_paste_requested)
        )
        self.choose_artwork_btn.clicked.connect(
            lambda: self._emit_artwork_request(self.artwork_choose_requested)
        )
        self.remove_artwork_btn.clicked.connect(
            lambda: self._emit_artwork_request(self.artwork_remove_requested)
        )
        layout.addWidget(artwork_container)

        layout.addSpacing(theme.spacing_lg)

        # == Section: Status & Rating (styled container) ==
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("STATUS & RATING", theme))

        sr_container = QFrame()
        sr_container.setStyleSheet(
            f"QFrame {{ background: {theme.surface_alt.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_sm}px; border: none; }}"
        )
        sr_inner = QVBoxLayout(sr_container)
        sr_inner.setContentsMargins(theme.spacing_sm, theme.spacing_sm, theme.spacing_sm, theme.spacing_sm)
        sr_inner.setSpacing(theme.spacing_sm)

        # Interactive status chips + star rating (replaces plain combo boxes)
        self.status = StatusChips()
        self.status.setEnabled(False)
        self.status.changed.connect(self._on_changed)
        sr_inner.addWidget(self.status)

        self.rating = StarRating()
        self.rating.setEnabled(False)
        self.rating.changed.connect(self._on_changed)
        sr_inner.addWidget(self.rating)

        layout.addWidget(sr_container)

        # == Section: Tags ==
        layout.addSpacing(theme.spacing_md)
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("TAGS", theme))
        self.tags = TagEditor()
        self.tags.setEnabled(False)
        self.tags.changed.connect(self._on_changed)
        layout.addWidget(self.tags)

        # == Section: Notes ==
        layout.addSpacing(theme.spacing_md)
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("NOTES", theme))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Short review or notes\u2026")
        self.notes.setEnabled(False)
        self.notes.setMinimumHeight(100)
        self.notes.setMaximumHeight(160)
        self.notes.textChanged.connect(self._on_changed)
        layout.addWidget(self.notes)

        # == Section: Source ==
        layout.addSpacing(theme.spacing_md)
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("SOURCE", theme))

        src_row = QHBoxLayout()
        src_row.setSpacing(theme.spacing_xs)
        self.source_url = QLineEdit()
        self.source_url.setPlaceholderText("Source page URL")
        self.source_url.setEnabled(False)
        self.source_url.textChanged.connect(self._on_changed)
        self.open_source_btn = QPushButton("Open")
        self.open_source_btn.setStyleSheet(ghost_btn_style(theme))
        self.open_source_btn.setEnabled(False)
        self.open_source_btn.clicked.connect(self._open_source)
        src_row.addWidget(self.source_url, 1)
        src_row.addWidget(self.open_source_btn)
        layout.addLayout(src_row)

        ver_row = QHBoxLayout()
        ver_row.setSpacing(theme.spacing_sm)
        iv_lbl = QLabel("Installed")
        iv_lbl.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        self.installed_ver = QLineEdit()
        self.installed_ver.setPlaceholderText("e.g., 0.9.2")
        self.installed_ver.setEnabled(False)
        self.installed_ver.setMaximumWidth(100)
        self.installed_ver.textChanged.connect(self._on_changed)
        ver_row.addWidget(iv_lbl)
        ver_row.addWidget(self.installed_ver)

        self.source_ver = QLabel("Source: \u2014")
        self.source_ver.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        ver_row.addWidget(self.source_ver, 1)
        layout.addLayout(ver_row)

        # == Section: Archives ==
        layout.addSpacing(theme.spacing_md)
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("ARCHIVES", theme))

        arch_row = QHBoxLayout()
        arch_row.setSpacing(theme.spacing_xs)
        af_lbl = QLabel("Folder")
        af_lbl.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        self.archive_folder = QLineEdit()
        self.archive_folder.setPlaceholderText("Archive folder path")
        self.archive_folder.setEnabled(False)
        self.archive_folder.textChanged.connect(self._on_changed)
        self.pick_archive_folder = QPushButton(AppIcons.ACT_FOLDER)
        self.pick_archive_folder.setStyleSheet(ghost_btn_style(theme))
        self.pick_archive_folder.setFixedSize(28, 28)
        self.pick_archive_folder.setEnabled(False)
        self.pick_archive_folder.clicked.connect(self._pick_archive_folder)
        self.open_archive_folder = QPushButton("Open")
        self.open_archive_folder.setStyleSheet(ghost_btn_style(theme))
        self.open_archive_folder.setEnabled(False)
        self.open_archive_folder.clicked.connect(self._open_archive_folder)
        arch_row.addWidget(af_lbl)
        arch_row.addWidget(self.archive_folder, 1)
        arch_row.addWidget(self.pick_archive_folder)
        arch_row.addWidget(self.open_archive_folder)
        layout.addLayout(arch_row)

        comp_row = QHBoxLayout()
        comp_row.setSpacing(theme.spacing_xs)
        ca_lbl = QLabel("Archive")
        ca_lbl.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 11px; "
            f"background: transparent; border: none;"
        )
        self.compressed_path = QLineEdit()
        self.compressed_path.setPlaceholderText(".zip / .rar / .7z")
        self.compressed_path.setEnabled(False)
        self.compressed_path.textChanged.connect(self._on_changed)
        self.pick_compressed = QPushButton(AppIcons.ACT_FOLDER)
        self.pick_compressed.setStyleSheet(ghost_btn_style(theme))
        self.pick_compressed.setFixedSize(28, 28)
        self.pick_compressed.setEnabled(False)
        self.pick_compressed.clicked.connect(self._pick_compressed)
        self.open_compressed = QPushButton("Open")
        self.open_compressed.setStyleSheet(ghost_btn_style(theme))
        self.open_compressed.setEnabled(False)
        self.open_compressed.clicked.connect(self._open_compressed)
        comp_row.addWidget(ca_lbl)
        comp_row.addWidget(self.compressed_path, 1)
        comp_row.addWidget(self.pick_compressed)
        comp_row.addWidget(self.open_compressed)
        layout.addLayout(comp_row)

        # == Section: Info ==
        layout.addSpacing(theme.spacing_md)
        layout.addWidget(self._section_divider(theme))
        layout.addWidget(self._section_header("INFO", theme))
        self.launcher_info = QLabel("")
        self.launcher_info.setStyleSheet(
            f"font-size: 11px; color: {theme.text_muted.name()}; "
            f"background: transparent; border: none; line-height: 1.5;"
        )
        self.launcher_info.setWordWrap(True)
        layout.addWidget(self.launcher_info)

        self.last_played = QLabel("")
        self.last_played.setStyleSheet(
            f"font-size: 11px; color: {theme.text_muted.name()}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self.last_played)

        layout.addStretch(1)

        # Register section widgets for collapsible toggling
        # Each layout/widget added after a section header belongs to that section
        self._register_section_widget("STATUS & RATING", sr_container)
        self._register_section_widget("CARD ARTWORK", artwork_container)
        self._register_section_widget("TAGS", self.tags)
        self._register_section_widget("NOTES", self.notes)
        self._register_section_widget("SOURCE", self.source_url)
        self._register_section_widget("SOURCE", self.open_source_btn)
        self._register_section_widget("SOURCE", self.installed_ver)
        self._register_section_widget("SOURCE", self.source_ver)
        self._register_section_widget("ARCHIVES", self.archive_folder)
        self._register_section_widget("ARCHIVES", self.pick_archive_folder)
        self._register_section_widget("ARCHIVES", self.open_archive_folder)
        self._register_section_widget("ARCHIVES", self.compressed_path)
        self._register_section_widget("ARCHIVES", self.pick_compressed)
        self._register_section_widget("ARCHIVES", self.open_compressed)
        self._register_section_widget("INFO", self.launcher_info)
        self._register_section_widget("INFO", self.last_played)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _section_divider(self, theme) -> QFrame:
        """Create a subtle horizontal divider between sections."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setFixedHeight(1)
        line.setStyleSheet(
            f"background: {theme.outline.name(QColor.HexArgb)}; border: none;"
        )
        return line

    def _section_header(self, text: str, theme) -> QPushButton:
        """Create a collapsible section header."""
        btn = QPushButton(f"\u25BE  {text}")
        btn.setStyleSheet(collapsible_header_style(theme))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        btn._section_text = text
        btn._collapsed = False
        btn._section_widgets = []
        btn.clicked.connect(lambda: self._toggle_section(btn))
        # Track sections for toggling
        if not hasattr(self, '_section_btns'):
            self._section_btns = []
        self._section_btns.append(btn)
        return btn

    def _toggle_section(self, btn: QPushButton) -> None:
        """Toggle visibility of section content widgets."""
        btn._collapsed = not btn._collapsed
        icon = "\u25B8" if btn._collapsed else "\u25BE"
        btn.setText(f"{icon}  {btn._section_text}")
        for w in btn._section_widgets:
            w.setVisible(not btn._collapsed)

    def _register_section_widget(self, section_text: str, widget) -> None:
        """Register a widget to be toggled by a section header."""
        if not hasattr(self, '_section_btns'):
            return
        for btn in self._section_btns:
            if btn._section_text == section_text:
                btn._section_widgets.append(widget)
                return

    # ---- public API ----

    def show_game(self, game: Optional[Game]) -> None:
        self._loading = True
        self._game = game

        if game is None:
            self.title.setText("Select a game")
            self.subtitle.setText("")
            self.play_btn.setEnabled(False)
            self.artwork_preview.set_game(None)
            for w in (self.status, self.rating, self.tags, self.notes,
                      self.source_url, self.installed_ver,
                      self.archive_folder, self.compressed_path,
                      self.pick_archive_folder, self.pick_compressed,
                      self.open_archive_folder, self.open_compressed,
                      self.open_source_btn, self.capture_artwork_btn,
                      self.paste_artwork_btn, self.choose_artwork_btn,
                      self.remove_artwork_btn):
                w.setEnabled(False)
            self.launcher_info.setText("")
            self.last_played.setText("")
            self.source_ver.setText("Source: \u2014")
            self._loading = False
            return

        self.title.setText(game.title)
        # Subtitle: type + confidence + tags summary
        parts = []
        if game.shortcut_type:
            parts.append(game.shortcut_type.upper())
        if game.confidence:
            parts.append(f"{game.confidence} confidence")
        self.subtitle.setText("  \u00B7  ".join(parts))

        self.play_btn.setEnabled(True)
        self.artwork_preview.set_game(game)
        self.capture_artwork_btn.setEnabled(True)
        self.paste_artwork_btn.setEnabled(True)
        self.choose_artwork_btn.setEnabled(True)
        self.remove_artwork_btn.setEnabled(bool(game.card_artwork_path))

        self.status.setEnabled(True)
        self.status.set_status(game.status)

        self.rating.setEnabled(True)
        self.rating.set_rating(game.rating)

        self.tags.setEnabled(True)
        self.tags.set_tags(game.tags)

        self.notes.setEnabled(True)
        self.notes.setPlainText(game.notes)

        self.source_url.setEnabled(True)
        self.source_url.setText(game.source_url)
        self.open_source_btn.setEnabled(bool(game.source_url))

        self.installed_ver.setEnabled(True)
        self.installed_ver.setText(game.installed_version_raw)

        src_raw = game.source_version_raw or "\u2014"
        checked = _fmt_dt(game.source_checked_at)
        self.source_ver.setText(f"Source: {src_raw}  (checked {checked})")

        for w in (self.archive_folder, self.pick_archive_folder, self.open_archive_folder,
                  self.compressed_path, self.pick_compressed, self.open_compressed):
            w.setEnabled(True)

        self.archive_folder.setText(game.archive_folder_path)
        self.compressed_path.setText(game.compressed_archive_path)

        target = game.backup_target_path or "\u2014"
        self.launcher_info.setText(
            f"Shortcut: {game.shortcut_type.upper()}  \u00B7  Confidence: {game.confidence}\n"
            f"Path: {game.shortcut_path}\n"
            f"Target: {target}"
        )
        lp = relative_time(game.last_played)
        self.last_played.setText(f"Last played: {lp if lp else 'Never'}")

        self._loading = False
        self.show_hint("")

    def apply_edits_to_game(self) -> None:
        if self._game is None:
            return
        self._game.status = self.status.status()
        self._game.rating = self.rating.rating()
        self._game.tags = self.tags.tags()
        self._game.notes = self.notes.toPlainText().strip()
        self._game.source_url = self.source_url.text().strip()
        self._game.installed_version_raw = self.installed_ver.text().strip()
        self._game.archive_folder_path = self.archive_folder.text().strip()
        self._game.compressed_archive_path = self.compressed_path.text().strip()

    def show_hint(self, text: str) -> None:
        if text:
            self.hint.setText(text)
            self.hint.show()
        else:
            self.hint.hide()

    # ---- private ----

    def _emit_play(self) -> None:
        if self._game is not None:
            self.play_clicked.emit(self._game.game_id)

    def _emit_artwork_request(self, signal: Signal) -> None:
        if self._game is not None:
            signal.emit(self._game.game_id)

    def _on_changed(self) -> None:
        if self._loading:
            return
        if self._game is not None:
            self.game_changed.emit(self._game.game_id)

    def _open_source(self) -> None:
        if not self._game or not self._game.source_url:
            return
        import webbrowser
        webbrowser.open(self._game.source_url)

    def _pick_archive_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select archive folder")
        if folder:
            self.archive_folder.setText(folder)
            self._on_changed()

    def _open_archive_folder(self) -> None:
        import os
        if self.archive_folder.text().strip():
            try:
                os.startfile(self.archive_folder.text().strip())
            except Exception:
                pass

    def _pick_compressed(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select compressed archive", "",
            "Archives (*.zip *.rar *.7z *.7zip *.tar *.gz);;All files (*)",
        )
        if path:
            self.compressed_path.setText(path)
            self._on_changed()

    def _open_compressed(self) -> None:
        import os
        if self.compressed_path.text().strip():
            try:
                os.startfile(self.compressed_path.text().strip())
            except Exception:
                pass
