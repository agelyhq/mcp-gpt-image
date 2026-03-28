# Spec: `openai-imagegen-mcp`

Python MCP server for image generation and iterative editing using OpenAI's `gpt-image-1.5` model.

## 1. Capabilities

### What gpt-image-1.5 supports via the Image API

**Generation** (`POST /v1/images/generations`)
- Text-to-image from prompt
- Multiple images per request (`n=1..4`)
- Size: `1024x1024`, `1536x1024`, `1024x1536`, `auto`
- Quality: `low`, `medium`, `high`, `auto`
- Format: `png`, `jpeg`, `webp` (with compression control 0-100)
- Background: `transparent`, `opaque`, `auto`
- Moderation: `auto`, `low`

**Editing** (`POST /v1/images/edits`)
- Edit one or more images with a text prompt
- Multiple input images (up to 5 with high fidelity on gpt-image-1.5)
- Inpainting with alpha-channel mask
- `input_fidelity`: `low` | `high` (high preserves faces, logos, fine details)

**Iterative workflows (stateless chaining)**
Each call is independent. Claude chains outputs as inputs:
```
generate("Agely logo, modern, health-tech")            -> v1.png
edit([v1.png], "add a subtle heart in the icon")        -> v2.png
edit([v2.png], "make background transparent")           -> v3.png
edit([v3.png, palette.png], "match these brand colors") -> v4.png
```

No server-side session needed. Claude tracks conversation state and feeds previous outputs back.

### Out of scope (v1)

- Responses API multi-turn (stateful server sessions, `previous_response_id`)
- Streaming partial images
- Batch API
- DALL-E 2/3 models

## 2. MCP Tools

### `generate_image`

Generate image(s) from a text prompt.

```python
prompt: str                              # required
model: str = "gpt-image-1.5"            # gpt-image-1.5 | gpt-image-1 | gpt-image-1-mini
size: str = "auto"                       # 1024x1024 | 1536x1024 | 1024x1536 | auto
quality: str = "auto"                    # low | medium | high | auto
output_format: str = "png"              # png | jpeg | webp
output_compression: int = 100           # 0-100, jpeg/webp only
background: str = "auto"                # transparent | opaque | auto
n: int = 1                              # 1-4
```

Returns: list of `{path: str, revised_prompt: str | None}`

### `edit_image`

Edit existing image(s) with a text prompt. Supports adding/removing elements, style transfer, inpainting with mask.

```python
prompt: str                              # required
image_paths: list[str]                   # required, 1+ local file paths
mask_path: str | None = None            # optional PNG with alpha channel
model: str = "gpt-image-1.5"
size: str = "auto"
quality: str = "auto"
output_format: str = "png"
output_compression: int = 100
background: str = "auto"
input_fidelity: str = "low"             # low | high
```

Returns: list of `{path: str, revised_prompt: str | None}`

## 3. Architecture

### Project structure

```
openai-imagegen-mcp/
├── pyproject.toml
├── Dockerfile
├── .env.example
├── src/
│   └── openai_imagegen_mcp/
│       ├── __init__.py
│       ├── __main__.py              # python -m entrypoint
│       ├── server.py                # FastMCP server instance + tool registration
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── generate.py          # generate_image tool
│       │   └── edit.py              # edit_image tool
│       ├── openai_client.py         # thin async wrapper around openai SDK
│       └── config.py                # env-based config
├── fastmcp_server.py                # cloud entrypoint (exports mcp/app)
└── tests/
    ├── test_generate.py
    └── test_edit.py
```

### Stack

- **FastMCP** `>=3.1.1` (standalone `fastmcp` package from Prefect)
- **OpenAI SDK** `>=1.60` (gpt-image-1.5 support)
- **Python** `>=3.11`
- **Package manager:** uv

### Transport modes

**stdio (local, default)**
For Claude Code, VS Code, Claude Desktop. No auth on the MCP transport layer; OpenAI API key is passed via env.

**streamable-http (remote)**
For cloud deployment (e.g. Cloud Run). Exposes HTTP endpoint. Can be protected by:
- GCP OAuth 2.1 via FastMCP's `GoogleProvider` (same pattern as google_workspace_mcp)
- Or Cloud Run IAP / API Gateway for simpler setups

### Config

All via environment variables:

```bash
# Required
OPENAI_API_KEY=sk-...

# Defaults
OPENAI_IMAGEGEN_OUTPUT_DIR=./generated-images
OPENAI_IMAGEGEN_DEFAULT_MODEL=gpt-image-1.5
OPENAI_IMAGEGEN_DEFAULT_QUALITY=auto
OPENAI_IMAGEGEN_TIMEOUT=180        # seconds, complex prompts can take ~2min

# Remote mode (streamable-http)
PORT=8000
# GCP OAuth 2.1 (optional, for protected remote access)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

## 4. Entrypoints

### CLI (main.py)

```python
parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
```

- `stdio`: `server.run()` (default, for local MCP clients)
- `streamable-http`: `server.run(transport="streamable-http", host=host, port=port)`

### Cloud (fastmcp_server.py)

Minimal module that forces HTTP transport, configures OAuth 2.1 if env vars present, imports tools, and exports `mcp = server` for `fastmcp run fastmcp_server.py`.

### pyproject.toml scripts

```toml
[project.scripts]
openai-imagegen-mcp = "openai_imagegen_mcp.__main__:main"
```

## 5. MCP Client Configs

### Claude Code / VS Code (stdio)

```json
{
  "mcpServers": {
    "openai-imagegen": {
      "command": "uv",
      "args": ["run", "--from", "openai-imagegen-mcp", "openai-imagegen-mcp"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### Local dev (stdio)

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

## 6. Key Design Decisions

1. **Image API only, not Responses API.** Stateless chaining is sufficient for iterative editing when Claude is the orchestrator. No server-side session state, no cleanup, no complexity.

2. **File paths as interface.** MCP tools return text, not binary. We decode base64 from the API, write to `output_dir` with timestamped filenames, and return the path. Claude can reference it in subsequent `edit_image` calls.

3. **Filename convention:** `{timestamp}_{prompt_slug}_{n}.{format}` (e.g. `20260328_143022_agely_logo_1.png`). Prevents collisions, sortable, human-readable.

4. **Dual transport, single codebase.** Same server instance, same tools. Only the entrypoint and auth layer differ between stdio and HTTP modes. Mirrors google_workspace_mcp's pattern.

5. **OpenAI client:** thin async wrapper using `openai` SDK. Runs sync SDK calls in `asyncio.to_thread()` (same pattern as google_workspace_mcp's service calls).

## 7. Error Handling

- **Missing API key:** fail fast at startup with clear message
- **Content policy violation:** catch `openai.BadRequestError`, return error text (no crash)
- **Invalid image paths:** validate existence + format before calling API
- **Timeout:** httpx timeout set to 180s (complex prompts can take ~2 min)
- **Rate limits:** surface OpenAI's rate limit error with retry-after hint

## 8. Pricing Reference (March 2026)

| Quality | 1024x1024 | 1536x1024 / 1024x1536 |
|---------|-----------|----------------------|
| Low     | $0.009    | ~$0.013              |
| Medium  | $0.034    | ~$0.051              |
| High    | $0.133    | ~$0.200              |

gpt-image-1-mini: $0.005-$0.052/image. Batch API: 50% discount.

## 9. v2 Roadmap

- Responses API multi-turn for server-managed iterative sessions
- Streaming partial images via MCP notifications
- Batch API support for bulk generation
- Optional cloud storage upload (GCS/S3) instead of local save
- `create_mask` helper tool (generate mask from natural language description)