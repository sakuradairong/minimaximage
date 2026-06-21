"""Tests for settings loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minimaximage.config import (
    Settings,
    clear_config_value,
    load_config,
    save_config,
)


def test_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="MINIMAX_API_KEY"):
        Settings.from_env()


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "abc")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.example.com/")
    monkeypatch.setenv("MINIMAXIMAGE_MODEL", "image-01-live")
    monkeypatch.setenv("MINIMAXIMAGE_ASPECT_RATIO", "16:9")
    monkeypatch.setenv("MINIMAXIMAGE_N", "3")
    monkeypatch.setenv("MINIMAXIMAGE_RESPONSE_FORMAT", "base64")

    s = Settings.from_env()
    assert s.api_key == "abc"
    assert s.base_url == "https://api.example.com"  # trailing slash stripped
    assert s.model == "image-01-live"
    assert s.aspect_ratio == "16:9"
    assert s.n == 3
    assert s.response_format == "base64"


# --------------------------------------------------------------------------- #
# config file I/O
# --------------------------------------------------------------------------- #


def test_load_config_missing_returns_empty(tmp_path: Path) -> None:
    assert load_config(tmp_path / "absent.json") == {}


def test_load_config_invalid_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")
    assert load_config(path) == {}


def test_load_config_ignores_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "k", "garbage": 1, "model": "image-01"}))
    cfg = load_config(path)
    assert cfg == {"api_key": "k", "model": "image-01"}


def test_save_config_writes_atomically(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "config.json"
    returned = save_config({"api_key": "secret"}, path=target)
    assert returned == target
    assert json.loads(target.read_text()) == {"api_key": "secret"}
    # No leftover .tmp file.
    assert not (target.parent / "config.json.tmp").exists()


def test_save_config_filters_unknown_keys(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    save_config({"api_key": "k", "garbage": 1}, path=target)
    assert json.loads(target.read_text()) == {"api_key": "k"}


def test_clear_config_value_removes_key(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    save_config({"api_key": "k", "model": "image-01"}, path=target)
    assert clear_config_value("api_key", path=target) is True
    assert json.loads(target.read_text()) == {"model": "image-01"}
    # Second call is a no-op.
    assert clear_config_value("api_key", path=target) is False


# --------------------------------------------------------------------------- #
# Settings.load — resolution chain
# --------------------------------------------------------------------------- #


def test_load_explicit_api_key_wins_over_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "from-env")
    save_config({"api_key": "from-config"}, path=tmp_path / "c.json")
    s = Settings.load(api_key="from-cli", config_path=tmp_path / "c.json")
    assert s.api_key == "from-cli"


def test_load_config_api_key_wins_over_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "from-env")
    save_config({"api_key": "from-config"}, path=tmp_path / "c.json")
    s = Settings.load(config_path=tmp_path / "c.json")
    assert s.api_key == "from-config"


def test_load_falls_back_to_env_when_no_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "from-env")
    s = Settings.load(config_path=tmp_path / "missing.json")
    assert s.api_key == "from-env"


def test_load_raises_when_no_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    with pytest.raises(OSError, match="API key is not set"):
        Settings.load(config_path=tmp_path / "missing.json")


def test_load_uses_config_defaults_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.delenv("MINIMAXIMAGE_MODEL", raising=False)
    monkeypatch.delenv("MINIMAX_BASE_URL", raising=False)
    save_config(
        {"api_key": "k", "model": "image-01-live", "base_url": "https://x.example/"},
        path=tmp_path / "c.json",
    )
    s = Settings.load(config_path=tmp_path / "c.json")
    assert s.api_key == "k"
    assert s.model == "image-01-live"
    assert s.base_url == "https://x.example"  # trailing slash stripped


def test_load_env_overrides_config_for_optional_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setenv("MINIMAXIMAGE_MODEL", "image-01")
    save_config({"api_key": "k", "model": "image-01-live"}, path=tmp_path / "c.json")
    s = Settings.load(config_path=tmp_path / "c.json")
    assert s.model == "image-01"


def test_load_handles_invalid_n_in_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    save_config({"api_key": "k", "n": "not-a-number"}, path=tmp_path / "c.json")
    s = Settings.load(config_path=tmp_path / "c.json")
    assert s.n == 1  # falls back to default
