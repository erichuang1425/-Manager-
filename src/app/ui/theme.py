from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    bg: QColor
    surface: QColor
    surface_alt: QColor
    card: QColor
    card_border: QColor
    card_hover: QColor
    text: QColor
    text_muted: QColor
    accent: QColor
    accent_alt: QColor
    chip_bg: QColor
    chip_border: QColor
    focus: QColor
    outline: QColor
    shadow: QColor
    # Semantic status colors
    status_backlog: QColor = None  # type: ignore[assignment]
    status_playing: QColor = None  # type: ignore[assignment]
    status_finished: QColor = None  # type: ignore[assignment]
    status_dropped: QColor = None  # type: ignore[assignment]
    # Semantic feedback colors
    success: QColor = None  # type: ignore[assignment]
    warning: QColor = None  # type: ignore[assignment]
    error: QColor = None  # type: ignore[assignment]
    # Surface hierarchy
    surface_raised: QColor = None  # type: ignore[assignment]
    surface_sunken: QColor = None  # type: ignore[assignment]
    # Header gradient
    header_bg: QColor = None  # type: ignore[assignment]
    # Surface overlay (with alpha for dropdowns/modals)
    surface_overlay: QColor = None  # type: ignore[assignment]
    # Interactive states
    interactive_hover: QColor = None  # type: ignore[assignment]
    interactive_active: QColor = None  # type: ignore[assignment]
    interactive_muted: QColor = None  # type: ignore[assignment]
    # Feedback: info
    info: QColor = None  # type: ignore[assignment]
    # Gradient support (for header/hero gradients)
    gradient_start: QColor = None  # type: ignore[assignment]
    gradient_end: QColor = None  # type: ignore[assignment]
    # Design tokens - spacing (8px grid system)
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    spacing_xl: int = 24
    # Design tokens - border radius
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    radius_xl: int = 18
    radius_pill: int = 50
    # Design tokens - animation durations (ms)
    anim_fast: int = 100
    anim_normal: int = 180
    anim_slow: int = 280
    # Design tokens - elevation/shadow intensity (0-255 alpha)
    elevation_low: int = 20
    elevation_mid: int = 40
    elevation_high: int = 70
    # Layout dimensions
    sidebar_width_min: int = 220
    sidebar_width_max: int = 320
    details_width_min: int = 340
    details_width_max: int = 520
    toolbar_height: int = 48
    grid_gap: int = 16
    grid_padding: int = 20
    card_min_width: int = 200
    card_max_width: int = 320
    # Section spacing
    section_gap: int = 24
    content_gap: int = 16
    inline_gap: int = 8
    # Sidebar collapsed width (icon-only)
    sidebar_collapsed_width: int = 48


def _c(r: int, g: int, b: int, a: int = 255) -> QColor:
    return QColor(r, g, b, a)


