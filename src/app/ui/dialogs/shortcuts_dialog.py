"""Keyboard shortcuts help dialog."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QHBoxLayout
)


class ShortcutsDialog(QDialog):
    """Shows all keyboard shortcuts in a clean table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)

        # Define shortcuts data
        shortcuts = [
            ("Navigation", ""),
            ("Ctrl+F or /", "Focus search bar"),
            ("Escape", "Clear search / Exit select mode / Close details"),
            ("Ctrl+G", "Focus grid"),
            ("Ctrl+1-5", "Navigate to sidebar section"),
            ("Return/Enter", "Launch selected game"),
            ("E", "Edit selected game (open details panel)"),
            ("", ""),
            ("Game Management", ""),
            ("Delete", "Delete selected game"),
            ("Ctrl+N", "New collection"),
            ("Ctrl+S", "Force save library"),
            ("F5", "Scan for new games"),
            ("Ctrl+U", "Check for updates"),
            ("Ctrl+P", "Pick a playable game from the current view"),
            ("", ""),
            ("Selection & Editing", ""),
            ("Ctrl+A", "Select all games"),
            ("Ctrl+Z", "Undo"),
            ("Ctrl+Shift+Z or Ctrl+Y", "Redo"),
            ("", ""),
            ("View & Display", ""),
            ("Ctrl+D", "Toggle details panel"),
            ("Ctrl+Shift+F", "Toggle focus mode"),
            ("", ""),
            ("Import & Export", ""),
            ("Ctrl+E", "Export library"),
            ("Ctrl+I", "Import library"),
            ("Ctrl+Shift+I", "Add shortcut files directly"),
            ("Ctrl+,", "Open settings page"),
            ("", ""),
            ("Customization", ""),
            ("Ctrl+T", "Open theme editor"),
            ("Ctrl+L", "Open layout customization"),
            ("Ctrl+Shift+R", "Reset layout"),
            ("", ""),
            ("Help", ""),
            ("Ctrl+Shift+/", "Show this shortcuts help"),
        ]

        self.table.setRowCount(len(shortcuts))

        for row, (key, action) in enumerate(shortcuts):
            # Key column
            key_item = QTableWidgetItem(key)
            if not action:  # Section headers
                font = QFont()
                font.setBold(True)
                key_item.setFont(font)
                key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            else:
                key_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, key_item)

            # Action column
            action_item = QTableWidgetItem(action)
            if not action:  # Section headers
                font = QFont()
                font.setBold(True)
                action_item.setFont(font)
            action_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 1, action_item)

        layout.addWidget(self.table)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
