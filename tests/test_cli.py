"""Smoke tests for the CLI entry point."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minimaximage.cli import build_parser, main
from tests.conftest import fake_response_body


def test_parser_includes_expected_flags() -> None:
    p = build_parser()
    flags = {a.dest for a in p._actions}
    assert {
        "prompt",
        "model",
        "aspect_ratio",
        "width",
        "height",
        "n",
        "seed",
        "response_format",
        "prompt_optimizer",
        "watermark",
        "reference",
        "output_dir",
        "print_json",
    } <= flags


def test_cli_writes_image_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_dir = tmp_path / "out"
    # 1x1 transparent PNG, base64 encoded.
    png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()
    body = fake_response_body(task_id="cli-task", b64=[png_b64])
    client = MagicMock()
    client.generate.return_value = body

    with patch("minimaximage.generate.MinimaxClient", return_value=client):
        rc = main(
            [
                "a fluffy cat",
                "--aspect-ratio",
                "1:1",
                "--n",
                "1",
                "--output-dir",
                str(out_dir),
            ]
        )

    assert rc == 0
    out_files = list(out_dir.iterdir())
    assert len(out_files) == 1
    assert out_files[0].read_bytes().startswith(b"\x89PNG")
    captured = capsys.readouterr()
    assert "Generated 1 image" in captured.out


def test_cli_print_json_outputs_response(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = fake_response_body(task_id="t-json", urls=["https://x/1.png"])
    client = MagicMock()
    client.generate.return_value = body

    with patch("minimaximage.generate.MinimaxClient", return_value=client):
        rc = main(["hi", "--print-json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "t-json"
    assert payload["images"] == ["https://x/1.png"]


def test_cli_rejects_partial_dimensions() -> None:
    with pytest.raises(SystemExit):
        main(["hi", "--width", "1024"])


def test_cli_rejects_aspect_ratio_with_dimensions() -> None:
    with pytest.raises(SystemExit):
        main(["hi", "--aspect-ratio", "16:9", "--width", "1024", "--height", "576"])


def test_cli_returns_nonzero_on_api_error(capsys: pytest.CaptureFixture[str]) -> None:
    client = MagicMock()
    client.generate.return_value = fake_response_body(
        status_code=1001, status_msg="content blocked", urls=[]
    )
    with patch("minimaximage.generate.MinimaxClient", return_value=client):
        rc = main(["forbidden"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "content blocked" in err


def test_cli_returns_nonzero_on_missing_api_key(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing MINIMAX_API_KEY must surface as a clean error, not a traceback.

    Regression test for the PyInstaller binary: when Settings.from_env() raises
    EnvironmentError, main() must catch it and print a friendly message.
    """
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    rc = main(["hi"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "MINIMAX_API_KEY" in err or "API key" in err
    assert "Traceback" not in err


def test_cli_api_key_flag_overrides_env(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "from-env")

    body = fake_response_body(task_id="cli-api-key", urls=["https://x/1.png"])
    response = MagicMock()
    response.to_dict.return_value = body
    response.id = "cli-api-key"
    response.success_count = 1
    response.failed_count = 0
    response.images = []

    monkeypatch.setattr("minimaximage.cli.generate_image", lambda *a, **kw: response)

    rc = main(["hi", "--api-key", "from-cli", "--print-json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["id"] == "cli-api-key"