THEMES: Dict[str, ThemeSpec] = {
    "dark": ThemeSpec(
        name="Dark",
        bg=_c(13, 19, 33),
        surface=_c(28, 35, 54, 235),
        surface_alt=_c(40, 48, 72, 225),
        card=_c(35, 44, 68, 230),
        card_border=_c(84, 98, 138, 105),
        card_hover=_c(112, 92, 255, 145),
        text=_c(242, 244, 252),
        text_muted=_c(166, 176, 202),
        accent=_c(132, 104, 255),
        accent_alt=_c(88, 216, 255),
        chip_bg=_c(74, 64, 116, 145),
        chip_border=_c(134, 110, 255, 90),
        focus=_c(132, 104, 255),
        outline=_c(78, 92, 130, 95),
        shadow=_c(0, 0, 0, 170),
        status_backlog=_c(120, 170, 230),
        status_playing=_c(80, 210, 130),
        status_finished=_c(255, 200, 80),
        status_dropped=_c(220, 100, 80),
        success=_c(80, 210, 130),
        warning=_c(255, 200, 80),
        error=_c(230, 75, 60),
        surface_raised=_c(48, 58, 86, 235),
        surface_sunken=_c(21, 27, 44, 240),
        header_bg=_c(23, 29, 47, 220),
        surface_overlay=_c(14, 20, 34, 225),
        interactive_hover=_c(58, 69, 102, 230),
        interactive_active=_c(49, 58, 88, 235),
        interactive_muted=_c(37, 45, 68, 220),
        info=_c(88, 216, 255),
        gradient_start=_c(18, 24, 42),
        gradient_end=_c(48, 40, 68),
        radius_sm=8, radius_md=12, radius_lg=16, radius_xl=20,
        toolbar_height=72, grid_gap=18, grid_padding=24,
        sidebar_width_min=220, details_width_min=340,
    ),
    "light": ThemeSpec(
        name="Light",
        bg=_c(243, 245, 249),
        surface=_c(249, 250, 253),
        surface_alt=_c(237, 240, 246),
        card=_c(255, 255, 255),
        card_border=_c(224, 228, 238),
        card_hover=_c(185, 208, 242),
        text=_c(24, 28, 36),
        text_muted=_c(100, 110, 128),
        accent=_c(56, 120, 240),
        accent_alt=_c(230, 90, 60),
        chip_bg=_c(232, 237, 246),
        chip_border=_c(208, 216, 230),
        focus=_c(56, 120, 240),
        outline=_c(214, 220, 232),
        shadow=_c(0, 0, 0, 50),
        status_backlog=_c(60, 130, 220),
        status_playing=_c(36, 168, 92),
        status_finished=_c(220, 152, 16),
        status_dropped=_c(205, 72, 56),
        success=_c(36, 168, 92),
        warning=_c(220, 152, 16),
        error=_c(215, 55, 45),
        surface_raised=_c(255, 255, 255),
        surface_sunken=_c(230, 234, 242),
        header_bg=_c(252, 253, 255),
        surface_overlay=_c(243, 245, 249, 225),
        interactive_hover=_c(226, 232, 244),
        interactive_active=_c(214, 222, 238),
        interactive_muted=_c(196, 204, 218),
        info=_c(56, 120, 240),
        gradient_start=_c(252, 253, 255),
        gradient_end=_c(237, 240, 246),
    ),
    "neubrutalism": ThemeSpec(
        name="Neubrutalism",
        bg=_c(247, 247, 247),
        surface=_c(250, 250, 250),
        surface_alt=_c(255, 255, 255),
        card=_c(255, 255, 255),
        card_border=_c(30, 30, 30),
        card_hover=_c(255, 245, 180),
        text=_c(20, 20, 20),
        text_muted=_c(60, 60, 60),
        accent=_c(255, 94, 91),
        accent_alt=_c(72, 133, 237),
        chip_bg=_c(255, 252, 190),
        chip_border=_c(30, 30, 30),
        focus=_c(72, 133, 237),
        outline=_c(30, 30, 30),
        shadow=_c(0, 0, 0, 180),
        status_backlog=_c(72, 133, 237),
        status_playing=_c(46, 196, 100),
        status_finished=_c(255, 200, 0),
        status_dropped=_c(255, 94, 91),
        success=_c(46, 196, 100),
        warning=_c(255, 200, 0),
        error=_c(255, 94, 91),
        surface_raised=_c(255, 255, 255),
        surface_sunken=_c(238, 238, 238),
        header_bg=_c(255, 255, 255),
        surface_overlay=_c(247, 247, 247, 230),
        interactive_hover=_c(255, 245, 180),
        interactive_active=_c(248, 238, 160),
        interactive_muted=_c(220, 220, 220),
        info=_c(72, 133, 237),
        gradient_start=_c(255, 255, 255),
        gradient_end=_c(247, 247, 247),
    ),
    "neumorphism": ThemeSpec(
        name="Neumorphism",
        bg=_c(228, 233, 241),
        surface=_c(235, 240, 247),
        surface_alt=_c(220, 226, 235),
        card=_c(235, 240, 247),
        card_border=_c(210, 216, 226),
        card_hover=_c(205, 213, 225),
        text=_c(46, 55, 70),
        text_muted=_c(100, 110, 125),
        accent=_c(126, 87, 194),
        accent_alt=_c(0, 191, 165),
        chip_bg=_c(220, 226, 235),
        chip_border=_c(210, 216, 226),
        focus=_c(126, 87, 194),
        outline=_c(190, 198, 212),
        shadow=_c(0, 0, 0, 70),
        status_backlog=_c(100, 140, 210),
        status_playing=_c(0, 191, 165),
        status_finished=_c(255, 180, 50),
        status_dropped=_c(210, 90, 70),
        success=_c(0, 191, 165),
        warning=_c(255, 180, 50),
        error=_c(210, 70, 60),
        surface_raised=_c(240, 245, 252),
        surface_sunken=_c(215, 220, 228),
        header_bg=_c(230, 235, 243),
        surface_overlay=_c(228, 233, 241, 210),
        interactive_hover=_c(215, 222, 234),
        interactive_active=_c(205, 213, 225),
        interactive_muted=_c(195, 202, 215),
        info=_c(126, 87, 194),
        gradient_start=_c(230, 235, 243),
        gradient_end=_c(220, 226, 235),
    ),
    "glassmorphism": ThemeSpec(
        name="Glassmorphism",
        bg=_c(12, 18, 30),
        surface=_c(20, 28, 44, 140),
        surface_alt=_c(28, 38, 58, 160),
        card=_c(32, 46, 70, 155),
        card_border=_c(92, 193, 255, 60),
        card_hover=_c(92, 193, 255, 110),
        text=_c(235, 242, 255),
        text_muted=_c(160, 180, 210),
        accent=_c(92, 193, 255),
        accent_alt=_c(255, 255, 255),
        chip_bg=_c(92, 193, 255, 35),
        chip_border=_c(92, 193, 255, 75),
        focus=_c(92, 193, 255),
        outline=_c(72, 120, 160, 65),
        shadow=_c(0, 0, 0, 100),
        status_backlog=_c(100, 180, 255),
        status_playing=_c(80, 230, 150),
        status_finished=_c(255, 200, 80),
        status_dropped=_c(255, 110, 90),
        success=_c(80, 230, 150),
        warning=_c(255, 200, 80),
        error=_c(255, 90, 70),
        surface_raised=_c(38, 54, 80, 170),
        surface_sunken=_c(10, 14, 24),
        header_bg=_c(16, 22, 36, 175),
        surface_overlay=_c(12, 18, 30, 180),
        interactive_hover=_c(40, 60, 90, 145),
        interactive_active=_c(50, 70, 100, 165),
        interactive_muted=_c(30, 44, 66, 125),
        info=_c(92, 193, 255),
        gradient_start=_c(16, 22, 36),
        gradient_end=_c(24, 36, 56),
    ),
    "high_contrast": ThemeSpec(
        name="High Contrast",
        bg=_c(0, 0, 0),
        surface=_c(0, 0, 0),
        surface_alt=_c(20, 20, 20),
        card=_c(0, 0, 0),
        card_border=_c(255, 255, 255),
        card_hover=_c(255, 255, 0),
        text=_c(255, 255, 255),
        text_muted=_c(255, 255, 255),
        accent=_c(0, 255, 255),
        accent_alt=_c(255, 255, 0),
        chip_bg=_c(0, 0, 0),
        chip_border=_c(255, 255, 255),
        focus=_c(255, 255, 0),
        outline=_c(255, 255, 255),
        shadow=_c(255, 255, 255, 80),
        status_backlog=_c(0, 255, 255),
        status_playing=_c(0, 255, 0),
        status_finished=_c(255, 255, 0),
        status_dropped=_c(255, 0, 0),
        success=_c(0, 255, 0),
        warning=_c(255, 255, 0),
        error=_c(255, 0, 0),
        surface_raised=_c(30, 30, 30),
        surface_sunken=_c(0, 0, 0),
        header_bg=_c(0, 0, 0),
        surface_overlay=_c(0, 0, 0, 240),
        interactive_hover=_c(40, 40, 40),
        interactive_active=_c(60, 60, 60),
        interactive_muted=_c(30, 30, 30),
        info=_c(0, 255, 255),
        gradient_start=_c(0, 0, 0),
        gradient_end=_c(20, 20, 20),
        # Larger focus indicators for accessibility
        radius_sm=4,
        radius_md=6,
        radius_lg=8,
        radius_xl=10,
    ),
    "nord": ThemeSpec(
        name="Nord",
        bg=_c(46, 52, 64),
        surface=_c(59, 66, 82),
        surface_alt=_c(67, 76, 94),
        card=_c(59, 66, 82),
        card_border=_c(76, 86, 106),
        card_hover=_c(94, 129, 172),
        text=_c(236, 239, 244),
        text_muted=_c(168, 178, 196),
        accent=_c(136, 192, 208),
        accent_alt=_c(191, 97, 106),
        chip_bg=_c(67, 76, 94),
        chip_border=_c(76, 86, 106),
        focus=_c(136, 192, 208),
        outline=_c(76, 86, 106),
        shadow=_c(0, 0, 0, 130),
        status_backlog=_c(129, 161, 193),
        status_playing=_c(163, 190, 140),
        status_finished=_c(235, 203, 139),
        status_dropped=_c(191, 97, 106),
        success=_c(163, 190, 140),
        warning=_c(235, 203, 139),
        error=_c(191, 97, 106),
        surface_raised=_c(67, 76, 94),
        surface_sunken=_c(40, 46, 58),
        header_bg=_c(52, 60, 74),
        surface_overlay=_c(46, 52, 64, 215),
        interactive_hover=_c(76, 86, 106),
        interactive_active=_c(67, 76, 94),
        interactive_muted=_c(59, 66, 82),
        info=_c(129, 161, 193),
        gradient_start=_c(52, 60, 74),
        gradient_end=_c(59, 66, 82),
    ),
    "catppuccin": ThemeSpec(
        name="Catppuccin Mocha",
        bg=_c(30, 30, 46),
        surface=_c(49, 50, 68),
        surface_alt=_c(69, 71, 90),
        card=_c(49, 50, 68),
        card_border=_c(69, 71, 90),
        card_hover=_c(137, 180, 250),
        text=_c(205, 214, 244),
        text_muted=_c(147, 153, 178),
        accent=_c(203, 166, 247),
        accent_alt=_c(250, 179, 135),
        chip_bg=_c(69, 71, 90),
        chip_border=_c(88, 91, 112),
        focus=_c(203, 166, 247),
        outline=_c(69, 71, 90),
        shadow=_c(0, 0, 0, 140),
        status_backlog=_c(137, 180, 250),
        status_playing=_c(166, 227, 161),
        status_finished=_c(249, 226, 175),
        status_dropped=_c(243, 139, 168),
        success=_c(166, 227, 161),
        warning=_c(249, 226, 175),
        error=_c(243, 139, 168),
        surface_raised=_c(69, 71, 90),
        surface_sunken=_c(24, 24, 37),
        header_bg=_c(36, 36, 54),
        surface_overlay=_c(30, 30, 46, 220),
        interactive_hover=_c(88, 91, 112),
        interactive_active=_c(69, 71, 90),
        interactive_muted=_c(49, 50, 68),
        info=_c(116, 199, 236),
        gradient_start=_c(36, 36, 54),
        gradient_end=_c(49, 50, 68),
    ),
}

