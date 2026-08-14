"""Tool registry.

Every module in this package that does not start with an underscore is a tool and
must expose `register(mcp, deps)`. Discovery is automatic, so adding a tool means
adding a file, and a tool that forgets to register fails at startup instead of
going silently missing from the server.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from gpt_image_mcp.deps import ToolDeps


def register_all_tools(mcp: FastMCP, deps: ToolDeps) -> None:
    """Import every tool module and let it register itself."""
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{__name__}.{module_info.name}")
        register = getattr(module, "register", None)
        if register is None:
            raise RuntimeError(
                f"Tool module '{module_info.name}' has no register(mcp, deps) function. "
                "Rename it with a leading underscore if it is a helper."
            )
        register(mcp, deps)
