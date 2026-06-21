"""Tests for the high-level generate_image function (with a mocked client)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from minimaximage.client import MinimaxError
from minimaximage.generate import generate_image
from minimaximage.models import ImageModel, ResponseFormat
from tests.conftest import fake_response_body


def _client_with(payload: dict) -> MagicMock:
    client = MagicMock()
    client.generate.return_value = payload
    return client


def test_generate_image_passes_payload_and_parses_response() -> None:
    client = _client_with(
        fake_response_body(task_id="t1", urls=["https://x/1.png", "https://x/2.png"])
    )

    resp = generate_image(
        "two cats",
        model=ImageModel.IMAGE_01,
        aspect_ratio="16:9",
        n=2,
        response_format=ResponseFormat.URL,
        seed=42,
        client=client,
    )

    assert resp.id == "t1"
    assert len(resp.images) == 2
    assert resp.is_success

    # Verify the JSON sent to the API matches the docs' contract.
    sent = client.generate.call_args.args[0]
    assert sent["model"] == "image-01"
    assert sent["prompt"] == "two cats"
    assert sent["aspect_ratio"] == "16:9"
    assert sent["n"] == 2
    assert sent["seed"] == 42
    assert sent["response_format"] == "url"


def test_generate_image_image_to_image_includes_subject_reference() -> None:
    client = _client_with(fake_response_body(urls=["https://x/1.png"]))
    generate_image(
        "girl near a window",
        model="image-01",
        aspect_ratio="16:9",
        reference_images=["https://ref/a.jpg"],
        client=client,
    )
    sent = client.generate.call_args.args[0]
    assert sent["subject_reference"] == [{"type": "character", "image_file": "https://ref/a.jpg"}]


def test_generate_image_raises_on_api_failure_status() -> None:
    client = _client_with(
        fake_response_body(status_code=1001, status_msg="content blocked", urls=[])
    )
    with pytest.raises(MinimaxError, match="content blocked"):
        generate_image("forbidden content", client=client)


def test_generate_image_validates_arguments() -> None:
    client = MagicMock()
    with pytest.raises(ValueError, match="prompt must not be empty"):
        generate_image("", client=client)
    client.generate.assert_not_called()


def test_generate_image_owns_client_when_none_passed() -> None:
    # When no client is passed, generate_image must create and close one.
    from minimaximage.client import MinimaxClient

    real = MinimaxClient(api_key="dummy")
    real.generate = MagicMock(  # type: ignore[method-assign]
        return_value=fake_response_body(urls=["https://x/1.png"])
    )
    real.close = MagicMock()  # type: ignore[method-assign]

    # Patch the symbol used inside generate_image.
    import minimaximage.generate as g

    orig_client = g.MinimaxClient
    g.MinimaxClient = MagicMock(return_value=real)  # type: ignore[misc]
    try:
        generate_image("hi")
    finally:
        g.MinimaxClient = orig_client  # type: ignore[misc]

    real.close.assert_called_once()
