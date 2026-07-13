"""Full-page application settings."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QCheckBox, QGroupBox, QFormLayout, QSpinBox, QScrollArea, QFrame,
)

from app.ui.theme import THEMES, FONTS, primary_btn_style, secondary_btn_style


class SettingsPage(QWidget):
    """Persistent settings view that replaces the small modal preferences box."""

    apply_requested = Signal(dict)
    choose_root_requested = Signal()
    scan_requested = Signal()
    add_shortcuts_requested = Signal()
    import_library_requested = Signal()
    export_library_requested = Signal()
    open_data_requested = Signal()
    theme_editor_requested = Signal()
    layout_editor_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from app.ui.theme import current_theme
        theme = current_theme()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(theme.spacing_sm, theme.spacing_sm, theme.spacing_xl, theme.spacing_xl)
        layout.setSpacing(theme.spacing_lg)

        title = QLabel("Settings")
        title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {theme.text.name()};")
        subtitle = QLabel("Library locations, appearance, browsing, behavior, and data tools are all managed here.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {theme.text_muted.name()};")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        library = QGroupBox("Library and imports")
        library_layout = QVBoxLayout(library)
        self.root_label = QLabel("No shortcut folder selected")
        self.root_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.root_label.setWordWrap(True)
        library_layout.addWidget(QLabel("Shortcut folder"))
        library_layout.addWidget(self.root_label)
        root_buttons = QHBoxLayout()
        for text, signal in [
            ("Change folder…", self.choose_root_requested),
            ("Scan now", self.scan_requested),
            ("Add shortcut files…", self.add_shortcuts_requested),
        ]:
            button = QPushButton(text)
            button.setStyleSheet(secondary_btn_style(theme))
            button.clicked.connect(signal.emit)
            root_buttons.addWidget(button)
        root_buttons.addStretch(1)
        library_layout.addLayout(root_buttons)
        layout.addWidget(library)

        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        self.theme_combo = QComboBox()
        self._theme_keys = list(THEMES.keys())
        self.theme_combo.addItems([THEMES[key].name for key in self._theme_keys])
        self.font_combo = QComboBox()
        self.font_combo.addItems(list(FONTS.keys()))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Small", "Default", "Large"])
        appearance_form.addRow("Theme", self.theme_combo)
        appearance_form.addRow("Font", self.font_combo)
        appearance_form.addRow("Text size", self.scale_combo)
        appearance_tools = QHBoxLayout()
        theme_editor = QPushButton("Open theme editor…")
        theme_editor.clicked.connect(self.theme_editor_requested.emit)
        layout_editor = QPushButton("Customize layout…")
        layout_editor.clicked.connect(self.layout_editor_requested.emit)
        appearance_tools.addWidget(theme_editor)
        appearance_tools.addWidget(layout_editor)
        appearance_tools.addStretch(1)
        appearance_form.addRow("Advanced", appearance_tools)
        layout.addWidget(appearance)

        browsing = QGroupBox("Browsing and behavior")
        browsing_form = QFormLayout(browsing)
        self.view_combo = QComboBox()
        self.view_combo.addItem("Grid", "comfortable")
        self.view_combo.addItem("List", "compact")
        self.browse_combo = QComboBox()
        self.browse_combo.addItem("Continuous scrolling", "scroll")
        self.browse_combo.addItem("Pages", "pages")
        self.page_size = QSpinBox()
        self.page_size.setRange(6, 120)
        self.page_size.setSingleStep(6)
        self.details_launch = QCheckBox("Show the details panel when the app opens")
        self.details_select = QCheckBox("Open details after selecting a game")
        self.details_visible = QCheckBox("Keep the details panel visible")
        self.focus_mode = QCheckBox("Start in distraction-free focus mode")
        browsing_form.addRow("Default library view", self.view_combo)
        browsing_form.addRow("Browse mode", self.browse_combo)
        browsing_form.addRow("Games per page", self.page_size)
        browsing_form.addRow("", self.details_launch)
        browsing_form.addRow("", self.details_select)
        browsing_form.addRow("", self.details_visible)
        browsing_form.addRow("", self.focus_mode)
        layout.addWidget(browsing)

        data = QGroupBox("Library data")
        data_layout = QHBoxLayout(data)
        for text, signal in [
            ("Import backup…", self.import_library_requested),
            ("Export library…", self.export_library_requested),
            ("Open data folder", self.open_data_requested),
        ]:
            button = QPushButton(text)
            button.setStyleSheet(secondary_btn_style(theme))
            button.clicked.connect(signal.emit)
            data_layout.addWidget(button)
        data_layout.addStretch(1)
        layout.addWidget(data)

        actions = QHBoxLayout()
        self.status_label = QLabel("Settings are saved locally on this PC.")
        self.status_label.setStyleSheet(f"color: {theme.text_muted.name()};")
        actions.addWidget(self.status_label, 1)
        reset_button = QPushButton("Reset defaults")
        reset_button.clicked.connect(self.reset_defaults)
        save_button = QPushButton("Save settings")
        save_button.setStyleSheet(primary_btn_style(theme))
        save_button.clicked.connect(lambda: self.apply_requested.emit(self.values()))
        actions.addWidget(reset_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        scroll.setWidget(body)

    def set_values(self, values: dict) -> None:
        self.root_label.setText(values.get("root_folder") or "No shortcut folder selected")
        theme_key = values.get("theme", "dark")
        if theme_key in self._theme_keys:
            self.theme_combo.setCurrentIndex(self._theme_keys.index(theme_key))
        self.font_combo.setCurrentText(values.get("font_family", "Segoe UI"))
        self.scale_combo.setCurrentText(values.get("font_scale", "default").title())
        self._set_combo_data(self.view_combo, values.get("view_mode", "comfortable"))
        self._set_combo_data(self.browse_combo, values.get("browse_mode", "scroll"))
        self.page_size.setValue(int(values.get("page_size", 24)))
        self.details_launch.setChecked(bool(values.get("details_on_launch", False)))
        self.details_select.setChecked(bool(values.get("details_on_selection", True)))
        self.details_visible.setChecked(bool(values.get("details_visible", False)))
        self.focus_mode.setChecked(bool(values.get("focus_mode", False)))

    def values(self) -> dict:
        return {
            "theme": self._theme_keys[self.theme_combo.currentIndex()],
            "font_family": self.font_combo.currentText(),
            "font_scale": self.scale_combo.currentText().lower(),
            "view_mode": self.view_combo.currentData(),
            "browse_mode": self.browse_combo.currentData(),
            "page_size": self.page_size.value(),
            "details_on_launch": self.details_launch.isChecked(),
            "details_on_selection": self.details_select.isChecked(),
            "details_visible": self.details_visible.isChecked(),
            "focus_mode": self.focus_mode.isChecked(),
        }

    def reset_defaults(self) -> None:
        self.set_values({})
        self.status_label.setText("Defaults selected. Choose Save settings to apply them.")

    def show_saved(self) -> None:
        self.status_label.setText("Settings saved.")

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
