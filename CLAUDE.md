# CLAUDE.md — openai-imagegen-mcp

## Purpose

MCP server exposing OpenAI's Image API (gpt-image-1.5) as two tools: `generate_image` and `edit_image`. Enables iterative image workflows where Claude chains outputs as inputs.

## Architecture

Clean Architecture with 3 layers:

- **Domain**: `openai_client.py` — async wrapper around OpenAI SDK (runs sync calls in `asyncio.to_thread()`), defines domain exceptions (`ImageClientError`, `ImageRateLimitError`)
- **Use Cases**: `tools/generate.py`, `tools/edit.py` — error handling + delegation to client; `tools/_validators.py` — shared parameter validation
- **Framework**: `server.py` (FastMCP wiring), `__main__.py` (CLI), root-level `fastmcp_server.py` (cloud entrypoint)

Config via `pydantic-settings` in `config.py`, reads from `.env`.

## Key Conventions

- **File paths as interface**: Tools return `{path, revised_prompt}`, never binary. Images saved to `output_dir` with timestamped filenames.
- **Dual transport**: stdio (default, local) and streamable-http (cloud). Same server instance.
- **No `response_format` param**: gpt-image-1.5 returns b64_json via `output_format` parameter directly. The older `response_format` param causes 400 errors.
- **Filename format**: `{YYYYMMDD_HHMMSS_ffffff}_{prompt_slug}_{n}.{format}` — microsecond precision prevents collisions under concurrency.
- **Error handling**: Domain exceptions (`ImageClientError`, `ImageRateLimitError`) and `ValueError` caught in tool layer, returned as `{error: ...}` — no crashes.

## Commands

```bash
make install   # uv sync --all-extras
make build     # uv build
make lint      # ruff check + format --check
make test      # pytest E2E tests (hits real OpenAI API)
make run       # Start stdio server
```

## Boundaries

- Tools validate parameters before calling OpenAI (size, quality, format, n, file existence)
- `openai_client.py` is the only module that imports `openai`
- Tools register themselves on the FastMCP instance via `register_*_tool()` functions
- Config is injected into `ImageClient`; tools receive the client instance

## Testing

E2E-style tests go through FastMCP Client → Server → mocked OpenAI SDK → disk. The OpenAI client is patched with `unittest.mock` in `conftest.py` to avoid real API calls in CI. Tests validate the full MCP tool lifecycle and file output.
