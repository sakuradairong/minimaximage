"""Download generated images to local files."""

from __future__ import annotations

import os
import re

import httpx

# Generated image URLs are valid for 24h per the API docs.
URL_EXPIRY_HOURS = 24

_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, default: str = "image") -> str:
    """Strip characters that are illegal in common filesystems."""
    cleaned = _INVALID_FS_CHARS.sub("_", name).strip().strip(".")
    # Fall back to the default when the cleaned name is empty or only
    # contained characters that all got replaced (e.g. "///" -> "___").
    return cleaned if cleaned and cleaned.strip("_") else default


def default_filename(image_id: str, index: int, ext: str = "png") -> str:
    """Build `image_id-N.png` (or `image_id` when only one image)."""
    stem = safe_filename(image_id or "image")
    return f"{stem}-{index}.{ext}" if index > 0 else f"{stem}.{ext}"


def download_to_path(url: str, path: str, *, timeout: float = 60.0) -> None:
    """Stream `url` to `path`. Creates parent directories as needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in resp.iter_bytes():
                if chunk:
                    fh.write(chunk)


__all__ = [
    "URL_EXPIRY_HOURS",
    "default_filename",
    "download_to_path",
    "safe_filename",
]
