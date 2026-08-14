"""Value types and constants describing what gpt-image-2 accepts.

Every literal here mirrors a constraint published by OpenAI. The tool signatures
use these aliases directly, so the MCP schema sent to clients stays in sync with
the API contract without a second declaration.
"""

from __future__ import annotations

from typing import Final, Literal

Quality = Literal["auto", "low", "medium", "high"]
OutputFormat = Literal["png", "jpeg", "webp"]
Moderation = Literal["auto", "low"]

# gpt-image-2 rejects background="transparent". The value is deliberately absent
# from this alias so clients get a schema error instead of an API bill.
Background = Literal["auto", "opaque"]

MODEL: Final = "gpt-image-2"

# Mainline chat model driving the image_generation tool in refine_image. An image
# model cannot be the primary model of a Responses call, so this is a separate id.
# "chat-latest" is the one alias that never goes stale: a generation alias such as
# gpt-5.6 has to be bumped by hand every time OpenAI ships a new line. The cost is
# that its behaviour can move under us, which is what GPT_IMAGE_REFINE_MODEL is for.
ORCHESTRATOR_MODEL: Final = "chat-latest"

MAX_PROMPT_CHARS: Final = 32_000
MAX_IMAGES_PER_CALL: Final = 10
MAX_EDIT_IMAGES: Final = 16
MAX_EDIT_IMAGE_BYTES: Final = 50 * 1024 * 1024
MAX_MASK_BYTES: Final = 4 * 1024 * 1024

PRESET_SIZES: Final = frozenset({"auto", "1024x1024", "1536x1024", "1024x1536"})
SIZE_MULTIPLE: Final = 16
MAX_WIDTH: Final = 3840
MAX_HEIGHT: Final = 2160
MAX_ASPECT_RATIO: Final = 3.0

# Which files can be sent as input, and how each one is labelled on the wire.
# One mapping rather than two: a format accepted without a mime type would be
# uploaded as an opaque blob, which the API rejects for no visible reason.
MIME_BY_SUFFIX: Final = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
EDIT_INPUT_SUFFIXES: Final = frozenset(MIME_BY_SUFFIX)

# Shown to the calling model in both tool schemas, so the rules it must satisfy
# are stated once and cannot drift between the two.
SIZE_DESCRIPTION: Final = (
    "'auto', a preset (1024x1024, 1536x1024, 1024x1536), or any WIDTHxHEIGHT with "
    f"both dimensions multiples of {SIZE_MULTIPLE}, an aspect ratio between 1:3 and "
    f"3:1, and a maximum of {MAX_WIDTH}x{MAX_HEIGHT}. Anything above 2560x1440 is "
    "experimental."
)

# Sessions are OpenAI response ids. The prefix is stable enough to reject typos
# locally, before spending a round trip on an id the client invented.
SESSION_ID_PREFIX: Final = "resp_"
SESSION_RETENTION_DAYS: Final = 30
