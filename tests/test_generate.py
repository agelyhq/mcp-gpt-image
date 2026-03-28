"""E2E tests for generate_image tool.

Tests the full MCP lifecycle: Client → Server → (mocked) OpenAI API → file on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import Client


async def test_generate_single_image(client: Client, clean_output_dir: Path):
    """Generate a single image and verify file exists on disk."""
    async with client:
        result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A simple red circle on white background",
                "size": "1024x1024",
                "quality": "low",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1
    assert "path" in parsed[0]
    assert "revised_prompt" in parsed[0]

    image_path = Path(parsed[0]["path"])
    assert image_path.exists()
    assert image_path.suffix == ".png"
    assert image_path.stat().st_size > 0


async def test_generate_multiple_images(client: Client, clean_output_dir: Path):
    """Generate multiple images in a single request."""
    async with client:
        result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A blue square",
                "n": 2,
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 2

    for item in parsed:
        path = Path(item["path"])
        assert path.exists()
        assert path.stat().st_size > 0


async def test_generate_jpeg_format(client: Client, clean_output_dir: Path):
    """Generate image in JPEG format with compression."""
    async with client:
        result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A green triangle",
                "output_format": "jpeg",
                "output_compression": 80,
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1

    image_path = Path(parsed[0]["path"])
    assert image_path.exists()
    assert image_path.suffix == ".jpeg"


async def test_generate_transparent_background(client: Client, clean_output_dir: Path):
    """Generate PNG with transparent background."""
    async with client:
        result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A yellow star icon",
                "background": "transparent",
                "output_format": "png",
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1
    assert Path(parsed[0]["path"]).exists()


async def test_generate_webp_format(client: Client, clean_output_dir: Path):
    """Generate image in WebP format."""
    async with client:
        result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A purple diamond",
                "output_format": "webp",
                "output_compression": 90,
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1

    image_path = Path(parsed[0]["path"])
    assert image_path.exists()
    assert image_path.suffix == ".webp"
