"""Shared fixtures for E2E tests with mocked OpenAI API."""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path  # noqa: TC003 — used at runtime
from unittest.mock import MagicMock, patch

import pytest

from openai_imagegen_mcp.config import Settings
from openai_imagegen_mcp.server import create_server


def _make_fake_png(
    width: int = 4,
    height: int = 4,
    r: int = 255,
    g: int = 0,
    b: int = 0,
) -> bytes:
    """Generate a minimal valid PNG image."""

    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes([r, g, b, 255]) * width
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


FAKE_PNG_BYTES = _make_fake_png()
FAKE_PNG_B64 = base64.b64encode(FAKE_PNG_BYTES).decode()


def _make_mock_response(n: int = 1) -> MagicMock:
    response = MagicMock()
    response.data = []
    for _ in range(n):
        img = MagicMock()
        img.b64_json = FAKE_PNG_B64
        img.revised_prompt = "A test image (revised)"
        response.data.append(img)
    return response


@pytest.fixture(scope="session")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("generated-images")


@pytest.fixture(scope="session")
def mock_openai():
    """Create a mock OpenAI client that returns fake images."""
    mock_client = MagicMock()

    def fake_generate(**kwargs):
        n = kwargs.get("n", 1)
        return _make_mock_response(n)

    def fake_edit(**kwargs):
        return _make_mock_response(1)

    mock_client.images.generate.side_effect = fake_generate
    mock_client.images.edit.side_effect = fake_edit
    return mock_client


@pytest.fixture(scope="session")
def settings(output_dir: Path) -> Settings:
    return Settings(
        openai_api_key="sk-fake-test-key",
        openai_imagegen_output_dir=str(output_dir),
    )  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def mcp_server(settings: Settings, mock_openai: MagicMock):
    with patch("openai_imagegen_mcp.openai_client.OpenAI", return_value=mock_openai):
        return create_server(settings)


@pytest.fixture
def clean_output_dir(output_dir: Path) -> Path:
    for f in output_dir.iterdir():
        if f.is_file():
            f.unlink()
    return output_dir


@pytest.fixture
def sample_image(output_dir: Path) -> Path:
    """Write a fake PNG to disk for use as edit input."""
    path = output_dir / "test_input.png"
    path.write_bytes(FAKE_PNG_BYTES)
    return path
