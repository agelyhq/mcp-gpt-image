"""Scenarios for generate_image, driven through the MCP client.

Each test runs the whole path: client, server, tool, fake SDK, file on disk.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from conftest import FAKE_JPEG_BYTES, error_text, payloads, sdk_error
from openai import BadRequestError, NotFoundError, RateLimitError

if TYPE_CHECKING:
    from conftest import FakeSdk
    from fastmcp import Client

# Parameters the gpt-image-2 endpoint rejects. None of them may ever be sent.
FORBIDDEN_KWARGS = ("response_format", "style", "input_fidelity")


async def test_generate_defaults_write_one_png(
    client: Client, fake_sdk: FakeSdk, output_dir: Path
) -> None:
    async with client:
        result = await client.call_tool("generate_image", {"prompt": "a red circle"})

    images = payloads(result)
    assert len(images) == 1
    assert images[0]["output_format"] == "png"
    assert images[0]["revised_prompt"]

    saved = Path(images[0]["path"])
    assert saved.parent == output_dir
    assert saved.is_file()
    assert saved.stat().st_size > 0

    sent = fake_sdk.generate_calls[0]
    assert sent["model"] == "gpt-image-2"
    assert sent["prompt"] == "a red circle"
    assert sent["n"] == 1
    for forbidden in FORBIDDEN_KWARGS:
        assert forbidden not in sent


async def test_generate_arbitrary_resolution_is_forwarded(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "a wide banner", "size": "1536x864"}
        )

    assert not result.is_error
    assert fake_sdk.generate_calls[0]["size"] == "1536x864"


async def test_generate_ten_images_returns_ten_distinct_paths(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        result = await client.call_tool("generate_image", {"prompt": "a blue square", "n": 10})

    images = payloads(result)
    paths = {image["path"] for image in images}
    assert len(paths) == 10
    assert all(Path(path).is_file() for path in paths)
    assert fake_sdk.generate_calls[0]["n"] == 10


async def test_generate_transparent_background_is_rejected_by_schema(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        result = await client.call_tool(
            "generate_image",
            {"prompt": "a logo", "background": "transparent"},
            raise_on_error=False,
        )

    assert result.is_error
    assert "background" in error_text(result)
    assert fake_sdk.generate_calls == []


@pytest.mark.parametrize(
    ("size", "reason"),
    [
        ("1000x1000", "multiples of 16"),
        ("4096x2160", "maximum is 3840x2160"),
        # Both dimensions are multiples of 16, so only the 3.2:1 ratio is wrong.
        ("1024x320", "aspect ratio"),
        ("big", "Use 'auto'"),
        # A zero dimension clears every bound, then divides by zero in the ratio
        # check. It has to fail as a validation error, not as a raw crash.
        ("0x1024", "Use 'auto'"),
        ("1024x0", "Use 'auto'"),
    ],
)
async def test_generate_invalid_size_errors_without_calling_the_api(
    client: Client, fake_sdk: FakeSdk, size: str, reason: str
) -> None:
    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "anything", "size": size}, raise_on_error=False
        )

    assert result.is_error
    assert reason in error_text(result)
    assert fake_sdk.generate_calls == []


async def test_generate_webp_request_answered_with_png_is_saved_as_png(
    client: Client, fake_sdk: FakeSdk
) -> None:
    """The API sometimes answers a webp request with PNG bytes.

    The extension has to follow the bytes, otherwise the file lies about itself.
    """
    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "a purple diamond", "output_format": "webp"}
        )

    images = payloads(result)
    assert images[0]["output_format"] == "png"
    assert images[0]["path"].endswith(".png")
    assert fake_sdk.generate_calls[0]["output_format"] == "webp"


async def test_generate_jpeg_sends_compression(client: Client, fake_sdk: FakeSdk) -> None:
    fake_sdk.image_bytes = FAKE_JPEG_BYTES

    async with client:
        result = await client.call_tool(
            "generate_image",
            {"prompt": "a green triangle", "output_format": "jpeg", "output_compression": 80},
        )

    images = payloads(result)
    assert images[0]["output_format"] == "jpeg"
    assert images[0]["path"].endswith(".jpeg")
    assert fake_sdk.generate_calls[0]["output_compression"] == 80


async def test_generate_png_omits_compression(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        await client.call_tool(
            "generate_image",
            {"prompt": "a red circle", "output_format": "png", "output_compression": 80},
        )

    assert "output_compression" not in fake_sdk.generate_calls[0]


async def test_generate_rate_limit_is_reported(client: Client, fake_sdk: FakeSdk) -> None:
    fake_sdk.error = sdk_error(RateLimitError, "Too many requests, slow down", 429)

    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "a red circle"}, raise_on_error=False
        )

    assert result.is_error
    assert "Rate limited" in error_text(result)


async def test_generate_bad_request_carries_the_api_message(
    client: Client, fake_sdk: FakeSdk
) -> None:
    fake_sdk.error = sdk_error(BadRequestError, "Unsupported parameter: 'style'", 400)

    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "a red circle"}, raise_on_error=False
        )

    assert result.is_error
    assert "Unsupported parameter: 'style'" in error_text(result)


async def test_generate_corrupt_payload_writes_nothing(
    client: Client, fake_sdk: FakeSdk, output_dir: Path
) -> None:
    fake_sdk.b64_override = base64.b64encode(b"not-an-image").decode()

    async with client:
        result = await client.call_tool(
            "generate_image", {"prompt": "a red circle"}, raise_on_error=False
        )

    assert result.is_error
    assert "not a PNG, a JPEG or a WEBP" in error_text(result)
    assert list(output_dir.glob("*")) == []


async def test_generate_low_moderation_is_forwarded(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        await client.call_tool(
            "generate_image", {"prompt": "a medical diagram", "moderation": "low"}
        )

    assert fake_sdk.generate_calls[0]["moderation"] == "low"


async def test_generate_unknown_model_surfaces_the_api_status(
    client: Client, fake_sdk: FakeSdk
) -> None:
    """A wrong GPT_IMAGE_MODEL comes back as a 404, which used to escape untranslated."""
    fake_sdk.error = sdk_error(NotFoundError, "The model 'gpt-image-9' does not exist", 404)

    async with client:
        result = await client.call_tool("generate_image", {"prompt": "a cat"}, raise_on_error=False)

    assert result.is_error
    message = error_text(result)
    assert "404" in message
    assert "gpt-image-9" in message
