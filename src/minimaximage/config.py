"""Load settings from environment, .env, and an optional user config file.

Resolution order for each field (highest priority first):

    1. Explicit argument passed to ``Settings.load(...)``
    2. ``~/.config/minimaximage/config.json`` (or platform equivalent)
    3. ``MINIMAX_API_KEY`` / ``MINIMAXIMAGE_*`` environment variables

The legacy ``Settings.from_env()`` still works and only reads env vars, so
existing tests keep passing.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from the current working directory if present. No-op when missing.
load_dotenv(override=False)

DEFAULT_BASE_URL = "https://api.minimaxi.com"

# Keys we accept in the config JSON file. Anything else is ignored.
_CONFIG_KEYS = {"api_key", "base_url", "model", "aspect_ratio", "n", "response_format"}


def config_path() -> Path:
    """Return the platform-appropriate config file location.

    - Windows: ``%APPDATA%\\minimaximage\\config.json``
    - macOS:   ``~/Library/Application Support/minimaximage/config.json``
    - Linux:   ``$XDG_CONFIG_HOME/minimaximage/config.json`` (default
               ``~/.config/minimaximage/config.json``)
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "minimaximage" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load the config JSON, returning an empty dict when missing or invalid."""
    target = path or config_path()
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in _CONFIG_KEYS}


def save_config(values: dict[str, Any], *, path: Path | None = None) -> Path:
    """Atomically write the given values to the config file. Returns the path."""
    cleaned = {k: v for k, v in values.items() if k in _CONFIG_KEYS}
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def clear_config_value(key: str, *, path: Path | None = None) -> bool:
    """Remove a single key from the config file. Returns True if it was present."""
    target = path or config_path()
    data = load_config(target)
    if key in data:
        del data[key]
        save_config(data, path=target)
        return True
    return False


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    aspect_ratio: str | None
    n: int
    response_format: str

    @classmethod
    def from_env(cls) -> Settings:
        """Strict env-only loader. Raises if MINIMAX_API_KEY is unset.

        Kept for backward compatibility with existing tests and callers that
        want to fail loudly when the env var is missing.
        """
        api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
        if not api_key:
            raise OSError("MINIMAX_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return cls(
            base_url=os.environ.get("MINIMAX_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            api_key=api_key,
            model=os.environ.get("MINIMAXIMAGE_MODEL", "image-01"),
            aspect_ratio=os.environ.get("MINIMAXIMAGE_ASPECT_RATIO") or None,
            n=int(os.environ.get("MINIMAXIMAGE_N", "1")),
            response_format=os.environ.get("MINIMAXIMAGE_RESPONSE_FORMAT", "url"),
        )

    @classmethod
    def load(
        cls,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        config_path: Path | None = None,
    ) -> Settings:
        """Resolve settings from explicit args → config file → env vars.

        Raises OSError when the API key cannot be resolved from any source.
        """
        config = load_config(config_path)

        resolved_key = (
            api_key or config.get("api_key") or os.environ.get("MINIMAX_API_KEY", "")
        ).strip()
        if not resolved_key:
            raise OSError(
                "API key is not set. Provide it via the GUI/API, "
                "MINIMAX_API_KEY env var, or save it via "
                '`save_config({"api_key": "..."})`.'
            )

        resolved_base = (
            base_url
            or config.get("base_url")
            or os.environ.get("MINIMAX_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")

        return cls(
            base_url=resolved_base,
            api_key=resolved_key,
            model=os.environ.get("MINIMAXIMAGE_MODEL") or str(config.get("model", "image-01")),
            aspect_ratio=os.environ.get("MINIMAXIMAGE_ASPECT_RATIO") or config.get("aspect_ratio"),
            n=_coerce_int(os.environ.get("MINIMAXIMAGE_N") or config.get("n"), default=1),
            response_format=os.environ.get("MINIMAXIMAGE_RESPONSE_FORMAT")
            or str(config.get("response_format", "url")),
        )


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "DEFAULT_BASE_URL",
    "Settings",
    "clear_config_value",
    "config_path",
    "load_config",
    "save_config",
]
