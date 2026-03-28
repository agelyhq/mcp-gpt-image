"""FastMCP server instance and tool registration."""

from __future__ import annotations

from fastmcp import FastMCP

from openai_imagegen_mcp.config import Settings, get_settings
from openai_imagegen_mcp.openai_client import ImageClient
from openai_imagegen_mcp.tools.edit import register_edit_tool
from openai_imagegen_mcp.tools.generate import register_generate_tool


def create_server(settings: Settings | None = None) -> FastMCP:
    """Create and configure the MCP server with all tools registered."""
    if settings is None:
        settings = get_settings()

    mcp = FastMCP(name="OpenAI Image Generation")
    client = ImageClient(settings)

    register_generate_tool(mcp, client)
    register_edit_tool(mcp, client)

    return mcp
