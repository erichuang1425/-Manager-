"""Export and import functionality for game library data."""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import csv
from datetime import datetime
from dataclasses import asdict

from app.models import Game, Collection


def export_to_json(games: List[Game], collections: List[Collection], path: Path) -> int:
    """Export library to JSON file.

    Args:
        games: List of games to export
        collections: List of collections to export
        path: Output file path

    Returns:
        Number of games exported
    """
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    data = {
        "export_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "games": [_game_to_dict(g) for g in games],
        "collections": [_collection_to_dict(c) for c in collections],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=serialize_datetime)

    return len(games)


def export_to_csv(games: List[Game], path: Path) -> int:
    """Export games to CSV file.

    Args:
        games: List of games to export
        path: Output file path

    Returns:
        Number of games exported
    """
    fieldnames = [
        "title", "status", "rating", "tags", "notes",
        "shortcut_path", "shortcut_type", "source_url",
        "installed_version", "last_played", "launch_count",
        "confidence", "game_id"
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for game in games:
            # Convert tags list to comma-separated string for CSV
            tags_str = ", ".join(game.tags) if game.tags else ""
            row = {
                "title": game.title,
                "status": game.status or "",
                "rating": game.rating or "",
                "tags": tags_str,
                "notes": game.notes or "",
                "shortcut_path": game.shortcut_path or "",
                "shortcut_type": game.shortcut_type or "",
                "source_url": game.source_url or "",
                "installed_version": game.installed_version_raw or "",
                "last_played": game.last_played.isoformat() if game.last_played else "",
                "launch_count": game.launch_count or 0,
                "confidence": game.confidence or "",
                "game_id": game.game_id,
            }
            writer.writerow(row)

    return len(games)


def export_to_markdown(games: List[Game], path: Path, include_stats: bool = True) -> int:
    """Export games to Markdown file.

    Args:
        games: List of games to export
        path: Output file path
        include_stats: Whether to include summary statistics

    Returns:
        Number of games exported
    """
    lines = ["# Game Library Export", ""]

    if include_stats:
        lines.append("## Summary")
        lines.append(f"- **Total Games**: {len(games)}")

        status_counts = {}
        for g in games:
            s = g.status or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        for status, count in sorted(status_counts.items()):
            lines.append(f"- **{status.capitalize()}**: {count}")
        lines.append("")

    lines.append("## Games")
    lines.append("")

    # Group by status
    by_status: Dict[str, List[Game]] = {}
    for g in games:
        s = g.status or "unknown"
        if s not in by_status:
            by_status[s] = []
        by_status[s].append(g)

    for status in ["playing", "backlog", "finished", "dropped", "unknown"]:
        if status not in by_status:
            continue

        lines.append(f"### {status.capitalize()}")
        lines.append("")

        for g in sorted(by_status[status], key=lambda x: x.title.lower()):
            rating = f" ({'★' * (g.rating // 2 if g.rating else 0)})" if g.rating else ""
            tags_str = ", ".join(g.tags) if g.tags else ""
            tags = f" `{tags_str}`" if tags_str else ""
            lines.append(f"- **{g.title}**{rating}{tags}")

        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return len(games)


def import_from_json(path: Path) -> Tuple[List[Game], List[Collection], Dict[str, Any]]:
    """Import library from JSON file.

    Args:
        path: Input file path

    Returns:
        Tuple of (games, collections, metadata)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    games = [_dict_to_game(g) for g in data.get("games", [])]
    collections = [_dict_to_collection(c) for c in data.get("collections", [])]

    metadata = {
        "export_version": data.get("export_version", "unknown"),
        "exported_at": data.get("exported_at", "unknown"),
        "game_count": len(games),
        "collection_count": len(collections),
    }

    return games, collections, metadata


def import_from_csv(path: Path) -> Tuple[List[Game], Dict[str, Any]]:
    """Import games from CSV file.

    Args:
        path: Input file path

    Returns:
        Tuple of (games, metadata)
    """
    games = []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse tags: could be comma-separated string from CSV export
            tags_raw = row.get("tags", "")
            if isinstance(tags_raw, str) and tags_raw:
                tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
            else:
                tags_list = []

            game = Game(
                game_id=row.get("game_id") or _generate_id(),
                title=row.get("title", "Unknown"),
                shortcut_path=row.get("shortcut_path") or "",
                shortcut_type=row.get("shortcut_type") or "",
                status=row.get("status") or "backlog",
                rating=int(row["rating"]) if row.get("rating") else None,
                tags=tags_list,
                notes=row.get("notes") or "",
                source_url=row.get("source_url") or "",
                installed_version_raw=row.get("installed_version") or "",
                launch_count=int(row["launch_count"]) if row.get("launch_count") else 0,
                confidence=row.get("confidence") or "medium",
                last_played=_parse_datetime(row.get("last_played")),
            )
            games.append(game)

    metadata = {
        "game_count": len(games),
        "source_file": str(path),
    }

    return games, metadata


def merge_imported_games(
    existing: List[Game],
    imported: List[Game],
    strategy: str = "skip"
) -> Tuple[List[Game], Dict[str, int]]:
    """Merge imported games with existing library.

    Args:
        existing: Current library games
        imported: Games to import
        strategy: "skip" (keep existing), "overwrite" (replace), or "merge" (combine)

    Returns:
        Tuple of (merged games list, stats dict)
    """
    existing_by_id = {g.game_id: g for g in existing}
    existing_by_title = {g.title.lower(): g for g in existing}

    stats = {"added": 0, "updated": 0, "skipped": 0}
    result = list(existing)

    for game in imported:
        # Check for existing by ID first, then by title
        existing_game = existing_by_id.get(game.game_id)
        if not existing_game:
            existing_game = existing_by_title.get(game.title.lower())

        if existing_game:
            if strategy == "skip":
                stats["skipped"] += 1
            elif strategy == "overwrite":
                # Replace existing game
                idx = result.index(existing_game)
                game.game_id = existing_game.game_id  # Keep original ID
                result[idx] = game
                stats["updated"] += 1
            elif strategy == "merge":
                # Merge fields (prefer non-empty values from import)
                _merge_game_fields(existing_game, game)
                stats["updated"] += 1
        else:
            # New game
            result.append(game)
            stats["added"] += 1

    return result, stats


def _game_to_dict(game: Game) -> Dict[str, Any]:
    """Convert Game to serializable dict."""
    d = {}
    for field in [
        "game_id", "title", "shortcut_path", "shortcut_type", "status",
        "rating", "tags", "notes", "source_url", "installed_version_raw",
        "source_version_raw", "launch_count", "confidence", "last_played",
        "archive_folder_path", "game_folder_path", "source_checked_at",
        "card_artwork_path",
    ]:
        val = getattr(game, field, None)
        if val is not None:
            if isinstance(val, datetime):
                val = val.isoformat()
            d[field] = val
    return d


def _dict_to_game(d: Dict[str, Any]) -> Game:
    """Convert dict to Game object."""
    # Parse datetime fields
    for dt_field in ["last_played", "source_checked_at"]:
        if d.get(dt_field):
            d[dt_field] = _parse_datetime(d[dt_field])

    return Game(**{k: v for k, v in d.items() if hasattr(Game, k) or k == "game_id"})


def _collection_to_dict(coll: Collection) -> Dict[str, Any]:
    """Convert Collection to serializable dict."""
    return {
        "collection_id": coll.collection_id,
        "name": coll.name,
        "type": coll.type,
        "game_ids": list(coll.game_ids) if coll.game_ids else [],
        "filter": coll.filter if coll.filter else {},
    }


def _dict_to_collection(d: Dict[str, Any]) -> Collection:
    """Convert dict to Collection object."""
    return Collection(
        collection_id=d.get("collection_id") or _generate_id(),
        name=d.get("name", "Unnamed"),
        type=d.get("type", "manual"),
        game_ids=d.get("game_ids", []),
        filter=d.get("filter", {}),
    )


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime from ISO format string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _generate_id() -> str:
    """Generate a new game ID."""
    import uuid
    return str(uuid.uuid4())


def _merge_game_fields(existing: Game, imported: Game) -> None:
    """Merge non-empty fields from imported game into existing."""
    merge_fields = [
        "status", "rating", "tags", "notes", "source_url",
        "installed_version_raw", "confidence", "card_artwork_path"
    ]

    for field in merge_fields:
        imported_val = getattr(imported, field, None)
        existing_val = getattr(existing, field, None)
        if imported_val and not existing_val:
            setattr(existing, field, imported_val)
