"""CLI entrypoint for the MCP server."""

from __future__ import annotations

import argparse
import sys

from openai_imagegen_mcp.config import get_settings
from openai_imagegen_mcp.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI Image Generation MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default: from env)")
    args = parser.parse_args()

    settings = get_settings()
    server = create_server(settings)

    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        port = args.port or settings.port
        server.run(transport="streamable-http", host=args.host, port=port)


if __name__ == "__main__":
    sys.exit(main())
