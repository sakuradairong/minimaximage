"""Tests for the download helper module."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from minimaximage.download import default_filename, download_to_path, safe_filename


def test_safe_filename_strips_illegal_chars() -> None:
    assert safe_filename("a/b:c?d*e") == "a_b_c_d_e"


def test_safe_filename_falls_back_to_default_for_empty() -> None:
    assert safe_filename("///") == "image"
    assert safe_filename("", default="fallback") == "fallback"


def test_default_filename_with_index() -> None:
    assert default_filename("task_1", 2) == "task_1-2.png"
    assert default_filename("task_1", 0) == "task_1.png"


def test_default_filename_sanitizes_id() -> None:
    assert default_filename("a/b?c", 0).endswith("a_b_c.png")


def test_download_to_path_creates_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "img.png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"PNGDATA")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http:
        # Patch stream by reaching into the module-level stream call.
        import minimaximage.download as dl

        orig_stream = dl.httpx.stream
        dl.httpx.stream = lambda *a, **kw: http.stream(*a, **kw)  # type: ignore[assignment]
        try:
            download_to_path("https://example.com/img.png", str(target))
        finally:
            dl.httpx.stream = orig_stream  # type: ignore[assignment]

    assert target.read_bytes() == b"PNGDATA"


def test_download_to_path_propagates_http_error(tmp_path: Path) -> None:
    target = tmp_path / "img.png"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http:
        import minimaximage.download as dl

        orig_stream = dl.httpx.stream
        dl.httpx.stream = lambda *a, **kw: http.stream(*a, **kw)  # type: ignore[assignment]
        try:
            with pytest.raises(httpx.HTTPStatusError):
                download_to_path("https://example.com/missing.png", str(target))
        finally:
            dl.httpx.stream = orig_stream  # type: ignore[assignment]

    assert not target.exists()
