"""minimaximage — generate images with the Minimax image_generation API."""

from minimaximage.client import MinimaxClient, MinimaxError
from minimaximage.config import (
    Settings,
    clear_config_value,
    config_path,
    load_config,
    save_config,
)
from minimaximage.generate import (
    ImageGenerationCommand,
    build_generation_command,
    generate_and_save,
    generate_image,
    generate_with_settings,
    parse_reference_urls,
    save_response_images,
)
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
    "ImageGenerationCommand",
    "ImageModel",
    "ImageRequest",
    "ImageResponse",
    "ImageResult",
    "MinimaxClient",
    "MinimaxError",
    "ResponseFormat",
    "Settings",
    "SubjectReference",
    "build_generation_command",
    "clear_config_value",
    "config_path",
    "generate_and_save",
    "generate_image",
    "generate_with_settings",
    "load_config",
    "parse_reference_urls",
    "parse_response",
    "save_config",
    "save_response_images",
]

__version__ = "0.1.0"
