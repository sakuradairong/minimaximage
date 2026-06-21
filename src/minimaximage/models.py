"""Types and validation for the Minimax image_generation API.

Mirrors the request/response schema documented at
https://platform.minimaxi.com/docs/api-reference/image-generation-t2i and
.../image-generation-i2i.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from minimaximage.download import download_to_path


class ImageModel(str, Enum):
    """Supported image generation models."""

    IMAGE_01 = "image-01"
    IMAGE_01_LIVE = "image-01-live"

    @classmethod
    def parse(cls, value: str) -> ImageModel:
        try:
            return cls(value)
        except ValueError as e:
            raise ValueError(f"Unknown model {value!r}. Supported: {[m.value for m in cls]}") from e


class AspectRatio(str, Enum):
    """Aspect ratios and the exact pixel dimensions they map to."""

    SQUARE = "1:1"  # 1024x1024
    WIDE = "16:9"  # 1280x720
    STANDARD = "4:3"  # 1152x864
    PHOTO = "3:2"  # 1248x832
    PORTRAIT_2_3 = "2:3"  # 832x1248
    PORTRAIT_3_4 = "3:4"  # 864x1152
    TALL = "9:16"  # 720x1280
    ULTRA_WIDE = "21:9"  # 1344x576 — image-01 only

    @property
    def width(self) -> int:
        return _PIXELS[self][0]

    @property
    def height(self) -> int:
        return _PIXELS[self][1]

    def supports(self, model: ImageModel) -> bool:
        """21:9 is restricted to image-01."""
        if self is AspectRatio.ULTRA_WIDE and model is not ImageModel.IMAGE_01:
            return False
        return True


_PIXELS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.SQUARE: (1024, 1024),
    AspectRatio.WIDE: (1280, 720),
    AspectRatio.STANDARD: (1152, 864),
    AspectRatio.PHOTO: (1248, 832),
    AspectRatio.PORTRAIT_2_3: (832, 1248),
    AspectRatio.PORTRAIT_3_4: (864, 1152),
    AspectRatio.TALL: (720, 1280),
    AspectRatio.ULTRA_WIDE: (1344, 576),
}

# API hard limits from the docs.
MAX_PROMPT_LEN = 1500
MAX_N = 9
MIN_DIM = 512
MAX_DIM = 2048


class ResponseFormat(str, Enum):
    URL = "url"
    BASE64 = "base64"


@dataclass(frozen=True)
class SubjectReference:
    """A reference image used for image-to-image (人物主体参考)."""

    image_file: str  # URL of the reference image
    type: str = "character"  # currently only "character" is documented

    def to_payload(self) -> dict[str, Any]:
        return {"type": self.type, "image_file": self.image_file}


@dataclass
class ImageRequest:
    """Parameters for POST /v1/image_generation.

    Pass `subject_reference` (one or more) to enable image-to-image mode.
    """

    model: ImageModel = ImageModel.IMAGE_01
    prompt: str = ""
    aspect_ratio: AspectRatio | None = None
    width: int | None = None
    height: int | None = None
    response_format: ResponseFormat = ResponseFormat.URL
    seed: int | None = None
    n: int = 1
    prompt_optimizer: bool = False
    aigc_watermark: bool = False
    subject_reference: list[SubjectReference] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if len(self.prompt) > MAX_PROMPT_LEN:
            raise ValueError(f"prompt exceeds {MAX_PROMPT_LEN} characters (got {len(self.prompt)})")
        if not (1 <= self.n <= MAX_N):
            raise ValueError(f"n must be in [1, {MAX_N}], got {self.n}")

        # width/height: image-01 only, must be set together, in range, multiple of 8.
        if self.width is not None or self.height is not None:
            if self.model is not ImageModel.IMAGE_01:
                raise ValueError("width/height are only supported by model 'image-01'")
            if self.width is None or self.height is None:
                raise ValueError("width and height must be set together")
            if not (MIN_DIM <= self.width <= MAX_DIM):
                raise ValueError(f"width must be in [{MIN_DIM}, {MAX_DIM}], got {self.width}")
            if self.width % 8 != 0:
                raise ValueError(f"width must be a multiple of 8, got {self.width}")
            if not (MIN_DIM <= self.height <= MAX_DIM):
                raise ValueError(f"height must be in [{MIN_DIM}, {MAX_DIM}], got {self.height}")
            if self.height % 8 != 0:
                raise ValueError(f"height must be a multiple of 8, got {self.height}")

        if self.aspect_ratio is not None and not self.aspect_ratio.supports(self.model):
            raise ValueError(
                f"aspect_ratio {self.aspect_ratio.value!r} is not supported by "
                f"model {self.model.value!r}"
            )

        if self.subject_reference and not all(ref.image_file for ref in self.subject_reference):
            raise ValueError("subject_reference entries must include image_file")

    def to_payload(self) -> dict[str, Any]:
        """Build the JSON body. Drops None values to keep the request clean."""
        body: dict[str, Any] = {
            "model": self.model.value,
            "prompt": self.prompt,
            "n": self.n,
            "response_format": self.response_format.value,
            "prompt_optimizer": self.prompt_optimizer,
            "aigc_watermark": self.aigc_watermark,
        }
        if self.aspect_ratio is not None:
            body["aspect_ratio"] = self.aspect_ratio.value
        if self.width is not None:
            body["width"] = self.width
        if self.height is not None:
            body["height"] = self.height
        if self.seed is not None:
            body["seed"] = self.seed
        if self.subject_reference:
            body["subject_reference"] = [r.to_payload() for r in self.subject_reference]
        return body


@dataclass(frozen=True)
class ImageResult:
    """One generated image (URL or base64)."""

    value: str  # either an https:// URL or base64-encoded data
    is_base64: bool

    def save(self, path: str) -> None:
        """Write the image to disk. base64 is decoded; URLs are fetched."""
        if self.is_base64:
            data = base64.b64decode(self.value)
            with open(path, "wb") as fh:
                fh.write(data)
        else:
            download_to_path(self.value, path)


@dataclass(frozen=True)
class ImageResponse:
    """Parsed API response."""

    id: str
    images: list[ImageResult]
    success_count: int
    failed_count: int
    status_code: int
    status_msg: str

    @property
    def is_success(self) -> bool:
        return self.status_code == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "images": [r.value for r in self.images],
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "status_code": self.status_code,
            "status_msg": self.status_msg,
        }


def parse_response(payload: dict[str, Any]) -> ImageResponse:
    """Parse the raw JSON body into an ImageResponse, or raise on shape errors."""
    try:
        base_resp = payload["base_resp"]
        metadata = payload.get("metadata", {})
        data = payload.get("data", {})
        raw_images = data.get("image_urls") or data.get("images") or []
    except (KeyError, TypeError) as e:
        raise ValueError(f"Malformed response: missing field {e!s}") from e

    images: list[ImageResult] = []
    for entry in raw_images:
        if isinstance(entry, str):
            # Heuristic: base64 strings are long and contain no "://"
            images.append(ImageResult(value=entry, is_base64=("://" not in entry)))
        elif isinstance(entry, dict):
            url = entry.get("url") or entry.get("image_url", "")
            b64 = entry.get("base64") or entry.get("b64", "")
            if b64:
                images.append(ImageResult(value=b64, is_base64=True))
            elif url:
                images.append(ImageResult(value=url, is_base64=False))
        else:
            raise ValueError(f"Unexpected image entry type: {type(entry).__name__}")

    return ImageResponse(
        id=payload.get("id", ""),
        images=images,
        success_count=int(metadata.get("success_count", len(images))),
        failed_count=int(metadata.get("failed_count", 0)),
        status_code=int(base_resp.get("status_code", -1)),
        status_msg=str(base_resp.get("status_msg", "")),
    )


__all__ = [
    "AspectRatio",
    "ImageModel",
    "ImageRequest",
    "ImageResponse",
    "ImageResult",
    "ResponseFormat",
    "SubjectReference",
    "parse_response",
    "asdict",  # re-exported for downstream use
    "MAX_PROMPT_LEN",
    "MAX_N",
    "MIN_DIM",
    "MAX_DIM",
]
