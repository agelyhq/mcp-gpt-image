"""Scenarios for refine_image, the only tool with a memory."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from conftest import error_text, payloads, sdk_error
from fastmcp import Client
from openai import BadRequestError, NotFoundError

from gpt_image_mcp.config import Settings
from gpt_image_mcp.domain.types import ORCHESTRATOR_MODEL
from gpt_image_mcp.server import create_server

if TYPE_CHECKING:
    from conftest import FakeSdk


async def _start_session(client: Client, instruction: str = "draw a lighthouse") -> str:
    result = await client.call_tool("refine_image", {"instruction": instruction})
    return payloads(result)["session_id"]


async def test_refine_first_turn_opens_a_session(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        result = await client.call_tool("refine_image", {"instruction": "draw a lighthouse"})

    refined = payloads(result)
    assert refined["session_id"].startswith("resp_")
    assert Path(refined["path"]).is_file()

    sent = fake_sdk.responses_calls[0]
    assert sent["model"] == ORCHESTRATOR_MODEL
    assert sent["tools"] == [{"type": "image_generation"}]
    assert "previous_response_id" not in sent


async def test_refine_honours_a_pinned_orchestrator_model(
    output_dir: Path, fake_sdk: FakeSdk
) -> None:
    """GPT_IMAGE_REFINE_MODEL must reach the API, since the default alias can drift."""
    pinned = Settings(
        openai_api_key="sk-test-key",
        gpt_image_output_dir=str(output_dir),
        gpt_image_refine_model="gpt-5.6-luna",
    )  # type: ignore[call-arg]

    async with Client(create_server(pinned, sdk=fake_sdk.client)) as client:
        await client.call_tool("refine_image", {"instruction": "draw a lighthouse"})

    assert fake_sdk.responses_calls[0]["model"] == "gpt-5.6-luna"


async def test_refine_first_turn_embeds_seed_images(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    async with client:
        result = await client.call_tool(
            "refine_image",
            {"instruction": "make the sky darker", "image_paths": [str(sample_png)]},
        )

    assert not result.is_error
    content = fake_sdk.responses_calls[0]["input"][0]["content"]
    images = [item for item in content if item["type"] == "input_image"]
    assert len(images) == 1
    assert images[0]["image_url"].startswith("data:image/png;base64,")
    assert content[0] == {"type": "input_text", "text": "make the sky darker"}


async def test_refine_second_turn_chains_on_the_session(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    async with client:
        first = await client.call_tool(
            "refine_image",
            {"instruction": "draw a lighthouse", "image_paths": [str(sample_png)]},
        )
        session_id = payloads(first)["session_id"]

        second = await client.call_tool(
            "refine_image", {"instruction": "remove the boat", "session_id": session_id}
        )

    assert payloads(second)["session_id"] != session_id

    sent = fake_sdk.responses_calls[1]
    assert sent["previous_response_id"] == session_id
    assert sent["input"] == "remove the boat"
    # The image stays on OpenAI's side, so nothing is re-uploaded on later turns.
    assert "input_image" not in json.dumps(sent, default=str)


async def test_refine_quality_high_configures_the_tool(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        await client.call_tool(
            "refine_image", {"instruction": "draw a lighthouse", "quality": "high"}
        )

    assert fake_sdk.responses_calls[0]["tools"] == [{"type": "image_generation", "quality": "high"}]


async def test_refine_quality_auto_leaves_the_tool_bare(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        await client.call_tool(
            "refine_image", {"instruction": "draw a lighthouse", "quality": "auto"}
        )

    assert fake_sdk.responses_calls[0]["tools"] == [{"type": "image_generation"}]


async def test_refine_expired_session_from_not_found(client: Client, fake_sdk: FakeSdk) -> None:
    async with client:
        session_id = await _start_session(client)
        fake_sdk.error = sdk_error(NotFoundError, "Response not found", 404)

        result = await client.call_tool(
            "refine_image",
            {"instruction": "remove the boat", "session_id": session_id},
            raise_on_error=False,
        )

    assert result.is_error
    message = error_text(result)
    assert "expired" in message
    assert "without session_id" in message


async def test_refine_expired_session_from_bad_request(client: Client, fake_sdk: FakeSdk) -> None:
    """A dropped session can surface as a 400 mentioning the previous response."""
    async with client:
        session_id = await _start_session(client)
        fake_sdk.error = sdk_error(
            BadRequestError, "Previous response with id 'resp_x' not found.", 400
        )

        result = await client.call_tool(
            "refine_image",
            {"instruction": "remove the boat", "session_id": session_id},
            raise_on_error=False,
        )

    assert result.is_error
    message = error_text(result)
    assert "expired" in message
    assert "without session_id" in message


async def test_refine_unrelated_bad_request_keeps_the_session_blameless(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        session_id = await _start_session(client)
        fake_sdk.error = sdk_error(
            BadRequestError, "Your request was rejected by our content policy", 400
        )

        result = await client.call_tool(
            "refine_image",
            {"instruction": "draw something forbidden", "session_id": session_id},
            raise_on_error=False,
        )

    assert result.is_error
    message = error_text(result)
    assert "content policy" in message
    assert "expired" not in message


async def test_refine_malformed_session_id_never_reaches_the_api(
    client: Client, fake_sdk: FakeSdk
) -> None:
    async with client:
        result = await client.call_tool(
            "refine_image",
            {"instruction": "remove the boat", "session_id": "abc"},
            raise_on_error=False,
        )

    assert result.is_error
    assert "Invalid session_id 'abc'" in error_text(result)
    assert fake_sdk.responses_calls == []


async def test_refine_answer_without_an_image_asks_for_a_rephrase(
    client: Client, fake_sdk: FakeSdk, output_dir: Path
) -> None:
    fake_sdk.output_items = [SimpleNamespace(type="message", content=[])]

    async with client:
        result = await client.call_tool(
            "refine_image", {"instruction": "what do you think of it?"}, raise_on_error=False
        )

    assert result.is_error
    assert "Phrase the instruction" in error_text(result)
    assert list(output_dir.glob("*")) == []


async def test_refine_rejects_images_on_a_running_session(
    client: Client, fake_sdk: FakeSdk, sample_png: Path
) -> None:
    """Passing both is a mistake worth naming, not something to silently drop.

    Ignoring the files would return a plausible image built from none of them,
    which reads as success.
    """
    async with client:
        session = await _start_session(client)
        result = await client.call_tool(
            "refine_image",
            {
                "instruction": "add a boat",
                "session_id": session,
                "image_paths": [str(sample_png)],
            },
            raise_on_error=False,
        )

    assert result.is_error
    assert "cannot be combined" in error_text(result)
    # The first turn is the only call that reached the API.
    assert len(fake_sdk.responses_calls) == 1
