"""Shared fixtures for the MCP test suite.

Nothing here touches the network. `create_server(settings, sdk=...)` is the only
seam used: a fake OpenAI SDK records the kwargs each adapter sends, so a test can
assert on the request as well as on the answer.
"""

from __future__ import annotations

import base64
import json
import struct
import zlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client, FastMCP

from gpt_image_mcp.config import Settings
from gpt_image_mcp.server import create_server

if TYPE_CHECKING:
    from pathlib import Path

REVISED_PROMPT = "A test image, as rewritten by the model"


def _make_fake_png(width: int = 4, height: int = 4) -> bytes:
    """Build a minimal but valid PNG."""

    def chunk(ctype: bytes, data: bytes) -> bytes:
        body = ctype + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(b"\x00" + bytes([255, 0, 0, 255]) * width for _ in range(height))
    return signature + ihdr + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def _make_fake_jpeg() -> bytes:
    """Bytes that sniff as JPEG. Only the magic number has to be right."""
    return b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"\x00" * 16 + b"\xff\xd9"


def _make_fake_webp() -> bytes:
    """Bytes that sniff as WEBP: RIFF, a size, then the WEBP tag."""
    payload = b"VP8L" + b"\x00" * 16
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + b"WEBP" + payload


FAKE_PNG_BYTES = _make_fake_png()
FAKE_JPEG_BYTES = _make_fake_jpeg()
FAKE_WEBP_BYTES = _make_fake_webp()


def sdk_error(error_type: type, message: str, status_code: int) -> Exception:
    """Build an openai APIStatusError subclass without an HTTP layer.

    The SDK only reads status_code, headers and request off the response, so a
    duck-typed object is enough and avoids constructing a real httpx2 response.
    """
    response = SimpleNamespace(status_code=status_code, headers={}, request=None)
    return error_type(message, response=response, body=None)


class FakeSdk:
    """Async stand-in for AsyncOpenAI, recording every call it receives."""

    def __init__(self) -> None:
        self.generate_calls: list[dict[str, Any]] = []
        self.edit_calls: list[dict[str, Any]] = []
        self.responses_calls: list[dict[str, Any]] = []

        # What the fake API answers with. Tests reassign these to change the reply.
        self.image_bytes: bytes = FAKE_PNG_BYTES
        self.b64_override: str | None = None
        self.error: Exception | None = None
        self.output_items: list[Any] | None = None

        self._response_count = 0

        self.client = MagicMock()
        self.client.images.generate = AsyncMock(side_effect=self._generate)
        self.client.images.edit = AsyncMock(side_effect=self._edit)
        self.client.responses.create = AsyncMock(side_effect=self._respond)

        # Each adapter narrows the shared client to its own timeout. The real SDK
        # returns a view sharing the transport; the fake returns itself so calls
        # keep landing in the same recorders.
        self.timeouts: list[Any] = []
        self.client.with_options = self._with_options

    def _with_options(self, **kwargs: Any) -> MagicMock:
        self.timeouts.append(kwargs.get("timeout"))
        return self.client

    @property
    def b64(self) -> str:
        if self.b64_override is not None:
            return self.b64_override
        return base64.b64encode(self.image_bytes).decode()

    def _image_response(self, n: int) -> SimpleNamespace:
        items = [
            SimpleNamespace(b64_json=self.b64, revised_prompt=REVISED_PROMPT) for _ in range(n)
        ]
        return SimpleNamespace(data=items)

    def _check_armed_error(self) -> None:
        if self.error is not None:
            raise self.error

    async def _generate(self, **kwargs: Any) -> SimpleNamespace:
        self.generate_calls.append(kwargs)
        self._check_armed_error()
        return self._image_response(kwargs.get("n", 1))

    async def _edit(self, **kwargs: Any) -> SimpleNamespace:
        self.edit_calls.append(kwargs)
        self._check_armed_error()
        return self._image_response(kwargs.get("n", 1))

    async def _respond(self, **kwargs: Any) -> SimpleNamespace:
        self.responses_calls.append(kwargs)
        self._check_armed_error()
        self._response_count += 1
        items = self.output_items
        if items is None:
            items = [
                SimpleNamespace(
                    type="image_generation_call",
                    result=self.b64,
                    revised_prompt=REVISED_PROMPT,
                )
            ]
        return SimpleNamespace(id=f"resp_{self._response_count:016d}", output=items)


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Where the server writes. Not created upfront: some tests assert it stays empty."""
    return tmp_path / "generated-images"


@pytest.fixture
def settings(output_dir: Path) -> Settings:
    return Settings(
        openai_api_key="sk-test-key",
        gpt_image_output_dir=str(output_dir),
    )  # type: ignore[call-arg]


@pytest.fixture
def fake_sdk() -> FakeSdk:
    return FakeSdk()


@pytest.fixture
def server(settings: Settings, fake_sdk: FakeSdk) -> FastMCP:
    return create_server(settings, sdk=fake_sdk.client)


@pytest.fixture
def client(server: FastMCP) -> Client:
    return Client(server)


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    path = tmp_path / "source.png"
    path.write_bytes(FAKE_PNG_BYTES)
    return path


@pytest.fixture
def sample_mask(tmp_path: Path) -> Path:
    path = tmp_path / "mask.png"
    path.write_bytes(FAKE_PNG_BYTES)
    return path


def make_pngs(directory: Path, count: int) -> list[str]:
    """Write `count` PNG files and return their paths as strings."""
    paths: list[str] = []
    for index in range(count):
        path = directory / f"input_{index}.png"
        path.write_bytes(FAKE_PNG_BYTES)
        paths.append(str(path))
    return paths


def payloads(result: Any) -> Any:
    """Read the JSON body of a successful tool call.

    A list of images for generate_image and edit_image, a single object for
    refine_image.
    """
    return json.loads(result.content[0].text)


def error_text(result: Any) -> str:
    """Read the message of a failed tool call."""
    return result.content[0].text
