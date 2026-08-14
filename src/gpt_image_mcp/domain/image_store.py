"""Persistence of generated images. The only module in the server that writes files."""

from __future__ import annotations

import base64
import binascii
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from gpt_image_mcp.domain.errors import ImageDecodeError
from gpt_image_mcp.domain.results import ImageResult

if TYPE_CHECKING:
    from pathlib import Path

    from gpt_image_mcp.domain.results import ImagePayload
    from gpt_image_mcp.domain.types import OutputFormat

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LEN = 40

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_RIFF_MAGIC = b"RIFF"
_WEBP_MAGIC = b"WEBP"


class ImageStore:
    """Writes base64 payloads under an output directory with collision-free names.

    Filenames are `{timestamp}_{prompt slug}_{index}.{ext}` with microsecond
    precision, so concurrent calls sharing a prompt never overwrite each other.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def save(self, payload: ImagePayload, prompt: str, index: int = 1) -> ImageResult:
        """Decode a payload and write it to disk.

        The extension comes from the bytes themselves, never from the format that
        was requested. The API has been known to return PNG for a webp request,
        and a file named `.webp` holding PNG bytes breaks whatever opens it next.

        Raises:
            ImageDecodeError: the payload is not valid base64, or not a known image.
        """
        try:
            data = base64.b64decode(payload.b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageDecodeError("The API returned a payload that is not valid base64") from exc

        output_format = self.sniff_format(data)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"{_timestamp()}_{_slugify(prompt)}_{index}.{output_format}"
        path.write_bytes(data)

        return ImageResult(
            path=str(path.resolve()),
            output_format=output_format,
            revised_prompt=payload.revised_prompt,
        )

    @staticmethod
    def sniff_format(data: bytes) -> OutputFormat:
        """Identify an image from its magic bytes.

        Raises:
            ImageDecodeError: the bytes match no format this server can name.
        """
        if data.startswith(_PNG_MAGIC):
            return "png"
        if data.startswith(_JPEG_MAGIC):
            return "jpeg"
        if data[:4] == _RIFF_MAGIC and data[8:12] == _WEBP_MAGIC:
            return "webp"
        raise ImageDecodeError(
            "The API returned data that is not a PNG, a JPEG or a WEBP image. "
            "Nothing was written to disk."
        )


def _slugify(text: str) -> str:
    return _SLUG_PATTERN.sub("_", text.lower()).strip("_")[:_SLUG_MAX_LEN]


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
