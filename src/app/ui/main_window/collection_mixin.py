"""Collection operations mixin for MainWindow."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import uuid

from PySide6.QtWidgets import QMessageBox, QInputDialog

from app.models import Collection
from app.logging_utils import kv

if TYPE_CHECKING:
    from .window import MainWindow


class CollectionMixin:
    """Mixin providing collection operations for MainWindow."""

    def _new_collection(self: "MainWindow") -> None:
        name, ok = QInputDialog.getText(self, "New Collection", "Collection name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        kind, ok2 = QInputDialog.getItem(
            self, "Collection Type", "Type:",
            [
                "manual",
                "smart (preset: Low confidence)",
                "smart (preset: HTML only)",
                "smart (preset: Backlog)",
                "smart (preset: Unplayed)",
            ],
            0, False
        )
        if not ok2:
            return

        c = Collection(collection_id=str(uuid.uuid4()), name=name)

        if kind == "manual":
            c.type = "manual"
            c.game_ids = []
        else:
            c.type = "smart"
            if "Low confidence" in kind:
                c.filter = {"confidence_in": ["low"]}
            elif "HTML only" in kind:
                c.filter = {"shortcut_type_in": ["html"]}
            elif "Backlog" in kind:
                c.filter = {"status_in": ["backlog"]}
            elif "Unplayed" in kind:
                c.filter = {"launch_count_max": 0}
            else:
                c.filter = {}

        # prevent duplicate names
        existing_names = {x.name.lower() for x in self._collections}
        if c.name.lower() in existing_names:
            QMessageBox.warning(self, "Name exists", "A collection with the same name already exists.")
            return

        self._collections.append(c)
        self._save_bundle()

        # jump to new collection in sidebar
        self._active_collection_id = c.collection_id
        self._refresh_ui_after_collections_change(keep_kind="collection", keep_id=c.collection_id)

    def _get_collection(self: "MainWindow", cid: Optional[str]) -> Optional[Collection]:
        if not cid:
            return None
        for c in self._collections:
            if c.collection_id == cid:
                return c
        return None

    def _nav_key(self: "MainWindow", kind: str, cid: Optional[str] = None) -> str:
        if kind == "collection" and cid:
            return f"collection:{cid}"
        return kind

    def _rename_active_collection(self: "MainWindow") -> None:
        c = self._get_collection(self._active_collection_id)
        if not c:
            return

        new_name, ok = QInputDialog.getText(self, "Rename Collection", "New name:", text=c.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        # prevent duplicate names
        if any(x.collection_id != c.collection_id and x.name.lower() == new_name.lower() for x in self._collections):
            QMessageBox.warning(self, "Name exists", "Another collection already uses that name.")
            return

        c.name = new_name
        self._save_bundle()
        self._rebuild_sidebar(select_kind="collection", select_id=c.collection_id)
        self._apply_search()

    def _delete_active_collection(self: "MainWindow") -> None:
        c = self._get_collection(self._active_collection_id)
        if not c:
            return

        if QMessageBox.question(self, "Delete Collection", f"Delete '{c.name}'?") != QMessageBox.Yes:
            return

        self._repo.set_collections(
            [x for x in self._collections if x.collection_id != c.collection_id]
        )
        self._active_collection_id = None
        self._save_bundle()

        self._rebuild_sidebar(select_kind="all")
        self._apply_search()

    def _on_nav_changed(self: "MainWindow", key: str) -> None:
        if not key:
            return
        if self._log_rate.allow("nav_change", 400):
            self._log.info("nav_change %s", kv(event="nav_change", key=key))

        is_library_view = key == "all" or key.startswith("collection:")

        # Resolve the target stack page from the nav key.
        if is_library_view:
            page = self.library_page
        else:
            page = {
                "home": self.home_page,
                "updates": self.updates,
                "health": self.health,
                "downloads": self.downloads,
                "import": self.import_page,
                "settings": self.settings_page,
            }.get(key)
        if page is None:
            if self._log_rate.allow("nav_unknown", 2000):
                self._log.warning("nav_change_unknown_key %s", kv(key=key))
            return

        self.page_stack.setCurrentWidget(page)

        # Details splitter panel: shown on the library page (per saved prefs),
        # hidden everywhere else — matching the previous behavior exactly.
        if is_library_view:
            self._apply_details_visibility()
        else:
            self._details_widget.hide()

        if is_library_view:
            if key == "all":
                self._active_collection_id = None
                self.content_title.setText("All Games")
            else:  # collection:<id>
                self._active_collection_id = key.split(":", 1)[1]
                c = self._get_collection(self._active_collection_id)
                self.content_title.setText(c.name if c else "Collection")

            c = self._get_collection(self._active_collection_id) if self._active_collection_id else None
            is_collection = c is not None
            self.rename_collection_btn.setEnabled(is_collection)
            self.delete_collection_btn.setEnabled(is_collection)
            self._apply_search()
            return

        # Non-library pages: no active collection, refresh page-specific data.
        self._active_collection_id = None
        self.rename_collection_btn.setEnabled(False)
        self.delete_collection_btn.setEnabled(False)

        if key == "home":
            self.home_page.refresh(self._all_games)
        elif key == "updates":
            self.updates.set_games(self._all_games)
        elif key == "health":
            self.health.set_games(self._all_games)
            self.health.set_ignored(self._ignored_health)
            self._settings["health_filter"] = self.health._filter_mode
            self._settings["health_density"] = self.health._density
            self._persist_settings()
        elif key == "downloads":
            self.downloads._refresh_list()
        elif key == "import":
            self.import_page.set_root_folder(self._root_folder)
        elif key == "settings":
            self.settings_page.set_values(self._settings_snapshot())

    def _rebuild_sidebar(self: "MainWindow", select_kind: str = "all", select_id: Optional[str] = None) -> None:
        selected_key = self._nav_key(select_kind, select_id)
        from app.services.filter_utils import game_needs_update
        updates_count = sum(1 for game in self._all_games if game_needs_update(game))
        health_count = 0
        if hasattr(self, "health"):
            health_count = len(self.health._collect_issues(self._all_games))
        downloads_count = 0
        if hasattr(self, "downloads"):
            downloads_count = len(self.downloads._manager.get_all_items())
        self.sidebar.set_games(self._all_games)
        self.sidebar.populate(
            all_count=len(self._all_games),
            updates_count=updates_count,
            health_count=health_count,
            collections=self._collections,
            selected_key=selected_key,
            downloads_count=downloads_count,
        )

    def _save_bundle(self: "MainWindow") -> None:
        self._repo.save()

    def _refresh_ui_after_collections_change(self: "MainWindow", keep_kind: str = "all", keep_id: Optional[str] = None) -> None:
        """Rebuild sidebar without forcibly resetting to All Games."""
        self._rebuild_sidebar(select_kind=keep_kind, select_id=keep_id)
        self._apply_search()
        self.statusBar().showMessage("Saved.", 2000)

    def _add_selected_to_collection(self: "MainWindow") -> None:
        if not self._selected_game_id:
            return

        g = self._get_game(self._selected_game_id)
        if not g:
            return

        manual = [c for c in self._collections if c.type == "manual"]
        if not manual:
            QMessageBox.information(self, "No manual collections", "Create a manual collection first.")
            return

        names = [c.name for c in sorted(manual, key=lambda x: x.name.lower())]
        choice, ok = QInputDialog.getItem(self, "Add to Collection", "Choose a manual collection:", names, 0, False)
        if not ok:
            return

        target = None
        for c in manual:
            if c.name == choice:
                target = c
                break
        if not target:
            return

        if not hasattr(target, "game_ids") or target.game_ids is None:
            target.game_ids = []

        if g.game_id not in target.game_ids:
            target.game_ids.append(g.game_id)
            self._save_bundle()
            self.statusBar().showMessage(f"Added '{g.title}' to '{target.name}'", 3000)
        else:
            self.statusBar().showMessage("Already in that collection.", 2000)

        self._apply_search()

    def _on_game_dropped_on_collection(self: "MainWindow", game_id: str, collection_id: str) -> None:
        """Handle drag-and-drop of game onto collection in sidebar."""
        g = self._get_game(game_id)
        if not g:
            return

        # Find the target collection
        target = None
        for c in self._collections:
            if c.collection_id == collection_id:
                target = c
                break

        if not target:
            return

        # Only allow adding to manual collections via drag-and-drop
        if target.type != "manual":
            self.statusBar().showMessage("Can only drag to manual collections", 2000)
            return

        if not hasattr(target, "game_ids") or target.game_ids is None:
            target.game_ids = []

        if g.game_id not in target.game_ids:
            target.game_ids.append(g.game_id)
            self._persist_library()
            self.statusBar().showMessage(f"Added '{g.title}' to '{target.name}'", 3000)
        else:
            self.statusBar().showMessage(f"'{g.title}' is already in '{target.name}'", 2000)

        self._apply_search()
