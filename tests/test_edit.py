"""E2E tests for edit_image tool.

Tests the full MCP lifecycle including iterative chaining: generate → edit → edit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client


@pytest.fixture
def client(mcp_server):
    return Client(mcp_server)


async def test_edit_image(client: Client, clean_output_dir: Path, sample_image: Path):
    """Edit an existing image and verify output."""
    async with client:
        result = await client.call_tool(
            "edit_image",
            {
                "prompt": "Add a red border",
                "image_paths": [str(sample_image)],
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1
    assert "path" in parsed[0]

    edited_path = Path(parsed[0]["path"])
    assert edited_path.exists()
    assert edited_path != sample_image
    assert edited_path.stat().st_size > 0


async def test_edit_with_high_fidelity(client: Client, clean_output_dir: Path, sample_image: Path):
    """Edit with high input fidelity."""
    async with client:
        result = await client.call_tool(
            "edit_image",
            {
                "prompt": "Add a hat",
                "image_paths": [str(sample_image)],
                "input_fidelity": "high",
                "quality": "low",
                "size": "1024x1024",
            },
        )

    parsed = json.loads(result.content[0].text)
    assert len(parsed) == 1
    assert Path(parsed[0]["path"]).exists()


async def test_iterative_workflow(client: Client, clean_output_dir: Path):
    """Full iterative chain: generate → edit → edit again."""
    async with client:
        gen_result = await client.call_tool(
            "generate_image",
            {
                "prompt": "A simple house drawing",
                "quality": "low",
                "size": "1024x1024",
            },
        )
        v1_path = json.loads(gen_result.content[0].text)[0]["path"]
        assert Path(v1_path).exists()

        edit1_result = await client.call_tool(
            "edit_image",
            {
                "prompt": "Add a garden",
                "image_paths": [v1_path],
                "quality": "low",
                "size": "1024x1024",
            },
        )
        v2_path = json.loads(edit1_result.content[0].text)[0]["path"]
        assert Path(v2_path).exists()

        edit2_result = await client.call_tool(
            "edit_image",
            {
                "prompt": "Make sky sunset orange",
                "image_paths": [v2_path],
                "quality": "low",
                "size": "1024x1024",
            },
        )

    v3_parsed = json.loads(edit2_result.content[0].text)
    v3_path = Path(v3_parsed[0]["path"])
    assert v3_path.exists()

    assert Path(v1_path).exists()
    assert Path(v2_path).exists()
    assert v3_path.exists()


async def test_edit_nonexistent_file_returns_error(client: Client, clean_output_dir: Path):
    """Editing a nonexistent file should raise a validation error."""
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="Image file not found"):
        async with client:
            await client.call_tool(
                "edit_image",
                {
                    "prompt": "Do something",
                    "image_paths": ["/nonexistent/fake.png"],
                    "quality": "low",
                    "size": "1024x1024",
                },
            )
