"""Translation of OpenAI SDK exceptions into domain errors.

Shared by both adapters so a new SDK exception is handled in one place. Anything
not listed here propagates: an unknown failure should surface as a crash in the
logs rather than as a misleading message to the caller.
"""

from __future__ import annotations

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

from gpt_image_mcp.domain.errors import (
    ImageError,
    ImageRateLimitError,
    ImageRequestError,
    ImageServiceError,
)


def translate_sdk_error(exc: Exception) -> ImageError:
    """Map an OpenAI SDK exception to the domain error the tools know how to report."""
    if isinstance(exc, RateLimitError):
        return ImageRateLimitError(_message(exc))
    if isinstance(exc, BadRequestError):
        return ImageRequestError(_message(exc))
    if isinstance(exc, AuthenticationError | PermissionDeniedError):
        return ImageServiceError(
            f"OpenAI refused the credentials: {_message(exc)}. Check OPENAI_API_KEY "
            "and that the organization has access to image models."
        )
    if isinstance(exc, APITimeoutError):
        return ImageServiceError(
            f"OpenAI did not answer in time: {_message(exc)}. "
            "Raise GPT_IMAGE_TIMEOUT for large sizes or complex prompts."
        )
    if isinstance(exc, APIConnectionError | InternalServerError):
        return ImageServiceError(f"OpenAI is unreachable or failing: {_message(exc)}")
    raise exc


def _message(exc: Exception) -> str:
    if isinstance(exc, APIStatusError):
        return exc.message
    return str(exc)