FONTS = {
    "Segoe UI": "Segoe UI",
    "Arial": "Arial",
    "Calibri": "Calibri",
    "Consolas": "Consolas",
}

FONT_SCALES = {"small": 0.92, "default": 1.0, "large": 1.15}

# Accessibility: reduced motion preference
_reduced_motion: bool = False


def set_reduced_motion(enabled: bool) -> None:
    """Enable or disable reduced motion for accessibility."""
    global _reduced_motion
    _reduced_motion = enabled


def is_reduced_motion() -> bool:
    """Check if reduced motion is enabled."""
    return _reduced_motion


def apply_theme(app: QApplication, theme_name: str, font_family: str, font_scale: str) -> None:
    theme = THEMES.get(theme_name.lower(), THEMES["dark"])
    scale = FONT_SCALES.get(font_scale, 1.0)

    # palette
    pal = QPalette()
    pal.setColor(QPalette.Window, theme.bg)
    pal.setColor(QPalette.Base, theme.surface)
    pal.setColor(QPalette.AlternateBase, theme.surface_alt)
    pal.setColor(QPalette.Button, theme.surface_alt)
    pal.setColor(QPalette.ButtonText, theme.text)
    pal.setColor(QPalette.Text, theme.text)
    pal.setColor(QPalette.WindowText, theme.text)
    pal.setColor(QPalette.Highlight, theme.focus)
    pal.setColor(QPalette.HighlightedText, theme.bg if theme.focus.value() > 128 else theme.text)
    pal.setColor(QPalette.Link, theme.accent)
    pal.setColor(QPalette.ToolTipBase, theme.surface_alt)
    pal.setColor(QPalette.ToolTipText, theme.text)
    app.setPalette(pal)

    base_font = QFont(font_family or "Segoe UI", max(11, round(13 * scale)))
    app.setFont(base_font)

    # Expose theme to widgets
    app.setProperty("theme_name", theme_name.lower())
    app.setProperty("theme_spec", theme)
    app.setProperty("font_scale", font_scale)
    app.setProperty("font_family", font_family)

    app.setStyle("Fusion")

    # Use design tokens for consistent styling
    r_sm, r_md = theme.radius_sm, theme.radius_md
    sp_sm, sp_md = theme.spacing_sm, theme.spacing_md

    css = f"""
    QWidget {{
        color: {theme.text.name()};
        background: {theme.bg.name(QColor.HexArgb)};
    }}
    QToolTip {{
        background: {theme.surface_alt.name(QColor.HexArgb)};
        color: {theme.text.name()};
        border: 1px solid {theme.outline.name(QColor.HexArgb)};
        border-radius: {r_sm}px;
        padding: {sp_sm - 4}px {sp_sm}px;
    }}
    QLineEdit, QTextEdit, QComboBox, QListWidget, QTableWidget {{
        background: {theme.surface.name(QColor.HexArgb)};
        color: {theme.text.name()};
        border: 1px solid {theme.outline.name(QColor.HexArgb)};
        border-radius: {r_sm}px;
        padding: {sp_sm - 2}px;
        selection-background-color: {theme.focus.name(QColor.HexArgb)};
        selection-color: {theme.bg.name(QColor.HexArgb)};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border-color: {theme.focus.name(QColor.HexArgb)};
    }}
    QPushButton, QToolButton {{
        color: {theme.text.name()};
        background: {theme.surface_alt.name(QColor.HexArgb)};
        border: 1px solid {theme.outline.name(QColor.HexArgb)};
        border-radius: {r_md}px;
        padding: {sp_sm - 2}px {sp_md}px;
    }}
    QPushButton:hover, QToolButton:hover {{
        border-color: {theme.focus.name(QColor.HexArgb)};
        background: {theme.surface_alt.lighter(108).name(QColor.HexArgb)};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background: {theme.surface_alt.darker(108).name(QColor.HexArgb)};
    }}
    QPushButton:disabled, QToolButton:disabled {{
        color: {theme.text_muted.name()};
        background: {theme.surface.name(QColor.HexArgb)};
        border-color: {theme.outline.darker(110).name(QColor.HexArgb)};
    }}
    QListWidget::item {{
        padding: {sp_sm - 4}px {sp_sm}px;
        border-radius: {r_sm}px;
    }}
    QListWidget::item:selected, QTableWidget::item:selected {{
        background: {theme.focus.name(QColor.HexArgb)};
        color: {theme.bg.name(QColor.HexArgb)};
    }}
    QListWidget::item:hover {{
        background: {theme.surface_alt.name(QColor.HexArgb)};
    }}
    QHeaderView::section {{
        background: {theme.surface_alt.name(QColor.HexArgb)};
        color: {theme.text.name()};
        border: 0px;
        padding: {sp_sm - 2}px {sp_sm}px;
        font-weight: 600;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        border-radius: 3px;
        margin: 4px 1px;
    }}
    QScrollBar:vertical:hover {{
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba({theme.text_muted.red()},{theme.text_muted.green()},{theme.text_muted.blue()},40);
        border-radius: 3px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},150);
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:pressed {{
        background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},200);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        border-radius: 3px;
        margin: 1px 4px;
    }}
    QScrollBar:horizontal:hover {{
        height: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba({theme.text_muted.red()},{theme.text_muted.green()},{theme.text_muted.blue()},40);
        border-radius: 3px;
        min-width: 40px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},150);
        border-radius: 5px;
    }}
    QScrollBar::handle:horizontal:pressed {{
        background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},200);
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: {sp_sm}px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {theme.text_muted.name()};
    }}
    QPushButton:focus, QToolButton:focus {{
        border: 2px solid {theme.focus.name(QColor.HexArgb)};
        outline: none;
    }}
    QListWidget:focus {{
        border: 1px solid {theme.focus.name(QColor.HexArgb)};
        outline: none;
    }}
    QTabBar::tab:focus {{
        border-bottom: 2px solid {theme.focus.name(QColor.HexArgb)};
    }}
    """
    app.setStyleSheet(css)


