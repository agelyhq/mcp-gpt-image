"""Composition root: builds the dependency graph and the FastMCP server."""

from __future__ import annotations

from importlib.metadata import version
from typing import TYPE_CHECKING

from fastmcp import FastMCP
from openai import AsyncOpenAI

from gpt_image_mcp.adapters.images_client import ImagesClient
from gpt_image_mcp.adapters.responses_client import ResponsesImageClient
from gpt_image_mcp.config import get_settings
from gpt_image_mcp.deps import ToolDeps
from gpt_image_mcp.domain.image_store import ImageStore
from gpt_image_mcp.tools import register_all_tools

if TYPE_CHECKING:
    from gpt_image_mcp.config import Settings

INSTRUCTIONS = """\
Image generation and editing with OpenAI gpt-image-2.

Tools return file paths, never image bytes. A path returned by one tool is a valid
input for another, which is how an image travels from one step to the next without
ever entering the conversation.

Pick the tool by the shape of the work: generate_image to draw from nothing,
edit_image for a single change to local files, refine_image when the same image
needs several rounds of correction. refine_image keeps the thread with the model,
so later turns take an instruction alone, and it is the only tool with a memory.

This model has no transparent background. Requests asking for one are refused.
"""


def create_server(settings: Settings | None = None, *, sdk: AsyncOpenAI | None = None) -> FastMCP:
    """Build the MCP server with every tool registered.

    One SDK client is shared by both adapters, so there is a single connection
    pool; each adapter narrows it to its own timeout.

    Args:
        settings: Configuration to use. Loaded from the environment when omitted.
        sdk: OpenAI client to use instead of a real one. This is the seam tests
            drive; production leaves it unset.
    """
    settings = settings or get_settings()
    client = sdk or AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    deps = ToolDeps(
        images=ImagesClient(client, model=settings.model, timeout=settings.timeout),
        responses=ResponsesImageClient(
            client, model=settings.refine_model, timeout=settings.refine_timeout
        ),
        store=ImageStore(settings.output_dir),
    )

    mcp = FastMCP(
        name="gpt-image",
        instructions=INSTRUCTIONS,
        # Without an explicit version, a client is told the FastMCP version instead.
        version=version("mcp-gpt-image"),
    )
    register_all_tools(mcp, deps)

    return mcp
