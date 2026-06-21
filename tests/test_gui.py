"""Tests for the GUI module's pure helpers (no Tk root required)."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip("tkinter", reason="GUI tests require tkinter")

from minimaximage.gui import (  # noqa: E402 — import after skip
    App,
    build_request_params,
    parse_references,
    save_response_images,
)

# --------------------------------------------------------------------------- #
# parse_references
# --------------------------------------------------------------------------- #


def test_parse_references_splits_and_trims() -> None:
    text = "  https://a.com/1.jpg  \nhttps://b.com/2.jpg\n\n  \nhttps://c.com/3.jpg"
    assert parse_references(text) == [
        "https://a.com/1.jpg",
        "https://b.com/2.jpg",
        "https://c.com/3.jpg",
    ]


def test_parse_references_empty_input() -> None:
    assert parse_references("") == []
    assert parse_references("\n\n  \n") == []


# --------------------------------------------------------------------------- #
# build_request_params
# --------------------------------------------------------------------------- #


def test_build_request_params_minimal() -> None:
    params = build_request_params(
        prompt="  a cat ",
        model="image-01",
        aspect_ratio="",
        n=1,
        seed="",
        response_format="url",
        prompt_optimizer=False,
        watermark=False,
        reference_text="",
    )
    assert params["prompt"] == "a cat"  # stripped
    assert params["model"] == "image-01"
    assert params["aspect_ratio"] is None
    assert params["seed"] is None
    assert params["n"] == 1
    assert params["response_format"] == "url"
    assert params["prompt_optimizer"] is False
    assert params["aigc_watermark"] is False
    assert params["reference_images"] is None


def test_build_request_params_full() -> None:
    params = build_request_params(
        prompt="two foxes",
        model="image-01-live",
        aspect_ratio="16:9",
        n=3,
        seed="42",
        response_format="base64",
        prompt_optimizer=True,
        watermark=True,
        reference_text="https://ref/a.jpg\nhttps://ref/b.jpg",
    )
    assert params["model"] == "image-01-live"
    assert params["aspect_ratio"] == "16:9"
    assert params["n"] == 3
    assert params["seed"] == 42  # parsed as int
    assert params["response_format"] == "base64"
    assert params["prompt_optimizer"] is True
    assert params["aigc_watermark"] is True
    assert params["reference_images"] == ["https://ref/a.jpg", "https://ref/b.jpg"]


def test_build_request_params_invalid_seed() -> None:
    with pytest.raises(ValueError):
        build_request_params(
            prompt="hi",
            model="image-01",
            aspect_ratio="",
            n=1,
            seed="not-a-number",
            response_format="url",
            prompt_optimizer=False,
            watermark=False,
            reference_text="",
        )


def test_build_request_params_invalid_model() -> None:
    with pytest.raises(ValueError, match="Unknown model"):
        build_request_params(
            prompt="hi",
            model="gpt-4",
            aspect_ratio="",
            n=1,
            seed="",
            response_format="url",
            prompt_optimizer=False,
            watermark=False,
            reference_text="",
        )


# --------------------------------------------------------------------------- #
# save_response_images
# --------------------------------------------------------------------------- #


def _make_response(*, task_id: str, items: list[tuple[str, bool]]) -> MagicMock:
    """Build a fake response object with .id and .images like ImageResponse."""
    resp = MagicMock()
    resp.id = task_id
    resp.images = [MagicMock(value=v, is_base64=b) for v, b in items]
    return resp


def test_save_response_images_writes_base64(tmp_path: Path) -> None:
    payload = base64.b64encode(b"FAKEPNGBYTES").decode()
    resp = _make_response(task_id="abc", items=[(payload, True)])

    paths = save_response_images(resp, tmp_path)

    assert len(paths) == 1
    assert paths[0] == tmp_path / "abc.png"
    assert paths[0].read_bytes() == b"FAKEPNGBYTES"


def test_save_response_images_creates_output_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "out"
    resp = _make_response(task_id="x", items=[("aGVsbG8=", True)])
    paths = save_response_images(resp, out)
    assert out.is_dir()
    assert paths[0].exists()


def test_save_response_images_indexes_multiple(tmp_path: Path) -> None:
    payload1 = base64.b64encode(b"ONE").decode()
    payload2 = base64.b64encode(b"TWO").decode()
    resp = _make_response(task_id="multi", items=[(payload1, True), (payload2, True)])

    paths = save_response_images(resp, tmp_path)
    assert paths[0].read_bytes() == b"ONE"
    assert paths[1].read_bytes() == b"TWO"
    # default_filename names the 0th entry without an index suffix.
    assert paths[0].name == "multi.png"
    assert paths[1].name == "multi-1.png"


# --------------------------------------------------------------------------- #
# Regression: worker must capture tk vars on the main thread
# --------------------------------------------------------------------------- #


def test_worker_accepts_plain_path_not_stringvar() -> None:
    """The worker signature must take a pathlib.Path, not a tk.StringVar.

    Reading a tk.Variable from a background thread raises
    `RuntimeError: main thread is not in main loop`. The fix in `_on_generate`
    is to call `self.outdir_var.get()` on the main thread and pass the
    resulting `Path` into the worker. This test enforces the signature so the
    fix cannot regress silently.
    """
    import inspect

    sig = inspect.signature(App._worker)
    params = list(sig.parameters.values())
    # First param is `self`, last positional must be the output dir.
    assert len(params) >= 2
    out_param = params[-1]
    annotation = out_param.annotation
    # Annotation should mention Path (stringified under `from __future__ import
    # annotations`).
    assert "Path" in str(annotation), (
        f"_worker should accept a pathlib.Path, got annotation {annotation!r}"
    )
