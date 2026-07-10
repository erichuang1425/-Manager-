"""Core MainWindow class combining all mixins."""
from __future__ import annotations
from typing import Dict, List, Optional
import os
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QSplitter, QMenu, QToolButton, QApplication, QFrame, QMessageBox,
    QWidgetAction,
)

from app.models import Game, Collection
from app.config import AppConfig
from app.events import EventBus, AppEvent
from app.repositories import JsonGameRepository
from app.storage import library_json_path, settings_json_path
from app.logging_utils import connect_safe, get_logger, kv, RateLimiter, wrap_slot
from app.ui.widgets import (
    GameGrid, DetailsPanel, FilterChipsBar, BatchToolbar,
    HealthChecksWidget, UpdatesWidget,
)
from app.ui.widgets.library_sidebar import LibrarySidebar
from app.ui.theme import (
    apply_theme, current_theme, header_bar_style,
    primary_btn_style, secondary_btn_style, ghost_btn_style,
    toolbar_btn_style, segmented_btn_style, icon_btn_style, popover_frame_style,
    section_header_style, scaled_toolbar_height,
)
from app.ui.icons import AppIcons

# Import all mixins
from .scan_mixin import ScanMixin
from .update_mixin import UpdateMixin
from .filter_mixin import FilterMixin
from .dialog_mixin import DialogMixin
from .collection_mixin import CollectionMixin
from .game_ops_mixin import GameOpsMixin
from .actions_mixin import ActionsMixin
from .ui_mixin import UIMixin
from .batch_mixin import BatchMixin

DEBUG_GUARDS = os.environ.get("GLM_GUARDS", "0") == "1"


