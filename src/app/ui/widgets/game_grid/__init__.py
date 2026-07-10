"""
Game Grid Package.

Displays games using Qt's native model/view/delegate pipeline (no per-card
widgets) for smooth scrolling and fast (re)rendering.

Classes:
    GameGrid: Container widget wiring the model/view/delegate together
    GameListModel: QAbstractListModel holding List[Game]
    GameCardDelegate: QStyledItemDelegate that paints each card
    GameGridView: IconMode QListView + input handling

Functions:
    status_label: Convert status code to display label
    confidence_icon: Get emoji icon for confidence level
    stars: Convert rating to star display
    relative_time: Convert datetime to relative time string
"""

from .grid import GameGrid
from .model import GameListModel, GameRole
from .delegate import GameCardDelegate
from .view import GameGridView
from .display_utils import status_label, confidence_icon, stars, relative_time

__all__ = [
    "GameGrid",
    "GameListModel",
    "GameRole",
    "GameCardDelegate",
    "GameGridView",
    "status_label",
    "confidence_icon",
    "stars",
    "relative_time",
]
