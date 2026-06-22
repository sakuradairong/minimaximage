"""Tests for the FastAPI web backend."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient  # type: ignore[import-not-found]

from minimaximage.server import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "minimaximage"}


def test_config_endpoint_hides_api_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MINIMAX_API_KEY", "secret")
    client = TestClient(create_app())
    response = client.get("/api/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["has_api_key"] is True
    assert "secret" not in str(payload)


def test_generate_endpoint_saves_images(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    image_payload = base64.b64encode(b"PNG").decode()
    fake_response = MagicMock()
    fake_response.id = "api-task"
    fake_response.success_count = 1
    fake_response.failed_count = 0
    fake_response.status_code = 0
    fake_response.status_msg = "success"
    fake_response.images = [MagicMock(value=image_payload, is_base64=True)]

    monkeypatch.setattr(
        "minimaximage.server.generate_with_settings",
        lambda *a, **kw: fake_response,
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/images/generate",
        json={
            "prompt": "a cat",
            "api_key": "inline-key",
            "response_format": "base64",
            "output_dir": str(tmp_path),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "api-task"
    assert payload["images"][0]["filename"] == "api-task.png"
    assert (tmp_path / "api-task.png").read_bytes() == b"PNG"
    assert (tmp_path / "history.json").exists()