def current_theme() -> ThemeSpec:
    app = QApplication.instance()
    if not app:
        return THEMES["dark"]
    spec = app.property("theme_spec")
    return spec if isinstance(spec, ThemeSpec) else THEMES["dark"]


def scaled_toolbar_height() -> int:
    """Compute toolbar height scaled by the current font scale and system DPI.

    The base toolbar_height (48px) is designed for 96 DPI at default font scale.
    This function adjusts it proportionally so the header remains comfortable
    at non-standard DPI settings or when the user selects a larger font.

    Returns:
        Scaled toolbar height in pixels.
    """
    app = QApplication.instance()
    base = current_theme().toolbar_height  # typically 48
    if not app:
        return base
    font_scale_name = app.property("font_scale") or "default"
    font_scale = FONT_SCALES.get(font_scale_name, 1.0)
    # Account for system DPI (96 is the baseline)
    screen = app.primaryScreen()
    dpi_scale = screen.logicalDotsPerInch() / 96.0 if screen else 1.0
    return max(36, round(base * font_scale * dpi_scale))


def shadow_style(theme: ThemeSpec, elevation: str = "mid") -> str:
    """Generate a box-shadow-like border effect for Qt widgets.

    Qt doesn't support CSS box-shadow, so we simulate depth with borders.
    For true shadows, use QGraphicsDropShadowEffect on the widget.

    Args:
        theme: Current theme spec
        elevation: "low", "mid", or "high"

    Returns:
        Border style string suggesting depth
    """
    alpha = getattr(theme, f"elevation_{elevation}", theme.elevation_mid)
    shadow_color = QColor(theme.shadow.red(), theme.shadow.green(), theme.shadow.blue(), alpha)
    return shadow_color.name(QColor.HexArgb)


