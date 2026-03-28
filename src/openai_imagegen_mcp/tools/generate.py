"""generate_image MCP tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai import BadRequestError, RateLimitError

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from openai_imagegen_mcp.openai_client import ImageClient


def register_generate_tool(mcp: FastMCP, client: ImageClient) -> None:
    """Register the generate_image tool on the MCP server."""

    @mcp.tool
    async def generate_image(
        prompt: str,
        model: str = "gpt-image-1.5",
        size: str = "auto",
        quality: str = "auto",
        output_format: str = "png",
        output_compression: int = 100,
        background: str = "auto",
        n: int = 1,
    ) -> list[dict[str, Any]]:
        """Generate image(s) from a text prompt using OpenAI's Image API.

        Args:
            prompt: Text description of the image to generate.
            model: Model to use (gpt-image-1.5, gpt-image-1, gpt-image-1-mini).
            size: Image size (1024x1024, 1536x1024, 1024x1536, auto).
            quality: Image quality (low, medium, high, auto).
            output_format: Output format (png, jpeg, webp).
            output_compression: Compression level 0-100 (jpeg/webp only).
            background: Background type (transparent, opaque, auto).
            n: Number of images to generate (1-4).

        Returns:
            List of dicts with 'path' (local file path) and 'revised_prompt'.
        """
        _validate_generate_params(size, quality, output_format, output_compression, background, n)

        try:
            return await client.generate(
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
                output_format=output_format,
                output_compression=output_compression,
                background=background,
                n=n,
            )
        except BadRequestError as exc:
            return [{"error": f"Content policy violation or bad request: {exc.message}"}]
        except RateLimitError as exc:
            return [{"error": f"Rate limited: {exc.message}"}]


def _validate_generate_params(
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    background: str,
    n: int,
) -> None:
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

    if not 1 <= n <= 4:
        raise ValueError(f"n must be 1-4, got {n}")
