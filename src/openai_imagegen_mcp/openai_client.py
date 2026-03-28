"""Thin async wrapper around the OpenAI Image API.

Runs sync SDK calls in asyncio.to_thread() to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import re
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in _save_image
from typing import TYPE_CHECKING, Any

from openai import BadRequestError as _SDKBadRequest
from openai import OpenAI
from openai import RateLimitError as _SDKRateLimit

if TYPE_CHECKING:
    from openai_imagegen_mcp.config import Settings


class ImageClientError(Exception):
    """Base error raised by ImageClient for bad requests."""


class ImageRateLimitError(Exception):
    """Raised when the OpenAI API rate-limits the request."""


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len]


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")


def _save_image(
    b64_data: str,
    output_dir: Path,
    prompt: str,
    index: int,
    fmt: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_timestamp()}_{_slugify(prompt)}_{index}.{fmt}"
    path = output_dir / filename
    path.write_bytes(base64.b64decode(b64_data))
    return path


class ImageClient:
    """Async interface to OpenAI's Image API."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_imagegen_timeout,
        )
        self._settings = settings

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        size: str = "auto",
        quality: str | None = None,
        output_format: str = "png",
        output_compression: int = 100,
        background: str = "auto",
        n: int = 1,
    ) -> list[dict[str, Any]]:
        model = model or self._settings.openai_imagegen_default_model
        quality = quality or self._settings.openai_imagegen_default_quality

        kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
        }
        if output_format in ("jpeg", "webp"):
            kwargs["output_compression"] = output_compression

        try:
            response = await asyncio.to_thread(self._client.images.generate, **kwargs)
        except _SDKBadRequest as exc:
            raise ImageClientError(exc.message) from exc
        except _SDKRateLimit as exc:
            raise ImageRateLimitError(exc.message) from exc

        output_dir = self._settings.output_dir
        results = []
        for i, image_data in enumerate(response.data):
            b64 = image_data.b64_json
            if not b64:
                results.append({"error": f"API returned no image data for index {i + 1}"})
                continue
            path = _save_image(b64, output_dir, prompt, i + 1, output_format)
            results.append(
                {
                    "path": str(path.resolve()),
                    "revised_prompt": getattr(image_data, "revised_prompt", None),
                }
            )

        return results

    async def edit(
        self,
        prompt: str,
        image_paths: list[str],
        mask_path: str | None = None,
        model: str | None = None,
        size: str = "auto",
        quality: str | None = None,
        output_format: str = "png",
        output_compression: int = 100,
        background: str = "auto",
        input_fidelity: str = "low",
    ) -> list[dict[str, Any]]:
        model = model or self._settings.openai_imagegen_default_model
        quality = quality or self._settings.openai_imagegen_default_quality

        with contextlib.ExitStack() as stack:
            images = [stack.enter_context(open(p, "rb")) for p in image_paths]
            kwargs: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "image": images if len(images) > 1 else images[0],
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "background": background,
                "input_fidelity": input_fidelity,
            }

            if mask_path:
                kwargs["mask"] = stack.enter_context(open(mask_path, "rb"))
            if output_format in ("jpeg", "webp"):
                kwargs["output_compression"] = output_compression

            try:
                response = await asyncio.to_thread(self._client.images.edit, **kwargs)
            except _SDKBadRequest as exc:
                raise ImageClientError(exc.message) from exc
            except _SDKRateLimit as exc:
                raise ImageRateLimitError(exc.message) from exc

        output_dir = self._settings.output_dir
        results = []
        for i, image_data in enumerate(response.data):
            b64 = image_data.b64_json
            if not b64:
                results.append({"error": f"API returned no image data for index {i + 1}"})
                continue
            path = _save_image(b64, output_dir, prompt, i + 1, output_format)
            results.append(
                {
                    "path": str(path.resolve()),
                    "revised_prompt": getattr(image_data, "revised_prompt", None),
                }
            )

        return results
