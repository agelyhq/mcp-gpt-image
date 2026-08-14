# 🎨 mcp-gpt-image

**An image MCP server built for the second draft, not the first.**

Getting one picture out of a model is the easy part. The afternoon goes on the twelve that
come after it: the sky is too bright, the logo drifted, the text on the sign came out wrong.
Most image connectors stop at the first picture and leave you to redo the loop by hand.

Three tools, OpenAI's [gpt-image-2](https://platform.openai.com/docs/models/gpt-image-2), and
file paths instead of base64.

## 🧱 The problem

You write a prompt, you get a picture, you want the sky darker. So you write the whole prompt
again with "darker sky" appended, because the model kept nothing from the first call. Every
correction is a full rewrite, and the model has no idea what it just drew.

When the connector hands images back as base64 it gets worse. The picture is now sitting in
the conversation: it cost tokens to arrive, it costs tokens again on every turn it stays
there, and feeding it into the next step means sending those same bytes back up. Two rounds
of that on a 1536x1024 image and the context window is mostly pixels.

This server takes the other route on both counts. Images travel as **file paths**:
`generate_image` writes a file and returns where it is, `edit_image` and `refine_image` take
paths as input, so a picture moves from one step to the next without ever entering the
conversation. And `refine_image` **holds the thread** with the model, so turn one is a full
description and turn two is "make the sky darker". Nothing is re-uploaded, nothing is
re-described.

## 📦 Install

```bash
claude mcp add gpt-image -e OPENAI_API_KEY=sk-... -- uvx mcp-gpt-image
```

Or in any MCP client's config:

```json
{
  "mcpServers": {
    "gpt-image": {
      "command": "uvx",
      "args": ["mcp-gpt-image"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "GPT_IMAGE_OUTPUT_DIR": "/home/you/images"
      }
    }
  }
}
```

Needs Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and an OpenAI key on an
organisation with access to image models. Transport is stdio, and stdio is the only one:
there is no HTTP mode and no Docker image, so there is no gateway to deploy and nothing
listening on a port.

## 🚀 Quickstart

Ask for a picture:

```
Generate a wide banner of a lighthouse in a storm, 1536x1024.
```

The agent calls `generate_image(prompt="...", size="1536x1024")` and gets back a path:

```json
[{ "path": "/home/you/images/20260814_142233_051182_a_wide_banner_of_a_lighthouse_in_a_1.png",
   "output_format": "png",
   "revised_prompt": null }]
```

Then keep working on it. Say what is wrong, not what you wanted in the first place:

```
Take that one and start a refinement session: make the sea rougher.
```

`refine_image(instruction="make the sea rougher", image_paths=["/home/you/images/2026...png"])`
returns a new path plus a `session_id` that looks like `resp_0a1b2c3d...`. From here the image
stays on OpenAI's side:

```
Now darken the sky and add a boat on the left.
```

`refine_image(instruction="darken the sky and add a boat on the left", session_id="resp_0a1b...")`.
No image is uploaded, no prompt is rewritten. The instruction alone travels.

And when the change is a one-off rather than a conversation, `edit_image` does it in a single
call, on local files, with an optional mask:

```
Put the logo from ~/brand/logo.png in the bottom right corner of the banner.
```

`edit_image(prompt="...", image_paths=["/home/you/images/2026...png", "/home/you/brand/logo.png"])`.

## ✨ What you can do

**🖼️ Draw from nothing.** `generate_image` takes a prompt of up to 32,000 characters and
writes up to 10 variations in one call. Sizes go well past the three presets: any
`WIDTHxHEIGHT` with both dimensions a multiple of 16 works, up to 3840x2160, which is how you
get a banner that fits your layout instead of one you have to crop.

**✂️ Edit and compose.** `edit_image` takes up to 16 local images and one prompt. One image in
means a change to that image; several in means the prompt decides what each one contributes,
which is how a product shot, a background and a logo become one picture. An optional PNG mask
marks the region to repaint. Every input is processed at full fidelity, so faces, logos and
lettering survive without a setting to find and switch on.

**🔁 Refine over several turns.** `refine_image` runs through the Responses API with a
reasoning model steering the drawing, and returns a `session_id`. Pass that id back and the
conversation continues: the model remembers the image and the instructions that shaped it,
so corrections read like corrections. Sessions live about 30 days. It is also the only tool
here that fills in `revised_prompt`, so you can read back how your instruction was understood
before you spend another turn guessing.
See [docs/refinement.md](docs/refinement.md).

**📁 Paths in, paths out.** Every tool returns `{path, output_format, revised_prompt}` with an
absolute path, and every tool that takes an image takes a path. The output of one call is
valid input to the next, and nothing binary ever crosses the MCP boundary. Filenames carry a
microsecond-precision UTC timestamp and a slug of the prompt, so concurrent calls sharing a
prompt cannot overwrite each other.

