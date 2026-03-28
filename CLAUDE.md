# CLAUDE.md — openai-imagegen-mcp

## Purpose

MCP server exposing OpenAI's Image API (gpt-image-1.5) as two tools: `generate_image` and `edit_image`. Enables iterative image workflows where Claude chains outputs as inputs.

## Architecture

Clean Architecture with 3 layers:

- **Domain**: `openai_client.py` — async wrapper around OpenAI SDK (runs sync calls in `asyncio.to_thread()`)
- **Use Cases**: `tools/generate.py`, `tools/edit.py` — validation + error handling + delegation to client
- **Framework**: `server.py` (FastMCP wiring), `__main__.py` (CLI), root-level `fastmcp_server.py` (cloud entrypoint)

Config via `pydantic-settings` in `config.py`, reads from `.env`.

## Key Conventions

- **File paths as interface**: Tools return `{path, revised_prompt}`, never binary. Images saved to `output_dir` with timestamped filenames.
- **Filename format**: `{YYYYMMDD_HHMMSS}_{prompt_slug}_{n}.{format}`
- **Dual transport**: stdio (default, local) and streamable-http (cloud). Same server instance.
- **No `response_format` param**: gpt-image-1.5 returns b64_json via `output_format` parameter directly. The older `response_format` param causes 400 errors.
- **Error handling**: `BadRequestError` and `RateLimitError` caught in tool layer, returned as `{error: ...}` — no crashes.

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

E2E only — tests go through FastMCP Client → Server → OpenAI API → disk. No mocks. Requires valid `OPENAI_API_KEY` in `.env`.
