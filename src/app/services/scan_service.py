from __future__ import annotations
import re
import uuid
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.logging_utils import get_logger, kv, RateLimiter

from app.models import Game
from app.services.shortcut_resolver import resolve_shortcut_any

SUPPORTED_EXTS = {".lnk", ".url", ".html"}

_DUP_RE = re.compile(r"^(?P<base>.+?)\s\((?P<n>\d+)\)$")
_log = get_logger("scan")
_rate = RateLimiter()

def _base_name_without_duplicate_suffix(stem: str) -> str:
    m = _DUP_RE.match(stem)
    return m.group("base") if m else stem

def find_duplicate_shortcuts_in_root(root_folder: str) -> Dict[str, List[Path]]:
    """
    Groups duplicates like:
      Game.lnk
      Game (1).lnk
      Game (2).lnk

    Group key is base name (without " (n)") + extension.
    """
    root = Path(root_folder)
    if not root.exists() or not root.is_dir():
        return {}

    groups: Dict[str, List[Path]] = {}
    for p in root.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        base = _base_name_without_duplicate_suffix(p.stem)
        key = f"{base}{p.suffix.lower()}"
        groups.setdefault(key, []).append(p)

    return {k: v for k, v in groups.items() if len(v) >= 2}

def move_duplicates_to_quarantine(root_folder: str, dups: Dict[str, List[Path]]) -> Path:
    """
    Moves duplicate shortcut files (keeps the first by name order in root).
    Moves others to _Duplicates_Removed_YYYYMMDD-HHMMSS inside root.
    """
    from datetime import datetime

    root = Path(root_folder)
    quarantine = root / f"_Duplicates_Removed_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    quarantine.mkdir(parents=True, exist_ok=True)

    for key, paths in dups.items():
        keep = sorted(paths, key=lambda p: p.name.lower())[0]
        for p in sorted(paths, key=lambda p: p.name.lower()):
            if p == keep:
                continue
            target = quarantine / p.name
            p.rename(target)

    return quarantine

def scan_shortcut_root(
    root_folder: str,
    progress: Optional[Callable[[str, int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> List[Game]:
    """
    Scans ONLY the top level of the shortcut root folder for .lnk/.url/.html.
    """
    root = Path(root_folder)
    if not root.exists() or not root.is_dir():
        _log.warning("scan_skip %s", kv(reason="missing_root", path=root_folder))
        if progress:
            progress("Shortcuts root not found.", 0, 0)
        return []

    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    files.sort(key=lambda p: p.name.lower())
    _log.info("scan_start %s", kv(path=root_folder, files=len(files)))
    return scan_shortcut_files(
        files, progress=progress, should_stop=should_stop, source_label=root_folder
    )


def scan_shortcut_files(
    paths: List[str | Path],
    progress: Optional[Callable[[str, int, int], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    source_label: str = "selected files",
) -> List[Game]:
    """Read selected shortcut files into importable game records.

    This is the direct-import counterpart to :func:`scan_shortcut_root`.  It
    deliberately accepts multiple files so users do not have to create or
    reorganize a dedicated shortcut folder before adding a game.
    """
    start = time.perf_counter()
    seen: set[str] = set()
    files: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        key = str(path.resolve(strict=False)).casefold()
        if key in seen or not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        seen.add(key)
        files.append(path)
    files.sort(key=lambda p: (p.name.casefold(), str(p).casefold()))

    if progress:
        progress(f"Found {len(files)} shortcut files…", 0, len(files))

    games: List[Game] = []
    errors = 0
    cancelled = False
    for idx, f in enumerate(files):
        if should_stop and should_stop():
            _log.info("scan_cancelled %s", kv(path=source_label, read=idx, total=len(files)))
            cancelled = True
            break
        if progress:
            progress(f"Reading shortcuts: {f.name} ({idx+1}/{len(files)})", idx + 1, len(files))
        try:
            resolved = resolve_shortcut_any(f)
        except Exception as e:
            _log.warning("scan_resolve_error %s", kv(path=str(f), err=e))
            errors += 1
            continue

        shortcut_type = f.suffix.lower().lstrip(".")  # lnk/url/html
        title = _base_name_without_duplicate_suffix(f.stem)

        game_folder_path = ""
        if resolved.target_path:
            t = Path(resolved.target_path)
            if t.is_dir():
                game_folder_path = str(t)
            else:
                game_folder_path = str(t.parent)

        conf = "high"
        if shortcut_type == "lnk" and not resolved.target_path:
            conf = "low"
        if shortcut_type == "url" and not resolved.url:
            conf = "low"
        if shortcut_type == "html" and not f.exists():
            conf = "low"

        g = Game(
            game_id=str(uuid.uuid4()),
            title=title,
            shortcut_path=str(f),
            shortcut_type=shortcut_type,
            backup_target_path=resolved.target_path,
            backup_args=resolved.args,
            backup_working_dir=resolved.working_dir,
            confidence=conf,
            game_folder_path=game_folder_path,
        )
        games.append(g)

    _log.info(
        "scan_done %s",
        kv(
            path=source_label,
            files=len(files),
            games=len(games),
            errors=errors,
            cancelled=cancelled,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        ),
    )
    return games
