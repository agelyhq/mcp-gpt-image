# openai-imagegen-mcp

Python MCP server for image generation and iterative editing using OpenAI's `gpt-image-1.5` model.

## Tech Stack

- **FastMCP** `>=2.0` — MCP server framework
- **OpenAI SDK** `>=1.60` — Image API client
- **Python** `>=3.11`
- **Package manager:** uv

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key with gpt-image-1.5 access

## Setup

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

make install
```

## Commands

```bash
make install   # Install dependencies
make build     # Build package
make lint      # Run ruff linter + formatter check
make test      # Run E2E tests (requires valid API key)
make run       # Start MCP server (stdio mode)
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_IMAGEGEN_OUTPUT_DIR` | No | `./generated-images` | Directory for generated images |
| `OPENAI_IMAGEGEN_DEFAULT_MODEL` | No | `gpt-image-1.5` | Default model |
| `OPENAI_IMAGEGEN_DEFAULT_QUALITY` | No | `auto` | Default quality |
| `OPENAI_IMAGEGEN_TIMEOUT` | No | `180` | API timeout in seconds |
| `PORT` | No | `8000` | HTTP port (streamable-http mode) |
| `GOOGLE_OAUTH_CLIENT_ID` | No | — | GCP OAuth client ID (remote mode) |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No | — | GCP OAuth client secret (remote mode) |

## MCP Tools

### `generate_image`

Generate image(s) from a text prompt. Returns list of `{path, revised_prompt}`.

Parameters: `prompt`, `model`, `size`, `quality`, `output_format`, `output_compression`, `background`, `n`

### `edit_image`

Edit existing image(s) with a text prompt. Supports inpainting with mask.

Parameters: `prompt`, `image_paths`, `mask_path`, `model`, `size`, `quality`, `output_format`, `output_compression`, `background`, `input_fidelity`

## MCP Client Configuration

### Claude Code / VS Code (stdio)

```json
{
  "mcpServers": {
    "openai-imagegen": {
      "command": "uv",
      "args": ["--directory", "/path/to/openai-imagegen-mcp", "run", "openai-imagegen-mcp"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### Remote (streamable-http)

```json
{
  "mcpServers": {
    "openai-imagegen": {
      "url": "https://imagegen-mcp.your-domain.com/mcp"
    }
  }
}
```
