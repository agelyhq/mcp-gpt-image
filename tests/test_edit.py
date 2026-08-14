"""Scenarios for edit_image, driven through the MCP client."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from conftest import FAKE_PNG_BYTES, error_text, make_pngs, payloads

if TYPE_CHECKING:
    from conftest import FakeSdk
    from fastmcp import Client


async def test_edit_single_image_sends_one_upload_tuple(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    async with client:
        result = await client.call_tool(
            "edit_image", {"prompt": "add a red border", "image_paths": [str(sample_png)]}
        )

    images = payloads(result)
    assert len(images) == 1
    assert Path(images[0]["path"]).is_file()

    sent = fake_sdk.edit_calls[0]
    assert isinstance(sent["image"], tuple)
    assert sent["image"] == ("source.png", FAKE_PNG_BYTES, "image/png")


async def test_edit_several_images_sends_a_list(
    client: Client, fake_sdk: FakeSdk, tmp_path: Path
) -> None:
    paths = make_pngs(tmp_path, 3)

    async with client:
        result = await client.call_tool(
            "edit_image", {"prompt": "combine these", "image_paths": paths}
        )

    assert not result.is_error
    sent_images = fake_sdk.edit_calls[0]["image"]
    assert isinstance(sent_images, list)
    assert len(sent_images) == 3
    assert [name for name, _, _ in sent_images] == ["input_0.png", "input_1.png", "input_2.png"]


async def test_edit_too_many_images_is_rejected_by_schema(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        result = await client.call_tool(
            "edit_image",
            {"prompt": "combine these", "image_paths": [f"/tmp/x{i}.png" for i in range(17)]},
            raise_on_error=False,
        )

    assert result.is_error
    assert "image_paths" in error_text(result)
    assert fake_sdk.edit_calls == []


async def test_edit_missing_file_names_the_path(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        result = await client.call_tool(
            "edit_image",
            {"prompt": "do something", "image_paths": ["/nonexistent/ghost.png"]},
            raise_on_error=False,
        )

    assert result.is_error
    assert "/nonexistent/ghost.png" in error_text(result)
    assert fake_sdk.edit_calls == []


async def test_edit_non_image_suffix_is_rejected(
    client: Client, fake_sdk: FakeSdk, tmp_path: Path
) -> None:
    note = tmp_path / "note.txt"
    note.write_text("this is not an image")

    async with client:
        result = await client.call_tool(
            "edit_image",
            {"prompt": "do something", "image_paths": [str(note)]},
            raise_on_error=False,
        )

    assert result.is_error
    assert "Unsupported image type '.txt'" in error_text(result)
    assert fake_sdk.edit_calls == []


async def test_edit_mask_is_forwarded(
    client: Client, fake_sdk: FakeSdk, sample_png: Path, sample_mask: Path
) -> None:
    async with client:
        result = await client.call_tool(
            "edit_image",
            {
                "prompt": "repaint the sky",
                "image_paths": [str(sample_png)],
                "mask_path": str(sample_mask),
            },
        )

    assert not result.is_error
    assert fake_sdk.edit_calls[0]["mask"] == ("mask.png", FAKE_PNG_BYTES, "image/png")


async def test_edit_missing_mask_is_rejected(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    async with client:
        result = await client.call_tool(
            "edit_image",
            {
                "prompt": "repaint the sky",
                "image_paths": [str(sample_png)],
                "mask_path": "/nonexistent/mask.png",
            },
            raise_on_error=False,
        )

    assert result.is_error
    assert "Mask file not found: /nonexistent/mask.png" in error_text(result)
    assert fake_sdk.edit_calls == []


async def test_edit_non_png_mask_is_rejected(
    client: Client, fake_sdk: FakeSdk, sample_png: Path, tmp_path: Path
) -> None:
    mask = tmp_path / "mask.jpeg"
    mask.write_bytes(FAKE_PNG_BYTES)

    async with client:
        result = await client.call_tool(
            "edit_image",
            {
                "prompt": "repaint the sky",
                "image_paths": [str(sample_png)],
                "mask_path": str(mask),
            },
            raise_on_error=False,
        )

    assert result.is_error
    assert "must be a PNG" in error_text(result)
    assert fake_sdk.edit_calls == []


async def test_edit_never_sends_fidelity_or_moderation(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    """gpt-image-2 is always high fidelity and its edit endpoint has no moderation key."""
    async with client:
        await client.call_tool(
            "edit_image",
            {
                "prompt": "add a hat",
                "image_paths": [str(sample_png)],
                "quality": "high",
                "background": "opaque",
            },
        )

    sent = fake_sdk.edit_calls[0]
    assert sent["model"] == "gpt-image-2"
    assert "input_fidelity" not in sent
    assert "moderation" not in sent
