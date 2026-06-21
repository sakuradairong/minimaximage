"""Thin HTTP client for the Minimax image_generation endpoint."""

from __future__ import annotations

import json
from typing import Any

import httpx


class MinimaxError(RuntimeError):
    """Raised when the API returns a non-success status or transport fails."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class MinimaxClient:
    """Synchronous client for POST /v1/image_generation.

    Holds an httpx.Client so callers can pass timeout / proxy kwargs once.
    """

    IMAGE_PATH = "/v1/image_generation"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.minimaxi.com",
        *,
        timeout: float = 120.0,
        **client_kwargs: Any,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            **client_kwargs,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MinimaxClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST the payload and return the parsed JSON body.

        Raises MinimaxError on transport failure, HTTP error, or non-JSON body.
        """
        try:
            response = self._client.post(self.IMAGE_PATH, json=payload)
        except httpx.HTTPError as e:
            raise MinimaxError(f"HTTP transport error: {e}") from e

        if response.status_code >= 400:
            raise MinimaxError(
                f"API returned HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
                body=response.text,
            )
        try:
            parsed: Any = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise MinimaxError(f"API returned non-JSON body: {response.text[:200]!r}") from e
        if not isinstance(parsed, dict):
            raise MinimaxError(f"API returned unexpected JSON shape: {parsed!r}")
        return parsed


__all__ = ["MinimaxClient", "MinimaxError"]
