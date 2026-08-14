"""Scenarios for the server surface itself: which tools exist and what they accept."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastmcp import FastMCP

from gpt_image_mcp import tools
from gpt_image_mcp.config import Settings
from gpt_image_mcp.server import create_server
from gpt_image_mcp.tools import register_all_tools

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeSdk
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


async def test_server_applies_each_configured_timeout_to_its_adapter(
    output_dir: Path, fake_sdk: FakeSdk
) -> None:
    """Both adapters share one client, so the timeouts must be applied per adapter.

    A shared client with a single timeout would silently give refinement the image
    budget, which is the shorter of the two whenever they are configured apart.
    """
    settings = Settings(
        openai_api_key="sk-test-key",
        gpt_image_output_dir=str(output_dir),
        gpt_image_timeout=111,
        gpt_image_refine_timeout=222,
    )  # type: ignore[call-arg]

    create_server(settings, sdk=fake_sdk.client)

    assert fake_sdk.timeouts == [111, 222]


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