def card_style(theme: ThemeSpec, hover: bool = False, radius: int | None = None) -> str:
    """Generate consistent card styling.

    Args:
        theme: Current theme spec
        hover: Whether this is for hover state
        radius: Override border radius (uses theme.radius_lg by default)

    Returns:
        Complete stylesheet for a card QFrame
    """
    r = radius if radius is not None else theme.radius_lg
    border_color = theme.card_hover if hover else theme.card_border
    bg = theme.card

    return (
        f"border: 1px solid {border_color.name(QColor.HexArgb)}; "
        f"border-radius: {r}px; "
        f"background: {bg.name(QColor.HexArgb)};"
    )


def chip_style(theme: ThemeSpec, bg_color: QColor | None = None, active: bool = False) -> str:
    """Generate consistent chip/pill button styling.

    Args:
        theme: Current theme spec
        bg_color: Override background color (uses theme.chip_bg by default)
        active: Whether this chip is in active/selected state

    Returns:
        Complete stylesheet for a chip QPushButton
    """
    bg = bg_color or theme.chip_bg
    border = theme.focus if active else theme.chip_border
    text = theme.bg if active else theme.text

    return (
        f"background: {bg.name(QColor.HexArgb)}; "
        f"color: {text.name()}; "
        f"padding: 3px 10px; "
        f"border-radius: {theme.radius_sm + 1}px; "
        f"font-size: 12px; "
        f"border: 1px solid {border.name(QColor.HexArgb)};"
    )


