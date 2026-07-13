"""Type-safe application configuration backed by settings.json."""
from __future__ import annotations
from dataclasses import dataclass, fields, asdict
from typing import Any, Dict, List, Optional

from app.storage.json_store import load_settings, save_settings
from app.storage.paths import settings_json_path


@dataclass
class AppConfig:
    """Type-safe application configuration.

    Replaces scattered self._settings.get("key", default) calls with
    typed attributes that have IDE autocompletion and default values.
    """
    root_folder: str = ""
    view_mode: str = "comfortable"
    focus_mode: bool = False
    quick_filter: str = "all"
    tag_filter: Optional[str] = None
    status_filter: str = "all"
    confidence_filter: str = "all"
    type_filter: str = "all"
    sort_by: str = "title"
    updates_filter: str = "all"
    updates_density: str = "comfortable"
    health_filter: str = "all"
    health_density: str = "comfortable"
    details_visible: bool = False
    details_on_launch: bool = False
    details_on_selection: bool = True
    theme: str = "dark"
    font_family: str = "Segoe UI"
    font_scale: str = "default"
    splitter_sizes: Optional[List[int]] = None
    browse_mode: str = "scroll"
    page_size: int = 24

    # Extra settings not managed as typed fields are preserved here
    _extra: Dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._extra is None:
            self._extra = {}

    @classmethod
    def load(cls) -> AppConfig:
        """Load config from settings.json, ignoring unknown fields gracefully."""
        raw = load_settings(settings_json_path())
        known = {f.name for f in fields(cls) if f.name != "_extra"}
        known_kwargs = {k: v for k, v in raw.items() if k in known}
        extra = {k: v for k, v in raw.items() if k not in known}
        config = cls(**known_kwargs)
        config._extra = extra
        return config

    def save(self) -> None:
        """Save config to settings.json, preserving extra fields."""
        data = asdict(self)
        data.pop("_extra", None)
        # Merge extra fields back so we don't lose custom_theme, etc.
        data.update(self._extra)
        save_settings(settings_json_path(), data)

    def update(self, **kwargs: Any) -> None:
        """Update multiple fields at once."""
        for key, value in kwargs.items():
            if hasattr(self, key) and key != "_extra":
                setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict of all settings (for backward compat with self._settings)."""
        data = asdict(self)
        data.pop("_extra", None)
        data.update(self._extra)
        return data

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access for backward compatibility."""
        if hasattr(self, key) and key != "_extra":
            return getattr(self, key)
        return self._extra.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        """Dict-like setter for backward compatibility."""
        if hasattr(self, key) and key != "_extra":
            setattr(self, key, value)
        else:
            self._extra[key] = value

    def __contains__(self, key: str) -> bool:
        """Dict-like 'in' operator for backward compatibility."""
        if hasattr(self, key) and key != "_extra":
            return True
        return key in self._extra

    def pop(self, key: str, default: Any = None) -> Any:
        """Remove an optional compatibility setting.

        Typed settings are reset to their dataclass default; extra settings
        are removed like a normal dictionary entry.
        """
        known = {f.name: f for f in fields(self) if f.name != "_extra"}
        if key in known:
            value = getattr(self, key)
            default_value = known[key].default
            setattr(self, key, default_value)
            return value
        return self._extra.pop(key, default)
