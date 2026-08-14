"""Shared plumbing for the tool modules: injected dependencies and error handling."""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from gpt_image_mcp.domain.errors import (
    ImageDecodeError,
    ImageRateLimitError,
    ImageRequestError,
    ImageServiceError,
    RefinementSessionError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from gpt_image_mcp.adapters.images_client import ImagesClient
    from gpt_image_mcp.adapters.responses_client import ResponsesImageClient
    from gpt_image_mcp.domain.image_store import ImageStore

_PREFIXES: list[tuple[type[Exception], str]] = [
    (ImageRateLimitError, "Rate limited by OpenAI: "),
    (ImageRequestError, "OpenAI rejected the request: "),
    (ImageServiceError, ""),
    (ImageDecodeError, ""),
    (RefinementSessionError, ""),
    (ValueError, ""),
]


@dataclass(frozen=True, slots=True)
class ToolDeps:
    """Everything the tools need, built once by the composition root."""

    images: ImagesClient
    responses: ResponsesImageClient
    store: ImageStore


def reports_errors[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Turn domain and validation errors into MCP tool errors.

    FastMCP forwards a ToolError message to the client untouched, which is what an
    agent needs to correct its own call. Anything not listed here is a bug in this
    server and is allowed to crash loudly.
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            for error_type, prefix in _PREFIXES:
                if isinstance(exc, error_type):
                    raise ToolError(f"{prefix}{exc}") from exc
            raise

    return wrapper