def focus_ring_style(theme: ThemeSpec, width: int = 2) -> str:
    """Generate focus ring styling for keyboard navigation.

    Args:
        theme: Current theme spec
        width: Border width for focus ring

    Returns:
        CSS border style for focus state
    """
    return f"border: {width}px solid {theme.focus.name(QColor.HexArgb)}; outline: none;"


def filter_chip_style(theme: ThemeSpec, active: bool = False, removable: bool = False) -> str:
    """Generate styling for active filter chips."""
    if active:
        bg = theme.accent
        text = theme.bg
        border = theme.accent.darker(110)
    else:
        bg = theme.chip_bg
        text = theme.text
        border = theme.chip_border

    return (
        f"background: {bg.name(QColor.HexArgb)}; "
        f"color: {text.name()}; "
        f"padding: 4px 12px; "
        f"border-radius: {theme.radius_md}px; "
        f"font-size: 13px; "
        f"font-weight: 500; "
        f"border: 1px solid {border.name(QColor.HexArgb)};"
    )


# --------------- Button style tiers ---------------

def primary_btn_style(theme: ThemeSpec) -> str:
    """Filled accent button for primary actions (Play, Scan)."""
    return (
        f"QPushButton, QToolButton {{ "
        f"background: {theme.accent.name()}; "
        f"color: {theme.bg.name()}; "
        f"border: none; "
        f"border-radius: {theme.radius_md}px; "
        f"padding: 6px 16px; "
        f"font-weight: 600; font-size: 13px; "
        f"}} "
        f"QPushButton:hover, QToolButton:hover {{ background: {theme.accent.lighter(112).name()}; }} "
        f"QPushButton:pressed, QToolButton:pressed {{ background: {theme.accent.darker(110).name()}; }} "
        f"QPushButton:disabled, QToolButton:disabled {{ background: {theme.surface_alt.name(QColor.HexArgb)}; "
        f"color: {theme.text_muted.name()}; }}"
    )


def secondary_btn_style(theme: ThemeSpec) -> str:
    """Outlined accent button for secondary actions (Check Updates, Open)."""
    return (
        f"QPushButton {{ "
        f"background: transparent; "
        f"color: {theme.accent.name()}; "
        f"border: 1px solid {theme.accent.name()}; "
        f"border-radius: {theme.radius_md}px; "
        f"padding: 5px 12px; "
        f"font-weight: 500; font-size: 12px; "
        f"}} "
        f"QPushButton:hover {{ background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},25); }} "
        f"QPushButton:pressed {{ background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},50); }} "
        f"QPushButton:disabled {{ color: {theme.text_muted.name()}; "
        f"border-color: {theme.outline.name(QColor.HexArgb)}; }}"
    )


