"""Scan operations mixin for MainWindow."""
from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
from pathlib import Path
import os
import sys
import subprocess

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QFileDialog

from app.models import Game
from app.storage import settings_json_path
from app.services import (
    find_duplicate_shortcuts_in_root, move_duplicates_to_quarantine,
    merge_scanned_into_library, pixmap_for_game,
)
from app.ui.dialogs import ScanWorker
from app.ui.widgets import show_success, show_error
from app.logging_utils import kv

if TYPE_CHECKING:
    from .window import MainWindow


class ScanMixin:
    """Mixin providing scan operations for MainWindow."""

    def _on_scan_clicked(self: "MainWindow") -> None:
        if self._scan_thread:
            QMessageBox.information(self, "Scan in progress", "A scan is already running. Please wait for it to finish.")
            return

        if not self._root_folder:
            self._choose_root_folder()
            if not self._root_folder:
                return

        root_path = Path(self._root_folder)
        if not root_path.exists() or not root_path.is_dir():
            choice = QMessageBox.question(
                self,
                "Shortcuts root missing",
                f"The configured shortcuts root no longer exists:\n\n{self._root_folder}\n\nPick a new folder now?",
            )
            if choice == QMessageBox.Yes:
                self._choose_root_folder()
                if not self._root_folder:
                    return
                root_path = Path(self._root_folder)
            else:
                return

        # 1) detect duplicates first
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            dups = find_duplicate_shortcuts_in_root(str(root_path))
        finally:
            QApplication.restoreOverrideCursor()
        if dups:
            lines = []
            for k, paths in dups.items():
                names = ", ".join([p.name for p in sorted(paths, key=lambda p: p.name.lower())])
                lines.append(f"- {k}: {names}")

            msg = (
                "Found duplicate shortcut files in the shortcuts root.\n\n"
                "Examples: Game.lnk and Game (1).lnk\n\n"
                "Duplicates:\n"
                + "\n".join(lines)
                + "\n\nMove duplicates to a quarantine folder now? (Recommended)"
            )

            choice = QMessageBox.question(self, "Duplicates found", msg, QMessageBox.Yes | QMessageBox.No)
            if choice == QMessageBox.Yes:
                quarantine = move_duplicates_to_quarantine(self._root_folder, dups)
                QMessageBox.information(
                    self, "Duplicates moved",
                    f"Moved duplicates to:\n{quarantine}\n\nKept the first file in root for each group."
                )

        # 2) Confirm scan target
        msg = f"Scan this shortcuts folder?\n\n{self._root_folder}\n\n(Top level only: .lnk / .url / .html)"
        if QMessageBox.question(self, "Scan shortcuts", msg) != QMessageBox.Yes:
            return

        self._start_scan_thread(str(root_path))

    def _on_import_shortcuts_clicked(self: "MainWindow") -> None:
        """Add selected .lnk/.url/.html files directly to the library."""
        if self._scan_thread:
            QMessageBox.information(
                self, "Scan in progress",
                "Wait for the current folder scan to finish before adding more shortcuts.",
            )
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Game Shortcuts",
            self._root_folder or str(Path.home()),
            "Game shortcuts (*.lnk *.url *.html);;Windows shortcuts (*.lnk);;Internet shortcuts (*.url);;HTML files (*.html)",
        )
        if not paths:
            return

        self._start_scan_thread(paths=paths)

    def _choose_and_scan_root(self: "MainWindow") -> None:
        """Always ask for a shortcut folder, then immediately scan it."""
        if self._choose_root_folder():
            self._on_scan_clicked()

    def _open_scanner_project(self: "MainWindow") -> None:
        """Launch relocated Scanner without blocking this Qt loop."""
        try:
            project_root = Path(__file__).resolve().parents[3]
            scanner_root = project_root / "external" / "scanner" / "GameShortcutMaker"
            entry = scanner_root / "app.py"
            if not entry.exists():
                raise FileNotFoundError(f"Scanner entry not found at {entry}")

            cmd = [
                sys.executable,
                "-c",
                "from external.scanner.GameShortcutMaker.app import run_app; run_app()",
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)
            subprocess.Popen(cmd, cwd=str(project_root), env=env)
            self.statusBar().showMessage("Opening Scanner…", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Open Scanner failed", f"{e}")

    def _choose_root_folder(self: "MainWindow") -> bool:
        folder = QFileDialog.getExistingDirectory(self, "Choose shortcuts root folder")
        if not folder:
            return False
        self._root_folder = folder
        self._settings["root_folder"] = folder
        self._persist_settings()
        if hasattr(self, "import_page"):
            self.import_page.set_root_folder(folder)
        if hasattr(self, "settings_page"):
            self.settings_page.set_values(self._settings_snapshot())
        self.statusBar().showMessage(f"Root folder set: {folder}", 5000)
        return True

    def _start_scan_thread(
        self: "MainWindow",
        root_folder: str = "",
        paths: Optional[List[str]] = None,
    ) -> None:
        source = root_folder or f"{len(paths or [])} selected files"
        self._log.info("scan_start %s", kv(event="scan", path=source))
        # progress dialog
        action = "Adding shortcuts" if paths else "Scanning"
        self._progress_dialog = QProgressDialog(f"{action}…\n{source}", "Cancel", 0, 0, self)
        self._progress_dialog.setWindowTitle(action)
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setMinimumWidth(420)
        self._progress_dialog.canceled.connect(self._cancel_scan)
        self._progress_dialog.show()
        self.scan_btn.setEnabled(False)

        # thread + worker
        self._scan_thread = QThread()
        self._scan_worker = ScanWorker(root_folder, paths=paths)
        self._scan_worker.moveToThread(self._scan_thread)

        # Use queued connections so UI updates stay on the main thread.
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress, Qt.QueuedConnection)
        self._scan_worker.finished.connect(self._on_scan_finished, Qt.QueuedConnection)
        self._scan_worker.failed.connect(self._on_scan_failed, Qt.QueuedConnection)

        self._scan_thread.start()

    def _cancel_scan(self: "MainWindow") -> None:
        if self._scan_worker:
            try:
                self._scan_worker.stop()
            except Exception:
                pass
        if self._progress_dialog:
            self._progress_dialog.setLabelText("Cancelling… (will stop after current file)")
            self._progress_dialog.setCancelButton(None)

    def _on_scan_progress(self: "MainWindow", msg: str, current: int = 0, total: int = 0) -> None:
        if self._progress_dialog:
            self._progress_dialog.setLabelText(msg)
            if total > 0:
                self._progress_dialog.setRange(0, total)
                self._progress_dialog.setValue(current)
            else:
                self._progress_dialog.setRange(0, 0)
        if self._log_rate.allow("scan_progress_log", 500):
            self._log.debug("scan_progress %s", kv(msg=msg, current=current, total=total))

    def _on_scan_failed(self: "MainWindow", err: str) -> None:
        self._cleanup_scan_thread()
        self._log.error("scan_failed %s", kv(err=err))
        self._notify_async_error(f"Scan failed: {err}")

    def _on_scan_finished(self: "MainWindow", games: list) -> None:
        cancelled = getattr(self._scan_worker, "cancelled", False) if self._scan_worker else False
        self._cleanup_scan_thread()

        if cancelled:
            self.statusBar().showMessage("Scan cancelled. No changes applied.", 6000)
            self._log.info("scan_cancelled %s", kv(event="scan", scanned=len(games)))
            return

        before = len(self._all_games)
        before_keys = {self._game_key(g) for g in self._all_games}
        scanned_keys = {self._game_key(g) for g in games}

        self._repo.update_all(merge_scanned_into_library(self._all_games, games))
        after = len(self._all_games)
        delta = after - before
        new_count = len(scanned_keys - before_keys)
        updated_count = len(scanned_keys & before_keys)

        # Prime icons only for items touched by this scan
        to_prime = [g for g in self._all_games if (self._game_key(g) in scanned_keys) and (not getattr(g, "icon_upscaled", False))]
        icons_refreshed = self._prime_icons(to_prime)
        self._persist_library()
        self._flush_save()  # immediate write after scan — don't defer bulk changes

        # Notify all subscribers that games have changed
        from app.events import AppEvent
        self._bus.emit(AppEvent.SCAN_COMPLETE, {"new": new_count, "updated": updated_count})
        self._bus.emit(AppEvent.GAMES_CHANGED)
        self._refresh_scan_views()

        msg_lines = [
            f"Shortcuts read: {len(games)}",
            f"New entries: {new_count}",
            f"Updated: {updated_count}",
            f"Icons refreshed: {icons_refreshed}",
            f"Library total: {after} ({'+' if delta>=0 else ''}{delta} vs previous)",
        ]
        msg = "Scan finished: no shortcut files found." if len(games) == 0 else "\n".join(msg_lines)
        self.statusBar().showMessage(msg, 8000)
        if len(games) == 0:
            show_error("No shortcuts found in the selected folder.")
        else:
            show_success(f"Scan complete: {new_count} new, {updated_count} updated games.")
        if hasattr(self, "import_page"):
            self.import_page.set_result(
                f"Added {new_count} new games and refreshed {updated_count} existing entries."
            )
        self._log.info(
            "scan_done %s",
            kv(event="scan", scanned=len(games), total=after, delta=delta, cancelled=cancelled),
        )

    def _cleanup_scan_thread(self: "MainWindow") -> None:
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None

        if self._scan_thread:
            self._scan_thread.quit()
            self._scan_thread.wait()
            self._scan_thread = None

        self._scan_worker = None
        self.scan_btn.setEnabled(True)

    def _refresh_scan_views(self: "MainWindow") -> None:
        """Refresh sidebar counts and any visible secondary views after a scan."""
        key = self.sidebar.current_key() if hasattr(self, "sidebar") else "all"
        select_kind = "all"
        select_id = None
        if key == "updates":
            select_kind = "updates"
        elif key == "health":
            select_kind = "health"
        elif key and key.startswith("collection:"):
            select_kind = "collection"
            select_id = key.split(":", 1)[1]

        self._rebuild_sidebar(select_kind=select_kind, select_id=select_id)

        if hasattr(self, "health") and self.health.isVisible():
            self.health.set_games(self._all_games)
            self.health.set_ignored(self._ignored_health)
        if hasattr(self, "updates") and self.updates.isVisible():
            self.updates.set_games(self._all_games)

    def _prime_icons(self: "MainWindow", games: List[Game], size: int = 256) -> int:
        """Warm high-quality icons for scanned games once."""
        count = 0
        seen_paths = set()
        for g in games:
            if getattr(g, "icon_upscaled", False):
                continue
            path = getattr(g, "shortcut_path", "") or ""
            if not path:
                continue
            key = path.lower()
            if key in seen_paths:
                continue
            seen_paths.add(key)
            try:
                pm = pixmap_for_game(g, size=size)
                if not pm.isNull():
                    g.icon_upscaled = True
                    count += 1
            except Exception as e:
                if self._log_rate.allow("icon_prime_error", 1500):
                    self._log.warning("icon_prime_error %s", kv(path=path, err=e))
        return count

    def _game_key(self: "MainWindow", g: Game) -> str:
        try:
            return str(Path(g.shortcut_path)).lower()
        except Exception:
            return g.shortcut_path.lower() if getattr(g, "shortcut_path", "") else ""
