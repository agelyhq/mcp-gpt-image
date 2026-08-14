# Getting started

From nothing to a generated image, then to the same image edited and refined. Fifteen minutes,
most of it waiting on the API.

## What you need

Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and an OpenAI API key belonging to an
organisation that has access to image models. A key that works for chat does not automatically
work here: image models are gated separately on some organisations, and the failure is a 401 or
a 403 rather than anything about images. Check the key first if you would rather not debug that
later.

## Install

The published package is `mcp-gpt-image` and the console script has the same name, so nothing
needs to be installed permanently:

```bash
uvx mcp-gpt-image --version
```

That downloads the package into a throwaway environment, prints the version and exits. If it
prints a version, the install story is over. Your MCP client will run the same command.

To work on the source instead:

```bash
git clone https://github.com/agelyhq/mcp-gpt-image.git
cd mcp-gpt-image
make install
cp .env.example .env    # then put your key in it
make run
```

`make run` starts the server on stdio. It will sit there reading its standard input and saying
nothing, which is correct: an MCP server over stdio has no console interface. Ctrl-C to stop it.

## Register it with a client

For Claude Code, one command:

```bash
claude mcp add gpt-image \
  -e OPENAI_API_KEY=sk-... \
  -e GPT_IMAGE_OUTPUT_DIR=/home/you/images \
  -- uvx mcp-gpt-image
```

For any other MCP client, the same thing as JSON:

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

Set `GPT_IMAGE_OUTPUT_DIR` to an absolute path. The default is `./generated-images`, relative to
whatever working directory your client happens to start the server in, and that directory is
rarely the one you think it is. An absolute path removes the question. The directory is created
on the first save, so it does not have to exist yet.

Restart the client, and it should list three tools: `generate_image`, `edit_image` and
`refine_image`.

## Your first image

Ask for something:

```
Generate a wide banner of a lighthouse in a storm, 1536x1024.
```

The agent calls `generate_image(prompt="a wide banner of a lighthouse in a storm",
size="1536x1024")`, and gets back a list with one entry:

```json
[
  {
    "path": "/home/you/images/20260814_142233_051182_a_wide_banner_of_a_lighthouse_in_a_1.png",
    "output_format": "png",
    "revised_prompt": null
  }
]
```

Open the file. The name is the UTC timestamp down to the microsecond, a slug of the prompt, and
the index within the call, which is what makes two simultaneous calls with the same prompt
impossible to collide. The path is absolute, and it is the only thing you ever have to pass
around: no image bytes enter the conversation, so handing this picture to the next tool is free.

The first call is a good moment to check the timeout. gpt-image-2 plans before it draws, and a
detailed prompt at a large size can take well over a minute. The default budget is 300 seconds.

## Edit it

`edit_image` takes local paths and one instruction. Composition is the same call as correction:
pass several images and let the prompt decide what each contributes.

```
Take that banner and put the logo from ~/brand/logo.png in the bottom right corner.
```

```
edit_image(
  prompt="place the logo in the bottom right corner, keeping it crisp",
  image_paths=[
    "/home/you/images/20260814_142233_051182_a_wide_banner_of_a_lighthouse_in_a_1.png",
    "/home/you/brand/logo.png"
  ]
)
```

The result has the same shape as `generate_image`: a list of `{path, output_format,
revised_prompt}`. Both inputs are processed at full fidelity, which is why the logo survives
legibly. There is no fidelity setting to raise, because gpt-image-2 has only the one mode.

## Refine it

When one instruction will not be the last one, start a session instead:

```
Start a refinement session on the banner: make the sea rougher.
```

```
refine_image(
  instruction="make the sea rougher",
  image_paths=["/home/you/images/20260814_142233_051182_a_wide_banner_of_a_lighthouse_in_a_1.png"]
)
```

This returns one object rather than a list, and it carries a session id:

```json
{
  "path": "/home/you/images/20260814_143010_774219_make_the_sea_rougher_1.png",
  "session_id": "resp_0a1b2c3d4e5f60718293a4b5c6d7e8f9",
  "output_format": "png",
  "revised_prompt": null
}
```

Keep that id. The next correction is one line, with no image attached and no prompt rewritten:

```
refine_image(
  instruction="darken the sky and add a small boat on the left",
  session_id="resp_0a1b2c3d4e5f60718293a4b5c6d7e8f9"
)
```

Every turn returns a session id. Use the newest one. The full lifecycle, the cost trade-off and
what to do when a session expires are in [refinement.md](refinement.md).

## Habits worth forming early

**Pass paths, never bytes.** The whole design rests on it. A path costs a handful of tokens and
is valid input to every tool here.

**Read `output_format` from the result.** Not from your request. The API sometimes answers a
webp request with PNG bytes, and this server names files after what actually arrived rather than
after what was asked. That is the deliberate behaviour, and
[troubleshooting.md](troubleshooting.md) explains why the opposite would be worse.

**Do not ask for a transparent background.** gpt-image-2 has none. `background` accepts `auto`
and `opaque` only, and the schema will reject anything else before OpenAI charges you for
finding out.

**Use `n` instead of looping.** One call with `n=5` returns five variations and five paths. Five
calls with `n=1` cost the same in images and more in round trips.

## Next

- [tools.md](tools.md), every parameter of the three tools
- [refinement.md](refinement.md), the multi-turn loop in detail
- [configuration.md](configuration.md), every environment variable
- [troubleshooting.md](troubleshooting.md), when something comes back wrong
