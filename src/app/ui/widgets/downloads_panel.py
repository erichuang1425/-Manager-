from __future__ import annotations
"""
Downloads Panel Widget for Game Library Manager.

Displays download queue, active downloads, and history.
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QFrame, QSizePolicy, QMenu, QLineEdit
)

from app.services.download_manager import (
    DownloadManager, DownloadItem, DownloadStatus,
    get_download_manager, format_size, format_speed, format_eta
)
from app.logging_utils import get_logger, kv, connect_safe, RateLimiter
from app.ui.theme import current_theme, chip_style
from app.ui.typography import get_scale, heading_style

_log = get_logger("ui.downloads")
_rate = RateLimiter()


class DownloadItemWidget(QFrame):
    """Widget representing a single download item."""

    pause_clicked = Signal(str)  # download_id
    resume_clicked = Signal(str)
    cancel_clicked = Signal(str)
    remove_clicked = Signal(str)

    def __init__(self, item: DownloadItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.item = item
        self._theme = current_theme()
        self._setup_ui()

    def _setup_ui(self) -> None:
        theme = self._theme
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background: {theme.surface.name(QColor.HexArgb)};
                border: 1px solid {theme.border.name(QColor.HexArgb)};
                border-radius: {theme.radius_md}px;
                padding: {theme.spacing_sm}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.spacing_sm, theme.spacing_sm, theme.spacing_sm, theme.spacing_sm)
        layout.setSpacing(theme.spacing_xs)

        # Title row
        title_row = QHBoxLayout()
        self.title_label = QLabel(self.item.game_title or "Download")
        self.title_label.setStyleSheet(f"font-weight: 600; color: {theme.text.name(QColor.HexArgb)};")
        title_row.addWidget(self.title_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)}; font-size: 11px;")
        title_row.addWidget(self.status_label)
        title_row.addStretch(1)

        # Action buttons
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFixedSize(60, 24)
        self.pause_btn.clicked.connect(lambda: self.pause_clicked.emit(self.item.download_id))

        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setFixedSize(60, 24)
        self.resume_btn.clicked.connect(lambda: self.resume_clicked.emit(self.item.download_id))
        self.resume_btn.hide()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(60, 24)
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.item.download_id))

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setFixedSize(60, 24)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.item.download_id))
        self.remove_btn.hide()

        title_row.addWidget(self.pause_btn)
        title_row.addWidget(self.resume_btn)
        title_row.addWidget(self.cancel_btn)
        title_row.addWidget(self.remove_btn)
        layout.addLayout(title_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {theme.border.name(QColor.HexArgb)};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {theme.accent.name(QColor.HexArgb)};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Info row
        info_row = QHBoxLayout()
        self.size_label = QLabel("0 B / 0 B")
        self.size_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)}; font-size: 11px;")
        info_row.addWidget(self.size_label)

        self.speed_label = QLabel("")
        self.speed_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)}; font-size: 11px;")
        info_row.addWidget(self.speed_label)

        self.eta_label = QLabel("")
        self.eta_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)}; font-size: 11px;")
        info_row.addStretch(1)
        info_row.addWidget(self.eta_label)
        layout.addLayout(info_row)

        self._update_ui()

    def _update_ui(self) -> None:
        """Update UI based on current item state."""
        item = self.item
        status = item.status

        # Update status label
        status_text = {
            DownloadStatus.QUEUED: "Queued",
            DownloadStatus.DOWNLOADING: "Downloading",
            DownloadStatus.PAUSED: "Paused",
            DownloadStatus.COMPLETED: "Completed",
            DownloadStatus.FAILED: f"Failed: {item.error_message[:50]}",
            DownloadStatus.CANCELLED: "Cancelled",
        }
        self.status_label.setText(status_text.get(status, "Unknown"))

        # Update progress
        progress = item.progress
        if progress.bytes_total > 0:
            self.progress_bar.setValue(int(progress.percent))
            self.size_label.setText(
                f"{format_size(progress.bytes_downloaded)} / {format_size(progress.bytes_total)}"
            )
        else:
            self.progress_bar.setValue(0)
            self.size_label.setText(format_size(progress.bytes_downloaded))

        # Update speed and ETA
        if status == DownloadStatus.DOWNLOADING:
            self.speed_label.setText(format_speed(progress.speed_bps))
            self.eta_label.setText(f"ETA: {format_eta(progress.eta_seconds)}")
        else:
            self.speed_label.setText("")
            self.eta_label.setText("")

        # Update button visibility
        if status == DownloadStatus.DOWNLOADING:
            self.pause_btn.show()
            self.resume_btn.hide()
            self.cancel_btn.show()
            self.remove_btn.hide()
        elif status == DownloadStatus.PAUSED:
            self.pause_btn.hide()
            self.resume_btn.show()
            self.cancel_btn.show()
            self.remove_btn.hide()
        elif status == DownloadStatus.QUEUED:
            self.pause_btn.hide()
            self.resume_btn.hide()
            self.cancel_btn.show()
            self.remove_btn.hide()
        else:  # Completed, Failed, Cancelled
            self.pause_btn.hide()
            self.resume_btn.hide()
            self.cancel_btn.hide()
            self.remove_btn.show()

    def update_progress(self, bytes_done: int, bytes_total: int, speed: float) -> None:
        """Update progress display."""
        self.item.progress.bytes_downloaded = bytes_done
        self.item.progress.bytes_total = bytes_total
        self.item.progress.speed_bps = speed
        if bytes_total > 0:
            self.item.progress.percent = (bytes_done / bytes_total) * 100
            remaining = bytes_total - bytes_done
            if speed > 0:
                self.item.progress.eta_seconds = remaining / speed
        self._update_ui()

    def set_status(self, status: DownloadStatus) -> None:
        """Update status."""
        self.item.status = status
        self._update_ui()


class DownloadsPanel(QWidget):
    """
    Panel showing download queue and progress.
    """

    open_folder_requested = Signal(str)  # path

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = current_theme()
        self._manager = get_download_manager()
        self._item_widgets: Dict[str, DownloadItemWidget] = {}

        self._setup_ui()
        self._connect_signals()
        self._start_refresh_timer()

    def _setup_ui(self) -> None:
        theme = self._theme
        scale = get_scale()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.spacing_sm)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Downloads")
        title.setStyleSheet(heading_style(theme, scale))
        header_row.addWidget(title)
        header_row.addStretch(1)

        # Filter buttons
        def make_filter_btn(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ {chip_style(theme)} }}
                QPushButton:checked {{ {chip_style(theme, active=True)} }}
                QPushButton:hover {{ border-color: {theme.focus.name(QColor.HexArgb)}; }}
            """)
            return btn

        self.filter_all = make_filter_btn("All")
        self.filter_active = make_filter_btn("Active")
        self.filter_completed = make_filter_btn("Done")
        self.filter_all.setChecked(True)

        for btn in (self.filter_all, self.filter_active, self.filter_completed):
            btn.clicked.connect(self._on_filter_clicked)
            header_row.addWidget(btn)

        layout.addLayout(header_row)

        # Direct queue entry: the panel used to be display-only, which made it
        # impossible to use unless another unfinished workflow added an item.
        queue_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste a direct download URL...")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(self._queue_entered_url)
        self.add_url_btn = QPushButton("Add Download")
        self.add_url_btn.clicked.connect(self._queue_entered_url)
        queue_row.addWidget(self.url_edit, 1)
        queue_row.addWidget(self.add_url_btn)
        layout.addLayout(queue_row)

        self.queue_status = QLabel("")
        self.queue_status.setWordWrap(True)
        self.queue_status.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)};")
        layout.addWidget(self.queue_status)

        # Actions row
        actions_row = QHBoxLayout()

        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self._on_clear_completed)
        actions_row.addWidget(self.clear_btn)

        self.cancel_all_btn = QPushButton("Cancel All")
        self.cancel_all_btn.setFixedHeight(28)
        self.cancel_all_btn.clicked.connect(self._on_cancel_all)
        actions_row.addWidget(self.cancel_all_btn)

        actions_row.addStretch(1)

        self.count_label = QLabel("0 downloads")
        self.count_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)};")
        actions_row.addWidget(self.count_label)

        layout.addLayout(actions_row)

        # Scroll area for download items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(theme.spacing_sm)
        self.scroll_layout.addStretch(1)

        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)

        # Empty state
        self.empty_label = QLabel("No downloads")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {theme.text_muted.name(QColor.HexArgb)}; padding: 40px;")
        self.scroll_layout.insertWidget(0, self.empty_label)

    def _connect_signals(self) -> None:
        """Connect to download manager signals."""
        self._manager.download_queued.connect(self._on_download_queued)
        self._manager.download_started.connect(self._on_download_started)
        self._manager.progress_updated.connect(self._on_progress_updated)
        self._manager.download_completed.connect(self._on_download_completed)
        self._manager.download_failed.connect(self._on_download_failed)
        self._manager.download_cancelled.connect(self._on_download_cancelled)
        self._manager.queue_changed.connect(self._refresh_list)

    def _start_refresh_timer(self) -> None:
        """Start timer to refresh display."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_list)
        self._refresh_timer.start(1000)  # Refresh every second

    def _on_filter_clicked(self) -> None:
        """Handle filter button click."""
        sender = self.sender()
        self.filter_all.setChecked(sender == self.filter_all)
        self.filter_active.setChecked(sender == self.filter_active)
        self.filter_completed.setChecked(sender == self.filter_completed)
        self._refresh_list()

    def _queue_entered_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url.lower().startswith(("http://", "https://")):
            self.queue_status.setText("Enter a complete http:// or https:// download URL.")
            return
        try:
            download_id = self.add_download(url)
        except Exception as exc:
            self.queue_status.setText(f"Could not queue download: {exc}")
            _log.exception("download_queue_ui_failed")
            return
        self.url_edit.clear()
        self.queue_status.setText(f"Download {download_id} added to the queue.")
        self._refresh_list()

    def _get_filter_mode(self) -> str:
        if self.filter_active.isChecked():
            return "active"
        elif self.filter_completed.isChecked():
            return "completed"
        return "all"

    def _refresh_list(self) -> None:
        """Refresh the download list display."""
        items = self._manager.get_all_items()
        filter_mode = self._get_filter_mode()

        # Filter items
        if filter_mode == "active":
            items = [i for i in items if i.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED)]
        elif filter_mode == "completed":
            items = [i for i in items if i.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)]

        # Sort: active first, then by creation time
        def sort_key(item: DownloadItem):
            status_order = {
                DownloadStatus.DOWNLOADING: 0,
                DownloadStatus.PAUSED: 1,
                DownloadStatus.QUEUED: 2,
                DownloadStatus.COMPLETED: 3,
                DownloadStatus.FAILED: 4,
                DownloadStatus.CANCELLED: 5,
            }
            return (status_order.get(item.status, 9), item.created_at)

        items.sort(key=sort_key)

        # Update count label
        active_count = len([i for i in self._manager.get_all_items() if i.status in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)])
        total_count = len(self._manager.get_all_items())
        self.count_label.setText(f"{active_count} active / {total_count} total")

        # Show/hide empty state
        self.empty_label.setVisible(len(items) == 0)

        # Update existing widgets and add new ones
        current_ids = set(i.download_id for i in items)
        existing_ids = set(self._item_widgets.keys())

        # Remove widgets for items no longer in list
        for did in existing_ids - current_ids:
            widget = self._item_widgets.pop(did)
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()

        # Add or update widgets
        for i, item in enumerate(items):
            if item.download_id not in self._item_widgets:
                widget = DownloadItemWidget(item)
                widget.pause_clicked.connect(self._on_pause)
                widget.resume_clicked.connect(self._on_resume)
                widget.cancel_clicked.connect(self._on_cancel)
                widget.remove_clicked.connect(self._on_remove)
                self._item_widgets[item.download_id] = widget
                # Insert before the stretch
                self.scroll_layout.insertWidget(i, widget)
            else:
                widget = self._item_widgets[item.download_id]
                widget.item = item
                widget._update_ui()

    def _on_download_queued(self, download_id: str) -> None:
        """Handle new download queued."""
        self._refresh_list()

    def _on_download_started(self, download_id: str) -> None:
        """Handle download started."""
        if download_id in self._item_widgets:
            self._item_widgets[download_id].set_status(DownloadStatus.DOWNLOADING)

    def _on_progress_updated(self, download_id: str, bytes_done: int, bytes_total: int, speed: float) -> None:
        """Handle progress update."""
        if download_id in self._item_widgets:
            self._item_widgets[download_id].update_progress(bytes_done, bytes_total, speed)

    def _on_download_completed(self, download_id: str, file_path: str) -> None:
        """Handle download completed."""
        if download_id in self._item_widgets:
            self._item_widgets[download_id].set_status(DownloadStatus.COMPLETED)
        _log.info("download_completed_ui %s", kv(id=download_id, path=file_path))

    def _on_download_failed(self, download_id: str, error: str) -> None:
        """Handle download failed."""
        if download_id in self._item_widgets:
            self._item_widgets[download_id].item.error_message = error
            self._item_widgets[download_id].set_status(DownloadStatus.FAILED)

    def _on_download_cancelled(self, download_id: str) -> None:
        """Handle download cancelled."""
        if download_id in self._item_widgets:
            self._item_widgets[download_id].set_status(DownloadStatus.CANCELLED)

    def _on_pause(self, download_id: str) -> None:
        """Handle pause button."""
        self._manager.pause(download_id)

    def _on_resume(self, download_id: str) -> None:
        """Handle resume button."""
        self._manager.resume(download_id)

    def _on_cancel(self, download_id: str) -> None:
        """Handle cancel button."""
        self._manager.cancel(download_id)

    def _on_remove(self, download_id: str) -> None:
        """Handle remove button."""
        self._manager.remove_from_queue(download_id)
        self._refresh_list()

    def _on_clear_completed(self) -> None:
        """Clear completed downloads."""
        count = self._manager.clear_completed()
        _log.info("downloads_cleared %s", kv(count=count))
        self._refresh_list()

    def _on_cancel_all(self) -> None:
        """Cancel all downloads."""
        self._manager.cancel_all()
        self._refresh_list()

    def add_download(
        self,
        url: str,
        game_id: Optional[str] = None,
        game_title: str = "",
        version: str = "",
    ) -> str:
        """
        Add a download to the queue.
        Returns download ID.
        """
        return self._manager.queue_download(
            url=url,
            game_id=game_id,
            game_title=game_title,
            version=version,
        )
