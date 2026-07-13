"""
Display utilities for game grid widgets.

Helper functions for formatting and displaying game information.
"""

from __future__ import annotations

import colorsys
import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Optional, Tuple


def status_label(status: str) -> str:
    """Convert status code to display label."""
    mapping = {
        "backlog": "Backlog",
        "playing": "Playing",
        "finished": "Finished",
        "dropped": "Dropped",
    }
    return mapping.get(status, status)


def confidence_icon(conf: str) -> str:
    """Get emoji icon for confidence level."""
    return {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "🟡")


def stars(rating: Optional[int]) -> str:
    """Convert numeric rating (1-10) to 5-star visual display."""
    if rating is None:
        return "—"
    five = max(1, min(5, round(rating / 2)))
    return "★" * five + "☆" * (5 - five)


def relative_time(dt: Optional[datetime]) -> str:
    """Convert datetime to human-readable relative time."""
    if dt is None:
        return ""

    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 0:
        return "just now"

    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7
    months = days / 30

    if seconds < 60:
        return "just now"
    elif minutes < 60:
        m = int(minutes)
        return f"{m}m ago"
    elif hours < 24:
        h = int(hours)
        return f"{h}h ago"
    elif days < 7:
        d = int(days)
        return f"{d}d ago"
    elif weeks < 4:
        w = int(weeks)
        return f"{w}w ago"
    elif months < 12:
        m = int(months)
        return f"{m}mo ago"
    else:
        return dt.strftime("%b %Y")


# ---------------------------------------------------------------------------
#  Generated cover tiles
#
#  When a game has no artwork (or only a tiny extracted shortcut icon) the
#  delegate paints a deterministic gradient tile with the title's initials.
#  The colour/geometry maths lives here as pure functions (no Qt types) so it
#  is unit-testable and stable across runs — ``hashlib`` is used instead of the
#  built-in ``hash()``, which is salted per-process.
# ---------------------------------------------------------------------------

# The default status; cards at this status hide their status chip at rest.
DEFAULT_STATUS = "backlog"

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)

# Explicit UI-font fallbacks for Traditional Chinese, Simplified Chinese, and
# Japanese title marks. Qt will use the first installed family containing the
# requested glyph, while retaining the user's configured font for Latin text.
CJK_FONT_FAMILIES = (
    "Microsoft JhengHei UI",
    "Microsoft YaHei UI",
    "Yu Gothic UI",
    "Meiryo UI",
)

_CJK_RANGES = (
    (0x3400, 0x4DBF),    # CJK Extension A
    (0x4E00, 0x9FFF),    # Unified ideographs
    (0xF900, 0xFAFF),    # Compatibility ideographs
    (0x20000, 0x2FA1F),  # Supplementary ideograph planes
    (0x3040, 0x309F),    # Hiragana
    (0x30A0, 0x30FF),    # Katakana
    (0x31F0, 0x31FF),    # Katakana phonetic extensions
    (0xAC00, 0xD7AF),    # Hangul syllables (graceful regional fallback)
)

# HSL bands chosen so tiles read as muted, dark-theme surfaces (they must sit
# comfortably next to theme.surface / theme.surface_alt) rather than neon.
_SAT_MIN, _SAT_SPAN = 0.34, 20          # saturation 0.34 .. 0.53
_LIGHT_MIN, _LIGHT_SPAN = 0.35, 11      # lightness  0.35 .. 0.45


def _title_seed(title: str) -> int:
    """Stable 48-bit integer derived from the title (case/space-insensitive)."""
    key = (title or "").strip().lower().encode("utf-8")
    return int.from_bytes(hashlib.md5(key).digest()[:6], "big")


def tile_initials(title: str) -> str:
    """Return a compact, Unicode-aware 1-2 character title mark.

    Latin titles use familiar word initials. Han, Hiragana, and Katakana titles
    use their first two meaningful characters so Traditional Chinese,
    Simplified Chinese, and Japanese cards never collapse to ``?``.
    """
    normalized = unicodedata.normalize("NFC", str(title or ""))
    words = _WORD_RE.findall(normalized)
    if not words:
        return "?"
    if any(_is_cjk_character(char) for char in words[0]):
        characters = [
            char for char in normalized
            if char.isalnum() or char in {"ー", "々", "ゝ", "ゞ", "ヽ", "ヾ"}
        ]
        return "".join(characters[:2]) or "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _is_cjk_character(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in _CJK_RANGES)


def cover_crop_rect(
    source_width: float,
    source_height: float,
    target_width: float,
    target_height: float,
) -> Tuple[float, float, float, float]:
    """Return a centered source crop that fills a target without distortion."""
    if min(source_width, source_height, target_width, target_height) <= 0:
        return 0.0, 0.0, 0.0, 0.0
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = crop_height * target_ratio
        return (source_width - crop_width) / 2.0, 0.0, crop_width, crop_height
    crop_width = source_width
    crop_height = crop_width / target_ratio
    return 0.0, (source_height - crop_height) / 2.0, crop_width, crop_height


def tile_gradient_hsl(title: str) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Deterministic (top, bottom) gradient stops as ``(h, s, l)`` floats in 0..1.

    Same title -> identical stops; different titles -> generally different hues.
    """
    seed = _title_seed(title)
    hue = (seed % 360) / 360.0
    hue2 = (((seed % 360) + 26) % 360) / 360.0
    sat = (_SAT_MIN + ((seed >> 9) % _SAT_SPAN) / 100.0)
    light = (_LIGHT_MIN + ((seed >> 17) % _LIGHT_SPAN) / 100.0)
    top = (hue, sat, light)
    bottom = (hue2, max(0.0, sat - 0.05), max(0.0, light - 0.13))
    return top, bottom


def tile_text_is_light(title: str) -> bool:
    """Whether initials should be drawn light (True) or dark (False).

    Decided from the gradient's mid relative-luminance so text always contrasts
    the tile.  With the muted dark bands above this is virtually always light,
    but the check keeps the pairing correct if the bands are ever widened.
    """
    (h1, s1, l1), (_h2, s2, l2) = tile_gradient_hsl(title)
    s = (s1 + s2) / 2.0
    l = (l1 + l2) / 2.0
    r, g, b = colorsys.hls_to_rgb(h1, l, s)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return lum < 0.5


def native_icon_size(
    source_width: float,
    source_height: float,
    max_extent: int = 48,
) -> Tuple[int, int]:
    """Fit an icon inside ``max_extent`` without ever enlarging it.

    Shortcut and executable icons are identity marks, not cover artwork. Keeping
    their source size (or reducing it) avoids the pixelated full-card scaling
    that prompted the generated-cover treatment in the first place.
    """
    if source_width <= 0 or source_height <= 0 or max_extent <= 0:
        return 0, 0
    scale = min(1.0, max_extent / max(source_width, source_height))
    return (
        max(1, round(source_width * scale)),
        max(1, round(source_height * scale)),
    )


# ---------------------------------------------------------------------------
#  Rest-state visibility rules (progressive disclosure)
# ---------------------------------------------------------------------------

def rating_is_set(rating: Optional[int]) -> bool:
    """True when a game carries a real rating (stars shown at rest)."""
    return bool(rating) and rating > 0


def status_is_default(status) -> bool:
    """True when a game is at the default status (status chip hidden at rest)."""
    return status == DEFAULT_STATUS
