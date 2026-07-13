"""Dialog management mixin for MainWindow."""
from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.theme import apply_theme, ThemeSpec, _c, THEMES
from app.ui.dialogs import PreferencesDialog, ThemeEditorDialog, LayoutCustomizationDialog, LayoutConfig
from app.ui.dialogs.bulk_source_import import BulkSourceImportDialog
from app.ui.dialogs.bulk_archive_import_dialog import BulkArchiveImportDialog
from app.ui.widgets import show_success, show_error

if TYPE_CHECKING:
    from .window import MainWindow


class DialogMixin:
    """Mixin providing dialog management for MainWindow."""

    def _toggle_details_panel(self: "MainWindow") -> None:
        desired = self.details_toggle.isChecked()
        if self._focus_mode and desired:
            # auto-exit focus to honor user intent
            self._focus_mode = False
            self.focus_btn.setChecked(False)
            self._settings["focus_mode"] = False
        if not desired:
            self._user_hid_details = True
        else:
            self._user_hid_details = False
        self._pulse_widget(self.details_toggle)
        self._details_visible = desired
        self._settings["details_visible"] = self._details_visible
        self._persist_settings()
        self._apply_details_visibility(animate=True)

    def _open_preferences(self: "MainWindow") -> None:
        """Navigate to the full settings page."""
        if hasattr(self, "settings_page"):
            self.settings_page.set_values(self._settings_snapshot())
            self.sidebar.set_selected("settings")

    def _open_theme_editor(self: "MainWindow") -> None:
        """Open the theme editor dialog."""
        dlg = ThemeEditorDialog(self, current_theme=self._theme)
        dlg.theme_changed.connect(self._apply_custom_theme)
        dlg.exec()

    def _restore_custom_theme(self: "MainWindow") -> None:
        """Restore a custom theme from saved settings on startup."""
        theme_data = self._settings.get("custom_theme", {})
        if not theme_data:
            return

        try:
            colors = theme_data.get("colors", {})
            tokens = theme_data.get("tokens", {})

            def make_color(d):
                return _c(d.get("r", 128), d.get("g", 128), d.get("b", 128), d.get("a", 255))

            custom_spec = ThemeSpec(
                name=theme_data.get("name", "Custom"),
                bg=make_color(colors.get("bg", {})),
                surface=make_color(colors.get("surface", {})),
                surface_alt=make_color(colors.get("surface_alt", {})),
                card=make_color(colors.get("card", {})),
                card_border=make_color(colors.get("card_border", {})),
                card_hover=make_color(colors.get("card_hover", {})),
                text=make_color(colors.get("text", {})),
                text_muted=make_color(colors.get("text_muted", {})),
                accent=make_color(colors.get("accent", {})),
                accent_alt=make_color(colors.get("accent_alt", {})),
                chip_bg=make_color(colors.get("chip_bg", {})),
                chip_border=make_color(colors.get("chip_border", {})),
                focus=make_color(colors.get("focus", {})),
                outline=make_color(colors.get("outline", {})),
                shadow=make_color(colors.get("shadow", {})),
                **tokens
            )
            THEMES["custom"] = custom_spec
        except Exception:
            # Fall back to dark theme if custom theme restoration fails
            self._theme = "dark"
            self._log.exception("restore_custom_theme_failed")

    def _apply_custom_theme(self: "MainWindow", theme_data: dict) -> None:
        """Apply a custom theme from the theme editor."""
        try:
            colors = theme_data.get("colors", {})
            tokens = theme_data.get("tokens", {})

            def make_color(d):
                return _c(d.get("r", 128), d.get("g", 128), d.get("b", 128), d.get("a", 255))

            custom_spec = ThemeSpec(
                name=theme_data.get("name", "Custom"),
                bg=make_color(colors.get("bg", {})),
                surface=make_color(colors.get("surface", {})),
                surface_alt=make_color(colors.get("surface_alt", {})),
                card=make_color(colors.get("card", {})),
                card_border=make_color(colors.get("card_border", {})),
                card_hover=make_color(colors.get("card_hover", {})),
                text=make_color(colors.get("text", {})),
                text_muted=make_color(colors.get("text_muted", {})),
                accent=make_color(colors.get("accent", {})),
                accent_alt=make_color(colors.get("accent_alt", {})),
                chip_bg=make_color(colors.get("chip_bg", {})),
                chip_border=make_color(colors.get("chip_border", {})),
                focus=make_color(colors.get("focus", {})),
                outline=make_color(colors.get("outline", {})),
                shadow=make_color(colors.get("shadow", {})),
                **tokens
            )

            THEMES["custom"] = custom_spec
            self._theme = "custom"
            self._settings["theme"] = "custom"
            self._settings["custom_theme"] = theme_data
            self._persist_settings()

            apply_theme(QApplication.instance(), "custom", self._font_family, self._font_scale)
            self._safe_refresh_ui()
            show_success(f"Applied theme: {theme_data.get('name', 'Custom')}")

        except Exception as e:
            self._log.exception("apply_custom_theme_failed")
            show_error(f"Failed to apply theme: {e}")

    def _open_layout_customization(self: "MainWindow") -> None:
        """Open the layout customization dialog."""
        config_data = self._settings.get("layout_config", {})
        config = LayoutConfig.from_dict(config_data) if config_data else LayoutConfig()

        dlg = LayoutCustomizationDialog(self, config=config)
        dlg.layout_changed.connect(self._apply_layout_config)
        dlg.exec()

    def _apply_layout_config(self: "MainWindow", config: LayoutConfig) -> None:
        """Apply layout configuration changes."""
        try:
            self._settings["layout_config"] = config.to_dict()
            self._persist_settings()

            if hasattr(self, 'sidebar'):
                self.sidebar.setVisible(config.show_sidebar)

            if hasattr(self, '_details_widget'):
                if not config.show_details_panel:
                    self._details_widget.hide()
                    self._details_visible = False
                elif self._details_visible:
                    self._details_widget.show()

            if hasattr(self, 'filter_chips'):
                self.filter_chips.setVisible(config.show_filter_chips)

            self.statusBar().setVisible(config.show_status_bar)

            total_width = self.width()
            sidebar_w = int(total_width * config.sidebar_width_pct / 100)
            details_w = int(total_width * config.details_width_pct / 100) if config.show_details_panel else 0
            grid_w = total_width - sidebar_w - details_w

            if hasattr(self, '_splitter'):
                self._splitter.setSizes([sidebar_w, grid_w, details_w])

            self.grid.refresh()
            show_success("Layout updated")

        except Exception as e:
            self._log.exception("apply_layout_config_failed")
            show_error(f"Failed to apply layout: {e}")

    def _apply_settings_values(self: "MainWindow", vals: dict) -> None:
        old_view = self._view_mode
        old_browse = self.grid.get_browse_mode()
        old_theme = self._theme
        old_font = self._font_family
        old_scale = self._font_scale

        self._view_mode = vals.get("view_mode", self._view_mode)
        self._details_on_launch = vals.get("details_on_launch", self._details_on_launch)
        self._details_on_selection = vals.get("details_on_selection", self._details_on_selection)
        self._theme = vals.get("theme", self._theme)
        self._font_family = vals.get("font_family", self._font_family)
        self._font_scale = vals.get("font_scale", self._font_scale)
        self._focus_mode = vals.get("focus_mode", self._focus_mode)
        self._details_visible = vals.get("details_visible", self._details_visible)
        browse_mode = vals.get("browse_mode", old_browse)
        page_size = int(vals.get("page_size", self._config.page_size))

        for key, val in [
            ("view_mode", self._view_mode),
            ("details_on_launch", self._details_on_launch),
            ("details_on_selection", self._details_on_selection),
            ("theme", self._theme),
            ("font_family", self._font_family),
            ("font_scale", self._font_scale),
            ("focus_mode", self._focus_mode),
            ("details_visible", self._details_visible),
            ("browse_mode", browse_mode),
            ("page_size", page_size),
        ]:
            self._settings[key] = val
        self._persist_settings()

        if (self._theme, self._font_family, self._font_scale) != (old_theme, old_font, old_scale):
            self._safe_refresh_ui()

        if self._view_mode != old_view:
            self.grid.set_view_mode(self._view_mode)
            self._update_view_mode_buttons()

        self.grid.set_page_size(page_size)
        if browse_mode != old_browse:
            self.grid.set_browse_mode(browse_mode)
        self._update_browse_mode_buttons()

        if vals.get("reset_layout"):
            self._reset_layout()

        self.focus_btn.setChecked(self._focus_mode)
        self.details_toggle.setChecked(self._details_visible)
        self._apply_focus_mode()
        if not self._focus_mode:
            self._apply_details_visibility()

        if hasattr(self, "settings_page"):
            self.settings_page.set_values(self._settings_snapshot())
            self.settings_page.show_saved()
        show_success("Settings saved")

        self._guard_top_level_windows()

    def _open_bulk_sources(self: "MainWindow") -> None:
        dlg = BulkSourceImportDialog(self, games=self._all_games)
        if dlg.exec():
            self._save_bundle()
            self._apply_search()

    def _open_bulk_archive_import(self: "MainWindow") -> None:
        """Open the bulk archive import dialog."""
        games_folder = self._settings.get("games_folder", str(Path.home() / "Games"))
        shortcuts_folder = self._root_folder or str(Path.home() / "Shortcuts")

        dlg = BulkArchiveImportDialog(
            parent=self,
            games_folder=games_folder,
            shortcuts_folder=shortcuts_folder,
            library=self._all_games,
        )

        def on_import_complete(new_games):
            """Handle newly imported games."""
            for game in new_games:
                self._repo.upsert(game)

            self._save_bundle()
            self._rebuild_search_cache()
            self._apply_search()
            self.sidebar.set_games(self._all_games)
            self.statusBar().showMessage(f"Imported {len(new_games)} games", 3000)

        dlg.import_complete.connect(on_import_complete)
        dlg.exec()
