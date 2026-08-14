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

# Mainline chat model driving the image_generation tool in refine_image. Image
# models cannot be the primary model of a Responses call, so this is a separate id.
ORCHESTRATOR_MODEL: Final = "gpt-5.6"

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

EDIT_INPUT_SUFFIXES: Final = frozenset({".png", ".jpg", ".jpeg", ".webp"})

# Sessions are OpenAI response ids. The prefix is stable enough to reject typos
# locally, before spending a round trip on an id the client invented.
SESSION_ID_PREFIX: Final = "resp_"
SESSION_RETENTION_DAYS: Final = 30
