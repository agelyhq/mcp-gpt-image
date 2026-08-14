"""Adapter over the Responses API image tool, used for multi-turn refinement.

The Images API forgets everything between calls. The Responses API keeps the
conversation, so turn two can say "make the sky darker" without resending the
image. That is the whole reason this adapter exists next to ImagesClient.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI, BadRequestError, NotFoundError, OpenAIError

from gpt_image_mcp.adapters._errors import translate_sdk_error
from gpt_image_mcp.domain.errors import ImageRequestError, RefinementSessionError
from gpt_image_mcp.domain.results import ImagePayload, RefinementTurn
from gpt_image_mcp.domain.types import ORCHESTRATOR_MODEL, SESSION_RETENTION_DAYS

if TYPE_CHECKING:
    from pathlib import Path

    from gpt_image_mcp.config import Settings

_IMAGE_CALL_TYPE = "image_generation_call"
_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_STALE_SESSION_HINTS = ("previous response", "not found")


class ResponsesImageClient:
    """Drives the built-in image_generation tool across conversation turns."""

    def __init__(self, settings: Settings, sdk: AsyncOpenAI | None = None) -> None:
        self._sdk = sdk or AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.refine_timeout,
        )

    async def start(
        self,
        *,
        instruction: str,
        image_paths: list[Path],
        tool_options: dict[str, Any],
    ) -> RefinementTurn:
        """Open a session, optionally seeded with local images."""
        content: list[dict[str, Any]] = [{"type": "input_text", "text": instruction}]
        content.extend(_as_input_image(path) for path in image_paths)

        try:
            return await self._create(
                model=ORCHESTRATOR_MODEL,
                input=[{"role": "user", "content": content}],
                tools=[{"type": "image_generation", **tool_options}],
            )
        except OpenAIError as exc:
            raise translate_sdk_error(exc) from exc

    async def continue_turn(
        self,
        *,
        instruction: str,
        session_id: str,
        tool_options: dict[str, Any],
    ) -> RefinementTurn:
        """Refine the image produced by an earlier turn.

        Only the instruction travels. The image stays on OpenAI's side, referenced
        by the previous response id.
        """
        try:
            return await self._create(
                model=ORCHESTRATOR_MODEL,
                previous_response_id=session_id,
                input=instruction,
                tools=[{"type": "image_generation", **tool_options}],
            )
        except NotFoundError as exc:
            raise _stale_session(session_id) from exc
        except BadRequestError as exc:
            # A stale id can come back as a 400 rather than a 404, so the message
            # decides. Anything else is an ordinary bad request.
            if any(hint in (exc.message or "").lower() for hint in _STALE_SESSION_HINTS):
                raise _stale_session(session_id) from exc
            raise translate_sdk_error(exc) from exc
        except OpenAIError as exc:
            raise translate_sdk_error(exc) from exc

    async def _create(self, **kwargs: Any) -> RefinementTurn:
        """Run one turn. SDK exceptions propagate: each caller maps them itself."""
        response = await self._sdk.responses.create(**kwargs)
        return RefinementTurn(response_id=response.id, payload=_extract_image(response))


def _as_input_image(path: Path) -> dict[str, Any]:
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode()
    return {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}", "detail": "auto"}


def _extract_image(response: Any) -> ImagePayload:
    calls = [item for item in response.output if getattr(item, "type", None) == _IMAGE_CALL_TYPE]
    if not calls:
        raise ImageRequestError(
            "The model answered without producing an image. Phrase the instruction as "
            "an explicit request to draw or modify the picture."
        )

    # Several tool calls in one turn are possible; the last one is the final image.
    last = calls[-1]
    return ImagePayload(b64=last.result, revised_prompt=getattr(last, "revised_prompt", None))


def _stale_session(session_id: str) -> RefinementSessionError:
    return RefinementSessionError(
        f"Session {session_id} is unknown or expired. Sessions last about "
        f"{SESSION_RETENTION_DAYS} days. Call refine_image without session_id to start a new one."
    )
