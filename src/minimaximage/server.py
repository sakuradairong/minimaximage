"""FastAPI backend for the modern minimaximage web/desktop UI."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException  # type: ignore[import-not-found]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, HTMLResponse  # type: ignore[import-not-found]
from fastapi.staticfiles import StaticFiles  # type: ignore[import-not-found]
from pydantic import BaseModel, Field  # type: ignore[import-not-found]

from minimaximage.config import Settings, load_config, save_config
from minimaximage.generate import (
    build_generation_command,
    generate_with_settings,
    save_response_images,
)
from minimaximage.models import ImageModel, ResponseFormat

APP_NAME = "minimaximage"
DEFAULT_OUTPUT_DIR = Path("./output")
HISTORY_FILE = "history.json"


class ConfigResponse(BaseModel):
    """Public config state. The API key value is never returned."""

    has_api_key: bool
    base_url: str
    model: str
    aspect_ratio: str | None
    n: int
    response_format: str


class ConfigUpdate(BaseModel):
    """Config values that can be persisted from the UI."""

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    aspect_ratio: str | None = None
    n: int | None = Field(default=None, ge=1, le=9)
    response_format: str | None = None


class GenerateRequest(BaseModel):
    """Request body for image generation."""

    prompt: str = Field(min_length=1, max_length=1500)
    model: Literal["image-01", "image-01-live"] = "image-01"
    aspect_ratio: str | None = "1:1"
    width: int | None = None
    height: int | None = None
    n: int = Field(default=1, ge=1, le=9)
    seed: int | None = None
    response_format: Literal["url", "base64"] = "url"
    prompt_optimizer: bool = False
    aigc_watermark: bool = False
    reference_images: list[str] = Field(default_factory=list)
    api_key: str | None = None
    output_dir: str | None = None


class GeneratedImage(BaseModel):
    """One saved generated image."""

    filename: str
    path: str
    file_url: str


class GenerateResponse(BaseModel):
    """Response body returned to the frontend."""

    id: str
    success_count: int
    failed_count: int
    status_code: int
    status_msg: str
    images: list[GeneratedImage]


class HistoryItem(BaseModel):
    """A compact generation-history record."""

    id: str
    created_at: str
    prompt: str
    model: str
    n: int
    images: list[GeneratedImage]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return _project_root()


def frontend_dist_dir() -> Path:
    """Return the built React frontend directory, if present."""
    override = os.environ.get("MINIMAXIMAGE_FRONTEND_DIR")
    if override:
        return Path(override)
    candidates = [
        _bundle_root() / "frontend" / "dist",
        _project_root() / "frontend" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return candidates[-1]


def _model_dump(model: BaseModel, *, exclude_none: bool = False) -> dict[str, Any]:
    """Return a dict for both Pydantic v1 and v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=exclude_none)
    return model.dict(exclude_none=exclude_none)


def _history_path(output_dir: Path) -> Path:
    return output_dir / HISTORY_FILE


def _load_history(output_dir: Path) -> list[dict[str, Any]]:
    path = _history_path(output_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save_history(output_dir: Path, history: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _history_path(output_dir).write_text(json.dumps(history[:100], indent=2), encoding="utf-8")


def _settings_or_400(api_key: str | None = None) -> Settings:
    try:
        return Settings.load(api_key=api_key or None)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    app = FastAPI(title="minimaximage API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": APP_NAME}

    @app.get("/api/config", response_model=ConfigResponse)
    def get_config() -> ConfigResponse:
        config = load_config()
        env_key = os.environ.get("MINIMAX_API_KEY", "").strip()
        try:
            settings = Settings.load()
        except OSError:
            settings = Settings(
                base_url=str(config.get("base_url") or "https://api.minimaxi.com"),
                api_key="",
                model=str(config.get("model", ImageModel.IMAGE_01.value)),
                aspect_ratio=config.get("aspect_ratio"),
                n=int(config.get("n", 1) or 1),
                response_format=str(config.get("response_format", ResponseFormat.URL.value)),
            )
        return ConfigResponse(
            has_api_key=bool(config.get("api_key") or env_key),
            base_url=settings.base_url,
            model=settings.model,
            aspect_ratio=settings.aspect_ratio,
            n=settings.n,
            response_format=settings.response_format,
        )

    @app.post("/api/config", response_model=ConfigResponse)
    def update_config(payload: ConfigUpdate) -> ConfigResponse:
        current = load_config()
        updates = _model_dump(payload, exclude_none=True)
        if "api_key" in updates:
            updates["api_key"] = str(updates["api_key"]).strip()
        save_config({**current, **updates})
        return get_config()

    @app.post("/api/images/generate", response_model=GenerateResponse)
    def generate(payload: GenerateRequest) -> GenerateResponse:
        settings = _settings_or_400(payload.api_key)
        if payload.aspect_ratio and (payload.width or payload.height):
            raise HTTPException(
                status_code=422,
                detail="aspect_ratio is mutually exclusive with width/height",
            )
        command = build_generation_command(
            prompt=payload.prompt,
            model=payload.model,
            aspect_ratio=payload.aspect_ratio,
            width=payload.width,
            height=payload.height,
            n=payload.n,
            seed=payload.seed,
            response_format=payload.response_format,
            prompt_optimizer=payload.prompt_optimizer,
            aigc_watermark=payload.aigc_watermark,
            reference_images=payload.reference_images,
        )
        output_dir = Path(payload.output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()
        try:
            response = generate_with_settings(command, settings)
            paths = save_response_images(response, output_dir)
        except Exception as exc:  # noqa: BLE001 - API boundary should return clean errors
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        images = [
            GeneratedImage(
                filename=path.name,
                path=str(path),
                file_url=f"/api/files/{path.name}",
            )
            for path in paths
        ]
        item = HistoryItem(
            id=response.id,
            created_at=datetime.now(UTC).isoformat(),
            prompt=payload.prompt,
            model=payload.model,
            n=payload.n,
            images=images,
        )
        history = [_model_dump(item), *_load_history(output_dir)]
        _save_history(output_dir, history)
        return GenerateResponse(
            id=response.id,
            success_count=response.success_count,
            failed_count=response.failed_count,
            status_code=response.status_code,
            status_msg=response.status_msg,
            images=images,
        )

    @app.get("/api/images/history", response_model=list[HistoryItem])
    def history(output_dir: str | None = None) -> list[HistoryItem]:
        target = Path(output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve()
        return [HistoryItem(**item) for item in _load_history(target)]

    @app.get("/api/files/{filename}")
    def file(filename: str, output_dir: str | None = None) -> FileResponse:
        if "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="invalid filename")
        target = Path(output_dir or DEFAULT_OUTPUT_DIR).expanduser().resolve() / filename
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(target)

    dist = frontend_dist_dir()
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", response_class=HTMLResponse, response_model=None)
    def spa(path: str = ""):
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return HTMLResponse(
            """
            <html><body style="font-family: sans-serif; padding: 2rem">
              <h1>minimaximage API is running</h1>
              <p>
                Build the React frontend with
                <code>cd frontend && npm install && npm run build</code>.
              </p>
              <p>API health: <a href="/api/health">/api/health</a></p>
            </body></html>
            """
        )

    return app


app = create_app()


__all__ = ["app", "create_app", "frontend_dist_dir"]
