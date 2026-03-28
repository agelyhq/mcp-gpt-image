"""Cloud entrypoint for fastmcp run.

Usage: fastmcp run fastmcp_server.py
Exports `mcp` for FastMCP's runner.
"""

from openai_imagegen_mcp.config import get_settings
from openai_imagegen_mcp.server import create_server

settings = get_settings()
mcp = create_server(settings)
