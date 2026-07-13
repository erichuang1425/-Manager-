"""Unit tests for the generated-cover-tile maths and the card's rest-state
visibility rules (``game_grid/display_utils.py``).

The shared conftest mocks PySide6, and importing the ``game_grid`` package pulls
in Qt-subclassing modules (delegate/view/model) that the mock can't build. The
functions under test are pure stdlib, so we load ``display_utils.py`` directly
from its file path — no package import, no Qt required.
"""
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app" / "ui" / "widgets" / "game_grid" / "display_utils.py"
)


def _load_display_utils():
    spec = importlib.util.spec_from_file_location("gg_display_utils", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


du = _load_display_utils()

_TITLES = [
    "Alpha Game", "Beta Quest", "Gamma Saga", "Delta Force", "Epsilon",
    "Zeta Project", "Hedgewars", "Celeste", "Hollow Knight", "Stardew Valley",
    "Doki Doki", "Katawa Shoujo", "Long Live The Queen", "VA-11 Hall-A",
    "Slay the Spire", "Baba Is You",
]


# --- deterministic gradient colours ---------------------------------------

def test_tile_gradient_is_deterministic():
    """Same title -> identical gradient stops across calls (and runs)."""
    assert du.tile_gradient_hsl("Alpha Game") == du.tile_gradient_hsl("Alpha Game")
    assert du.tile_gradient_hsl("") == du.tile_gradient_hsl("")


def test_tile_gradient_varies_across_titles():
    """Different titles generally yield different top hues."""
    top_hues = {round(du.tile_gradient_hsl(t)[0][0], 5) for t in _TITLES}
    # Allow the odd hash collision but require the field to be clearly varied.
    assert len(top_hues) >= len(_TITLES) - 2


def test_tile_gradient_case_and_space_insensitive():
    assert du.tile_gradient_hsl("Alpha Game") == du.tile_gradient_hsl("  alpha game  ")


def test_tile_gradient_within_muted_bands():
    """Stops stay muted and dark so tiles sit next to the dark theme surface."""
    for t in _TITLES + ["", "12345", "游戏名称"]:
        (h1, s1, l1), (h2, s2, l2) = du.tile_gradient_hsl(t)
        for h in (h1, h2):
            assert 0.0 <= h < 1.0
        for s in (s1, s2):
            assert 0.25 <= s <= 0.60          # muted, not neon
        for l in (l1, l2):
            assert 0.15 <= l <= 0.50          # dark-ish tiles


def test_tile_text_is_light_is_bool_and_deterministic():
    v = du.tile_text_is_light("Alpha Game")
    assert isinstance(v, bool)
    assert v == du.tile_text_is_light("Alpha Game")


def test_tile_text_mostly_light_on_dark_tiles():
    """Because tiles are intentionally dark, the initials read light on most."""
    light = sum(du.tile_text_is_light(t) for t in _TITLES)
    assert light >= int(0.8 * len(_TITLES))


# --- native-size executable icon -----------------------------------------

def test_native_icon_size_never_upscales_small_icon():
    assert du.native_icon_size(16, 16, 48) == (16, 16)
    assert du.native_icon_size(32, 24, 48) == (32, 24)


def test_native_icon_size_scales_large_icon_down_proportionally():
    assert du.native_icon_size(256, 128, 48) == (48, 24)
    assert du.native_icon_size(100, 200, 50) == (25, 50)


def test_native_icon_size_rejects_invalid_dimensions():
    assert du.native_icon_size(0, 32, 48) == (0, 0)
    assert du.native_icon_size(32, -1, 48) == (0, 0)
    assert du.native_icon_size(32, 32, 0) == (0, 0)


# --- initials --------------------------------------------------------------

def test_tile_initials_two_words():
    assert du.tile_initials("Alpha Game") == "AG"
    assert du.tile_initials("Long Live The Queen") == "LL"


def test_tile_initials_single_word_uses_two_chars():
    assert du.tile_initials("hedgewars") == "HE"
    assert du.tile_initials("X") == "X"


def test_tile_initials_skips_symbol_leaders():
    assert du.tile_initials("[Demo] Cool Thing") == "DC"
    assert du.tile_initials("3D World") == "3W"


def test_tile_initials_empty_or_symbol_only():
    assert du.tile_initials("") == "?"
    assert du.tile_initials("!!!") == "?"
    assert du.tile_initials(None) == "?"


def test_tile_initials_support_traditional_and_simplified_chinese():
    assert du.tile_initials("返校") == "返校"
    assert du.tile_initials("黑神话：悟空") == "黑神"


def test_tile_initials_support_japanese_scripts():
    assert du.tile_initials("龍が如く") == "龍が"
    assert du.tile_initials("ゲーム") == "ゲー"
    assert du.tile_initials("ファイナル・ファンタジー") == "ファ"


def test_cover_crop_rect_center_crops_wide_and_tall_images():
    assert du.cover_crop_rect(1600, 900, 400, 400) == (350.0, 0.0, 900.0, 900)
    assert du.cover_crop_rect(900, 1600, 400, 200) == (0.0, 575.0, 900, 450.0)


def test_cover_crop_rect_rejects_invalid_dimensions():
    assert du.cover_crop_rect(0, 100, 50, 50) == (0.0, 0.0, 0.0, 0.0)


# --- rest-state visibility rules ------------------------------------------

def test_rating_is_set():
    assert du.rating_is_set(8) is True
    assert du.rating_is_set(1) is True
    assert du.rating_is_set(0) is False
    assert du.rating_is_set(None) is False


def test_status_is_default():
    assert du.status_is_default("backlog") is True
    assert du.status_is_default("playing") is False
    assert du.status_is_default("finished") is False


def test_status_is_default_accepts_enum():
    # The real Game default is the GameStatus.BACKLOG str-enum member, not a
    # plain string, so the predicate must treat it as the default too.
    from app.models.enums import GameStatus
    assert du.status_is_default(GameStatus.BACKLOG) is True
    assert du.status_is_default(GameStatus.PLAYING) is False
