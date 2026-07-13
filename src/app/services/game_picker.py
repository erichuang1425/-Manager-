"""Decision-oriented game selection for the "Pick for me" experience."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import Callable, Iterable, Optional, Sequence

from app.models import Game


PICK_MODES = ("balanced", "continue", "discover")


@dataclass(frozen=True)
class PickResult:
    """A selected game plus the context needed to explain the choice."""

    game: Game
    reason: str
    candidate_count: int
    mode: str


def _status_value(game: Game) -> str:
    status = getattr(game, "status", "")
    return str(getattr(status, "value", status))


def launch_path_candidates(game: Game) -> tuple[str, ...]:
    """Return unique launch paths in the same broad order used by launching."""
    values = (
        getattr(game, "shortcut_path", "") or "",
        getattr(game, "executable_path", "") or "",
        getattr(game, "backup_target_path", "") or "",
    )
    seen: set[str] = set()
    paths: list[str] = []
    for value in values:
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            paths.append(value)
    return tuple(paths)


def _path_exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def playable_candidates(
    games: Iterable[Game],
    *,
    exists: Callable[[str], bool] = _path_exists,
) -> list[Game]:
    """Exclude completed, dropped, and currently unlaunchable entries."""
    candidates: list[Game] = []
    for game in games:
        if _status_value(game) in {"finished", "dropped"}:
            continue
        if any(exists(path) for path in launch_path_candidates(game)):
            candidates.append(game)
    return candidates


def candidates_for_mode(games: Iterable[Game], mode: str) -> list[Game]:
    """Apply a picker mode to an already-playable collection."""
    candidates = list(games)
    if mode == "continue":
        active = [game for game in candidates if _status_value(game) == "playing"]
        return active or candidates
    if mode == "discover":
        unplayed = [game for game in candidates if game.launch_count == 0]
        return unplayed or candidates
    return candidates


def _local_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _age(now: datetime, then: datetime) -> timedelta:
    age = _local_naive(now) - _local_naive(then)
    return max(age, timedelta(0))


def _choice_weight(game: Game, now: datetime) -> float:
    """Favor useful choices while strongly cooling down very recent games."""
    weight = 1.0
    if game.launch_count == 0:
        weight += 2.75
    if _status_value(game) == "playing":
        weight += 1.5
    if game.rating:
        weight += max(0.0, (game.rating - 5) * 0.3)
    if game.last_played:
        age = _age(now, game.last_played)
        if age < timedelta(hours=24):
            weight *= 0.08
        elif age < timedelta(days=7):
            weight *= 0.35
        elif age < timedelta(days=30):
            weight *= 0.7
    return max(weight, 0.01)


def _pick_reason(game: Game, mode: str, now: datetime) -> str:
    reasons: list[str] = []
    if mode == "continue" and _status_value(game) == "playing":
        reasons.append("it is already in progress")
    elif mode == "discover" and game.launch_count == 0:
        reasons.append("you have never launched it")
    else:
        if game.launch_count == 0:
            reasons.append("you have not played it yet")
        elif _status_value(game) == "playing":
            reasons.append("it is already in progress")

    if game.rating and game.rating >= 8:
        reasons.append(f"you rated it {game.rating}/10")
    if game.last_played and _age(now, game.last_played) >= timedelta(days=30):
        reasons.append("it has been out of rotation for a while")
    if not reasons:
        reasons.append("it fits this view without being overplayed recently")

    if len(reasons) == 1:
        detail = reasons[0]
    else:
        detail = ", ".join(reasons[:-1]) + f", and {reasons[-1]}"
    return f"Picked because {detail}."


def pick_game(
    games: Iterable[Game],
    *,
    mode: str = "balanced",
    exclude_ids: Iterable[str] = (),
    rng: Optional[random.Random] = None,
    now: Optional[datetime] = None,
    validate_paths: bool = True,
) -> Optional[PickResult]:
    """Choose a game by mode, avoiding immediate reroll repeats when possible."""
    normalized_mode = mode if mode in PICK_MODES else "balanced"
    source_games: Sequence[Game]
    if validate_paths:
        source_games = playable_candidates(games)
    else:
        source_games = list(games)
    candidates = candidates_for_mode(source_games, normalized_mode)
    candidate_count = len(candidates)
    if not candidates:
        return None

    excluded = set(exclude_ids)
    unseen = [game for game in candidates if game.game_id not in excluded]
    if unseen:
        candidates = unseen

    current_time = now or datetime.now()
    weights = [_choice_weight(game, current_time) for game in candidates]
    if normalized_mode == "continue":
        weights = [
            weight + min(game.launch_count, 10) * 0.15
            for game, weight in zip(candidates, weights)
        ]
    source = rng or random.SystemRandom()
    selected = source.choices(candidates, weights=weights, k=1)[0]
    return PickResult(
        game=selected,
        reason=_pick_reason(selected, normalized_mode, current_time),
        candidate_count=candidate_count,
        mode=normalized_mode,
    )


def pick_random_game(
    games: Iterable[Game],
    *,
    rng: Optional[random.Random] = None,
    now: Optional[datetime] = None,
) -> Optional[Game]:
    """Compatibility helper returning only the selected game."""
    result = pick_game(games, rng=rng, now=now)
    return result.game if result else None
