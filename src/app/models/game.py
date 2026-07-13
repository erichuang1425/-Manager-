from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from app.models.enums import GameStatus, Confidence


@dataclass
class Game:
    game_id: str
    title: str

    # Shortcut entry (centralized launcher directory)
    shortcut_path: str = ""              # absolute path to .lnk/.url/.html
    shortcut_type: str = ""              # lnk | url | html

    # Backup launch info (mainly from .lnk)
    backup_target_path: str = ""         # resolved target exe/file path
    backup_args: str = ""                # resolved arguments from .lnk
    backup_working_dir: str = ""         # resolved working directory from .lnk

    # Library metadata
    status: str = GameStatus.BACKLOG
    rating: Optional[int] = None         # 1..10
    tags: List[str] = field(default_factory=list)
    last_played: Optional[datetime] = None
    launch_count: int = 0
    notes: str = ""

    # Quality flags
    confidence: str = Confidence.MEDIUM

    # Source / update tracking
    source_url: str = ""                 # source page (e.g., f95zone thread)
    source_checked_at: Optional[datetime] = None  # last time we parsed source page
    installed_version_raw: str = ""      # local version string (manual/detected)
    source_version_raw: str = ""         # raw version string from source page
    source_version_num: Optional[str] = None  # numeric component extracted (e.g., 0.1.1)
    source_version_suffix: str = ""      # label / suffix, e.g., "Redux Demo"

    # Archive tracking
    archive_folder_path: str = ""        # extracted archive folder path
    compressed_archive_path: str = ""    # original compressed archive (.zip/.rar/etc)
    game_folder_path: str = ""           # resolved folder from shortcut target (best-effort)

    # Icon quality tracking
    icon_upscaled: bool = False          # True once a high-quality icon has been cached
    dominant_color_hex: str = ""         # cached hex color from icon, e.g. "#3a7bd5"

    # F95zone integration (Phase 6-10)
    f95_thread_id: Optional[int] = None  # F95zone thread ID
    f95_category: str = ""               # Completed, Ongoing, Abandoned, On Hold
    f95_tags: List[str] = field(default_factory=list)  # Tags from F95zone thread
    developer: str = ""                  # Developer/creator name

    # Download tracking
    download_url: str = ""               # Last download URL used
    download_host: str = ""              # Host type (mega, gdrive, etc.)
    last_download_at: Optional[datetime] = None  # Last download timestamp

    # Installation paths
    install_path: str = ""               # Root installation folder
    executable_path: str = ""            # Path to main game executable
    save_folder_path: str = ""           # Path to save game folder

    # Backup/versioning
    has_backup: bool = False             # Whether a backup exists
    backup_path: str = ""                # Path to version backup folder

    # Card personalization
    card_artwork_path: str = ""          # managed screenshot/image used as card background
