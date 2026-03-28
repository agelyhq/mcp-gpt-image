"""generate_image MCP tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai_imagegen_mcp.openai_client import ImageClientError, ImageRateLimitError
from openai_imagegen_mcp.tools._validators import validate_generate_params

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
        try:
            validate_generate_params(
                size,
                quality,
                output_format,
                output_compression,
                background,
                n,
            )

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
        except ValueError as exc:
            return [{"error": str(exc)}]
        except ImageClientError as exc:
            return [{"error": f"Content policy violation or bad request: {exc}"}]
        except ImageRateLimitError as exc:
            return [{"error": f"Rate limited: {exc}"}]