def ghost_btn_style(theme: ThemeSpec) -> str:
    """Borderless button for subtle actions (Settings, Close)."""
    return (
        f"QPushButton, QToolButton {{ "
        f"background: transparent; "
        f"color: {theme.text_muted.name()}; "
        f"border: none; "
        f"border-radius: {theme.radius_sm}px; "
        f"padding: 4px 8px; "
        f"font-size: 13px; "
        f"}} "
        f"QPushButton:hover, QToolButton:hover {{ "
        f"color: {theme.text.name()}; "
        f"background: {theme.surface_alt.name(QColor.HexArgb)}; }} "
        f"QPushButton:pressed, QToolButton:pressed {{ "
        f"background: {theme.surface_alt.darker(108).name(QColor.HexArgb)}; }}"
    )


def danger_btn_style(theme: ThemeSpec) -> str:
    """Red-tinted button for destructive actions (Delete, Remove)."""
    err = theme.error or _c(230, 75, 60)
    return (
        f"QPushButton {{ "
        f"background: transparent; "
        f"color: {err.name()}; "
        f"border: 1px solid {err.name()}; "
        f"border-radius: {theme.radius_md}px; "
        f"padding: 7px 16px; "
        f"font-weight: 500; font-size: 13px; "
        f"}} "
        f"QPushButton:hover {{ background: rgba({err.red()},{err.green()},{err.blue()},25); }} "
        f"QPushButton:pressed {{ background: rgba({err.red()},{err.green()},{err.blue()},50); }}"
    )


def toolbar_btn_style(theme: ThemeSpec) -> str:
    """Compact neutral button for toolbar actions (Updates, Filter, View).

    Reads as a quiet surface chip at rest; accent-tinted on hover. Covers both
    QPushButton and QToolButton (the popover triggers use QToolButton).
    """
    acc = theme.accent
    return (
        f"QPushButton, QToolButton {{ "
        f"background: {theme.surface_alt.name(QColor.HexArgb)}; "
        f"color: {theme.text.name()}; "
        f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
        f"border-radius: {theme.radius_md}px; "
        f"padding: 5px 12px; "
        f"font-size: 12px; font-weight: 500; "
        f"}} "
        f"QToolButton::menu-indicator {{ image: none; width: 0; }} "
        f"QPushButton:hover, QToolButton:hover {{ "
        f"border-color: {acc.name()}; "
        f"background: rgba({acc.red()},{acc.green()},{acc.blue()},28); }} "
        f"QPushButton:pressed, QToolButton:pressed {{ "
        f"background: rgba({acc.red()},{acc.green()},{acc.blue()},50); }} "
        f"QPushButton:disabled, QToolButton:disabled {{ "
        f"color: {theme.text_muted.name()}; "
        f"border-color: {theme.outline.name(QColor.HexArgb)}; }}"
    )


def segmented_btn_style(theme: ThemeSpec, position: str = "mid") -> str:
    """Joined toggle button for a segmented control (quick-filter pills).

    Args:
        theme: Current theme spec
        position: "left", "mid", or "right" — controls which corners round and
            avoids doubled borders between adjacent segments.
    """
    acc = theme.accent
    r = theme.radius_md
    if position == "left":
        radius = f"border-top-left-radius: {r}px; border-bottom-left-radius: {r}px; border-right: none;"
    elif position == "right":
        radius = f"border-top-right-radius: {r}px; border-bottom-right-radius: {r}px;"
    else:  # mid
        radius = "border-right: none;"
    return (
        f"QPushButton {{ "
        f"background: {theme.surface_alt.name(QColor.HexArgb)}; "
        f"color: {theme.text_muted.name()}; "
        f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
        f"border-radius: 0px; {radius} "
        f"padding: 5px 12px; "
        f"font-size: 12px; font-weight: 500; "
        f"}} "
        f"QPushButton:hover {{ color: {theme.text.name()}; "
        f"background: {theme.interactive_hover.name(QColor.HexArgb)}; }} "
        f"QPushButton:checked {{ "
        f"background: {acc.name()}; color: {theme.bg.name()}; "
        f"border-color: {acc.name()}; font-weight: 600; }}"
    )


