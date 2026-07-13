"""Centralized icon system for consistent iconography across the app.

Uses carefully selected Unicode glyphs that render well across Windows fonts.
All icons are accessed through the AppIcons class to ensure consistency.
"""
from __future__ import annotations


class AppIcons:
    """Centralized icon definitions for the application.

    Icons are chosen for visual clarity at small sizes and consistent
    rendering on Windows with Segoe UI / Segoe UI Symbol.
    """

    # Navigation — distinct, recognizable at 14-18px
    NAV_HOME = "\U0001F3E0"       # House / Home landing page
    NAV_LIBRARY = "\U0001F3AE"    # Game controller / Library
    NAV_UPDATES = "\U0001F504"    # Counterclockwise arrows / Refresh
    NAV_HEALTH = "\U0001F6E1"     # Shield / Health checks
    NAV_COLLECTION = "\U0001F4C1" # Folder / Collection
    NAV_SMART = "\u2728"          # Sparkles / Smart collection
    NAV_TOOLS = "\u2699\uFE0F"    # Gear / Tools

    # Actions — clear intent at a glance
    ACT_SCAN = "\u25B6"           # Play triangle / Scan
    ACT_PLAY = "\u25B6"           # Play triangle
    ACT_FOLDER = "\U0001F4C2"     # Open folder
    ACT_SEARCH = "\U0001F50D"     # Magnifying glass
    ACT_FILTER = "\U0001F50E"     # Filter / magnifying glass right
    ACT_SETTINGS = "\u2699"       # Gear
    ACT_ADD = "+"                 # Plus
    ACT_REMOVE = "\u2715"         # X mark
    ACT_EDIT = "\u270F\uFE0F"     # Pencil
    ACT_EXPORT = "\u21E5"         # Right arrow / Export
    ACT_IMPORT = "\u21E4"         # Left arrow / Import
    ACT_CLOSE = "\u2715"          # X mark
    ACT_DOWNLOAD = "\u2B07"       # Down arrow / Download

    # Status indicators — semantically distinct
    STS_BACKLOG = "\u25CB"        # Circle outline / Not started
    STS_PLAYING = "\u25B6"        # Play / Active
    STS_FINISHED = "\u2714"       # Heavy checkmark / Done
    STS_DROPPED = "\u2718"        # Heavy X / Dropped
    STS_UPDATE = "\u2B06"         # Up arrow / Update available

    # Feedback — standard signal icons
    FB_SUCCESS = "\u2714"         # Heavy checkmark
    FB_WARNING = "\u26A0"         # Warning triangle
    FB_ERROR = "\u2718"           # Heavy X mark
    FB_INFO = "\u2139"            # Info circle

    # UI elements — chrome & decoration
    UI_CHEVRON_RIGHT = "\u203A"   # Single right angle quote
    UI_CHEVRON_DOWN = "\u2304"    # Down caret
    UI_CHEVRON_LEFT = "\u2039"    # Single left angle quote
    UI_DOTS = "\u22EF"            # Horizontal ellipsis
    UI_STAR_FULL = "\u2605"       # Filled star
    UI_STAR_EMPTY = "\u2606"      # Empty star
    UI_CLOCK = "\U0001F552"       # Clock face 3 o'clock
    UI_TAG = "\U0001F3F7"         # Label / Tag
    UI_PIN = "\U0001F4CC"         # Pin
    UI_DRAG = "\u2630"            # Trigram / drag handle
    UI_EXPAND = "\u25B8"          # Right-pointing triangle (collapsed)
    UI_COLLAPSE = "\u25BE"        # Down-pointing triangle (expanded)
    UI_ARROW_LEFT = "\u2190"      # Left arrow
    UI_ARROW_RIGHT = "\u2192"     # Right arrow
    UI_PAGES = "\u2630"           # Trigram / Pages mode
    UI_SCROLL = "\u2195"          # Up-down arrow / Scroll mode
    UI_VIEW = "\u25a6"            # Square with grid / View options
    UI_FOCUS = "\u26f6"           # Square four corners / Focus (full-width) mode
    UI_DETAILS = "\u25e8"         # Square right-half black / Details side panel
    UI_SELECT = "\u2611"          # Ballot box with check / Multi-select mode
    UI_DICE = "\u2684"            # Die / Pick for me

    @staticmethod
    def status_icon(status: str) -> str:
        """Get the icon character for a game status."""
        return {
            "backlog": AppIcons.STS_BACKLOG,
            "playing": AppIcons.STS_PLAYING,
            "finished": AppIcons.STS_FINISHED,
            "dropped": AppIcons.STS_DROPPED,
        }.get(status, AppIcons.STS_BACKLOG)

    @staticmethod
    def nav_icon(key: str) -> str:
        """Get the icon character for a navigation item."""
        return {
            "home": AppIcons.NAV_HOME,
            "all": AppIcons.NAV_LIBRARY,
            "updates": AppIcons.NAV_UPDATES,
            "health": AppIcons.NAV_HEALTH,
            "downloads": AppIcons.ACT_DOWNLOAD,
            "import": AppIcons.ACT_IMPORT,
            "settings": AppIcons.ACT_SETTINGS,
            "tools": AppIcons.NAV_TOOLS,
        }.get(key, AppIcons.NAV_COLLECTION)
