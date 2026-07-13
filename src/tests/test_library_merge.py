"""Regression coverage for scan merges that must retain user-owned metadata."""

from app.models import Game
from app.services.library_merge import merge_scanned_into_library


def test_scan_merge_preserves_card_artwork_path():
    existing = Game(
        game_id="stable-id",
        title="返校",
        shortcut_path=r"C:\Games\Detention.lnk",
        card_artwork_path=r"C:\Artwork\detention.jpg",
    )
    rescanned = Game(
        game_id="new-scan-id",
        title="Detention",
        shortcut_path=r"C:\Games\Detention.lnk",
        backup_target_path=r"C:\Games\Detention\Detention.exe",
    )

    merged = merge_scanned_into_library([existing], [rescanned])

    assert len(merged) == 1
    assert merged[0].game_id == "stable-id"
    assert merged[0].title == "返校"
    assert merged[0].card_artwork_path == r"C:\Artwork\detention.jpg"
    assert merged[0].backup_target_path.endswith("Detention.exe")
