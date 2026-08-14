"""Domain errors raised by the adapters and translated to MCP errors by the tools.

Grouped in one module because they form a single hierarchy and none of them
carries behaviour. Nothing here knows about OpenAI or FastMCP.

The split that matters is who can act on the failure. A caller can fix a
validation error or a rejected request by changing its next call; it can do
nothing about a configuration error or an outage.
"""

from __future__ import annotations


class ImageError(Exception):
    """Base class for every failure this server reports to its caller."""


class ImageValidationError(ImageError):
    """The call breaks a rule this server checks before spending a request."""


class ImageRequestError(ImageError):
    """The API refused the request: bad parameters, or a content policy hit."""


class ImageRateLimitError(ImageError):
    """The API rate-limited the request."""


class ImageConfigurationError(ImageError):
    """The credentials or the model id are wrong. Retrying will not help."""


class ImageServiceError(ImageError):
    """The API was unreachable, timed out, or failed on its side."""


class ImageDecodeError(ImageError):
    """The API returned bytes that are not a PNG, a JPEG or a WEBP."""


class ImageStorageError(ImageError):
    """The image could not be written to the output directory."""


class RefinementSessionError(ImageError):
    """The refinement session id is unknown or has expired."""
