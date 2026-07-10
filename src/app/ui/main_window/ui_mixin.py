"""UI helpers mixin for MainWindow."""
from __future__ import annotations
from typing import TYPE_CHECKING
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QVBoxLayout, QLabel,
    QProgressBar, QMessageBox,
)

from app.ui.theme import apply_theme, is_reduced_motion
from app.ui.dialogs import PreferencesDialog
from app.logging_utils import kv

if TYPE_CHECKING:
    from .window import MainWindow


# Breakpoint thresholds with hysteresis to prevent flickering at boundaries.
# When crossing a boundary in one direction, require crossing back by the
# hysteresis amount before switching again.
_BP_COMPACT = 900
_BP_DEFAULT = 1200
_BP_HYSTERESIS = 40  # px buffer zone


class UIMixin:
    """Mixin providing UI helper methods for MainWindow."""

    def _render(self: "MainWindow") -> None:
        start = time.perf_counter()
        self._render_count += 1
        self.grid.set_games(self._filtered)
        if hasattr(self, "_update_dashboard_cards"):
            self._update_dashboard_cards()
        if self._selected_game_id is not None:
            g = self._get_game(self._selected_game_id)
            self.details.show_game(g)
            self._ensure_details_visible()
        self._apply_quick_filter_buttons()
        self._update_view_mode_buttons()
        self._update_browse_mode_buttons()
        if hasattr(self, 'update_footer'):
            self.update_footer()
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        if self._render_count == 1:
            self._set_startup_status("Rendering grid\u2026")
            self._log.info("main_render_first %s", kv(duration_ms=duration_ms, filtered=len(self._filtered)))
            self._hide_startup_overlay()
        elif self._log_rate.allow("main_render", interval_ms=800):
            self._log.debug("main_render %s", kv(duration_ms=duration_ms, filtered=len(self._filtered)))

    def _notify_async_error(self: "MainWindow", text: str) -> None:
        """Non-blocking error toast for background tasks."""
        try:
            box = QMessageBox(QMessageBox.Critical, "Error", f"{text}\nSee manager.log.", QMessageBox.Ok, self)
            box.setWindowModality(Qt.NonModal)
            box.setAttribute(Qt.WA_DeleteOnClose)
            box.show()
        except Exception:
            self._log.exception("toast_error_failed")

    def _update_view_mode_buttons(self: "MainWindow") -> None:
        self.view_comfort.setChecked(self._view_mode == "comfortable")
        self.view_compact.setChecked(self._view_mode == "compact")

    def _pulse_widget(self: "MainWindow", widget) -> None:
        """No-op click feedback.

        This used to attach a QGraphicsOpacityEffect + QPropertyAnimation to the
        button on every click — an off-screen render pass per frame, and the
        effect stayed bolted to the widget afterwards.  The buttons already
        signal state through their checked styling, so drop the effect entirely
        and make sure no stale one lingers from a previous build.
        """
        if widget is not None and widget.graphicsEffect() is not None:
            widget.setGraphicsEffect(None)

    def _on_view_mode_changed(self: "MainWindow") -> None:
        self._view_mode = "compact" if self.sender() == self.view_compact else "comfortable"
        self._pulse_widget(self.sender())
        self.grid.set_view_mode(self._view_mode)
        self._settings["view_mode"] = self._view_mode
        self._persist_settings()
        self._update_view_mode_buttons()

    def _on_browse_mode_changed(self: "MainWindow") -> None:
        """Handle browse mode toggle between scroll and pages."""
        mode = "pages" if self.sender() == self.browse_pages_btn else "scroll"
        self._pulse_widget(self.sender())
        self.grid.set_browse_mode(mode)
        self._settings["browse_mode"] = mode
        self._persist_settings()
        self._update_browse_mode_buttons()

    def _update_browse_mode_buttons(self: "MainWindow") -> None:
        """Update browse mode button checked states."""
        mode = self.grid.get_browse_mode()
        self.browse_scroll_btn.setChecked(mode == "scroll")
        self.browse_pages_btn.setChecked(mode == "pages")

    def _toggle_focus_mode(self: "MainWindow") -> None:
        self._focus_mode = self.focus_btn.isChecked()
        self._pulse_widget(self.focus_btn)
        self._settings["focus_mode"] = self._focus_mode
        self._persist_settings()
        self._apply_focus_mode()

    def _apply_focus_mode(self: "MainWindow", initial: bool = False) -> None:
        if self._focus_mode:
            self._details_widget.hide()
            # Use actual sidebar width (may be collapsed to 48px)
            sidebar_w = self._splitter.sizes()[0] if len(self._splitter.sizes()) == 3 else 220
            sidebar_w = min(sidebar_w, 220)  # Cap at default expanded width
            self._splitter.setSizes([sidebar_w, max(800, self.width() - sidebar_w - 40), 0])
        else:
            self._details_widget.show()
            if not initial:
                sizes = self._settings.get("splitter_sizes")
                if isinstance(sizes, list) and len(sizes) == 3:
                    self._splitter.setSizes([int(x) for x in sizes])
            else:
                self._apply_details_visibility(initial=True)
        self.details_toggle.setEnabled(not self._focus_mode)
        self.grid.refresh()

    def _on_splitter_moved(self: "MainWindow", *_args) -> None:
        sizes = self._splitter.sizes()
        if self._details_visible and not self._focus_mode and len(sizes) == 3:
            min_grid = 480
            min_details = 260
            # Priority: grid always gets minimum viable width first
            if sizes[1] < min_grid and sizes[2] > min_details:
                deficit = min_grid - sizes[1]
                sizes[2] = max(min_details, sizes[2] - deficit)
                sizes[1] = min_grid
                self._splitter.setSizes(sizes)
            elif sizes[2] < min_details:
                delta = min_details - sizes[2]
                sizes[2] = min_details
                sizes[1] = max(min_grid, sizes[1] - delta)
                self._splitter.setSizes(sizes)
        self._settings["splitter_sizes"] = sizes
        self._persist_settings()

    def _apply_filter_combo_defaults(self: "MainWindow") -> None:
        def set_if(combo: QComboBox, value: str):
            for i in range(combo.count()):
                if combo.itemText(i).lower() == value:
                    combo.setCurrentIndex(i)
                    break
        set_if(self.status_filter, self._status_filter)
        set_if(self.conf_filter, self._confidence_filter)
        set_if(self.type_filter, self._type_filter)
        self._apply_quick_filter_buttons()

    def _persist_settings(self: "MainWindow") -> None:
        self._config.save()

    def _save_updates_prefs(self: "MainWindow") -> None:
        self._settings["updates_filter"] = self.updates._filter_mode
        self._settings["updates_density"] = self.updates._density
        self._persist_settings()

    def _save_health_prefs(self: "MainWindow") -> None:
        self._settings["health_filter"] = self.health._filter_mode
        self._settings["health_density"] = self.health._density
        self._persist_settings()

    def _ensure_details_visible(self: "MainWindow") -> None:
        if self._focus_mode:
            return
        if not self._details_visible and self._details_on_selection and not self._user_hid_details:
            self._details_visible = True
            self.details_toggle.setChecked(True)
            self._settings["details_visible"] = True
            self._persist_settings()
        self._apply_details_visibility()

    def _apply_details_visibility(
        self: "MainWindow", initial: bool = False, animate: bool = False,
    ) -> None:
        sidebar_w = self._splitter.sizes()[0] if len(self._splitter.sizes()) == 3 else 220
        if self._details_visible and not self._focus_mode:
            self._details_widget.show()
            # Priority-based: allocate sidebar first, then grid gets majority, details gets remainder
            # Grid must have at least 480px; details target 300px but shrinks if needed
            remaining = self.width() - sidebar_w
            details_w = min(300, max(260, remaining - 540))
            grid_w = max(480, remaining - details_w)
            target = [sidebar_w, grid_w, details_w]
        else:
            target = [sidebar_w, max(700, self.width() - sidebar_w), 0]

        if animate and not is_reduced_motion() and not initial:
            self._animate_splitter(target)
        else:
            if not self._details_visible:
                self._details_widget.hide()
            self._splitter.setSizes(target)
        self.grid.refresh()

    def _animate_splitter(self: "MainWindow", target_sizes: list) -> None:
        """Set splitter sizes directly.

        Previously this tweened the sizes through chained QTimer.singleShot
        steps, which forces a full relayout of both panes (and a grid refresh)
        on every frame — visible jank for no real benefit.  A panel resize does
        not need animating; snap straight to the target.
        """
        self._splitter.setSizes(target_sizes)
        if not self._details_visible:
            self._details_widget.hide()

    def _reset_layout(self: "MainWindow") -> None:
        self._splitter.setSizes([220, self.width() - 520, 300 if self._details_visible else 0])
        self._settings["splitter_sizes"] = self._splitter.sizes()
        self._persist_settings()
        self.grid.refresh()

    def _safe_refresh_ui(self: "MainWindow") -> None:
        """Re-apply palette/QSS/font only; avoid rebuilding views."""
        self._log.info("safe_refresh_ui %s", kv(event="safe_refresh"))
        apply_theme(QApplication.instance(), self._theme, self._font_family, self._font_scale)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ---------- Responsive breakpoint system ----------
    def _apply_responsive_type(self: "MainWindow") -> None:
        """Responsive layout adjustments based on window width breakpoints.

        < 900px:   Compact - sidebar collapses, details hidden, icons-only toolbar
        900-1200:  Default - sidebar visible, optional details, full toolbar
        > 1200px:  Expanded - wide sidebar, details visible, spacious toolbar
        """
        width = self.width()

        # Typography scale
        bucket = "normal"
        if width < 1100:
            bucket = "small"
        elif width > 1500:
            bucket = "large"

        if bucket != self._type_scale_bucket:
            self._type_scale_bucket = bucket
            self.grid.set_type_scale(bucket)
            font_delta = {"small": -1, "normal": 0, "large": 1}[bucket]
            self._bump_table_font(self.updates.table, base=10 + font_delta)
            self._bump_table_font(self.health.table, base=10 + font_delta)

        # Breakpoint-based layout adjustments with hysteresis to prevent
        # flickering when the window width hovers near a breakpoint boundary.
        prev_bp = getattr(self, "_current_breakpoint", None)
        if prev_bp == "compact":
            # Must cross above compact threshold + hysteresis to leave compact
            bp = "compact" if width < _BP_COMPACT + _BP_HYSTERESIS else (
                "default" if width <= _BP_DEFAULT else "expanded"
            )
        elif prev_bp == "expanded":
            # Must cross below expanded threshold - hysteresis to leave expanded
            bp = "expanded" if width > _BP_DEFAULT - _BP_HYSTERESIS else (
                "compact" if width < _BP_COMPACT else "default"
            )
        else:
            # Default / initial: use standard thresholds
            bp = "compact" if width < _BP_COMPACT else (
                "default" if width <= _BP_DEFAULT else "expanded"
            )

        if bp == prev_bp:
            return
        self._current_breakpoint = bp

        if bp == "compact":
            if hasattr(self, 'sidebar') and not self.sidebar.is_collapsed():
                self.sidebar.set_collapsed(True, animate=True)
            if self._details_visible and not self._focus_mode:
                self._apply_details_visibility(animate=True)
            self._set_toolbar_compact(True)
        elif bp == "default":
            if hasattr(self, 'sidebar') and self.sidebar.is_collapsed():
                self.sidebar.set_collapsed(False, animate=True)
            if self._details_visible and not self._focus_mode:
                self._apply_details_visibility(animate=True)
            self._set_toolbar_compact(False)
        else:  # expanded
            if hasattr(self, 'sidebar') and self.sidebar.is_collapsed():
                self.sidebar.set_collapsed(False, animate=True)
            if self._details_visible and not self._focus_mode:
                self._apply_details_visibility(animate=True)
            self._set_toolbar_compact(False)

    def _set_toolbar_compact(self: "MainWindow", compact: bool) -> None:
        """Collapse the primary toolbar buttons to icon-only in compact mode.

        Secondary controls (sort, layout, browse, filters) now live inside the
        Filter/View popovers, so only the always-visible primary actions need to
        shrink at narrow widths.
        """
        from app.ui.icons import AppIcons
        if compact:
            self.scan_btn.setText(AppIcons.ACT_SCAN)
            self.check_updates_btn.setText(AppIcons.NAV_UPDATES)
        else:
            self.scan_btn.setText(f"{AppIcons.ACT_SCAN}  Scan")
            self.check_updates_btn.setText(f"{AppIcons.NAV_UPDATES}  Updates")

    def _bump_table_font(self: "MainWindow", table, base: int) -> None:
        f = table.font()
        f.setPointSize(max(8, base))
        table.setFont(f)
        header = table.horizontalHeader()
        hf = header.font()
        hf.setPointSize(max(8, base))
        header.setFont(hf)
        row_h = 40 if base >= 11 else 34
        for r in range(table.rowCount()):
            table.setRowHeight(r, row_h)

    def _guard_top_level_windows(self: "MainWindow") -> None:
        """Debug guardrail to catch accidental top-level widgets."""
        from app.ui.main_window.window import DEBUG_GUARDS
        if not DEBUG_GUARDS:
            return
        allowed_types = (type(self), PreferencesDialog)
        for w in QApplication.topLevelWidgets():
            if isinstance(w, allowed_types):
                continue
            name = w.__class__.__name__
            title = getattr(w, "windowTitle", lambda: "")()
            self._log.error("Unexpected top-level window: %s | title=%s", name, title)
            try:
                w.close()
            except Exception:
                pass

    # ---------- startup overlay ----------
    def _build_startup_overlay(self: "MainWindow", host) -> None:
        try:
            from app.ui.theme import current_theme
            from PySide6.QtGui import QColor

            theme = current_theme()
            bg = theme.bg
            overlay = QFrame(host)
            # Theme-aware scrim so the splash reads correctly on light themes too.
            overlay.setStyleSheet(
                f"background: rgba({bg.red()},{bg.green()},{bg.blue()},190);"
            )
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            overlay.hide()

            scrim_layout = QVBoxLayout(overlay)
            scrim_layout.setContentsMargins(20, 20, 20, 20)
            scrim_layout.addStretch(2)

            # Centered card so the splash feels intentional, not a flat wash.
            card = QFrame()
            card.setObjectName("startupCard")
            card.setMaximumWidth(360)
            card.setStyleSheet(
                f"#startupCard {{ background: {theme.surface.name(QColor.HexArgb)}; "
                f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
                f"border-radius: {theme.radius_lg}px; }} "
                f"#startupCard QLabel {{ background: transparent; border: none; }}"
            )
            layout = QVBoxLayout(card)
            layout.setContentsMargins(28, 28, 28, 28)
            layout.setSpacing(12)

            from app.ui.icons import AppIcons

            brand = QLabel(AppIcons.NAV_LIBRARY)
            brand.setStyleSheet(
                f"color: {theme.accent.name()}; font-size: 40px;"
            )
            title = QLabel("Game Library Manager")
            title.setStyleSheet(
                f"color: {theme.text.name()}; font-size: 18px; font-weight: 700;"
            )
            status = QLabel("Starting\u2026")
            status.setStyleSheet(f"color: {theme.text_muted.name()}; font-size: 12px;")
            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setTextVisible(False)
            bar.setFixedHeight(4)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {theme.surface_sunken.name(QColor.HexArgb)}; "
                f"border: none; border-radius: 2px; }} "
                f"QProgressBar::chunk {{ background: {theme.accent.name()}; "
                f"border-radius: 2px; }}"
            )
            layout.addWidget(brand, 0, Qt.AlignCenter)
            layout.addWidget(title, 0, Qt.AlignCenter)
            layout.addWidget(status, 0, Qt.AlignCenter)
            layout.addSpacing(4)
            layout.addWidget(bar)

            scrim_layout.addWidget(card, 0, Qt.AlignCenter)
            scrim_layout.addStretch(3)
            self._startup_overlay = overlay
            self._startup_status = status
            overlay.show()
            self._update_startup_overlay_geometry()
        except Exception:
            self._startup_overlay = None
            self._startup_status = None

    def _set_startup_status(self: "MainWindow", text: str) -> None:
        if self._startup_status:
            self._startup_status.setText(text)
            if self._startup_overlay:
                self._startup_overlay.raise_()
        if self._log_rate.allow("startup_status", 400):
            self._log.info("startup_status %s", kv(text=text))

    def _hide_startup_overlay(self: "MainWindow") -> None:
        if self._startup_overlay and not self._first_render_done:
            self._first_render_done = True
            self._startup_overlay.hide()

    def _update_startup_overlay_geometry(self: "MainWindow") -> None:
        if not self._startup_overlay:
            return
        try:
            self._startup_overlay.setGeometry(self.centralWidget().geometry())
        except Exception:
            pass
