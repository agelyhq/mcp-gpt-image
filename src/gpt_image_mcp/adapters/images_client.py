"""Adapter over the OpenAI Images API, pinned to gpt-image-2."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai import OpenAIError

from gpt_image_mcp.adapters._errors import translate_sdk_error
from gpt_image_mcp.domain.errors import ImageRequestError
from gpt_image_mcp.domain.results import ImagePayload
from gpt_image_mcp.domain.types import MIME_BY_SUFFIX

if TYPE_CHECKING:
    from pathlib import Path

    from openai import AsyncOpenAI

    from gpt_image_mcp.domain.types import Background, Moderation, OutputFormat, Quality

# Compression is only meaningful for lossy formats, and sending it with png is
# rejected. Parameters gpt-image-2 refuses outright are never built at all:
# input_fidelity (the model is always high fidelity), response_format and style
# (both DALL-E only), and moderation on edits (absent from that schema).
_COMPRESSIBLE_FORMATS = frozenset({"jpeg", "webp"})


class ImagesClient:
    """Generates and edits images through /v1/images, one call per tool invocation."""

    def __init__(self, sdk: AsyncOpenAI, model: str, timeout: int) -> None:
        self._sdk = sdk.with_options(timeout=timeout)
        self._model = model

    async def generate(
        self,
        *,
        prompt: str,
        size: str,
        quality: Quality,
        output_format: OutputFormat,
        output_compression: int,
        background: Background,
        moderation: Moderation,
        n: int,
    ) -> list[ImagePayload]:
        """Create images from a prompt alone."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
            "moderation": moderation,
        }
        if output_format in _COMPRESSIBLE_FORMATS:
            kwargs["output_compression"] = output_compression

        try:
            response = await self._sdk.images.generate(**kwargs)
        except OpenAIError as exc:
            raise translate_sdk_error(exc) from exc

        return _payloads(response)

    async def edit(
        self,
        *,
        prompt: str,
        image_paths: list[Path],
        mask_path: Path | None,
        size: str,
        quality: Quality,
        output_format: OutputFormat,
        output_compression: int,
        background: Background,
        n: int,
    ) -> list[ImagePayload]:
        """Edit or compose local images.

        Files are read into memory and sent as multipart tuples rather than as open
        handles, so no descriptor stays open across the await.
        """
        images = [_upload(path) for path in image_paths]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "image": images if len(images) > 1 else images[0],
            "n": n,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
        }
        if mask_path is not None:
            kwargs["mask"] = _upload(mask_path)
        if output_format in _COMPRESSIBLE_FORMATS:
            kwargs["output_compression"] = output_compression

        try:
            response = await self._sdk.images.edit(**kwargs)
        except OpenAIError as exc:
            raise translate_sdk_error(exc) from exc

        return _payloads(response)


def _upload(path: Path) -> tuple[str, bytes, str]:
    # Suffixes are validated upstream, so a miss here would be a defect rather
    # than caller input; octet-stream makes the API say so instead of guessing.
    mime = MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
    return (path.name, path.read_bytes(), mime)


def _payloads(response: Any) -> list[ImagePayload]:
    payloads = [
        ImagePayload(b64=item.b64_json, revised_prompt=getattr(item, "revised_prompt", None))
        for item in response.data
        if item.b64_json
    ]
    if not payloads:
        # Dropping this quietly would return an empty list and leave the caller
        # guessing why no file appeared.
        raise ImageRequestError("The API answered without any image data.")
    return payloads
