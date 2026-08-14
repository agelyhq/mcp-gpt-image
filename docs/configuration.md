# Configuration

Everything is configured through environment variables. There is no config file and no command
line option beyond `--version`, because an MCP server started by a client has nowhere to read
options from except its environment. `config.py` is the only module that touches the
environment, so the table below is the complete list.

## The variables

| Variable | Required | Default | What it does |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | none | Your OpenAI key. It keeps its standard name rather than a prefixed one, so a machine already set up for OpenAI needs nothing new. |
| `GPT_IMAGE_OUTPUT_DIR` | no | `./generated-images` | Directory where images are written. Created on the first save, parents included. |
| `GPT_IMAGE_MODEL` | no | `gpt-image-2` | The image model id. Only gpt-image-2 ids belong here. |
| `GPT_IMAGE_REFINE_MODEL` | no | `chat-latest` | The mainline chat model that drives `refine_image`. A chat model id, never an image model id. See [The refinement model](#the-refinement-model). |
| `GPT_IMAGE_TIMEOUT` | no | `300` | Seconds before an Images API call is abandoned. Covers `generate_image` and `edit_image`. |
| `GPT_IMAGE_REFINE_TIMEOUT` | no | `300` | The same, for the Responses API call behind `refine_image`. |

Names are matched case-insensitively, so `gpt_image_model` in a `.env` works as well as the
uppercase form. An empty value is treated as unset and falls back to the default, which means a
`.env` copied from the example and only half filled in still starts a working server. Unknown
variables are ignored rather than rejected, so the server tolerates sharing an environment with
everything else on the machine.

There is nothing to configure about the transport. The server speaks MCP over stdio and only
stdio: no host, no port, no path, no authentication of its own.

## Where settings come from

Two sources, in this order:

1. **The process environment.** For a server started by an MCP client, that is the `env` block of
   the client's config, plus whatever the client itself inherited.
2. **A `.env` file** in the server's working directory.

The process environment wins. The `.env` file is mainly a development convenience: clone the
repo, copy `.env.example` to `.env`, put your key in it, and `make run` works. In a client
config, set the variables in the `env` block instead, because you rarely control which directory
the client starts the server in.

Settings are read once per process and cached. Changing a variable means restarting the server,
which for most people means restarting the MCP client.

## Where images go

`GPT_IMAGE_OUTPUT_DIR` deserves more thought than it looks like it needs, because the default is
relative. `./generated-images` resolves against the server's working directory, and when an MCP
client spawns the server that directory is the client's, not yours. Images end up somewhere real
but surprising, and the paths in the results are the only reason you find them.

Set an absolute path:

```json
"env": {
  "OPENAI_API_KEY": "sk-...",
  "GPT_IMAGE_OUTPUT_DIR": "/home/you/images"
}
```

The directory is created on the first save. Nothing is ever cleaned up: every generation, every
edit and every refinement turn leaves a file, deliberately, because an intermediate version you
can go back to is worth more than a tidy folder. On a busy week that folder grows, and pruning
it is your job.

Files are named `{YYYYMMDD_HHMMSS_ffffff}_{prompt slug}_{index}.{ext}`, timestamped in UTC to
the microsecond. That precision is not decoration: two tools called concurrently with the same
prompt would otherwise write the same filename, and one image would silently replace the other.

## Floating id or pinned snapshot

`GPT_IMAGE_MODEL` accepts two useful values.

**`gpt-image-2`**, the default, follows whatever OpenAI currently serves under that name.
Improvements arrive without any change on your side. So do behaviour changes.

**`gpt-image-2-2026-04-21`** pins the snapshot released on that date. Output stays reproducible
against a fixed model, which is what you want when images have already shipped, when you are
comparing prompt variants and need the model held still, or when a regression has to be traced
to your prompt rather than to a silent update.

Pin it for anything published, leave it floating for exploratory work. Note that pinned
snapshots are eventually retired too, so a pin is a decision to revisit rather than a decision
made once.

Nothing else belongs in this variable. This server supports gpt-image-2 and nothing else: the
older image models were shut down or scheduled for retirement through 2026, and the tools expose
no `model` parameter for a caller to override per call. Setting an id from another family here
gets you an error from OpenAI, not a fallback.

`refine_image` is the exception, and it ignores this variable entirely. It runs on the Responses
API with the built-in image tool, and the model in front of that tool is a mainline chat model
rather than an image one. An image model cannot be the primary model of a Responses call, so
there is no version of this where the two share a setting. That model has its own variable,
below.

## The refinement model

`GPT_IMAGE_REFINE_MODEL` names the chat model that steers `refine_image`. It defaults to
`chat-latest`.

That default is chosen for one property: it is the only alias that never goes stale. A
generation alias has to be bumped by hand every time OpenAI ships a new line, and `gpt-5.6` is
not even listed in `/v1/models`, though it resolves to `gpt-5.6-sol` when you call it. Pointing
at the moving alias means a new mainline model arrives without an upgrade here. The price of
that is real, and it is why the variable exists: a moving alias can change behaviour without
warning, on a day you did not choose.

These values were verified against the live API in August 2026, and all of them accept the
built-in `image_generation` tool:

| Value | Notes |
|---|---|
| `chat-latest` | The default. Always the current mainline model, whichever that is. |
| `gpt-5.6` | The generation alias. Resolves to `gpt-5.6-sol`, and is absent from `/v1/models`. |
| `gpt-5.6-sol` | What `gpt-5.6` actually runs. Pin this to hold that behaviour still. |
| `gpt-5.6-terra` | The same line, a different point on the cost and quality curve. |
| `gpt-5.6-luna` | The cheap tier of the line. Worth trying when refinement turns dominate the bill. |

Pin one of them when the default drifts under you and you need yesterday's behaviour back, or
when you would rather pay less per turn than have the best available reasoning in front of the
drawing. Leave it alone otherwise. A pin is a decision to revisit, because the pinned ids retire
too. [refinement.md](refinement.md) covers when the trade is worth making.

Setting an image model id here does not work. The two models sit on different endpoints and
`GPT_IMAGE_MODEL` is the one that takes gpt-image-2 ids.

## Timeouts

Both default to 300 seconds, and both exist because gpt-image-2 is slow in a way that older
image models were not: it plans before it draws, and a complex prompt can take up to two
minutes. Sizes above 2560x1440 sit at the top of that range.

**`GPT_IMAGE_TIMEOUT`** covers `generate_image` and `edit_image`. Raise it if you routinely ask
for 4K sizes with long prompts. Lower it if you would rather fail fast than have an agent wait
five minutes on a call that is not coming back, but do not go below about 120 seconds or you
will be cancelling calls that would have succeeded.

**`GPT_IMAGE_REFINE_TIMEOUT`** covers `refine_image` alone. A refinement turn is a reasoning
model thinking, then an image model drawing, so it is slower than a plain generation of the same
picture. Keep it at or above `GPT_IMAGE_TIMEOUT`.

A timeout arrives as a tool error saying OpenAI did not answer in time. It is not a retry
signal on its own: if the same prompt times out twice, the size or the prompt is the problem
rather than the budget.

## A complete client config

```json
{
  "mcpServers": {
    "gpt-image": {
      "command": "uvx",
      "args": ["mcp-gpt-image"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "GPT_IMAGE_OUTPUT_DIR": "/home/you/images",
        "GPT_IMAGE_MODEL": "gpt-image-2-2026-04-21",
        "GPT_IMAGE_REFINE_MODEL": "gpt-5.6-sol",
        "GPT_IMAGE_TIMEOUT": "300",
        "GPT_IMAGE_REFINE_TIMEOUT": "420"
      }
    }
  }
}
```

Your key is in that file in plain text, and the file is usually in your home directory or in a
repository. Keep it out of version control, or point the value at a secret your client can
expand.

## Next

- [tools.md](tools.md), every parameter of the three tools
- [troubleshooting.md](troubleshooting.md), when a setting turns out to be the cause