**🛑 Errors you can act on.** A refusal comes back as an MCP tool error carrying the API's own
message, never as a success payload with an `error` key buried in it. An agent reading
`OpenAI rejected the request: ...` can fix its own call; an agent reading a successful result
that happens to contain an error string usually cannot.

## 🧨 The things that will bite you

Four of them, and none is a bug in this server. They are worth knowing before they cost you a
debugging session.

**Transparent backgrounds are gone.** gpt-image-2 does not do them. The API refuses
`background="transparent"` outright, so the parameter here accepts only `auto` and `opaque`
and the schema rejects anything else before a request is billed. This is a real regression
against the previous generation: if your pipeline cut out a subject on transparency, that
pipeline needs a mask or an external background remover now.

**A webp request used to come back as a PNG.** The API did that for a while, and a file named
`.webp` holding PNG bytes breaks whatever opens it next. Measured in August 2026, it no longer
does: a webp request returns genuine WEBP bytes and the file is saved as `.webp`. The server
still sniffs the magic bytes of what actually arrived and names the file after them, because a
regression upstream must never be able to produce a file whose extension lies about its own
contents. Code for it anyway: `output_format` in the result is authoritative, it describes the
bytes on disk, and it may differ from the `output_format` you asked for. Trust the result, not
the request.

**Refinement costs more per image.** A reasoning model drives `refine_image`, and you pay for
it on every turn including the first. For a single picture, `generate_image` is cheaper and
just as good. Refinement pays for itself from the second correction onward, when the
alternative is re-uploading an image and rewriting a prompt each time. Pick per task, not per
project.

**Sessions expire.** A `session_id` is an OpenAI response id and lasts about 30 days. After
that, or on an id that never existed, the tool fails with a message saying so. Recovery is
cheap because you still have the file: call `refine_image` with `image_paths` pointing at the
last saved image and no `session_id`, and a fresh session starts from that picture.

## 🤖 One model, deliberately

This server supports gpt-image-2 and nothing else. There is no `model` parameter on any tool.

That is not laziness, it is the state of the API. `dall-e-2` and `dall-e-3` were shut down on
2026-05-12. On 2026-06-02 OpenAI announced that `gpt-image-1.5`, `gpt-image-1-mini` and
`chatgpt-image-latest` retire on 2026-12-01, all of them migrating to gpt-image-2. A model
selector here would offer one live option and a list of dates. gpt-image-2 also currently
ranks first on the Artificial Analysis text-to-image leaderboard, so there is nothing to
trade away.

What you can pin is the snapshot. `GPT_IMAGE_MODEL=gpt-image-2-2026-04-21` freezes behaviour
on the release of 2026-04-21, which is what you want when a silent model update would change
output you have already shipped.

The chat model that steers `refine_image` is a separate decision under a separate variable,
`GPT_IMAGE_REFINE_MODEL`, because it is not an image model at all and cannot share a setting
with one.

## ⚙️ Configuration

Everything is environment variables, set in your MCP client's config. There is no config
file, and `config.py` is the only module that reads the environment, so this list is
complete. A `.env` in the working directory is read too.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | none | Standard OpenAI key, reused under its usual name so an existing setup works untouched. |
| `GPT_IMAGE_OUTPUT_DIR` | no | `./generated-images` | Where images are written. Created on first save. Relative paths resolve against the server's working directory, so an absolute path is safer. |
| `GPT_IMAGE_MODEL` | no | `gpt-image-2` | The image model. Set it to `gpt-image-2-2026-04-21` to pin the snapshot. |
| `GPT_IMAGE_REFINE_MODEL` | no | `chat-latest` | The mainline chat model that steers `refine_image`. The default alias never goes stale; pin `gpt-5.6-sol`, `gpt-5.6-terra` or `gpt-5.6-luna` to hold behaviour still or to trade cost against quality. |
| `GPT_IMAGE_TIMEOUT` | no | `300` | Seconds before `generate_image` or `edit_image` gives up. Complex prompts and 4K sizes sit near the top of that budget. |
| `GPT_IMAGE_REFINE_TIMEOUT` | no | `300` | The same, for `refine_image`, which is slower because it plans before it draws. |

Details, and how to choose the timeouts, in [docs/configuration.md](docs/configuration.md).

## 📚 Documentation

Full docs in [docs/](docs/). Start with
[getting-started.md](docs/getting-started.md), then
[tools.md](docs/tools.md) for every parameter of the three tools,
[refinement.md](docs/refinement.md) for the multi-turn workflow, and
[troubleshooting.md](docs/troubleshooting.md) when something comes back wrong.

## 📜 Licence

[FSL-1.1-MIT](LICENSE). Source available, not open source: read it, fork it, run it, build on
it and ship products with it, with one restriction, you may not use it to make a competing
product. Every release converts to plain MIT 2 years after it ships, automatically.
