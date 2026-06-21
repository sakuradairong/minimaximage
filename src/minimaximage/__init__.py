"""minimaximage — generate images with the Minimax image_generation API."""

from minimaximage.client import MinimaxClient, MinimaxError
from minimaximage.config import (
    Settings,
    clear_config_value,
    config_path,
    load_config,
    save_config,
)
from minimaximage.generate import generate_image
from minimaximage.models import (
    AspectRatio,
    ImageModel,
    ImageRequest,
    ImageResponse,
    ImageResult,
    ResponseFormat,
    SubjectReference,
    parse_response,
)

__all__ = [
    "AspectRatio",
    "ImageModel",
    "ImageRequest",
    "ImageResponse",
    "ImageResult",
    "MinimaxClient",
    "MinimaxError",
    "ResponseFormat",
    "Settings",
    "SubjectReference",
    "clear_config_value",
    "config_path",
    "generate_image",
    "load_config",
    "parse_response",
    "save_config",
]

__version__ = "0.1.0"
