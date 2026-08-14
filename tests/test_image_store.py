"""Focused tests for ImageStore.

Format sniffing and filename building have no path through the MCP surface that
can observe them on their own, so they are exercised directly.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from conftest import FAKE_JPEG_BYTES, FAKE_PNG_BYTES, FAKE_WEBP_BYTES

from gpt_image_mcp.domain.errors import ImageDecodeError
from gpt_image_mcp.domain.image_store import ImageStore
from gpt_image_mcp.domain.results import ImagePayload


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (FAKE_PNG_BYTES, "png"),
        (FAKE_JPEG_BYTES, "jpeg"),
        (FAKE_WEBP_BYTES, "webp"),
    ],
)
def test_image_store_sniffs_known_formats(data: bytes, expected: str) -> None:
    assert ImageStore.sniff_format(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        b"not-an-image",
        b"",
        # RIFF container that is not a WEBP, so the tag at offset 8 decides.
        b"RIFF\x10\x00\x00\x00WAVEfmt ",
    ],
)
def test_image_store_rejects_unknown_formats(data: bytes) -> None:
    with pytest.raises(ImageDecodeError):
        ImageStore.sniff_format(data)


def test_image_store_save_names_the_file_after_the_prompt(tmp_path: Path) -> None:
    store = ImageStore(tmp_path / "images")
    payload = ImagePayload(b64=base64.b64encode(FAKE_PNG_BYTES).decode(), revised_prompt="revised")

    result = store.save(payload, "A red circle on white", index=3)

    saved = Path(result.path)
    assert saved.is_absolute()
    assert saved.is_file()
    assert saved.read_bytes() == FAKE_PNG_BYTES
    assert saved.name.endswith("_a_red_circle_on_white_3.png")
    assert result.output_format == "png"
    assert result.revised_prompt == "revised"


def test_image_store_save_twice_never_overwrites(tmp_path: Path) -> None:
    store = ImageStore(tmp_path / "images")
    payload = ImagePayload(b64=base64.b64encode(FAKE_PNG_BYTES).decode())

    first = store.save(payload, "same prompt")
    second = store.save(payload, "same prompt")

    assert first.path != second.path
    assert len(list((tmp_path / "images").iterdir())) == 2
