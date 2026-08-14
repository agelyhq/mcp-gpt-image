"""Translation of OpenAI SDK exceptions into domain errors.

Shared by both adapters so a new SDK exception is handled in one place. The
function is total on purpose: it always returns an error to raise, never raises
one itself, because a caller writing `raise translate(exc) from exc` would
otherwise lose the chaining and let a raw SDK exception cross the boundary.
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
    ImageConfigurationError,
    ImageError,
    ImageRateLimitError,
    ImageRequestError,
    ImageServiceError,
)


def translate_sdk_error(exc: Exception) -> ImageError:
    """Map an OpenAI SDK exception to the domain error the tools report."""
    if isinstance(exc, RateLimitError):
        return ImageRateLimitError(_message(exc))

    if isinstance(exc, BadRequestError):
        return ImageRequestError(_message(exc))

    if isinstance(exc, AuthenticationError | PermissionDeniedError):
        return ImageConfigurationError(
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

    if isinstance(exc, APIStatusError):
        # 404, 409, 422 and anything else with a status. A wrong GPT_IMAGE_MODEL
        # lands here as a 404, and used to escape untranslated.
        return ImageRequestError(f"OpenAI returned {exc.status_code}: {_message(exc)}")

    return ImageServiceError(f"Unexpected failure from the OpenAI SDK: {exc}")


def _message(exc: Exception) -> str:
    if isinstance(exc, APIStatusError):
        return exc.message
    return str(exc)