class MainWindow(
    ScanMixin,
    UpdateMixin,
    FilterMixin,
    DialogMixin,
    CollectionMixin,
    GameOpsMixin,
    ActionsMixin,
    UIMixin,
    BatchMixin,
    QMainWindow,
):
    """Main application window combining all functionality through mixins."""

    # ------------------------------------------------------------------
    # Library data access (single source of truth = JsonGameRepository)
    #
    # The game list, id index, and collection list are exposed as read-only
    # properties backed directly by the repository. Reads always reflect the
    # repository's live state, so the window can never hold a stale alias, and
    # structural mutations must go through repository methods
    # (add/upsert/remove/update_all/set_collections) rather than rebinding
    # these attributes — assigning to them raises AttributeError by design.
    # ------------------------------------------------------------------
    @property
    def _all_games(self) -> List[Game]:
        return self._repo.get_all()

    @property
    def _games_by_id(self) -> Dict[str, Game]:
        return self._repo.index

    @property
    def _collections(self) -> List[Collection]:
        return self._repo.get_collections()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Game Library Manager")
        self.resize(1200, 750)
        self._log = get_logger("ui.main")
        self._log_rate = RateLimiter()
        self._render_count = 0
        self._c = lambda sig, fn, label, **ctx: connect_safe(sig, fn, self._log, label, **ctx)
        self._t0 = time.perf_counter()
        self._log.info("startup_init %s", kv(ts=time.strftime('%H:%M:%S')))

        self._startup_overlay = None
        self._startup_status = None
        self._first_render_done = False

        # Load settings via typed AppConfig
        settings_start = time.perf_counter()
        self._config = AppConfig.load()
        # Backward-compat dict interface for mixins that still use self._settings
        self._settings = self._config
        self._log.info(
            "startup_settings_loaded %s",
            kv(duration_ms=round((time.perf_counter() - settings_start) * 1000, 1)),
        )

        # Initialize state from config (direct attribute access)
        self._root_folder: str = self._config.root_folder
        self._view_mode: str = self._config.view_mode
        self._focus_mode: bool = self._config.focus_mode
        self._quick_filter: str = self._config.quick_filter
        self._tag_filter: Optional[str] = self._config.tag_filter
        self._status_filter: str = self._config.status_filter
        self._confidence_filter: str = self._config.confidence_filter
        self._type_filter: str = self._config.type_filter
        self._sort_by: str = self._config.sort_by
        self._updates_filter: str = self._config.updates_filter
        self._updates_density: str = self._config.updates_density
        self._health_filter: str = self._config.health_filter
        self._health_density: str = self._config.health_density
        self._details_visible: bool = self._config.details_visible
        self._details_on_launch: bool = self._config.details_on_launch
        self._details_on_selection: bool = self._config.details_on_selection
        self._user_hid_details: bool = False
        self._theme: str = self._config.theme
        self._font_family: str = self._config.font_family
        self._font_scale: str = self._config.font_scale

        # Load library via repository
        lib_start = time.perf_counter()
        self._repo = JsonGameRepository(library_json_path())
        self._active_collection_id: Optional[str] = None
        self._log.info(
            "startup_library_loaded %s",
            kv(count=len(self._all_games), collections=len(self._collections),
               duration_ms=round((time.perf_counter() - lib_start) * 1000, 1)),
        )
        self._set_startup_status("Building UI\u2026")
        self._log.info("data_paths %s", kv(library=library_json_path(), settings=settings_json_path()))

        self._filtered: List[Game] = list(self._all_games)
        self._init_search_cache()
        self._selected_game_id: Optional[str] = None
        self._ignored_health: dict[str, set[str]] = {}

        # Event bus for decoupled inter-component communication
        self._bus = EventBus()
        self._bus.on(AppEvent.GAMES_CHANGED, lambda _: self._rebuild_search_cache())
        self._bus.on(AppEvent.GAMES_CHANGED, lambda _: self._apply_search())
        self._bus.on(AppEvent.GAME_EDITED, lambda gid: self._search_cache.invalidate(gid) if hasattr(self, '_search_cache') else None)

        if self._theme == "custom" and "custom_theme" in self._settings:
            self._restore_custom_theme()

        apply_theme(QApplication.instance(), self._theme, self._font_family, self._font_scale)

        # Debounced save: coalesce rapid _persist_library() calls into one write
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._flush_save)
        self._save_dirty = False

        # Worker handles
        self._scan_thread = None
        self._scan_worker = None
        self._progress_dialog = None
        self._update_thread = None
        self._update_worker = None
        self._update_progress_dialog = None

        # Build UI
        ui_build_start = time.perf_counter()
        self._build_ui()
        self._log.info(
            "startup_ui_built %s",
            kv(duration_ms=round((time.perf_counter() - ui_build_start) * 1000, 1)),
        )

        self._finalize_startup()
        self._setup_shortcuts()

    # ------------------------------------------------------------------ #
    #  Layout
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        """Build the redesigned main UI layout."""
        theme = current_theme()
        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Startup overlay
        self._build_startup_overlay(root)
        self._set_startup_status("Loading library\u2026")

        # -- Header bar (slim, branded) --
        self._build_header_bar(outer, theme)

        # -- Main body: sidebar | content | details --
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.outline.name(QColor.HexArgb)}; }}"
        )

        self.sidebar = LibrarySidebar()
        self.sidebar.nav_changed.connect(wrap_slot(self._log, "nav_changed")(self._on_nav_changed))
        self.sidebar.new_collection_requested.connect(self._new_collection)
        self.sidebar.rename_collection_requested.connect(self._rename_collection_by_id)
        self.sidebar.delete_collection_requested.connect(self._delete_collection_by_id)
        self.sidebar.game_dropped_on_collection.connect(self._on_game_dropped_on_collection)
        self.sidebar.set_games(self._all_games)

        content = self._build_content_area(theme)
        details = self._build_details_panel(theme)

        splitter.addWidget(self.sidebar)
        splitter.addWidget(content)
        splitter.addWidget(details)
        self._details_widget = details
        self._splitter = splitter

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 0)
        splitter.splitterMoved.connect(self._on_splitter_moved)
        splitter.setChildrenCollapsible(False)

        self._type_scale_bucket = "normal"

        outer.addWidget(splitter, 1)

        # -- Footer status bar --
        self._build_footer_bar(outer, theme)

        # Restore splitter sizes
        sizes = self._settings.get("splitter_sizes")
        if isinstance(sizes, list) and len(sizes) == 3:
            splitter.setSizes([int(x) for x in sizes])
        else:
            # Sidebar expanded, details hidden by default to maximize grid space
            splitter.setSizes([220, self.width() - 220, 0])

    def _build_header_bar(self, outer: QVBoxLayout, theme) -> None:
        """Build the slim branded header bar, scaled for DPI and font size."""
        header = QFrame()
        header.setFixedHeight(scaled_toolbar_height())
        # Flat header (was a diagonal qlineargradient) — reads cleaner and
        # lighter alongside the flattened card grid.
        header.setStyleSheet(
            f"QFrame {{ {header_bar_style(theme)} }}"
            f"QFrame QLabel {{ background: transparent; border: none; }}"
            f"QFrame QLineEdit {{ background: transparent; border: none; }}"
        )

        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(theme.spacing_lg, 0, theme.spacing_lg, 0)
        hbox.setSpacing(theme.spacing_md)

        # App title
        self.title_label = QLabel(f"{AppIcons.NAV_LIBRARY}  Game Library Manager")
        self.title_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {theme.text.name()};"
        )
        hbox.addWidget(self.title_label)
        hbox.addStretch(1)

        # Search bar (centered, pill-shaped)
        self.search = QLineEdit()
        self.search.setPlaceholderText(f" {AppIcons.ACT_SEARCH}  Search games, tags, notes\u2026")
        self.search.setToolTip(
            "Search by title, tags, or notes.\n"
            "Advanced: status:playing, tag:rpg, rating:>7, has:source"
        )
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(300)
        self.search.setMaximumWidth(500)
        self.search.setStyleSheet(
            f"QLineEdit {{ "
            f"background: {theme.surface_sunken.name(QColor.HexArgb)}; "
            f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
            f"border-radius: {theme.radius_pill}px; "
            f"padding: 5px 16px; "
            f"color: {theme.text.name()}; "
            f"font-size: 12px; "
            f"}} "
            f"QLineEdit:focus {{ "
            f"border-color: {theme.accent.name()}; "
            f"background: {theme.surface.name(QColor.HexArgb)}; "
            f"}}"
        )
        # Debounce search input to avoid grid rebuilds on every keystroke
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(300)
        self._search_debounce.timeout.connect(self._apply_search)
        self.search.textChanged.connect(self._on_search_text_changed)
        hbox.addWidget(self.search, 2)
        hbox.addStretch(1)

        # Right-side buttons (ghost style)
        self._build_tools_menu(theme)
        hbox.addWidget(self.tools_btn)

        outer.addWidget(header)

    def _build_tools_menu(self, theme) -> None:
        """Build the tools dropdown menu."""
        tools_menu = QMenu(self)
        act_bulk = QAction("Bulk Source URLs\u2026", self)
        act_bulk.triggered.connect(self._open_bulk_sources)
        act_bulk_archive = QAction("Bulk Archive Import\u2026", self)
        act_bulk_archive.triggered.connect(self._open_bulk_archive_import)
        act_scan = QAction("Scanner", self)
        act_scan.triggered.connect(self._open_scanner_project)
        tools_menu.addAction(act_bulk)
        tools_menu.addAction(act_bulk_archive)
        tools_menu.addAction(act_scan)
        tools_menu.addSeparator()
        act_settings = QAction(f"{AppIcons.ACT_SETTINGS}  Settings", self)
        act_settings.triggered.connect(self._open_preferences)
        act_theme_editor = QAction("Theme Editor\u2026", self)
        act_theme_editor.triggered.connect(self._open_theme_editor)
        act_layout = QAction("Layout Customization\u2026", self)
        act_layout.triggered.connect(self._open_layout_customization)
        act_shortcuts = QAction("Keyboard Shortcuts", self)
        act_shortcuts.triggered.connect(self._show_shortcuts_help)
        act_data = QAction("Open Data Folder", self)
        act_data.triggered.connect(self._open_data_folder)
        tools_menu.addAction(act_settings)
        tools_menu.addAction(act_theme_editor)
        tools_menu.addAction(act_layout)
        tools_menu.addAction(act_shortcuts)
        tools_menu.addSeparator()
        tools_menu.addAction(act_data)

        self.tools_btn = QToolButton()
        self.tools_btn.setText(f"{AppIcons.NAV_TOOLS}")
        self.tools_btn.setToolTip("Tools and settings")
        self.tools_btn.setPopupMode(QToolButton.InstantPopup)
        self.tools_btn.setMenu(tools_menu)
        self.tools_btn.setStyleSheet(
            ghost_btn_style(theme) +
            " QToolButton { font-size: 16px; padding: 4px 8px; min-width: 32px; }"
        )

    def _build_content_area(self, theme) -> QWidget:
        """Build the center content area with context toolbar and grid."""
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(theme.spacing_lg, 0, theme.spacing_lg, 0)
        content_layout.setSpacing(0)
        content.setMinimumWidth(480)

        # -- Single context toolbar (replaces the old two-row control area) --
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, theme.spacing_sm, 0, theme.spacing_sm)
        toolbar.setSpacing(theme.spacing_sm)

        # Primary actions
        self.scan_btn = QPushButton(f"{AppIcons.ACT_SCAN}  Scan")
        self.scan_btn.setStyleSheet(primary_btn_style(theme))
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setToolTip("Scan shortcuts root folder")
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        toolbar.addWidget(self.scan_btn)

        self.check_updates_btn = QToolButton()
        self.check_updates_btn.setText(f"{AppIcons.NAV_UPDATES}  Updates")
        self.check_updates_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.check_updates_btn.setStyleSheet(toolbar_btn_style(theme))
        self.check_updates_btn.setCursor(Qt.PointingHandCursor)
        self.check_updates_btn.setToolTip("Check for game updates")
        self.check_updates_btn.clicked.connect(self._on_check_updates_fetch)
        updates_menu = QMenu(self)
        act_fetch = QAction("Background fetch && parse", self)
        act_open = QAction("Open sources only", self)
        act_fetch.triggered.connect(self._on_check_updates_fetch)
        act_open.triggered.connect(self._on_check_updates_open_only)
        updates_menu.addAction(act_fetch)
        updates_menu.addAction(act_open)
        self.check_updates_btn.setMenu(updates_menu)
        toolbar.addWidget(self.check_updates_btn)

        toolbar.addWidget(self._toolbar_separator(theme))

        # Quick-filter segmented control (keeps the same pill widgets/handlers)
        self.pill_all = QPushButton("All")
        self.pill_all.setToolTip("Show all games")
        self.pill_missing = QPushButton("Missing")
        self.pill_missing.setToolTip("Games with missing shortcuts")
        self.pill_updates = QPushButton("Updates")
        self.pill_updates.setToolTip("Games with available updates")
        self.pill_source = QPushButton("Source")
        self.pill_source.setToolTip("Games with a source URL")
        seg = QHBoxLayout()
        seg.setContentsMargins(0, 0, 0, 0)
        seg.setSpacing(0)
        pills = [self.pill_all, self.pill_missing, self.pill_updates, self.pill_source]
        for i, btn in enumerate(pills):
            pos = "left" if i == 0 else ("right" if i == len(pills) - 1 else "mid")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(segmented_btn_style(theme, pos))
            btn.clicked.connect(self._on_quick_filter)
            seg.addWidget(btn)
        toolbar.addLayout(seg)

        toolbar.addStretch(1)

        # Filter popover (hosts status / confidence / type filters + tag + clear)
        self.filter_btn = self._build_filter_popover(theme)
        toolbar.addWidget(self.filter_btn)

        # View popover (hosts sort + layout + browse mode)
        self.view_btn = self._build_view_popover(theme)
        toolbar.addWidget(self.view_btn)

        toolbar.addWidget(self._toolbar_separator(theme))

        # Panel toggles — compact icon-only buttons
        self.focus_btn = QPushButton(AppIcons.UI_FOCUS)
        self.focus_btn.setToolTip("Focus mode — full-width grid (hide sidebar & details)")
        self.details_toggle = QToolButton()
        self.details_toggle.setText(AppIcons.UI_DETAILS)
        self.details_toggle.setToolTip("Show/hide details panel (Ctrl+D)")
        self.select_btn = QPushButton(AppIcons.UI_SELECT)
        self.select_btn.setToolTip("Multi-select mode (Ctrl+Click)")
        for tog in (self.focus_btn, self.details_toggle, self.select_btn):
            tog.setCheckable(True)
            tog.setCursor(Qt.PointingHandCursor)
            tog.setFixedSize(30, 30)
            tog.setStyleSheet(icon_btn_style(theme))
        self.focus_btn.setChecked(self._focus_mode)
        self.focus_btn.clicked.connect(self._toggle_focus_mode)
        self.details_toggle.setChecked(self._details_visible)
        self.details_toggle.clicked.connect(self._toggle_details_panel)
        self.select_btn.clicked.connect(self._toggle_multi_select_mode)
        toolbar.addWidget(self.focus_btn)
        toolbar.addWidget(self.details_toggle)
        toolbar.addWidget(self.select_btn)

        content_layout.addLayout(toolbar)

        # Filter chips bar
        self.filter_chips = FilterChipsBar()
        self.filter_chips.filter_removed.connect(self._on_filter_chip_removed)
        self.filter_chips.clear_all_clicked.connect(self._clear_all_filters)
        content_layout.addWidget(self.filter_chips)

        # Batch toolbar
        self.batch_toolbar = BatchToolbar()
        self.batch_toolbar.set_status_requested.connect(self._on_batch_set_status)
        self.batch_toolbar.add_tag_requested.connect(self._on_batch_add_tag)
        self.batch_toolbar.add_to_collection_requested.connect(self._on_batch_add_to_collection)
        self.batch_toolbar.select_all_clicked.connect(lambda: self.grid.select_all())
        self.batch_toolbar.clear_selection_clicked.connect(lambda: self.grid.clear_selection())
        self.batch_toolbar.exit_mode_clicked.connect(self._exit_multi_select_mode)
        content_layout.addWidget(self.batch_toolbar)

        # Content title (shows current view name)
        self.content_title = QLabel("All Games")
        self.content_title.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {theme.text.name()}; "
            f"padding: {theme.spacing_xs}px 0; background: transparent; border: none;"
        )
        content_layout.addWidget(self.content_title)

        # Game grid
        self.grid = GameGrid()
        self.grid.context_action.connect(self._on_grid_context_action)
        self.grid.game_selected.connect(self._on_game_selected)
        self.grid.game_play.connect(self._on_game_play)
        self.grid.status_filter_requested.connect(self._on_status_filter_requested)
        self.grid.updates_requested.connect(self._jump_to_updates)
        self.grid.rating_changed.connect(self._on_rating_changed)
        self.grid.tag_filter_requested.connect(self._on_tag_filter_requested)
        self.grid.scan_requested.connect(self._on_scan_clicked)
        self.grid.selection_changed.connect(self._on_selection_changed)

        # Health and Updates widgets
        self.health = HealthChecksWidget()
        self.health.open_folder_requested.connect(self._open_shortcut_folder)
        self.health.remove_game_requested.connect(self._remove_game)
        self.health.fix_requested.connect(self._fix_game)
        self.health.resolve_requested.connect(self._resolve_issue)
        self.health.ignore_requested.connect(self._ignore_issue)

        self.updates = UpdatesWidget()
        self.updates.open_source_requested.connect(self._open_source_for_game)
        self.updates.mark_installed_requested.connect(self._mark_installed_from_source)

        self._apply_saved_widget_prefs()

        content_layout.addWidget(self.grid, 1)
        content_layout.addWidget(self.health, 1)
        content_layout.addWidget(self.updates, 1)
        self.health.hide()
        self.updates.hide()

        # Keep hidden collection buttons for backward compatibility with mixins.
        # Must be created before _rebuild_sidebar() because sidebar population
        # emits nav_changed which calls _on_nav_changed, which accesses these.
        self.new_collection_btn = QPushButton()
        self.new_collection_btn.hide()
        self.add_to_collection_btn = QPushButton()
        self.add_to_collection_btn.hide()
        self.rename_collection_btn = QPushButton()
        self.rename_collection_btn.hide()
        self.delete_collection_btn = QPushButton()
        self.delete_collection_btn.hide()

        self._rebuild_sidebar()

        return content

    # ------------------------------------------------------------------ #
    #  Toolbar popovers (Filter / View)
    # ------------------------------------------------------------------ #

    def _toolbar_separator(self, theme) -> QFrame:
        """A 1px vertical divider for grouping toolbar controls."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(
            f"background: {theme.outline.name(QColor.HexArgb)}; border: none; "
            f"margin: 4px 2px;"
        )
        return sep

    def _make_popover_button(self, label: str, tooltip: str, content: QWidget, theme) -> QToolButton:
        """Wrap a content widget in an auto-closing popover anchored to a button."""
        btn = QToolButton()
        btn.setText(label)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setPopupMode(QToolButton.InstantPopup)
        btn.setStyleSheet(toolbar_btn_style(theme))
        menu = QMenu(btn)
        menu.setStyleSheet("QMenu { background: transparent; border: none; padding: 0; margin: 0; }")
        action = QWidgetAction(menu)
        action.setDefaultWidget(content)
        menu.addAction(action)
        btn.setMenu(menu)
        return btn

    def _popover_container(self, theme):
        """Return (frame, vbox) for a styled popover body."""
        frame = QFrame()
        frame.setObjectName("popover")
        frame.setStyleSheet(popover_frame_style(theme))
        col = QVBoxLayout(frame)
        col.setContentsMargins(
            theme.spacing_md, theme.spacing_md, theme.spacing_md, theme.spacing_md
        )
        col.setSpacing(theme.spacing_sm)
        return frame, col

    def _popover_label(self, text: str, theme) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(section_header_style(theme))
        return lbl

    def _build_filter_popover(self, theme) -> QToolButton:
        """Filter popover hosting the status / confidence / type / tag filters.

        The combo widgets keep their original attribute names so every handler
        in filter_mixin continues to work unchanged.
        """
        frame, col = self._popover_container(theme)
        frame.setMinimumWidth(240)

        col.addWidget(self._popover_label("STATUS", theme))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Backlog", "Playing", "Finished", "Dropped"])
        self.status_filter.setToolTip("Filter by status")
        status_label = self._status_filter.capitalize() if self._status_filter != "all" else "All"
        self.status_filter.setCurrentText(status_label)
        self.status_filter.currentTextChanged.connect(self._on_filter_changed)
        col.addWidget(self.status_filter)

        col.addWidget(self._popover_label("CONFIDENCE", theme))
        self.conf_filter = QComboBox()
        self.conf_filter.addItems(["All", "High", "Medium", "Low"])
        self.conf_filter.setToolTip("Filter by confidence")
        confidence_label = self._confidence_filter.capitalize() if self._confidence_filter != "all" else "All"
        self.conf_filter.setCurrentText(confidence_label)
        self.conf_filter.currentTextChanged.connect(self._on_filter_changed)
        col.addWidget(self.conf_filter)

        col.addWidget(self._popover_label("TYPE", theme))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "lnk", "url", "html"])
        self.type_filter.setToolTip("Filter by type")
        self.type_filter.setCurrentText(self._type_filter if self._type_filter != "all" else "All")
        self.type_filter.currentTextChanged.connect(self._on_filter_changed)
        col.addWidget(self.type_filter)

        # Tag filter row (only visible while a tag filter is active)
        tag_row = QHBoxLayout()
        tag_row.setContentsMargins(0, 0, 0, 0)
        self.tag_filter_label = QLabel("")
        self.tag_filter_label.setStyleSheet(
            f"color: {theme.accent.name()}; font-weight: 600; "
            f"background: transparent; border: none;"
        )
        self.tag_filter_label.hide()
        self.clear_tag_btn = QPushButton(AppIcons.ACT_CLOSE)
        self.clear_tag_btn.setStyleSheet(ghost_btn_style(theme))
        self.clear_tag_btn.setFixedSize(24, 24)
        self.clear_tag_btn.clicked.connect(self._clear_tag_filter)
        self.clear_tag_btn.setVisible(False)
        tag_row.addWidget(self.tag_filter_label, 1)
        tag_row.addWidget(self.clear_tag_btn)
        col.addLayout(tag_row)

        clear_all = QPushButton("Clear all filters")
        clear_all.setStyleSheet(secondary_btn_style(theme))
        clear_all.setCursor(Qt.PointingHandCursor)
        clear_all.clicked.connect(self._clear_all_filters)
        col.addWidget(clear_all)

        return self._make_popover_button(
            f"{AppIcons.ACT_FILTER}  Filter", "Filter games", frame, theme
        )

    def _build_view_popover(self, theme) -> QToolButton:
        """View popover hosting sort + layout + browse-mode controls."""
        frame, col = self._popover_container(theme)
        frame.setMinimumWidth(220)

        col.addWidget(self._popover_label("SORT BY", theme))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Title", "Last Played", "Rating", "Launch Count", "Last Checked"])
        self.sort_combo.setToolTip("Sort order")
        self.sort_combo.setCurrentText({
            "title": "Title", "last_played": "Last Played", "rating": "Rating",
            "launch_count": "Launch Count", "last_checked": "Last Checked",
        }.get(self._sort_by, "Title"))
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        col.addWidget(self.sort_combo)

        col.addWidget(self._popover_label("LAYOUT", theme))
        self.view_comfort = QPushButton("Grid")
        self.view_comfort.setToolTip("Comfortable grid view")
        self.view_compact = QPushButton("List")
        self.view_compact.setToolTip("Compact list view")
        layout_row = QHBoxLayout()
        layout_row.setContentsMargins(0, 0, 0, 0)
        layout_row.setSpacing(0)
        for i, btn in enumerate((self.view_comfort, self.view_compact)):
            pos = "left" if i == 0 else "right"
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(segmented_btn_style(theme, pos))
            btn.clicked.connect(self._on_view_mode_changed)
            layout_row.addWidget(btn)
        col.addLayout(layout_row)

        col.addWidget(self._popover_label("BROWSE", theme))
        self.browse_scroll_btn = QPushButton(f"{AppIcons.UI_SCROLL} Scroll")
        self.browse_scroll_btn.setToolTip("Continuous scrolling mode (virtual scroll)")
        self.browse_pages_btn = QPushButton(f"{AppIcons.UI_PAGES} Pages")
        self.browse_pages_btn.setToolTip("Paginated browsing mode")
        browse_row = QHBoxLayout()
        browse_row.setContentsMargins(0, 0, 0, 0)
        browse_row.setSpacing(0)
        for i, btn in enumerate((self.browse_scroll_btn, self.browse_pages_btn)):
            pos = "left" if i == 0 else "right"
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(segmented_btn_style(theme, pos))
            btn.clicked.connect(self._on_browse_mode_changed)
            browse_row.addWidget(btn)
        col.addLayout(browse_row)

        return self._make_popover_button(
            f"{AppIcons.UI_VIEW}  View", "View options", frame, theme
        )

    def _update_filter_badge(self) -> None:
        """Refresh the Filter button label with a count of active filters."""
        if not hasattr(self, "filter_btn"):
            return
        count = sum((
            self._status_filter != "all",
            self._confidence_filter != "all",
            self._type_filter != "all",
            bool(self._tag_filter),
        ))
        label = f"{AppIcons.ACT_FILTER}  Filter"
        if count:
            label += f"  ({count})"
        self.filter_btn.setText(label)

    def _apply_saved_widget_prefs(self) -> None:
        """Apply saved preferences to health and updates widgets."""
        self.updates._filter_mode = self._updates_filter
        self.updates.filter_all.setChecked(self._updates_filter == "all")
        self.updates.filter_updates.setChecked(self._updates_filter == "updates")
        self.updates.filter_unknown.setChecked(self._updates_filter == "unknown")
        self.updates.set_density(self._updates_density)
        for btn in (self.updates.density_comfort, self.updates.density_compact,
                    self.updates.filter_all, self.updates.filter_updates, self.updates.filter_unknown):
            btn.clicked.connect(self._save_updates_prefs)

        self.health._filter_mode = self._health_filter
        for key, btn in [
            ("all", self.health.filter_all),
            ("errors", self.health.filter_errors),
            ("warnings", self.health.filter_warn),
            ("missing_source", self.health.filter_missing_source),
            ("missing_archive", self.health.filter_missing_archive),
        ]:
            btn.setChecked(self._health_filter == key)
        self.health.set_density(self._health_density)
        for btn in (self.health.density_comfort, self.health.density_compact,
                    self.health.filter_all, self.health.filter_errors, self.health.filter_warn,
                    self.health.filter_missing_source, self.health.filter_missing_archive):
            btn.clicked.connect(self._save_health_prefs)

    def _build_details_panel(self, theme) -> QWidget:
        """Build the right details panel."""
        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(theme.spacing_md, theme.spacing_sm, theme.spacing_md, theme.spacing_sm)
        details_layout.setSpacing(0)
        details.setMinimumWidth(260)
        details.setMaximumWidth(400)

        self.details = DetailsPanel()
        self.details.play_clicked.connect(self._on_game_play)
        self.details.game_changed.connect(self._on_game_changed)

        details_layout.addWidget(self.details, 1)
        return details

    def _build_footer_bar(self, outer: QVBoxLayout, theme) -> None:
        """Build the custom status/footer bar, scaled for DPI and font size."""
        footer = QFrame()
        # Scale footer proportionally (base 28px relative to 48px toolbar)
        footer.setFixedHeight(max(24, round(scaled_toolbar_height() * 28 / 48)))
        footer.setStyleSheet(
            f"QFrame {{ "
            f"background: {theme.surface.name(QColor.HexArgb)}; "
            f"border-top: 1px solid {theme.outline.name(QColor.HexArgb)}; "
            f"}} "
            f"QFrame QLabel {{ background: transparent; border: none; font-size: 11px; }}"
        )
        hbox = QHBoxLayout(footer)
        hbox.setContentsMargins(theme.spacing_lg, 0, theme.spacing_lg, 0)
        hbox.setSpacing(theme.spacing_lg)

        self._footer_count = QLabel("")
        self._footer_count.setStyleSheet(f"color: {theme.text_muted.name()};")
        hbox.addWidget(self._footer_count)

        self._footer_filters = QLabel("")
        self._footer_filters.setStyleSheet(f"color: {theme.text_muted.name()};")
        hbox.addWidget(self._footer_filters)

        hbox.addStretch(1)

        self._footer_theme = QLabel(f"Theme: {self._theme.title()}")
        self._footer_theme.setStyleSheet(f"color: {theme.text_muted.name()};")
        hbox.addWidget(self._footer_theme)

        outer.addWidget(footer)

    def update_footer(self) -> None:
        """Update footer bar with current counts and filter info."""
        if not hasattr(self, '_footer_count'):
            return
        total = len(self._all_games)
        shown = len(self._filtered)
        if total == shown:
            self._footer_count.setText(f"{total} games")
        else:
            self._footer_count.setText(f"{shown} of {total} games")

        # Active filter summary
        parts = []
        if self._status_filter != "all":
            parts.append(f"Status: {self._status_filter}")
        if self._tag_filter:
            parts.append(f"Tag: {self._tag_filter}")
        if self._quick_filter != "all":
            parts.append(f"View: {self._quick_filter}")
        self._footer_filters.setText("  |  ".join(parts) if parts else "")

    # ------------------------------------------------------------------ #
    #  Startup / Lifecycle
    # ------------------------------------------------------------------ #

    def _finalize_startup(self) -> None:
        """Finalize startup: apply modes, render, show status."""
        # Suppress grid renders while we bulk-apply saved config.  Each of the
        # calls below (focus mode, details, view mode, browse mode) would
        # individually trigger a full grid render.  We suppress until the end
        # and do a single render.
        self.grid._render_suppressed = True

        self._apply_focus_mode(initial=True)
        if self._details_on_launch:
            self._details_visible = True
            self.details_toggle.setChecked(True)
        self._apply_details_visibility(initial=True)
        self._log.info(
            "startup_layout_ready %s",
            kv(details_visible=self._details_visible, view_mode=self._view_mode,
               width=self.width(), height=self.height()),
        )
        self.grid.set_view_mode(self._view_mode)
        # Apply saved browse mode (scroll vs pages)
        browse_mode = self._config.browse_mode
        page_size = self._config.page_size
        self.grid.set_page_size(page_size)
        self.grid.set_browse_mode(browse_mode)
        self._update_browse_mode_buttons()
        self._update_view_mode_buttons()
        self._apply_quick_filter_buttons()
        self._apply_filter_combo_defaults()
        self._apply_responsive_type()

        # Un-suppress and do the single authoritative startup render.
        self.grid._render_suppressed = False
        first_render_start = time.perf_counter()
        self._render()
        if not self._all_games:
            self.statusBar().showMessage("Tip: Click Scan to choose your games root folder.", 8000)
        else:
            self.statusBar().showMessage(f"Loaded {len(self._all_games)} games", 5000)
        self._log.info(
            "startup_first_render_done %s",
            kv(duration_ms=round((time.perf_counter() - first_render_start) * 1000, 1),
               total_ms=round((time.perf_counter() - self._t0) * 1000, 1),
               games=len(self._all_games))
        )

        # Tell the user if the library was recovered from a backup, or could not
        # be read at all. Deferred so the dialog appears over the shown window.
        if self._repo.recovery_report.needs_notice:
            QTimer.singleShot(0, self._surface_recovery_notice)

    def _surface_recovery_notice(self) -> None:
        """Explain corruption recovery to the user (recovered backup / unreadable library)."""
        report = self._repo.recovery_report
        if report.fatal:
            detail = (
                "Your library file could not be read and may be corrupt, so the "
                "application started with an empty library."
            )
            if report.quarantined:
                saved = "\n".join(str(p) for p in report.quarantined)
                detail += (
                    "\n\nA copy of the unreadable data has been preserved so you "
                    f"can attempt manual recovery:\n{saved}"
                )
            else:
                detail += f"\n\nAffected file:\n{report.path}"
            icon = QMessageBox.Critical
            title = "Library could not be read"
        elif report.recovered:
            detail = (
                "Your primary library file was missing or unreadable, so it was "
                f"restored from the most recent good copy:\n{report.source}\n\n"
                "Your library has been recovered and will be re-saved normally."
            )
            icon = QMessageBox.Warning
            title = "Library recovered"
        else:
            return
        self._log.warning(
            "recovery_notice %s",
            kv(fatal=report.fatal, recovered=report.recovered, source=str(report.source)),
        )
        box = QMessageBox(icon, title, detail, QMessageBox.Ok, self)
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_startup_overlay_geometry()
        self._apply_responsive_type()
        if self._log_rate.allow("resize", interval_ms=300):
            self._log.debug("resize %s", kv(w=self.width(), h=self.height()))

    def _persist_library(self) -> None:
        """Schedule a debounced library save (500ms coalesce window)."""
        self._save_dirty = True
        self._save_timer.start()

    def _flush_save(self) -> None:
        """Immediately persist library if dirty. Called by timer and closeEvent."""
        if self._save_dirty:
            self._save_bundle()
            self._save_dirty = False

    def closeEvent(self, event) -> None:
        """Ensure pending saves are flushed before exit."""
        self._save_timer.stop()
        self._flush_save()
        super().closeEvent(event)

    def _refresh_list(self) -> None:
        self._apply_search()

    # Compatibility stubs for collection management via sidebar signals
    def _rename_collection_by_id(self, coll_id: str) -> None:
        """Rename a collection by ID (called from sidebar context menu)."""
        self._active_collection_id = coll_id
        self._rename_active_collection()

    def _delete_collection_by_id(self, coll_id: str) -> None:
        """Delete a collection by ID (called from sidebar context menu)."""
        self._active_collection_id = coll_id
        self._delete_active_collection()
