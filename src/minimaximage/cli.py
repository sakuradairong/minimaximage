"""Command-line entry point for minimaximage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from minimaximage.client import MinimaxClient
from minimaximage.config import Settings
from minimaximage.generate import (
    build_generation_command,
    generate_with_settings,
    save_response_images,
)
from minimaximage.models import (
    MAX_N,
    AspectRatio,
    ImageModel,
    ResponseFormat,
)


def _print_json(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="minimaximage",
        description=(
            "Generate images with the Minimax image_generation API (image-01 / image-01-live)."
        ),
    )
    p.add_argument("prompt", help="Text description of the image (≤1500 chars).")

    p.add_argument(
        "--model",
        choices=[m.value for m in ImageModel],
        default=None,
        help="Model name (default: $MINIMAXIMAGE_MODEL or image-01).",
    )
    p.add_argument(
        "--aspect-ratio",
        "--ar",
        dest="aspect_ratio",
        choices=[a.value for a in AspectRatio],
        default=None,
        help="Output aspect ratio. Mutually exclusive with --width/--height.",
    )
    p.add_argument(
        "--width",
        type=int,
        default=None,
        help="Output width in px (image-01 only; pairs with --height, multiple of 8, 512-2048).",
    )
    p.add_argument(
        "--height",
        type=int,
        default=None,
        help="Output height in px (image-01 only; must pair with --width).",
    )
    p.add_argument(
        "--n",
        type=int,
        default=None,
        help=f"Number of images to generate (1-{MAX_N}).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )
    p.add_argument(
        "--format",
        dest="response_format",
        choices=[f.value for f in ResponseFormat],
        default=None,
        help="How the API returns images: 'url' (24h expiry) or 'base64'.",
    )
    p.add_argument(
        "--prompt-optimizer",
        action="store_true",
        help="Ask the API to rewrite the prompt for better results.",
    )
    p.add_argument(
        "--watermark",
        action="store_true",
        help="Add an AIGC watermark to the generated images.",
    )
    p.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="URL",
        help="Reference image URL for image-to-image mode. Repeatable.",
    )
    p.add_argument(
        "--api-key",
        default=None,
        help=(
            "API key for this invocation. Overrides the saved config and the "
            "MINIMAX_API_KEY env var. Not persisted."
        ),
    )
    p.add_argument(
        "--output-dir",
        "-o",
        default="./output",
        help="Where to save generated images (default: ./output).",
    )
    p.add_argument(
        "--print-json",
        action="store_true",
        help="Print the full API response as JSON instead of saving files.",
    )
    return p


def _resolve_settings(args: argparse.Namespace) -> Settings:
    # Resolution order: --api-key flag → saved config → env vars.
    settings = Settings.load(api_key=args.api_key)
    # CLI overrides env/config defaults for optional fields.
    return Settings(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=args.model or settings.model,
        aspect_ratio=args.aspect_ratio or settings.aspect_ratio,
        n=args.n if args.n is not None else settings.n,
        response_format=args.response_format or settings.response_format,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = _resolve_settings(args)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if (args.width is None) != (args.height is None):
        parser.error("--width and --height must be set together")
    if args.aspect_ratio and (args.width or args.height):
        parser.error("--aspect-ratio is mutually exclusive with --width/--height")

    try:
        command = build_generation_command(
            prompt=args.prompt,
            model=args.model or settings.model,
            aspect_ratio=args.aspect_ratio or settings.aspect_ratio,
            width=args.width,
            height=args.height,
            response_format=args.response_format or settings.response_format,
            seed=args.seed,
            n=args.n if args.n is not None else settings.n,
            prompt_optimizer=args.prompt_optimizer,
            aigc_watermark=args.watermark,
            reference_images=args.reference or None,
        )
        response = generate_with_settings(command, settings, client_factory=MinimaxClient)
    except Exception as e:  # surface a clean error to the user
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.print_json:
        _print_json(response.to_dict())
        return 0

    out_dir = Path(args.output_dir)
    saved = save_response_images(response, out_dir)

    print(f"Generated {response.success_count} image(s); failed={response.failed_count}")
    for path in saved:
        print(path)
    return 0


__all__ = ["build_parser", "main"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
