# CLAUDE.md, mcp-gpt-image

## Purpose

MCP server exposing OpenAI's `gpt-image-2` as three tools: `generate_image`,
`edit_image` and `refine_image`. The point of the server is chaining: Claude
generates a picture, feeds the returned path back in, and keeps correcting it.

## Architecture

Three layers, dependencies pointing inward only.

- **Domain** (`domain/`): `types.py` holds every Literal alias and constant that
  mirrors an API constraint; `results.py` the data carried between layers;
  `image_store.py` the only module that writes files; `errors.py` the exception
  hierarchy. Imports neither `openai` nor `fastmcp`.
- **Adapters** (`adapters/`): `images_client.py` for `/v1/images`,
  `responses_client.py` for the Responses API image tool, `_errors.py` for the
  single translation from SDK exceptions to domain errors. The only modules that
  call the OpenAI SDK. `server.py` names `AsyncOpenAI` too, but for a type
  annotation on the injection seam, never to make a call.
- **Tools** (`tools/`): one file per MCP tool, plus `_base.py` (dependency bundle
  and the error decorator) and `_validation.py`.
- **Composition root**: `server.py`. Nothing else builds a client or a store.

## Key conventions

- **Tool discovery is automatic.** `tools/__init__.py` imports every module in the
  package that does not start with `_` and calls its `register(mcp, deps)`. A tool
  module without that function raises at startup. Adding a tool means adding a
  file; helpers must be underscore-prefixed or they will be treated as tools.
- **The schema is the validation.** `Literal` aliases and `Field(ge=, le=)`
  become enums and bounds in the MCP tool schema, so the client is refused before
  a call is billed. `_validation.py` only holds what JSON Schema cannot express:
  parsing a free-form size, and touching the filesystem.
- **File paths as the interface.** Tools return paths, never bytes. An image never
  enters the conversation, so passing it between tools costs nothing.
- **The extension follows the bytes.** `ImageStore.sniff_format` reads the magic
  bytes and names the file after what actually arrived. The API sometimes answers a
  webp request with PNG, and a `.webp` file holding PNG bytes breaks the next tool
  that opens it.
- **Errors surface as `ToolError`.** The `reports_errors` decorator in
  `tools/_base.py` converts domain and validation errors. FastMCP passes the
  message through untouched, which is what lets a calling agent fix its own call.
  Anything unlisted crashes on purpose.
- **Async all the way.** `AsyncOpenAI`, awaited directly. There is no
  `asyncio.to_thread` wrapper any more.

## What gpt-image-2 refuses

Learned the hard way, do not reintroduce:

- `background="transparent"` returns an API error. The `Background` alias has two
  values for that reason.
- `input_fidelity` is rejected: the model always works at high fidelity.
- `response_format` and `style` belong to DALL-E, which was shut down in May 2026.
- `moderation` exists on generations but not on edits.
- Inside the Responses `image_generation` tool object, only `quality` is confirmed
  as a configuration key. Framing and format live on the other two tools.

The model id is the single point of change: `MODEL` in `domain/types.py`, or the
`GPT_IMAGE_MODEL` variable to pin the `gpt-image-2-2026-04-21` snapshot.
`ORCHESTRATOR_MODEL` (`gpt-5.6`) is the mainline model driving `refine_image`; an
image model cannot be the primary model of a Responses call.

## Commands

```bash
make install   # uv sync --all-extras
make check     # lint + test, what CI runs
make lint      # ruff check, ruff format --check, mypy
make test      # pytest, fully mocked, never hits the network
make run       # start the server on stdio
make build     # uv build
```

## Testing

Every test drives the real MCP surface: `fastmcp.Client(server)` calling tools by
name. The single seam is `create_server(settings, sdk=...)`, which injects a mock
in place of `AsyncOpenAI`; there is no `patch()` on an import path. Tests assert on
what was sent to the SDK as much as on what came back, because half the contract is
about parameters this server must never send.

Building SDK exceptions in tests needs a duck-typed response object, not a real
one: `openai` 3.x runs on HTTPX2 and constructing a genuine response is a trap.

## Publishing

Version lives in `pyproject.toml` only. A published GitHub release triggers
`release.yml`, which checks the tag against that version, runs the gates, builds,
then uploads through PyPI trusted publishing. No token exists anywhere.
