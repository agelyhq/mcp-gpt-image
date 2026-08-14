"""Checks that JSON Schema cannot express.

Enums and numeric bounds are already enforced by the tool signatures: a Literal
becomes an enum in the schema, and Field(ge=..., le=...) becomes minimum/maximum.
Only what needs to look at the filesystem or parse a string lands here.
"""

from __future__ import annotations

from pathlib import Path

from gpt_image_mcp.domain.types import (
    EDIT_INPUT_SUFFIXES,
    MAX_ASPECT_RATIO,
    MAX_EDIT_IMAGE_BYTES,
    MAX_EDIT_IMAGES,
    MAX_HEIGHT,
    MAX_MASK_BYTES,
    MAX_WIDTH,
    PRESET_SIZES,
    SESSION_ID_PREFIX,
    SIZE_MULTIPLE,
)

_MIN_SESSION_ID_LEN = len(SESSION_ID_PREFIX) + 8


def validate_size(size: str) -> None:
    """Check a size against the rules gpt-image-2 publishes.

    Only the documented constraints are enforced. Anything else is left to the API
    so its own message reaches the caller instead of a guess made here.

    Raises:
        ValueError: the size is malformed or outside the published limits.
    """
    if size in PRESET_SIZES:
        return

    width, height = _parse_dimensions(size)

    if width % SIZE_MULTIPLE or height % SIZE_MULTIPLE:
        raise ValueError(
            f"Invalid size '{size}': both dimensions must be multiples of {SIZE_MULTIPLE}."
        )
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        raise ValueError(f"Invalid size '{size}': the maximum is {MAX_WIDTH}x{MAX_HEIGHT}.")
    if max(width, height) / min(width, height) > MAX_ASPECT_RATIO:
        raise ValueError(f"Invalid size '{size}': the aspect ratio must stay between 1:3 and 3:1.")


def validate_input_images(image_paths: list[str]) -> list[Path]:
    """Resolve input image paths, checking each one exists and can be sent.

    Raises:
        ValueError: a path is missing, is not an image, or is too large.
    """
    if not image_paths:
        raise ValueError("At least one image path is required.")
    if len(image_paths) > MAX_EDIT_IMAGES:
        raise ValueError(f"At most {MAX_EDIT_IMAGES} images, got {len(image_paths)}.")

    resolved = []
    for raw in image_paths:
        path = Path(raw)
        if not path.is_file():
            raise ValueError(f"Image file not found: {raw}")
        if path.suffix.lower() not in EDIT_INPUT_SUFFIXES:
            raise ValueError(
                f"Unsupported image type '{path.suffix}' for {raw}. "
                f"Use one of {', '.join(sorted(EDIT_INPUT_SUFFIXES))}."
            )
        if path.stat().st_size > MAX_EDIT_IMAGE_BYTES:
            raise ValueError(f"Image {raw} is over the {MAX_EDIT_IMAGE_BYTES // 1024**2}MB limit.")
        resolved.append(path)

    return resolved


def validate_mask(mask_path: str | None) -> Path | None:
    """Resolve an optional mask path.

    Dimensions must match the first input image, but checking that would mean
    decoding the image, so the API owns that rule.

    Raises:
        ValueError: the mask is missing, not a PNG, or too large.
    """
    if mask_path is None:
        return None

    path = Path(mask_path)
    if not path.is_file():
        raise ValueError(f"Mask file not found: {mask_path}")
    if path.suffix.lower() != ".png":
        raise ValueError(f"The mask must be a PNG with an alpha channel, got '{path.suffix}'.")
    if path.stat().st_size > MAX_MASK_BYTES:
        raise ValueError(f"Mask {mask_path} is over the {MAX_MASK_BYTES // 1024**2}MB limit.")

    return path


def validate_session_id(session_id: str) -> None:
    """Reject a session id that cannot be an OpenAI response id.

    Raises:
        ValueError: the id has the wrong shape.
    """
    if not session_id.startswith(SESSION_ID_PREFIX) or len(session_id) < _MIN_SESSION_ID_LEN:
        raise ValueError(
            f"Invalid session_id '{session_id}'. It must be an id returned by a previous "
            f"refine_image call, starting with '{SESSION_ID_PREFIX}'. "
            "Omit it to start a new session."
        )


def _parse_dimensions(size: str) -> tuple[int, int]:
    width, _, height = size.partition("x")
    if not width.isdigit() or not height.isdigit():
        raise ValueError(
            f"Invalid size '{size}'. Use 'auto', a preset, or WIDTHxHEIGHT such as '1536x864'."
        )
    return int(width), int(height)
