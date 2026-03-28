"""edit_image MCP tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai_imagegen_mcp.openai_client import ImageClientError, ImageRateLimitError
from openai_imagegen_mcp.tools._validators import validate_edit_params

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
        try:
            validate_edit_params(
                image_paths,
                mask_path,
                size,
                quality,
                output_format,
                output_compression,
                background,
                input_fidelity,
            )

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
        except ValueError as exc:
            return [{"error": str(exc)}]
        except ImageClientError as exc:
            return [{"error": f"Content policy violation or bad request: {exc}"}]
        except ImageRateLimitError as exc:
            return [{"error": f"Rate limited: {exc}"}]
