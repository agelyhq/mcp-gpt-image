"""generate_image: text to image, one shot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from gpt_image_mcp.domain.results import ImageResult
from gpt_image_mcp.domain.types import (
    MAX_IMAGES_PER_CALL,
    MAX_PROMPT_CHARS,
    Background,
    Moderation,
    OutputFormat,
    Quality,
)
from gpt_image_mcp.tools._base import ToolDeps, reports_errors
from gpt_image_mcp.tools._validation import validate_size

if TYPE_CHECKING:
    from fastmcp import FastMCP

_SIZE_HELP = (
    "'auto', a preset (1024x1024, 1536x1024, 1024x1536), or any WIDTHxHEIGHT with "
    "both dimensions multiples of 16, an aspect ratio between 1:3 and 3:1, and a "
    "maximum of 3840x2160. Anything above 2560x1440 is experimental."
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register generate_image on the server."""

    @mcp.tool
    @reports_errors
    async def generate_image(
        prompt: Annotated[str, Field(max_length=MAX_PROMPT_CHARS)],
        size: Annotated[str, Field(description=_SIZE_HELP)] = "auto",
        quality: Quality = "auto",
        output_format: OutputFormat = "png",
        output_compression: Annotated[int, Field(ge=0, le=100)] = 100,
        background: Background = "auto",
        moderation: Moderation = "auto",
        n: Annotated[int, Field(ge=1, le=MAX_IMAGES_PER_CALL)] = 1,
    ) -> list[ImageResult]:
        """Draw one or more images from a text description and save them to disk.

        Returns the file paths, never the image bytes, so an image costs nothing to
        pass around and can be fed straight back into edit_image or refine_image.

        Transparent backgrounds do not exist on this model. Use opaque or auto.

        The output_format field of the result describes the bytes actually written,
        which can differ from what was asked: the API sometimes answers a webp
        request with a PNG, and the file is named after its real content.

        Args:
            prompt: What to draw. Detail helps; up to 32000 characters.
            size: See the field description. Wide sizes are useful for banners.
            quality: Higher quality costs more and takes longer.
            output_format: png keeps detail, jpeg and webp trade some for size.
            output_compression: 0 to 100, only applied to jpeg and webp.
            background: opaque forces a filled background, auto lets the model pick.
            moderation: low relaxes the default filtering on legitimate prompts.
            n: How many variations to draw in one call, up to 10.
        """
        validate_size(size)

        payloads = await deps.images.generate(
            prompt=prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            output_compression=output_compression,
            background=background,
            moderation=moderation,
            n=n,
        )

        return [deps.store.save(payload, prompt, i) for i, payload in enumerate(payloads, start=1)]
