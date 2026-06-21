"""Tests for the HTTP client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from minimaximage.client import MinimaxClient, MinimaxError


def _client_with_post_return(post_return: object) -> MagicMock:
    """Build a fake httpx.Client instance whose `.post(...)` returns `post_return`."""
    http = MagicMock()
    http.post.return_value = post_return
    return http


def test_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        MinimaxClient(api_key="")


def test_client_post_returns_parsed_json() -> None:
    http = _client_with_post_return(
        MagicMock(status_code=200, json=lambda: {"data": {"image_urls": ["u"]}}, text="")
    )
    with patch("minimaximage.client.httpx.Client", return_value=http) as Client:
        c = MinimaxClient(api_key="k")
        body = c.generate({"prompt": "hi"})

    assert body == {"data": {"image_urls": ["u"]}}
    sent_kwargs = http.post.call_args.kwargs
    assert sent_kwargs["json"] == {"prompt": "hi"}
    headers = Client.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer k"
    assert headers["Content-Type"] == "application/json"


def test_client_raises_on_http_error() -> None:
    http = _client_with_post_return(MagicMock(status_code=500, text="boom", json=lambda: {}))
    with patch("minimaximage.client.httpx.Client", return_value=http):
        c = MinimaxClient(api_key="k")
        with pytest.raises(MinimaxError, match="HTTP 500"):
            c.generate({"prompt": "hi"})


def test_client_raises_on_non_json_body() -> None:
    resp = MagicMock(status_code=200, text="not-json")
    resp.json.side_effect = ValueError("not json")
    http = _client_with_post_return(resp)
    with patch("minimaximage.client.httpx.Client", return_value=http):
        c = MinimaxClient(api_key="k")
        with pytest.raises(MinimaxError, match="non-JSON"):
            c.generate({"prompt": "hi"})


def test_client_raises_on_unexpected_json_shape() -> None:
    http = _client_with_post_return(
        MagicMock(status_code=200, json=lambda: ["not", "a", "dict"], text="")
    )
    with patch("minimaximage.client.httpx.Client", return_value=http):
        c = MinimaxClient(api_key="k")
        with pytest.raises(MinimaxError, match="unexpected JSON shape"):
            c.generate({"prompt": "hi"})


def test_client_raises_on_transport_error() -> None:
    http = MagicMock()
    http.post.side_effect = httpx.ConnectError("dns failed")
    with patch("minimaximage.client.httpx.Client", return_value=http):
        c = MinimaxClient(api_key="k")
        with pytest.raises(MinimaxError, match="transport error"):
            c.generate({"prompt": "hi"})


def test_client_context_manager_closes() -> None:
    http = MagicMock()
    with patch("minimaximage.client.httpx.Client", return_value=http):
        with MinimaxClient(api_key="k") as c:
            assert c is not None
        http.close.assert_called_once()
