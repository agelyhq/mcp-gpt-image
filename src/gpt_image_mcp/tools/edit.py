"""edit_image: local images in, edited image out, one shot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from gpt_image_mcp.domain.results import ImageResult
from gpt_image_mcp.domain.types import (
    MAX_EDIT_IMAGES,
    MAX_IMAGES_PER_CALL,
    MAX_PROMPT_CHARS,
    Background,
    OutputFormat,
    Quality,
)
from gpt_image_mcp.tools._base import ToolDeps, reports_errors
from gpt_image_mcp.tools._validation import validate_input_images, validate_mask, validate_size

if TYPE_CHECKING:
    from fastmcp import FastMCP

_SIZE_HELP = (
    "'auto', a preset (1024x1024, 1536x1024, 1024x1536), or any WIDTHxHEIGHT with "
    "both dimensions multiples of 16, an aspect ratio between 1:3 and 3:1, and a "
    "maximum of 3840x2160."
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register edit_image on the server."""

    @mcp.tool
    @reports_errors
    async def edit_image(
        prompt: Annotated[str, Field(max_length=MAX_PROMPT_CHARS)],
        image_paths: Annotated[list[str], Field(min_length=1, max_length=MAX_EDIT_IMAGES)],
        mask_path: str | None = None,
        size: Annotated[str, Field(description=_SIZE_HELP)] = "auto",
        quality: Quality = "auto",
        output_format: OutputFormat = "png",
        output_compression: Annotated[int, Field(ge=0, le=100)] = 100,
        background: Background = "auto",
        n: Annotated[int, Field(ge=1, le=MAX_IMAGES_PER_CALL)] = 1,
    ) -> list[ImageResult]:
        """Modify local images, or compose several of them into one, and save the result.

        Pass one image to change it, or several to combine them: the prompt decides
        what each one contributes. Every input is processed at full fidelity, so
        faces, logos and text survive the edit without a setting to turn on.

        Use this for a single instruction. When an image needs several rounds of
        correction, refine_image keeps the conversation and costs less to steer.

        Args:
            prompt: What to change, add, remove, or how to combine the inputs.
            image_paths: Local paths to the source images, up to 16, under 50MB each.
            mask_path: Optional PNG whose transparent areas mark what to repaint.
                It must match the dimensions of the first image.
            size: See the field description.
            quality: Higher quality costs more and takes longer.
            output_format: png keeps detail, jpeg and webp trade some for size.
            output_compression: 0 to 100, only applied to jpeg and webp.
            background: opaque forces a filled background, auto lets the model pick.
            n: How many variations to produce in one call, up to 10.
        """
        validate_size(size)
        images = validate_input_images(image_paths)
        mask = validate_mask(mask_path)

        payloads = await deps.images.edit(
            prompt=prompt,
            image_paths=images,
            mask_path=mask,
            size=size,
            quality=quality,
            output_format=output_format,
            output_compression=output_compression,
            background=background,
            n=n,
        )

        return [deps.store.save(payload, prompt, i) for i, payload in enumerate(payloads, start=1)]
