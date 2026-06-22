"""Tests for the application use-case layer."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

from minimaximage.config import Settings
from minimaximage.generate import (
    build_generation_command,
    generate_with_settings,
    parse_reference_urls,
    save_response_images,
)
from tests.conftest import fake_response_body


def test_parse_reference_urls_splits_and_trims() -> None:
    assert parse_reference_urls(" https://a/1.png \n\nhttps://b/2.png") == [
        "https://a/1.png",
        "https://b/2.png",
    ]


def test_build_generation_command_coerces_form_values() -> None:
    command = build_generation_command(
        prompt="  a cat  ",
        model="image-01",
        aspect_ratio="1:1",
        n=2,
        seed="42",
        response_format="base64",
        prompt_optimizer=True,
        aigc_watermark=True,
        reference_text="https://ref/a.png",
    )

    kwargs = command.to_generate_kwargs()
    assert kwargs["prompt"] == "a cat"
    assert kwargs["model"] == "image-01"
    assert kwargs["aspect_ratio"] == "1:1"
    assert kwargs["seed"] == 42
    assert kwargs["response_format"] == "base64"
    assert kwargs["reference_images"] == ["https://ref/a.png"]


def test_generate_with_settings_uses_resolved_credentials() -> None:
    client = MagicMock()
    client.generate.return_value = fake_response_body(task_id="app", urls=[])
    settings = Settings(
        base_url="https://api.example.com",
        api_key="resolved-key",
        model="image-01",
        aspect_ratio=None,
        n=1,
        response_format="url",
    )
    command = build_generation_command(prompt="hi", model="image-01")

    factory = MagicMock(return_value=client)
    response = generate_with_settings(command, settings, client_factory=factory)

    assert response.id == "app"
    factory.assert_called_once_with(api_key="resolved-key", base_url="https://api.example.com")
    client.close.assert_called_once()


def test_save_response_images_writes_base64(tmp_path: Path) -> None:
    payload = base64.b64encode(b"PNG").decode()
    response = MagicMock()
    response.id = "saved"
    response.images = [MagicMock(value=payload, is_base64=True)]

    paths = save_response_images(response, tmp_path)

    assert paths == [tmp_path / "saved.png"]
    assert paths[0].read_bytes() == b"PNG"
