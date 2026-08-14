"""Command line entrypoint. The server speaks MCP over stdio and nothing else."""

from __future__ import annotations

import argparse
from importlib.metadata import version

from gpt_image_mcp.server import create_server


def main() -> None:
    """Start the MCP server on stdio."""
    parser = argparse.ArgumentParser(
        prog="mcp-gpt-image",
        description="MCP server for image generation and refinement with OpenAI gpt-image-2.",
    )
    parser.add_argument("--version", action="version", version=version("mcp-gpt-image"))
    parser.parse_args()

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
