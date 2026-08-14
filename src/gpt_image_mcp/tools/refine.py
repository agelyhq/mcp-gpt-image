"""refine_image: one image, many turns, without resending it every time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from gpt_image_mcp.domain.constraints import validate_input_images, validate_session_id
from gpt_image_mcp.domain.errors import ImageValidationError
from gpt_image_mcp.domain.results import RefinementResult
from gpt_image_mcp.domain.types import MAX_PROMPT_CHARS, Quality
from gpt_image_mcp.tools._errors import as_tool_errors

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from gpt_image_mcp.deps import ToolDeps

_SESSION_HELP = (
    "The session_id returned by a previous refine_image call. Omit it to start a new session."
)
_IMAGES_HELP = (
    "Local images to start a new session from. Cannot be combined with session_id, "
    "which already carries the image being refined."
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register refine_image on the server."""

    @mcp.tool
    @as_tool_errors
    async def refine_image(
        instruction: Annotated[str, Field(max_length=MAX_PROMPT_CHARS)],
        session_id: Annotated[str | None, Field(description=_SESSION_HELP)] = None,
        image_paths: Annotated[list[str] | None, Field(description=_IMAGES_HELP)] = None,
        quality: Quality = "auto",
    ) -> RefinementResult:
        """Refine an image over several turns, keeping the thread with the model.

        Turn one: give an instruction, optionally with local images to start from,
        and keep the session_id that comes back. Turn two and after: pass that
        session_id with the next instruction alone. The image stays on OpenAI's
        side, so corrections read like a conversation ("darker sky", "remove the
        car") instead of a full prompt rewritten each time.

        This costs more per image than generate_image, because a reasoning model
        drives the drawing. It pays off from the second turn on, and it is the only
        tool here that remembers what came before. Sessions last about 30 days.

        Unlike the other two tools, this one returns the prompt the model wrote for
        itself, which is the quickest way to see how your instruction was read.

        Args:
            instruction: What to draw, or what to change since the last turn.
            session_id: See the field description.
            image_paths: See the field description.
            quality: Higher quality costs more and takes longer.
        """
        if session_id is not None:
            _reject_images_on_a_running_session(image_paths)
            validate_session_id(session_id)
            turn = await deps.responses.continue_turn(
                instruction=instruction,
                session_id=session_id,
                quality=quality,
            )
        else:
            turn = await deps.responses.start(
                instruction=instruction,
                image_paths=validate_input_images(image_paths or []),
                quality=quality,
            )

        saved = deps.store.save(turn.payload, instruction)
        return RefinementResult(
            path=saved.path,
            session_id=turn.response_id,
            output_format=saved.output_format,
            revised_prompt=saved.revised_prompt,
        )


def _reject_images_on_a_running_session(image_paths: list[str] | None) -> None:
    """Fail loudly rather than ignoring images the caller meant to be used.

    Dropping them silently returns a plausible picture built from none of the
    files that were supplied, which reads as success.
    """
    if image_paths:
        raise ImageValidationError(
            "image_paths cannot be combined with session_id: the session already holds "
            "the image being refined. Omit session_id to start a new session from these "
            "files, or omit image_paths to keep refining the current one."
        )
