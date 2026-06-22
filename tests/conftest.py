"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from minimaximage import config as config_module


@pytest.fixture(autouse=True)
def _stub_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure tests run with a hermetic environment.

    The user config file in %APPDATA% may contain a real API key from a prior
    session. Redirect ``config_path()`` to a temp path so tests are isolated
    from the host machine, while leaving the original ``load_config`` in
    place so explicit ``path=`` arguments still work.
    """
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key-not-real")
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
    for var in (
        "MINIMAXIMAGE_MODEL",
        "MINIMAXIMAGE_ASPECT_RATIO",
        "MINIMAXIMAGE_N",
        "MINIMAXIMAGE_RESPONSE_FORMAT",
    ):
        monkeypatch.delenv(var, raising=False)
    fake_config = tmp_path / "minimaximage" / "config.json"
    monkeypatch.setattr(config_module, "config_path", lambda: fake_config)


def fake_response_body(
    *,
    task_id: str = "task-abc",
    urls: list[str] | None = None,
    b64: list[str] | None = None,
    success: int | None = None,
    failed: int = 0,
    status_code: int = 0,
    status_msg: str = "success",
) -> dict:
    """Build a payload that mirrors the real API response shape."""
    images = urls or []
    if b64:
        images = b64
    return {
        "id": task_id,
        "data": {"image_urls": images},
        "metadata": {
            "success_count": success if success is not None else len(images),
            "failed_count": str(failed),
        },
        "base_resp": {"status_code": status_code, "status_msg": status_msg},
    }
