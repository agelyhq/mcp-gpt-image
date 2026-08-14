"""Data carried between the adapters, the store and the tools.

ImagePayload is what comes back from OpenAI, ImageResult and RefinementResult are
what the MCP tools return. Keeping them apart means the store owns the transition
from bytes in memory to a file on disk, and nothing else does.
"""

from __future__ import annotations

from dataclasses import dataclass

from gpt_image_mcp.domain.types import OutputFormat


@dataclass(frozen=True, slots=True)
class ImagePayload:
    """A base64 image as received from the API, before it touches the disk."""

    b64: str
    revised_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ImageResult:
    """A saved image. The path is absolute so any tool can reuse it as an input."""

    path: str
    output_format: OutputFormat
    revised_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class RefinementResult:
    """A saved image plus the session id needed to keep refining it."""

    path: str
    session_id: str
    output_format: OutputFormat
    revised_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class RefinementTurn:
    """One Responses API round trip: the image it produced and the id to continue from."""

    response_id: str
    payload: ImagePayload
