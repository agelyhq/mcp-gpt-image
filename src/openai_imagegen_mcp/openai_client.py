"""Thin async wrapper around the OpenAI Image API.

Runs sync SDK calls in asyncio.to_thread() to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import base64
import re
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in _save_image
from typing import TYPE_CHECKING, Any

from openai import OpenAI

if TYPE_CHECKING:
    from openai_imagegen_mcp.config import Settings


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len]


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")


def _save_image(
    b64_data: str,
    output_dir: Path,
    prompt: str,
    index: int,
    fmt: str,
) -> Path:
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

        response = await asyncio.to_thread(self._client.images.generate, **kwargs)

        output_dir = self._settings.output_dir
        results = []
        for i, image_data in enumerate(response.data):
            b64 = image_data.b64_json
            if not b64:
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

        images = [open(p, "rb") for p in image_paths]  # noqa: SIM115

        kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "image": images if len(images) > 1 else images[0],
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
        }

        if mask_path:
            kwargs["mask"] = open(mask_path, "rb")  # noqa: SIM115

        if output_format in ("jpeg", "webp"):
            kwargs["output_compression"] = output_compression

        try:
            response = await asyncio.to_thread(self._client.images.edit, **kwargs)
        finally:
            for f in images:
                f.close()
            if "mask" in kwargs:
                kwargs["mask"].close()

        output_dir = self._settings.output_dir
        results = []
        for i, image_data in enumerate(response.data):
            b64 = image_data.b64_json
            if not b64:
                continue
            path = _save_image(b64, output_dir, prompt, i + 1, output_format)
            results.append(
                {
                    "path": str(path.resolve()),
                    "revised_prompt": getattr(image_data, "revised_prompt", None),
                }
            )

        return results
