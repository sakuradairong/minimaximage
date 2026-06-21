"""High-level image generation helpers built on top of MinimaxClient."""

from __future__ import annotations

from minimaximage.client import MinimaxClient, MinimaxError
from minimaximage.models import (
    AspectRatio,
    ImageModel,
    ImageRequest,
    ImageResponse,
    ResponseFormat,
    SubjectReference,
    parse_response,
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
    short-lived client is created.
    """
    # Normalize string enums to enum instances.
    model_e = ImageModel.parse(model) if isinstance(model, str) else model
    aspect_e = AspectRatio(aspect_ratio) if isinstance(aspect_ratio, str) else aspect_ratio
    fmt_e = ResponseFormat(response_format) if isinstance(response_format, str) else response_format

    refs: list[SubjectReference] = []
    for url in reference_images or []:
        refs.append(SubjectReference(image_file=url))

    request = ImageRequest(
        model=model_e,
        prompt=prompt,
        aspect_ratio=aspect_e,
        width=width,
        height=height,
        response_format=fmt_e,
        seed=seed,
        n=n,
        prompt_optimizer=prompt_optimizer,
        aigc_watermark=aigc_watermark,
        subject_reference=refs,
    )

    owns_client = client is None
    if owns_client:
        from minimaximage.client import MinimaxClient as _Client  # noqa: F401
        from minimaximage.config import Settings  # local to avoid cycle

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


__all__ = ["generate_image"]
