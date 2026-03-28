"""edit_image MCP tool registration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from openai import BadRequestError, RateLimitError

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from openai_imagegen_mcp.openai_client import ImageClient


def register_edit_tool(mcp: FastMCP, client: ImageClient) -> None:
    """Register the edit_image tool on the MCP server."""

    @mcp.tool
    async def edit_image(
        prompt: str,
        image_paths: list[str],
        mask_path: str | None = None,
        model: str = "gpt-image-1.5",
        size: str = "auto",
        quality: str = "auto",
        output_format: str = "png",
        output_compression: int = 100,
        background: str = "auto",
        input_fidelity: str = "low",
    ) -> list[dict[str, Any]]:
        """Edit existing image(s) with a text prompt using OpenAI's Image API.

        Supports adding/removing elements, style transfer, and inpainting with mask.

        Args:
            prompt: Text description of the edit to apply.
            image_paths: List of local file paths to source images (1-5).
            mask_path: Optional PNG with alpha channel for inpainting.
            model: Model to use (gpt-image-1.5, gpt-image-1, gpt-image-1-mini).
            size: Image size (1024x1024, 1536x1024, 1024x1536, auto).
            quality: Image quality (low, medium, high, auto).
            output_format: Output format (png, jpeg, webp).
            output_compression: Compression level 0-100 (jpeg/webp only).
            background: Background type (transparent, opaque, auto).
            input_fidelity: Input fidelity (low, high). High preserves faces/logos.

        Returns:
            List of dicts with 'path' (local file path) and 'revised_prompt'.
        """
        _validate_edit_params(
            image_paths,
            mask_path,
            size,
            quality,
            output_format,
            output_compression,
            background,
            input_fidelity,
        )

        try:
            return await client.edit(
                prompt=prompt,
                image_paths=image_paths,
                mask_path=mask_path,
                model=model,
                size=size,
                quality=quality,
                output_format=output_format,
                output_compression=output_compression,
                background=background,
                input_fidelity=input_fidelity,
            )
        except BadRequestError as exc:
            return [{"error": f"Content policy violation or bad request: {exc.message}"}]
        except RateLimitError as exc:
            return [{"error": f"Rate limited: {exc.message}"}]


def _validate_edit_params(
    image_paths: list[str],
    mask_path: str | None,
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    background: str,
    input_fidelity: str,
) -> None:
    if not image_paths:
        raise ValueError("At least one image_path is required")

    if len(image_paths) > 5:
        raise ValueError(f"Maximum 5 input images, got {len(image_paths)}")

    for p in image_paths:
        if not Path(p).is_file():
            raise ValueError(f"Image file not found: {p}")

    if mask_path and not Path(mask_path).is_file():
        raise ValueError(f"Mask file not found: {mask_path}")

    valid_sizes = {"1024x1024", "1536x1024", "1024x1536", "auto"}
    if size not in valid_sizes:
        raise ValueError(f"Invalid size '{size}'. Must be one of {valid_sizes}")

    valid_qualities = {"low", "medium", "high", "auto"}
    if quality not in valid_qualities:
        raise ValueError(f"Invalid quality '{quality}'. Must be one of {valid_qualities}")

    valid_formats = {"png", "jpeg", "webp"}
    if output_format not in valid_formats:
        raise ValueError(f"Invalid format '{output_format}'. Must be one of {valid_formats}")

    if not 0 <= output_compression <= 100:
        raise ValueError(f"output_compression must be 0-100, got {output_compression}")

    valid_backgrounds = {"transparent", "opaque", "auto"}
    if background not in valid_backgrounds:
        raise ValueError(f"Invalid background '{background}'. Must be one of {valid_backgrounds}")

    valid_fidelities = {"low", "high"}
    if input_fidelity not in valid_fidelities:
        raise ValueError(f"Invalid fidelity '{input_fidelity}'. Must be one of {valid_fidelities}")
