"""pywebview desktop launcher for the FastAPI + React UI."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn  # type: ignore[import-not-found]

from minimaximage.server import create_app

HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ServerHandle:
    """Information about the background API server."""

    url: str
    thread: threading.Thread
    server: uvicorn.Server


def find_free_port(start: int = DEFAULT_PORT) -> int:
    """Find an available localhost TCP port."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("No free localhost port found")


def start_server(port: int | None = None) -> ServerHandle:
    """Start the FastAPI app in a background thread."""
    selected_port = port or find_free_port()
    config = uvicorn.Config(
        create_app(),
        host=HOST,
        port=selected_port,
        log_level="warning",
        access_log=False,
        log_config=None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="minimaximage-api", daemon=True)
    thread.start()
    url = f"http://{HOST}:{selected_port}"
    _wait_for_server(url)
    return ServerHandle(url=url, thread=thread, server=server)


def _wait_for_server(url: str, *, timeout: float = 8.0) -> None:
    """Wait briefly until uvicorn starts accepting connections."""
    import httpx

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{url}/api/health", timeout=0.5)
            if response.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - startup polling
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"API server did not start: {last_error}")


def _block_until_killed() -> None:
    """Keep the fallback browser server alive for desktop builds."""
    while True:
        time.sleep(3600)


def open_window(url: str) -> None:
    """Open the desktop window, falling back to a browser if pywebview fails."""
    try:
        import webview  # type: ignore[import-not-found]

        window_kwargs: dict[str, Any] = {
            "title": "minimaximage",
            "url": url,
            "width": 1280,
            "height": 860,
            "min_size": (960, 680),
        }
        webview.create_window(**window_kwargs)
        webview.start()
    except Exception:  # noqa: BLE001 - keep desktop launcher usable without pywebview
        _write_error_log("pywebview failed; falling back to browser")
        webbrowser.open(url)
        _block_until_killed()


def _error_log_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "minimaximage"
    base.mkdir(parents=True, exist_ok=True)
    return base / "desktop-error.log"


def _write_error_log(message: str) -> None:
    _error_log_path().write_text(
        f"{message}\n\n{traceback.format_exc()}",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    """Launch the local API and open the React UI in pywebview."""
    _ = argv
    handle: ServerHandle | None = None
    try:
        handle = start_server()
        open_window(handle.url)
        return 0
    except Exception as exc:  # noqa: BLE001 - entrypoint should show a clean error
        _write_error_log(f"Cannot start minimaximage desktop: {exc}")
        if sys.stderr is not None:
            print(f"Cannot start minimaximage desktop: {exc}", file=sys.stderr)
        return 1
    finally:
        if handle is not None:
            handle.server.should_exit = True


__all__ = ["find_free_port", "main", "open_window", "start_server"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
