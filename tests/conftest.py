"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _stub_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure MINIMAX_API_KEY is set so Settings.from_env() works in tests."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key-not-real")
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)


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