def icon_btn_style(theme: ThemeSpec, active: bool = False) -> str:
    """Square icon toggle button (Focus / Details / Select).

    The active flag is only used as a default; checkable buttons also honor the
    :checked pseudo-state so the style works for QToolButton toggles too.
    """
    acc = theme.accent
    return (
        f"QPushButton, QToolButton {{ "
        f"background: transparent; "
        f"color: {theme.text_muted.name()}; "
        f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
        f"border-radius: {theme.radius_sm}px; "
        f"padding: 0; font-size: 14px; "
        f"}} "
        f"QPushButton:hover, QToolButton:hover {{ "
        f"color: {theme.text.name()}; "
        f"background: {theme.surface_alt.name(QColor.HexArgb)}; }} "
        f"QPushButton:checked, QToolButton:checked {{ "
        f"background: {acc.name()}; color: {theme.bg.name()}; "
        f"border-color: {acc.name()}; }}"
    )


def popover_frame_style(theme: ThemeSpec) -> str:
    """Shared container look for the Filter / View popovers."""
    sr = theme.surface_raised or theme.surface
    return (
        f"QFrame#popover {{ "
        f"background: {sr.name(QColor.HexArgb)}; "
        f"border: 1px solid {theme.outline.name(QColor.HexArgb)}; "
        f"border-radius: {theme.radius_lg}px; "
        f"}} "
        f"QFrame#popover QLabel {{ background: transparent; border: none; "
        f"color: {theme.text_muted.name()}; }}"
    )


def header_bar_style(theme: ThemeSpec) -> str:
    """Style for the slim header/title bar."""
    hbg = theme.header_bg or theme.surface
    return (
        f"background: {hbg.name(QColor.HexArgb)}; "
        f"border-bottom: 1px solid {theme.outline.name(QColor.HexArgb)};"
    )


def section_header_style(theme: ThemeSpec) -> str:
    """Style for section headers (uppercase, small, muted)."""
    return (
        f"color: {theme.text_muted.name()}; "
        f"font-size: 11px; font-weight: 700; "
        f"letter-spacing: 1px; "
        f"padding: {theme.spacing_sm}px {theme.spacing_sm}px {theme.spacing_xs}px; "
        f"border: none; background: transparent;"
    )


def status_color(theme: ThemeSpec, status: str) -> QColor:
    """Get the semantic color for a game status."""
    mapping = {
        "backlog": theme.status_backlog,
        "playing": theme.status_playing,
        "finished": theme.status_finished,
        "dropped": theme.status_dropped,
    }
    return mapping.get(status) or theme.accent


def sidebar_item_style(theme: ThemeSpec) -> str:
    """Style for sidebar navigation items with left accent bar on selection."""
    return f"""
        QListWidget {{
            background: transparent;
            border: none;
            outline: none;
        }}
        QListWidget::item {{
            padding: {theme.spacing_sm}px {theme.spacing_md}px;
            border-radius: {theme.radius_sm}px;
            margin: 2px {theme.spacing_xs}px;
            border: none;
            border-left: 3px solid transparent;
            font-size: 13px;
        }}
        QListWidget::item:selected {{
            background: rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},25);
            color: {theme.accent.name()};
            border-left: 3px solid {theme.accent.name()};
            font-weight: 600;
        }}
        QListWidget::item:hover:!selected {{
            background: {theme.surface_alt.name(QColor.HexArgb)};
            border-left: 3px solid rgba({theme.accent.red()},{theme.accent.green()},{theme.accent.blue()},12);
        }}
    """


def collapsible_header_style(theme: ThemeSpec) -> str:
    """Style for collapsible section headers with toggle indicator."""
    return (
        f"QPushButton {{ "
        f"color: {theme.text_muted.name()}; "
        f"font-size: 11px; font-weight: 700; "
        f"letter-spacing: 1px; "
        f"text-align: left; "
        f"padding: {theme.spacing_sm}px {theme.spacing_sm}px {theme.spacing_xs}px; "
        f"border: none; background: transparent; "
        f"}} "
        f"QPushButton:hover {{ color: {theme.text.name()}; }}"
    )


def gradient_header_style(theme: ThemeSpec) -> str:
    """Style using gradient colors for header backgrounds."""
    gs = theme.gradient_start or theme.header_bg or theme.surface
    ge = theme.gradient_end or theme.surface_alt
    return (
        f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        f"stop:0 {gs.name(QColor.HexArgb)}, stop:1 {ge.name(QColor.HexArgb)}); "
        f"border-bottom: 1px solid {theme.outline.name(QColor.HexArgb)};"
    )
