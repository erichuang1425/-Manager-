from datetime import datetime, timedelta, timezone
import random

from app.models import Game
from app.models.enums import GameStatus
from app.services.game_picker import (
    candidates_for_mode,
    launch_path_candidates,
    pick_game,
    pick_random_game,
    playable_candidates,
)


def game(game_id: str, **overrides) -> Game:
    values = {"game_id": game_id, "title": game_id.title()}
    values.update(overrides)
    return Game(**values)


def test_launch_paths_are_unique_and_keep_launch_order():
    selected = game(
        "paths",
        shortcut_path="game.lnk",
        executable_path="game.exe",
        backup_target_path="GAME.EXE",
    )
    assert launch_path_candidates(selected) == ("game.lnk", "game.exe")


def test_playable_candidates_exclude_completed_and_missing_paths(tmp_path):
    shortcut = tmp_path / "game.lnk"
    shortcut.touch()
    games = [
        game("ready", shortcut_path=str(shortcut)),
        game("finished", shortcut_path=str(shortcut), status=GameStatus.FINISHED),
        game("dropped", shortcut_path=str(shortcut), status="dropped"),
        game("missing", shortcut_path=str(tmp_path / "missing.lnk")),
    ]
    assert [item.game_id for item in playable_candidates(games)] == ["ready"]


def test_picker_returns_none_when_nothing_can_be_launched(tmp_path):
    missing = game("missing", shortcut_path=str(tmp_path / "missing.lnk"))
    assert pick_random_game([missing]) is None


def test_modes_focus_on_continue_and_discover(tmp_path):
    shortcut = tmp_path / "game.lnk"
    shortcut.touch()
    active = game(
        "active",
        shortcut_path=str(shortcut),
        status=GameStatus.PLAYING,
        launch_count=4,
    )
    fresh = game("fresh", shortcut_path=str(shortcut), launch_count=0)
    playable = playable_candidates([active, fresh])

    assert candidates_for_mode(playable, "continue") == [active]
    assert candidates_for_mode(playable, "discover") == [fresh]

    continued = pick_game(playable, mode="continue", validate_paths=False, rng=random.Random(1))
    discovered = pick_game(playable, mode="discover", validate_paths=False, rng=random.Random(1))
    assert continued and continued.game is active and "in progress" in continued.reason
    assert discovered and discovered.game is fresh and "never" in discovered.reason


def test_balanced_picker_favors_unplayed_over_very_recent(tmp_path):
    now = datetime(2026, 7, 13, 12, 0, 0)
    shortcut = tmp_path / "game.lnk"
    shortcut.touch()
    fresh = game("fresh", shortcut_path=str(shortcut), launch_count=0)
    recent = game(
        "recent",
        shortcut_path=str(shortcut),
        launch_count=20,
        last_played=now - timedelta(minutes=5),
    )
    rng = random.Random(42)

    picks = [
        pick_game([fresh, recent], rng=rng, now=now).game.game_id
        for _ in range(100)
    ]
    assert picks.count("fresh") > 90


def test_reroll_avoids_seen_game_until_pool_is_exhausted(tmp_path):
    shortcut = tmp_path / "game.lnk"
    shortcut.touch()
    first = game("first", shortcut_path=str(shortcut))
    second = game("second", shortcut_path=str(shortcut))

    result = pick_game(
        [first, second],
        exclude_ids={"first"},
        rng=random.Random(2),
    )
    assert result and result.game is second


def test_picker_handles_timezone_aware_play_history(tmp_path):
    shortcut = tmp_path / "game.lnk"
    shortcut.touch()
    now = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)
    played = game(
        "aware",
        shortcut_path=str(shortcut),
        last_played=now - timedelta(days=45),
        launch_count=2,
    )
    result = pick_game([played], now=now)
    assert result and "out of rotation" in result.reason

