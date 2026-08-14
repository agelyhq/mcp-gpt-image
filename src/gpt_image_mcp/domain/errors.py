"""Domain errors raised by the adapters and translated to MCP errors by the tools.

Grouped in one module because they form a single hierarchy and none of them
carries behaviour. Nothing here knows about OpenAI or FastMCP.
"""

from __future__ import annotations


class ImageError(Exception):
    """Base class for every failure this server reports to its caller."""


class ImageRequestError(ImageError):
    """The API refused the request: bad parameters, or a content policy hit."""


class ImageRateLimitError(ImageError):
    """The API rate-limited the request."""


class ImageServiceError(ImageError):
    """The API was unreachable, timed out, or failed on its side."""


class ImageDecodeError(ImageError):
    """The API returned bytes that are not a PNG, a JPEG or a WEBP."""


class RefinementSessionError(ImageError):
    """The refinement session id is unknown or has expired."""
