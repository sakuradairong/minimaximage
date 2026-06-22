"""Application use-cases and SDK helpers for image generation.

This module is the project's application boundary: adapters such as the CLI and
GUI translate user input into an ``ImageGenerationCommand``; this layer coerces
that input into domain models, calls the Minimax API client, and can persist the
returned images.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from minimaximage.client import MinimaxClient, MinimaxError
from minimaximage.config import Settings
from minimaximage.download import default_filename, download_to_path
from minimaximage.models import (
    AspectRatio,
    ImageModel,
    ImageRequest,
    ImageResponse,
    ResponseFormat,
    SubjectReference,
    parse_response,
)


class ClientFactory(Protocol):
    """Callable that creates a configured Minimax client."""

    def __call__(self, *, api_key: str, base_url: str) -> MinimaxClient: ...


@dataclass(frozen=True)
class ImageGenerationCommand:
    """Validated user intent for one image-generation request."""

    prompt: str
    model: ImageModel
    aspect_ratio: AspectRatio | None = None
    width: int | None = None
    height: int | None = None
    response_format: ResponseFormat = ResponseFormat.URL
    seed: int | None = None
    n: int = 1
    prompt_optimizer: bool = False
    aigc_watermark: bool = False
    reference_images: list[str] | None = None

    def to_generate_kwargs(self) -> dict[str, Any]:
        """Return kwargs accepted by ``generate_image``."""
        return {
            "prompt": self.prompt,
            "model": self.model,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "response_format": self.response_format,
            "seed": self.seed,
            "n": self.n,
            "prompt_optimizer": self.prompt_optimizer,
            "aigc_watermark": self.aigc_watermark,
            "reference_images": self.reference_images,
        }


def parse_reference_urls(text: str) -> list[str]:
    """Parse newline-separated reference image URLs."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_generation_command(
    *,
    prompt: str,
    model: ImageModel | str,
    aspect_ratio: AspectRatio | str | None = None,
    width: int | None = None,
    height: int | None = None,
    n: int = 1,
    seed: int | str | None = None,
    response_format: ResponseFormat | str = ResponseFormat.URL,
    prompt_optimizer: bool = False,
    aigc_watermark: bool = False,
    reference_images: list[str] | None = None,
    reference_text: str | None = None,
) -> ImageGenerationCommand:
    """Coerce adapter input into a typed generation command."""
    model_e = ImageModel.parse(model) if isinstance(model, str) else model
    if isinstance(aspect_ratio, str):
        aspect_e = AspectRatio(aspect_ratio) if aspect_ratio else None
    else:
        aspect_e = aspect_ratio
    fmt_e = ResponseFormat(response_format) if isinstance(response_format, str) else response_format

    refs = list(reference_images or [])
    if reference_text:
        refs.extend(parse_reference_urls(reference_text))

    if isinstance(seed, str):
        seed_value = int(seed) if seed.strip() else None
    else:
        seed_value = seed

    return ImageGenerationCommand(
        prompt=prompt.strip(),
        model=model_e,
        aspect_ratio=aspect_e,
        width=width,
        height=height,
        response_format=fmt_e,
        seed=seed_value,
        n=n,
        prompt_optimizer=prompt_optimizer,
        aigc_watermark=aigc_watermark,
        reference_images=refs or None,
    )


def generate_image(
    prompt: str,
    *,
    model: ImageModel | str = ImageModel.IMAGE_01,
    aspect_ratio: AspectRatio | str | None = None,
    width: int | None = None,
    height: int | None = None,
    response_format: ResponseFormat | str = ResponseFormat.URL,
    seed: int | None = None,
    n: int = 1,
    prompt_optimizer: bool = False,
    aigc_watermark: bool = False,
    reference_images: list[str] | None = None,
    client: MinimaxClient | None = None,
) -> ImageResponse:
    """Run a single image generation request.

    Pass `reference_images` (URLs) to switch into image-to-image mode.
    The caller owns the client lifecycle when passing one in; otherwise a
    short-lived client is created from environment settings.
    """
    command = build_generation_command(
        prompt=prompt,
        model=model,
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        response_format=response_format,
        seed=seed,
        n=n,
        prompt_optimizer=prompt_optimizer,
        aigc_watermark=aigc_watermark,
        reference_images=reference_images,
    )

    refs = [SubjectReference(image_file=url) for url in command.reference_images or []]
    request = ImageRequest(
        model=command.model,
        prompt=command.prompt,
        aspect_ratio=command.aspect_ratio,
        width=command.width,
        height=command.height,
        response_format=command.response_format,
        seed=command.seed,
        n=command.n,
        prompt_optimizer=command.prompt_optimizer,
        aigc_watermark=command.aigc_watermark,
        subject_reference=refs,
    )

    owns_client = client is None
    if owns_client:
        # Lazy-load settings to defer env access for unit tests.
        settings = Settings.from_env()
        client = MinimaxClient(api_key=settings.api_key, base_url=settings.base_url)

    try:
        body = client.generate(request.to_payload())
    finally:
        if owns_client:
            client.close()

    response = parse_response(body)
    if not response.is_success:
        raise MinimaxError(
            f"API reported failure: {response.status_msg} (code={response.status_code})",
            body=body,
        )
    return response


def generate_with_settings(
    command: ImageGenerationCommand,
    settings: Settings,
    *,
    client_factory: ClientFactory = MinimaxClient,
) -> ImageResponse:
    """Execute a generation command using resolved settings."""
    client = client_factory(api_key=settings.api_key, base_url=settings.base_url)
    try:
        return generate_image(**command.to_generate_kwargs(), client=client)
    finally:
        client.close()


def save_response_images(response: ImageResponse | Any, out_dir: Path) -> list[Path]:
    """Persist every image in the response to ``out_dir`` and return paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, img in enumerate(response.images):
        path = out_dir / default_filename(response.id, idx)
        if img.is_base64:
            path.write_bytes(base64.b64decode(img.value))
        else:
            download_to_path(img.value, str(path))
        paths.append(path)
    return paths


def generate_and_save(
    command: ImageGenerationCommand,
    settings: Settings,
    out_dir: Path,
    *,
    client_factory: ClientFactory = MinimaxClient,
) -> list[Path]:
    """Execute a command and save all returned images."""
    response = generate_with_settings(command, settings, client_factory=client_factory)
    return save_response_images(response, out_dir)


__all__ = [
    "ImageGenerationCommand",
    "build_generation_command",
    "generate_and_save",
    "generate_image",
    "generate_with_settings",
    "parse_reference_urls",
    "save_response_images",
]
