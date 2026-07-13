from __future__ import annotations
from typing import Dict, List
from pathlib import Path

from app.models import Game

def _key_for_game(g: Game) -> str:
    # Stable key: shortcut path (case-insensitive on Windows)
    return str(Path(g.shortcut_path)).lower()

def merge_scanned_into_library(existing: List[Game], scanned: List[Game]) -> List[Game]:
    """
    Keep user edits from existing games, update scan-derived fields from scanned games.
    """
    existing_map: Dict[str, Game] = {_key_for_game(g): g for g in existing}
    merged: List[Game] = []

    for s in scanned:
        k = _key_for_game(s)
        if k in existing_map:
            e = existing_map[k]

            # Keep identity + user metadata (prefer existing values)
            s.game_id = e.game_id
            s.title = e.title or s.title
            s.rating = e.rating
            s.tags = e.tags
            s.notes = e.notes
            s.status = e.status
            s.last_played = e.last_played
            s.launch_count = e.launch_count
            s.source_url = e.source_url
            s.source_checked_at = e.source_checked_at
            s.installed_version_raw = e.installed_version_raw
            s.source_version_raw = e.source_version_raw
            s.source_version_num = e.source_version_num
            s.source_version_suffix = e.source_version_suffix
            s.archive_folder_path = e.archive_folder_path
            s.compressed_archive_path = e.compressed_archive_path
            # Preserve user-entered folder path when present, but allow newly
            # resolved paths to populate empty slots.
            if e.game_folder_path:
                s.game_folder_path = e.game_folder_path
            # Keep icon cache flag so we don't re-prime icons unnecessarily.
            s.icon_upscaled = getattr(e, "icon_upscaled", False)
            s.card_artwork_path = getattr(e, "card_artwork_path", "")

        merged.append(s)

    # Optionally keep “orphaned” entries (shortcuts removed from disk)
    # If you want them to show as broken in Health Checks, keep them:
    scanned_keys = {_key_for_game(s) for s in scanned}
    for e in existing:
        if _key_for_game(e) not in scanned_keys:
            # Keep it; Health Checks will flag it as missing
            merged.append(e)

    # Sort by title
    merged.sort(key=lambda g: g.title.lower())
    return merged
