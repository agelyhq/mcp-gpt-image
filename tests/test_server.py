"""Scenarios for the server surface itself: which tools exist and what they accept."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from gpt_image_mcp import tools
from gpt_image_mcp.tools import register_all_tools

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import Client

EXPECTED_TOOLS = {"generate_image", "edit_image", "refine_image"}


async def test_server_exposes_exactly_three_tools(client: Client) -> None:
    async with client:
        listed = await client.list_tools()

    assert {tool.name for tool in listed} == EXPECTED_TOOLS


async def test_server_generate_schema_has_no_model_and_no_transparency(client: Client) -> None:
    """The multi-model surface is gone: one model, and no transparent background."""
    async with client:
        listed = await client.list_tools()

    generate = next(tool for tool in listed if tool.name == "generate_image")
    properties = generate.inputSchema["properties"]

    assert properties["background"]["enum"] == ["auto", "opaque"]
    assert "model" not in properties


async def test_server_registry_rejects_a_module_without_register(tmp_path: Path) -> None:
    """A file dropped in the tools package must register itself or fail at startup."""
    (tmp_path / "probe_not_a_tool.py").write_text('"""A module that forgot to register."""\n')
    importlib.invalidate_caches()
    tools.__path__.append(str(tmp_path))

    try:
        with pytest.raises(RuntimeError, match="has no register"):
            register_all_tools(FastMCP(name="probe"), MagicMock())
    finally:
        tools.__path__.remove(str(tmp_path))
        sys.modules.pop("gpt_image_mcp.tools.probe_not_a_tool", None)
        importlib.invalidate_caches()
