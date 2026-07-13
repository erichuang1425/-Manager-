"""Redesigned library sidebar with icons, sections, collapsible mode, and rich navigation."""
from __future__ import annotations
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QPushButton, QMenu, QSizePolicy,
)
from PySide6.QtGui import QFont, QColor

from app.models import Collection
from app.services.collection_engine import apply_collection
from app.ui.theme import current_theme, sidebar_item_style, ghost_btn_style, is_reduced_motion
from app.ui.icons import AppIcons


def _collection_key(collection_id: str) -> str:
    return f"collection:{collection_id}"


class LibrarySidebar(QWidget):
    """Sidebar widget with rich navigation, icons, sections, and context menus.

    Supports collapsible icon-only mode for narrow windows.
    """

    nav_changed = Signal(str)
    new_collection_requested = Signal()
    rename_collection_requested = Signal(str)
    delete_collection_requested = Signal(str)
    collapse_toggled = Signal(bool)  # True = collapsed
    game_dropped_on_collection = Signal(str, str)  # (game_id, collection_id)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = current_theme()
        theme = self._theme
        self._collapsed = False
        self._pinned_expanded = True  # User preference: keep expanded
        self._expanded_width = theme.sidebar_width_min
        self._collapsed_width = theme.sidebar_collapsed_width
        self._hover_expand = False

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setMinimumWidth(self._expanded_width)
        self.setMaximumWidth(theme.sidebar_width_max)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.spacing_md, theme.spacing_lg, theme.spacing_md, theme.spacing_lg)
        layout.setSpacing(theme.spacing_sm)

        # Sidebar header
        header = QHBoxLayout()
        header.setContentsMargins(theme.spacing_lg, theme.spacing_sm, theme.spacing_md, theme.spacing_md)
        self._title_label = QLabel(f"{AppIcons.NAV_LIBRARY}  Game Library")
        self._title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.text.name()}; line-height: 125%; "
            f"background: transparent; border: none;"
        )
        self._title_label.setMinimumWidth(0)
        header.addWidget(self._title_label, 1)
        header.addStretch(1)

        # Collapse toggle button
        self._collapse_btn = QPushButton(AppIcons.UI_CHEVRON_LEFT)
        self._collapse_btn.setToolTip("Collapse sidebar")
        self._collapse_btn.setFixedSize(24, 24)
        self._collapse_btn.setStyleSheet(ghost_btn_style(theme))
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        header.addWidget(self._collapse_btn)
        layout.addLayout(header)

        # Main nav list
        self.list = QListWidget()
        self.list.setStyleSheet(sidebar_item_style(theme))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)

        # Enable drag-and-drop
        self.list.setAcceptDrops(True)
        self.list.setDragEnabled(False)  # We only accept drops, not initiate drags
        self.list.viewport().setAcceptDrops(True)
        self.list.dragEnterEvent = self._drag_enter_event
        self.list.dragMoveEvent = self._drag_move_event
        self.list.dropEvent = self._drop_event

        layout.addWidget(self.list, 1)

        help_card = QLabel("Tip: drag a game onto a manual collection to organize it.")
        help_card.setWordWrap(True)
        help_card.setMaximumHeight(84)
        help_card.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {theme.surface_alt.name(QColor.HexArgb)}, stop:1 rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},38)); "
            f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; border-radius: {theme.radius_lg}px; "
            f"padding: {theme.spacing_lg}px; color: {theme.text.name()}; font-size: 12px;"
        )
        layout.addWidget(help_card)

        # New collection button at bottom
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(theme.spacing_sm, theme.spacing_xs, theme.spacing_sm, 0)
        self.new_btn = QPushButton(f"{AppIcons.ACT_ADD}  New Collection")
        self.new_btn.setStyleSheet(ghost_btn_style(theme))
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.setToolTip("Create a new collection")
        self.new_btn.setMinimumWidth(0)
        self.new_btn.clicked.connect(lambda: self.new_collection_requested.emit())
        btn_row.addWidget(self.new_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Version label
        self._ver_label = QLabel("v4.0")
        self._ver_label.setStyleSheet(
            f"color: {theme.text_muted.name()}; font-size: 10px; "
            f"padding: {theme.spacing_xs}px {theme.spacing_lg}px; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._ver_label)

        self._collections: List[Collection] = []
        self._games = None
        self._updates_count = 0
        self._health_count = 0
        self._downloads_count = 0

        # Animation for collapse/expand
        self._width_anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._width_anim.setDuration(200 if not is_reduced_motion() else 0)
        self._width_anim.setEasingCurve(QEasingCurve.OutCubic)

    # ---- public API ----
    def set_games(self, games) -> None:
        self._games = games

    def set_collections(self, collections: List[Collection], games=None) -> None:
        if games is not None:
            self._games = games
        self._collections = collections or []
        key = self.current_key() or "all"
        all_count = len(self._games) if self._games else 0
        self.populate(
            all_count, self._updates_count, self._health_count,
            self._collections, key, self._downloads_count,
        )

    def populate(
        self,
        all_count: int,
        updates_count: int,
        health_count: int,
        collections: List[Collection],
        selected_key: str = "all",
        downloads_count: int = 0,
    ) -> None:
        self._updates_count = updates_count
        self._health_count = health_count
        self._downloads_count = downloads_count
        self._collections = collections or []
        self.list.blockSignals(True)
        self.list.clear()

        fm = self.list.fontMetrics()
        max_w = max(160, self.list.viewport().width() - 24)

        if self._collapsed:
            self._add_icon_item(AppIcons.NAV_HOME, "Home", -1, "home")
            self._add_icon_item(AppIcons.NAV_LIBRARY, "All Games", all_count, "all")
            for c in sorted(
                [c for c in self._collections if c.type == "manual"],
                key=lambda x: x.name.lower(),
            ):
                cnt = self._collection_count(c)
                self._add_icon_item(
                    AppIcons.NAV_COLLECTION, c.name, cnt,
                    _collection_key(c.collection_id),
                )
            for c in sorted(
                [c for c in self._collections if c.type == "smart"],
                key=lambda x: x.name.lower(),
            ):
                cnt = self._collection_count(c)
                self._add_icon_item(
                    AppIcons.NAV_SMART, c.name, cnt,
                    _collection_key(c.collection_id),
                )
            self._add_icon_item(AppIcons.NAV_UPDATES, "Updates", updates_count, "updates")
            self._add_icon_item(AppIcons.NAV_HEALTH, "Health Checks", health_count, "health")
            self._add_icon_item(AppIcons.ACT_DOWNLOAD, "Downloads", downloads_count, "downloads")
            self._add_icon_item(AppIcons.ACT_IMPORT, "Add Games", -1, "import")
            self._add_icon_item(AppIcons.ACT_SETTINGS, "Settings", -1, "settings")
        else:
            self._add_nav_item(AppIcons.NAV_HOME, "Home", -1, "home", fm, max_w)
            self._add_nav_item(AppIcons.NAV_LIBRARY, "All Games", all_count, "all", fm, max_w)

            manual = sorted(
                [c for c in self._collections if c.type == "manual"],
                key=lambda x: x.name.lower(),
            )
            if manual:
                self._add_section_header("COLLECTIONS")
                for c in manual:
                    cnt = self._collection_count(c)
                    self._add_nav_item(
                        AppIcons.NAV_COLLECTION, c.name, cnt,
                        _collection_key(c.collection_id), fm, max_w,
                    )

            smart = sorted(
                [c for c in self._collections if c.type == "smart"],
                key=lambda x: x.name.lower(),
            )
            if smart:
                self._add_section_header("SMART")
                for c in smart:
                    cnt = self._collection_count(c)
                    self._add_nav_item(
                        AppIcons.NAV_SMART, c.name, cnt,
                        _collection_key(c.collection_id), fm, max_w,
                    )

            self._add_section_header("TOOLS")
            self._add_nav_item(AppIcons.NAV_UPDATES, "Updates", updates_count, "updates", fm, max_w)
            self._add_nav_item(AppIcons.NAV_HEALTH, "Health Checks", health_count, "health", fm, max_w)
            self._add_nav_item(AppIcons.ACT_DOWNLOAD, "Downloads", downloads_count, "downloads", fm, max_w)
            self._add_nav_item(AppIcons.ACT_IMPORT, "Add Games", -1, "import", fm, max_w)
            self._add_nav_item(AppIcons.ACT_SETTINGS, "Settings", -1, "settings", fm, max_w)

        # Select the item while signals are still blocked.  Callers always
        # handle state updates (e.g. _apply_search) explicitly, so emitting
        # nav_changed here would be redundant and can crash during init when
        # widgets like _footer_count don't exist yet.
        self.set_selected(selected_key)
        self.list.blockSignals(False)

    def update_counts(self, all_count: int, updates_count: int, health_count: int) -> None:
        key = self.current_key() or "all"
        self.populate(all_count, updates_count, health_count, self._collections, key)

    def set_selected(self, key: str) -> None:
        if not key:
            return
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it and it.data(Qt.UserRole) == key:
                self.list.setCurrentRow(i)
                return

    def current_key(self) -> Optional[str]:
        it = self.list.currentItem()
        if not it:
            return None
        return it.data(Qt.UserRole)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        """Collapse or expand the sidebar."""
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._update_collapsed_visuals()

        target_width = self._collapsed_width if collapsed else self._expanded_width
        if animate and not is_reduced_motion():
            # Set minimum width to collapsed width for smooth animation in both directions
            self.setMinimumWidth(self._collapsed_width)
            self._width_anim.stop()
            # Disconnect any previous finished handler to prevent stacking
            try:
                self._width_anim.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._width_anim.setStartValue(self.maximumWidth())
            self._width_anim.setEndValue(target_width)
            self._width_anim.finished.connect(
                lambda: self._on_collapse_anim_finished(collapsed)
            )
            self._width_anim.start()
        else:
            self.setMaximumWidth(target_width)
            self.setMinimumWidth(target_width)

        # Repopulate with collapsed/expanded items
        key = self.current_key() or "all"
        all_count = len(self._games) if self._games else 0
        self.populate(
            all_count, self._updates_count, self._health_count,
            self._collections, key, self._downloads_count,
        )
        self.collapse_toggled.emit(collapsed)

    def _on_collapse_anim_finished(self, collapsed: bool) -> None:
        """Finalize min/max width after collapse animation completes."""
        try:
            self._width_anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        target = self._collapsed_width if collapsed else self._expanded_width
        self.setMinimumWidth(target)
        self.setMaximumWidth(self._theme.sidebar_width_max if not collapsed else target)

    def select_by_index(self, index: int) -> None:
        """Select a sidebar item by index (for keyboard shortcuts)."""
        selectable_rows = [
            row for row in range(self.list.count())
            if self.list.item(row) and self.list.item(row).data(Qt.UserRole)
        ]
        if 0 <= index < len(selectable_rows):
            self.list.setCurrentRow(selectable_rows[index])

    # ---- private helpers ----
    def _update_collapsed_visuals(self) -> None:
        """Show/hide text elements based on collapsed state."""
        show = not self._collapsed
        self._title_label.setVisible(show)
        self.new_btn.setVisible(show)
        self._ver_label.setVisible(show)
        self._collapse_btn.setText(
            AppIcons.UI_CHEVRON_RIGHT if self._collapsed else AppIcons.UI_CHEVRON_LEFT
        )
        self._collapse_btn.setToolTip(
            "Expand sidebar" if self._collapsed else "Collapse sidebar"
        )

    def _toggle_collapse(self) -> None:
        self._pinned_expanded = self._collapsed  # Toggle pin state
        self.set_collapsed(not self._collapsed)

    def _add_section_header(self, text: str) -> None:
        theme = self._theme
        item = QListWidgetItem(f"  {text}")
        item.setFlags(Qt.NoItemFlags)
        font = item.font()
        font.setPointSize(9)
        font.setWeight(QFont.Bold)
        item.setFont(font)
        item.setForeground(theme.text_muted)
        item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), 36))
        self.list.addItem(item)

    def _add_nav_item(
        self, icon: str, label: str, count: int,
        key: str, fm, max_w: int,
    ) -> None:
        count_str = f"  ·  {count}" if count >= 0 else ""
        display = f"{icon}  {label}{count_str}"
        elided = fm.elidedText(display, Qt.ElideRight, max_w)
        item = QListWidgetItem(elided)
        item.setToolTip(f"{label} ({count})" if count >= 0 else label)
        item.setData(Qt.UserRole, key)
        item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), 38))
        self.list.addItem(item)

    def _add_icon_item(self, icon: str, label: str, count: int, key: str) -> None:
        """Add an icon-only item for collapsed mode."""
        item = QListWidgetItem(icon)
        item.setTextAlignment(Qt.AlignCenter)
        item.setToolTip(f"{label} ({count})" if count >= 0 else label)
        item.setData(Qt.UserRole, key)
        item.setSizeHint(item.sizeHint().__class__(self._collapsed_width - 8, 38))
        self.list.addItem(item)

    def _collection_count(self, coll: Collection) -> int:
        try:
            if self._games is not None:
                return len(apply_collection(self._games, coll))
            if hasattr(coll, "game_ids") and coll.game_ids is not None:
                return len(coll.game_ids)
        except Exception:
            pass
        return 0

    def _on_row_changed(self, idx: int) -> None:
        it = self.list.item(idx)
        if not it:
            return
        key = it.data(Qt.UserRole)
        if not key:
            return
        self.nav_changed.emit(str(key))

    def _on_context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.UserRole)
        if not key or not key.startswith("collection:"):
            return

        coll_id = key.replace("collection:", "")
        menu = QMenu(self)
        rename_act = menu.addAction(f"{AppIcons.ACT_EDIT}  Rename")
        delete_act = menu.addAction(f"{AppIcons.ACT_REMOVE}  Delete")

        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen == rename_act:
            self.rename_collection_requested.emit(coll_id)
        elif chosen == delete_act:
            self.delete_collection_requested.emit(coll_id)

    # ---- Drag-and-drop handlers ----
    def _drag_enter_event(self, event) -> None:
        """Handle drag enter event."""
        if event.mimeData().hasText() or event.mimeData().hasFormat("application/x-game-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move_event(self, event) -> None:
        """Handle drag move event."""
        if event.mimeData().hasText() or event.mimeData().hasFormat("application/x-game-id"):
            # Check if we're over a collection item
            item = self.list.itemAt(event.position().toPoint())
            if item:
                key = item.data(Qt.UserRole)
                if key and key.startswith("collection:"):
                    event.acceptProposedAction()
                    # Highlight the item being hovered over
                    self.list.setCurrentItem(item)
                    return
        event.ignore()

    def _drop_event(self, event) -> None:
        """Handle drop event."""
        if not (event.mimeData().hasText() or event.mimeData().hasFormat("application/x-game-id")):
            event.ignore()
            return

        # Get the item we dropped on
        item = self.list.itemAt(event.position().toPoint())
        if not item:
            event.ignore()
            return

        key = item.data(Qt.UserRole)
        if not key or not key.startswith("collection:"):
            event.ignore()
            return

        # Extract game ID and collection ID
        game_id = event.mimeData().text()
        collection_id = key.replace("collection:", "")

        # Emit signal for parent to handle
        self.game_dropped_on_collection.emit(game_id, collection_id)
        event.acceptProposedAction()

    def resizeEvent(self, event) -> None:
        """Refresh item labels on resize to re-elide text for current width."""
        super().resizeEvent(event)
        if self._collapsed:
            return
        # Only re-elide if width actually changed
        new_w = self.list.viewport().width()
        if new_w == getattr(self, '_last_elide_width', -1):
            return
        self._last_elide_width = new_w
        fm = self.list.fontMetrics()
        max_w = max(120, new_w - 24)
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item:
                continue
            tooltip = item.toolTip()
            key = item.data(Qt.UserRole)
            if not key or not tooltip:
                continue  # Skip section headers
            elided = fm.elidedText(tooltip, Qt.ElideRight, max_w)
            if elided != item.text():
                item.setText(elided)

    # Sidebar expand/collapse is controlled only by the toggle button,
    # not by hover, to prevent accidental distracting layout shifts.
