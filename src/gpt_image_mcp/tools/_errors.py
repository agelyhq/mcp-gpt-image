"""Turning domain errors into MCP tool errors."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError

from gpt_image_mcp.domain.errors import ImageError, ImageRateLimitError, ImageRequestError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def as_tool_errors[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Report domain failures on the MCP error channel.

    FastMCP forwards a ToolError message to the client untouched, which is what
    lets a calling agent correct its own call. Only ImageError is caught: anything
    else is a defect in this server and crashes, rather than being dressed up as
    something the caller did wrong.
    """

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except ImageError as exc:
            raise ToolError(f"{_prefix(exc)}{exc}") from exc

    return wrapper


def _prefix(exc: ImageError) -> str:
    if isinstance(exc, ImageRateLimitError):
        return "Rate limited by OpenAI: "
    if isinstance(exc, ImageRequestError):
        return "OpenAI rejected the request: "
    return ""
