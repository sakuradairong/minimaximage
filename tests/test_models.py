"""Tests for the request/response dataclasses in minimaximage.models."""

from __future__ import annotations

import pytest

from minimaximage.models import (
    AspectRatio,
    ImageModel,
    ImageRequest,
    ResponseFormat,
    SubjectReference,
    parse_response,
)

# --------------------------------------------------------------------------- #
# ImageRequest validation
# --------------------------------------------------------------------------- #


def test_request_default_payload_has_required_fields() -> None:
    req = ImageRequest(prompt="a cat")
    payload = req.to_payload()
    assert payload["model"] == "image-01"
    assert payload["prompt"] == "a cat"
    assert payload["n"] == 1
    assert payload["response_format"] == "url"
    assert payload["prompt_optimizer"] is False
    assert "aspect_ratio" not in payload  # None is dropped
    assert "width" not in payload
    assert "subject_reference" not in payload


def test_request_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="prompt must not be empty"):
        ImageRequest(prompt="")
    with pytest.raises(ValueError, match="prompt must not be empty"):
        ImageRequest(prompt="   ")


def test_request_rejects_prompt_over_limit() -> None:
    with pytest.raises(ValueError, match="exceeds 1500"):
        ImageRequest(prompt="x" * 1501)


@pytest.mark.parametrize("n", [0, -1, 10])
def test_request_rejects_out_of_range_n(n: int) -> None:
    with pytest.raises(ValueError, match=r"n must be in \[1, 9\]"):
        ImageRequest(prompt="hi", n=n)


def test_request_accepts_width_height_for_image_01() -> None:
    req = ImageRequest(prompt="hi", model=ImageModel.IMAGE_01, width=1024, height=768)
    payload = req.to_payload()
    assert payload["width"] == 1024
    assert payload["height"] == 768


def test_request_rejects_width_height_for_image_01_live() -> None:
    with pytest.raises(ValueError, match="only supported by model 'image-01'"):
        ImageRequest(prompt="hi", model=ImageModel.IMAGE_01_LIVE, width=1024, height=768)


def test_request_requires_both_dimensions() -> None:
    with pytest.raises(ValueError, match="must be set together"):
        ImageRequest(prompt="hi", width=1024, height=None)


def test_request_rejects_dimension_out_of_range() -> None:
    with pytest.raises(ValueError, match=r"width must be in \[512, 2048\]"):
        ImageRequest(prompt="hi", width=256, height=1024)


def test_request_rejects_dimension_not_multiple_of_8() -> None:
    with pytest.raises(ValueError, match="multiple of 8"):
        ImageRequest(prompt="hi", width=1023, height=1024)


def test_request_rejects_ultra_wide_for_live_model() -> None:
    with pytest.raises(ValueError, match="not supported by model 'image-01-live'"):
        ImageRequest(
            prompt="hi",
            model=ImageModel.IMAGE_01_LIVE,
            aspect_ratio=AspectRatio.ULTRA_WIDE,
        )


def test_request_subject_reference_serializes() -> None:
    req = ImageRequest(
        prompt="hi",
        subject_reference=[SubjectReference(image_file="https://example.com/a.jpg")],
    )
    payload = req.to_payload()
    assert payload["subject_reference"] == [
        {"type": "character", "image_file": "https://example.com/a.jpg"}
    ]


def test_request_rejects_empty_subject_reference_url() -> None:
    with pytest.raises(ValueError, match="image_file"):
        ImageRequest(
            prompt="hi",
            subject_reference=[SubjectReference(image_file="")],
        )


# --------------------------------------------------------------------------- #
# AspectRatio metadata
# --------------------------------------------------------------------------- #


def test_aspect_ratio_pixel_mapping_matches_docs() -> None:
    assert (AspectRatio.SQUARE.width, AspectRatio.SQUARE.height) == (1024, 1024)
    assert (AspectRatio.WIDE.width, AspectRatio.WIDE.height) == (1280, 720)
    assert (AspectRatio.ULTRA_WIDE.width, AspectRatio.ULTRA_WIDE.height) == (1344, 576)


def test_ultra_wide_only_supported_by_image_01() -> None:
    assert AspectRatio.ULTRA_WIDE.supports(ImageModel.IMAGE_01) is True
    assert AspectRatio.ULTRA_WIDE.supports(ImageModel.IMAGE_01_LIVE) is False
    assert AspectRatio.SQUARE.supports(ImageModel.IMAGE_01_LIVE) is True


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #


def test_parse_response_with_urls() -> None:
    payload = {
        "id": "abc",
        "data": {"image_urls": ["https://x/1.png", "https://x/2.png"]},
        "metadata": {"success_count": "2", "failed_count": "0"},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }
    resp = parse_response(payload)
    assert resp.id == "abc"
    assert resp.is_success
    assert len(resp.images) == 2
    assert all(not img.is_base64 for img in resp.images)
    assert resp.success_count == 2
    assert resp.failed_count == 0


def test_parse_response_with_base64() -> None:
    payload = {
        "id": "xyz",
        "data": {"image_urls": ["aGVsbG8="]},
        "metadata": {"success_count": 1, "failed_count": 0},
        "base_resp": {"status_code": 0, "status_msg": "ok"},
    }
    resp = parse_response(payload)
    assert resp.images[0].is_base64
    assert resp.images[0].value == "aGVsbG8="


def test_parse_response_failure_status() -> None:
    payload = {
        "id": "bad",
        "data": {"image_urls": []},
        "metadata": {"success_count": 0, "failed_count": 1},
        "base_resp": {"status_code": 1001, "status_msg": "content blocked"},
    }
    resp = parse_response(payload)
    assert not resp.is_success
    assert resp.status_msg == "content blocked"


def test_parse_response_rejects_malformed_body() -> None:
    with pytest.raises(ValueError, match="Malformed response"):
        parse_response({"data": {}})


# --------------------------------------------------------------------------- #
# ImageModel.parse
# --------------------------------------------------------------------------- #


def test_image_model_parse_accepts_known() -> None:
    assert ImageModel.parse("image-01-live") is ImageModel.IMAGE_01_LIVE


def test_image_model_parse_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown model"):
        ImageModel.parse("gpt-4")


# Touch ResponseFormat so the import is considered used.
def test_response_format_values() -> None:
    assert ResponseFormat.URL.value == "url"
    assert ResponseFormat.BASE64.value == "base64"
