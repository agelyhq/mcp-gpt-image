# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.0 - 2026-08-14

A breaking release, top to bottom. The package has a new name, a new import path, one supported
model and a third tool. Nothing from 0.1.x is carried forward: there are no compatibility
shims, no deprecated aliases and no dual code paths, because the model this server was written
against is being retired and a transitional layer would only have made the migration slower to
find.

Migrating is a matter of changing the command your MCP client runs, renaming five environment
variables, and deleting the `model` and `input_fidelity` arguments from any tool call you have
scripted.

### Added

- **`refine_image`, multi-turn refinement.** The reason this release exists. It runs through the
  OpenAI Responses API with the built-in image generation tool, driven by the mainline model
  `gpt-5.6`, and returns a `session_id` alongside the saved image. Passing that id on the next
  call continues the same conversation, so a correction is one sentence rather than a rewritten
  prompt plus a re-uploaded image. Sessions last about 30 days. It costs more per image than
  `generate_image`, because a reasoning model is doing the steering, and it pays for itself from
  the second turn on.
- **Local validation of the refinement session id.** An id that cannot be an OpenAI response id
  is rejected here with a message telling you to omit it, rather than spending a round trip on an
  id an agent invented.
- **Custom sizes, validated before the request leaves.** Any `WIDTHxHEIGHT` with both dimensions
  a multiple of 16, an aspect ratio between 1:3 and 3:1 and a maximum of 3840x2160 is accepted,
  and the four rules are checked locally so a malformed size costs a validation error instead of
  a billed refusal.
- **`output_format` on every result.** Callers previously had to infer the format from the file
  extension, which was the wrong thing to trust. See the format detection change below.
- **A documentation set** under [docs/](docs/): getting started, a full tool reference, the
  refinement workflow, configuration, and troubleshooting organised by symptom.

### Changed

- **Package renamed from `openai-imagegen-mcp` to `mcp-gpt-image`.** The old name described a
  family of models that no longer exists, and it put the vendor first in a name that people type.
  The console script is now `mcp-gpt-image`, so client configs need their `args` updated.
- **Import path renamed from `openai_imagegen_mcp` to `gpt_image_mcp`.** Only relevant if you
  imported the server to embed it; the MCP surface is unaffected.
- **Environment variables renamed from `OPENAI_IMAGEGEN_*` to `GPT_IMAGE_*`.**
  `OPENAI_IMAGEGEN_OUTPUT_DIR` becomes `GPT_IMAGE_OUTPUT_DIR`,
  `OPENAI_IMAGEGEN_DEFAULT_MODEL` becomes `GPT_IMAGE_MODEL`, and `OPENAI_IMAGEGEN_TIMEOUT`
  becomes `GPT_IMAGE_TIMEOUT`, joined by the new `GPT_IMAGE_REFINE_TIMEOUT`. The prefix now
  matches the package rather than the vendor. `OPENAI_API_KEY` deliberately keeps its standard
  name so an existing OpenAI setup works untouched.
- **Only gpt-image-2 is supported.** `dall-e-2` and `dall-e-3` were shut down on 2026-05-12, and
  on 2026-06-02 OpenAI announced that `gpt-image-1.5`, `gpt-image-1-mini` and
  `chatgpt-image-latest` retire on 2026-12-01, all migrating to gpt-image-2. Supporting a family
  of models with one live member would have been a menu of expiry dates. `GPT_IMAGE_MODEL` still
  lets you choose between the floating `gpt-image-2` and the pinned snapshot
  `gpt-image-2-2026-04-21`, which is the only choice left that changes anything.
- **Errors surface as MCP tool errors instead of an `{"error": ...}` payload.** The old shape
  returned a successful tool result whose content happened to describe a failure, and agents read
  that as an image that exists. A tool error carrying the API's own message is something a caller
  can actually react to, and the message is passed through untouched so it can.
- **The output format is detected from the returned bytes, not from the request.** The API
  sometimes answers a webp request with PNG data, and a file named `.webp` holding PNG bytes
  breaks whatever opens it next, far away from the cause. Files are now named after their real
  content and the result reports what was written, which means `output_format` in a result can
  differ from the `output_format` you asked for. That is the deliberate behaviour.
- **Default timeouts raised to 300 seconds.** gpt-image-2 plans before it draws, and complex
  prompts can take up to two minutes, with large sizes at the top of that range. The old
  180-second budget cancelled calls that would have succeeded.
- **Python floor raised to 3.12**, and dependencies moved to `fastmcp>=3.4.7,<4` and
  `openai>=3.0,<4`. The FastMCP floor is where Starlette is pinned above CVE-2026-48710, and an
  OpenAI SDK older than 3.0 predates gpt-image-2 entirely.

### Removed

- **The `model` parameter on the tools.** With one supported model, a per-call override could
  only ever be a way to get an error from OpenAI. The model is a server setting now, which is
  also the right place for a decision about reproducibility.
- **`input_fidelity` on `edit_image`.** gpt-image-2 always processes input images at high
  fidelity, so the parameter has nothing left to select. Faces, logos and lettering survive an
  edit without a setting to remember, which is a straight improvement: forgetting to raise it was
  the usual reason a logo came back smudged.
- **`background="transparent"`.** gpt-image-2 does not support transparent backgrounds and the
  API refuses the value, so it is absent from the schema and a client asking for it gets an
  immediate schema error rather than a billed refusal. This is a real regression against the
  previous generation: pipelines that relied on a cut-out subject now need a mask or an external
  background remover.
- **HTTP transport and the cloud entrypoint.** The streamable-http mode, the `PORT` variable and
  the root-level `fastmcp_server.py` are gone. Every real use of this server was a local MCP
  client spawning it on stdio, and the HTTP path carried a deployment story, an authentication
  question and a surface area that nothing was using.
- **The Docker image and its Dockerfile.** They existed to serve the HTTP mode, and they went
  with it. A stdio server is started by its client and has nothing to containerise.
- **The `response_format` parameter.** It belonged to the DALL-E models and returns a 400 on
  gpt-image-2, which returns base64 through `output_format` directly.

### Fixed

- **Concurrent calls sharing a prompt no longer overwrite each other.** Filenames carry a UTC
  timestamp with microsecond precision, so two tools invoked at the same moment with the same
  prompt write two files rather than one.
- **A malformed API payload no longer writes a broken file.** Bytes that are not a PNG, a JPEG or
  a WEBP are refused with a typed error and nothing is written, instead of leaving a file on disk
  that fails to open later.
- **File descriptors no longer stay open across an await in `edit_image`.** Input images are read
  into memory and sent as multipart tuples, so a slow API call cannot hold handles open for its
  duration.

## 0.1.0

Initial release, as `openai-imagegen-mcp`. Two tools, `generate_image` and `edit_image`, on
`gpt-image-1.5`, over stdio or streamable-http. Never published to PyPI, so 0.2.0 is the first
version anyone can install.
