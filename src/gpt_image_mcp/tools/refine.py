"""refine_image: one image, many turns, without resending it every time."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field

from gpt_image_mcp.domain.results import RefinementResult
from gpt_image_mcp.domain.types import MAX_PROMPT_CHARS, Quality
from gpt_image_mcp.tools._base import ToolDeps, reports_errors
from gpt_image_mcp.tools._validation import validate_input_images, validate_session_id

if TYPE_CHECKING:
    from fastmcp import FastMCP

_SESSION_HELP = (
    "The session_id returned by a previous refine_image call. Omit it to start a "
    "new session from scratch."
)
_IMAGES_HELP = (
    "Local images to start the session from. Ignored when session_id is given, "
    "because the session already holds the image."
)


def register(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register refine_image on the server."""

    @mcp.tool
    @reports_errors
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

        Args:
            instruction: What to draw, or what to change since the last turn.
            session_id: See the field description.
            image_paths: See the field description.
            quality: Higher quality costs more and takes longer.
        """
        # Only quality is confirmed as a configuration key of the image_generation
        # tool. Framing and format belong to generate_image and edit_image, where
        # the API contract is documented.
        tool_options: dict[str, Any] = {} if quality == "auto" else {"quality": quality}

        if session_id is not None:
            validate_session_id(session_id)
            turn = await deps.responses.continue_turn(
                instruction=instruction,
                session_id=session_id,
                tool_options=tool_options,
            )
        else:
            turn = await deps.responses.start(
                instruction=instruction,
                image_paths=validate_input_images(image_paths) if image_paths else [],
                tool_options=tool_options,
            )

        saved = deps.store.save(turn.payload, instruction)
        return RefinementResult(
            path=saved.path,
            session_id=turn.response_id,
            output_format=saved.output_format,
            revised_prompt=saved.revised_prompt,
        )
