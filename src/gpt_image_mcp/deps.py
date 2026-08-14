"""The dependency bundle handed to every tool at registration time.

It lives outside the tools package on purpose. Modules inside `tools/` are
discovered as tools unless their name starts with an underscore, and the
composition root should not have to import a private module to build this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpt_image_mcp.adapters.images_client import ImagesClient
    from gpt_image_mcp.adapters.responses_client import ResponsesImageClient
    from gpt_image_mcp.domain.image_store import ImageStore


@dataclass(frozen=True, slots=True)
class ToolDeps:
    """Everything the tools need, built once by the composition root."""

    images: ImagesClient
    responses: ResponsesImageClient
    store: ImageStore
