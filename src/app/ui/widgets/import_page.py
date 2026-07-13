"""First-class import hub for every supported library entry path."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QScrollArea,
)
from PySide6.QtGui import QColor

from app.ui.icons import AppIcons
from app.ui.theme import current_theme, primary_btn_style, secondary_btn_style


class ImportPage(QWidget):
    """A visible, self-explanatory home for adding games and metadata."""

    add_shortcuts_requested = Signal()
    scan_folder_requested = Signal()
    import_library_requested = Signal()
    bulk_sources_requested = Signal()
    import_archives_requested = Signal()
    shortcut_maker_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        theme = current_theme()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(theme.spacing_sm, theme.spacing_sm, theme.spacing_sm, theme.spacing_xl)
        layout.setSpacing(theme.spacing_lg)

        title = QLabel("Add games")
        title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {theme.text.name()};")
        subtitle = QLabel(
            "Choose the source that matches what you already have. Shortcut files add games immediately; "
            "folder scans keep a larger shortcut library in sync."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"font-size: 13px; color: {theme.text_muted.name()};")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        root_card = QFrame()
        root_card.setStyleSheet(
            f"QFrame {{ background: {theme.surface.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_lg}px; }}"
            "QFrame QLabel { background: transparent; border: none; }"
        )
        root_row = QHBoxLayout(root_card)
        root_row.setContentsMargins(theme.spacing_lg, theme.spacing_md, theme.spacing_lg, theme.spacing_md)
        root_copy = QVBoxLayout()
        root_title = QLabel("Shortcut folder")
        root_title.setStyleSheet(f"font-weight: 700; color: {theme.text.name()};")
        self.root_label = QLabel("No folder selected")
        self.root_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.root_label.setWordWrap(True)
        self.root_label.setStyleSheet(f"color: {theme.text_muted.name()};")
        root_copy.addWidget(root_title)
        root_copy.addWidget(self.root_label)
        root_row.addLayout(root_copy, 1)
        scan_now = QPushButton(f"{AppIcons.ACT_SCAN}  Choose folder and scan")
        scan_now.setStyleSheet(primary_btn_style(theme))
        scan_now.clicked.connect(self.scan_folder_requested.emit)
        root_row.addWidget(scan_now)
        layout.addWidget(root_card)

        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.spacing_md)
        grid.setVerticalSpacing(theme.spacing_md)
        cards = [
            (
                "Shortcut files", "Add one or many .lnk, .url, or .html files without changing your folder structure.",
                f"{AppIcons.ACT_ADD}  Choose shortcut files", self.add_shortcuts_requested,
            ),
            (
                "Library backup", "Restore or merge a Game Library Manager JSON/CSV export.",
                f"{AppIcons.ACT_IMPORT}  Import JSON or CSV", self.import_library_requested,
            ),
            (
                "Source URLs", "Match a pasted list of source pages to games already in your library.",
                f"{AppIcons.ACT_IMPORT}  Match source URLs", self.bulk_sources_requested,
            ),
            (
                "Game archives", "Scan ZIP, RAR, and other archives, extract selected games, and create shortcuts.",
                f"{AppIcons.ACT_IMPORT}  Import archives", self.import_archives_requested,
            ),
            (
                "Create shortcuts", "Use the bundled shortcut maker when your games do not have launch shortcuts yet.",
                f"{AppIcons.ACT_ADD}  Open shortcut maker", self.shortcut_maker_requested,
            ),
        ]
        for index, (heading, description, button_text, signal) in enumerate(cards):
            grid.addWidget(self._card(heading, description, button_text, signal), index // 2, index % 2)
        layout.addLayout(grid)

        self.result_label = QLabel("Ready to import.")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet(f"color: {theme.text_muted.name()}; padding: 4px;")
        layout.addWidget(self.result_label)
        layout.addStretch(1)
        scroll.setWidget(body)

    def _card(self, heading: str, description: str, button_text: str, signal) -> QFrame:
        theme = current_theme()
        frame = QFrame()
        frame.setMinimumHeight(160)
        frame.setStyleSheet(
            f"QFrame {{ background: {theme.card.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.card_border.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_lg}px; }}"
            "QFrame QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(theme.spacing_lg, theme.spacing_lg, theme.spacing_lg, theme.spacing_lg)
        heading_label = QLabel(heading)
        heading_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.text.name()};")
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"font-size: 12px; color: {theme.text_muted.name()};")
        button = QPushButton(button_text)
        button.setStyleSheet(secondary_btn_style(theme))
        button.clicked.connect(signal.emit)
        layout.addWidget(heading_label)
        layout.addWidget(desc_label, 1)
        layout.addWidget(button, 0, Qt.AlignLeft)
        return frame

    def set_root_folder(self, folder: str) -> None:
        self.root_label.setText(folder or "No shortcut folder selected yet")

    def set_result(self, message: str, success: bool = True) -> None:
        theme = current_theme()
        color = theme.accent if success else theme.warning
        self.result_label.setStyleSheet(f"color: {color.name()}; padding: 4px; font-weight: 600;")
        self.result_label.setText(message)
