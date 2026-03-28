"""Shared parameter validation for image tools."""

from __future__ import annotations

from pathlib import Path

VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
VALID_QUALITIES = {"low", "medium", "high", "auto"}
VALID_FORMATS = {"png", "jpeg", "webp"}
VALID_BACKGROUNDS = {"transparent", "opaque", "auto"}
VALID_FIDELITIES = {"low", "high"}


def validate_common_params(
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    background: str,
) -> None:
    """Validate parameters shared by generate and edit tools."""
    if size not in VALID_SIZES:
        raise ValueError(f"Invalid size '{size}'. Must be one of {VALID_SIZES}")

    if quality not in VALID_QUALITIES:
        raise ValueError(f"Invalid quality '{quality}'. Must be one of {VALID_QUALITIES}")

    if output_format not in VALID_FORMATS:
        raise ValueError(f"Invalid format '{output_format}'. Must be one of {VALID_FORMATS}")

    if not 0 <= output_compression <= 100:
        raise ValueError(f"output_compression must be 0-100, got {output_compression}")

    if background not in VALID_BACKGROUNDS:
        raise ValueError(f"Invalid background '{background}'. Must be one of {VALID_BACKGROUNDS}")


def validate_generate_params(
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    background: str,
    n: int,
) -> None:
    """Validate generate_image parameters."""
    validate_common_params(size, quality, output_format, output_compression, background)

    if not 1 <= n <= 4:
        raise ValueError(f"n must be 1-4, got {n}")


def validate_edit_params(
    image_paths: list[str],
    mask_path: str | None,
    size: str,
    quality: str,
    output_format: str,
    output_compression: int,
    background: str,
    input_fidelity: str,
) -> None:
    """Validate edit_image parameters."""
    if not image_paths:
        raise ValueError("At least one image_path is required")

    if len(image_paths) > 5:
        raise ValueError(f"Maximum 5 input images, got {len(image_paths)}")

    for p in image_paths:
        if not Path(p).is_file():
            raise ValueError(f"Image file not found: {p}")

    if mask_path and not Path(mask_path).is_file():
        raise ValueError(f"Mask file not found: {mask_path}")

    validate_common_params(size, quality, output_format, output_compression, background)

    if input_fidelity not in VALID_FIDELITIES:
        raise ValueError(f"Invalid fidelity '{input_fidelity}'. Must be one of {VALID_FIDELITIES}")
