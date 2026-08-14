# Troubleshooting

Organised by what you observed, because that is what you have when something breaks. Each entry
says what the symptom means, what to check and in what order, and where to read further.

Several of these are properties of gpt-image-2 rather than mistakes in your call. Those entries
say so in their first lines, so you do not spend an hour looking for a bug that is a model
limitation.

Errors from this server arrive as MCP tool errors carrying a readable message. There is no
success payload with an error hidden inside it, so if your client reports a result, an image
really was written.

## background="transparent" is refused

**What you see.** Either a schema validation error from your MCP client, naming `background` and
listing `auto` and `opaque` as the permitted values, or, if something bypassed the schema,
`OpenAI rejected the request: ...` mentioning the background parameter.

**A model limitation, not a bug.** gpt-image-2 does not support transparent backgrounds. This is
a regression against the previous generation, where `background="transparent"` on a PNG or WEBP
gave you a cut-out subject. The API refuses it now, so `transparent` is deliberately absent from
the tool schema here: a client asking for it gets a local schema error instead of a billed round
trip that was always going to fail.

**What to do instead.**

1. Generate opaque, then cut out afterwards with a background remover outside this server. This
   is the only route that gives you a real alpha channel.
2. If the background is uniform and you control the prompt, ask for a flat single colour
   background you can key out later. Less reliable than a remover, but it needs no extra tooling.
3. If only part of an image needs replacing, use `edit_image` with a mask rather than reaching
   for transparency at all. That covers most of what people actually wanted transparency for.

**Read more.** [tools.md](tools.md), the section on backgrounds.

## The saved file has an extension I did not ask for

**What you see.** You called `generate_image(output_format="webp")` and the result reads:

```json
{ "path": ".../20260814_142233_051182_a_lighthouse_1.png", "output_format": "png" }
```

**Deliberate.** The API sometimes answers a webp request with PNG bytes. This server identifies
the image from its magic bytes and names the file after what actually arrived, rather than after
what was requested. The alternative is a file called `.webp` containing PNG data, which breaks
the next program that opens it and does so far away from the cause.

**What to check, in order.**

1. Read `output_format` from the result rather than assuming it matches your request. It always
   describes the bytes on disk.
2. Look at the path in the result rather than reconstructing one from the prompt and the format
   you asked for. Reconstructed paths are where this actually hurts.
3. If you need a guaranteed format, convert after the fact. Nothing in this server can force the
   API to honour the request.

**Read more.** [tools.md](tools.md), the results section.

## Session ... is unknown or expired

**What you see.**

```
Session resp_0a1b2c3d4e5f60718293a4b5c6d7e8f9 is unknown or expired. Sessions last about
30 days. Call refine_image without session_id to start a new one.
```

**What it means.** Refinement sessions are OpenAI response ids and they last about 30 days. The
id you passed is past that, or was never a real id. There is no way to revive one.

**What to check, in order.**

1. Whether the id is one this server returned. An id that an agent constructed from a pattern
   rather than copied is the most common cause, and it produces this error immediately.
2. Whether you passed the newest id. Every turn returns its own, and the last one is the head of
   the conversation.
3. How old the conversation is. Past a month, expect this.

**How to carry on.** You have not lost the work, only the conversation, because every turn wrote
a file. Start a fresh session from the last image:

```
refine_image(
  instruction="continue from this: warm up the light on the horizon",
  image_paths=["/home/you/images/20260814_143901_772104_the_boat_is_too_big_1.png"]
)
```

The next couple of instructions have to name what they refer to instead of pointing at it, then
the new session has its own memory.

**Read more.** [refinement.md](refinement.md), the session lifecycle.

## Invalid session_id, before anything is sent

**What you see.**

```
Invalid session_id 'sess_12345'. It must be an id returned by a previous refine_image call,
starting with 'resp_'. Omit it to start a new session.
```

**A local check.** The shape of the id is validated here, before a request goes out, because an
id that cannot possibly be an OpenAI response id is not worth a round trip. Real ids start with
`resp_` and are much longer than the prefix.

**What it usually is.** An agent inventing a plausible-looking id rather than reusing the one
from the previous result. Pass the exact string from the last `refine_image` response, or omit
the parameter entirely to start again.

## OpenAI refused the credentials

**What you see.**

```
OpenAI refused the credentials: <the API's message>. Check OPENAI_API_KEY and that the
organization has access to image models.
```

**What it means.** A 401 or a 403. The key is wrong, revoked, or belongs to an organisation
without access to image models. The second case surprises people, because the same key works
perfectly well for chat.

**What to check, in order.**

1. That the key reached the server. Environment variables set in your shell do not automatically
   reach a server your MCP client spawns: put the key in the client config's `env` block, or in a
   `.env` in the working directory the server actually starts in.
2. That the key is current. A rotated or revoked key gives the same 401 as a typo.
3. That the organisation can use image models. Try a `generate_image` call against a key you know
   has image access. If that works and yours does not, it is access, not configuration.
4. That you are not looking at a project key scoped to models that exclude gpt-image-2.

**Read more.** [configuration.md](configuration.md), where settings come from.

## Rate limited by OpenAI

**What you see.**

```
Rate limited by OpenAI: <the API's message>
```

**What it means.** You crossed a per-minute limit on requests or on tokens. Image models have
noticeably tighter limits than chat models on most tiers, and image calls are individually large,
so the ceiling arrives sooner than you would expect from experience with text.

**What to check, in order.**

1. Whether you are batching with several concurrent calls. Serialise them, or space them out.
2. Whether `n` is doing what you think. One call with `n=10` is one request producing ten
   images, and it is the friendlier shape here than ten calls with `n=1`.
3. Your organisation's tier and current limits, in the OpenAI dashboard. The message names the
   limit that was hit.

There is no retry loop in this server, on purpose: an automatic retry against a rate limit turns
one visible failure into a slow, invisible one. Wait, then call again.

## Invalid size, before any request

**What you see.** One of:

```
Invalid size '1500x900': both dimensions must be multiples of 16.
Invalid size '4096x2304': the maximum is 3840x2160.
Invalid size '2048x512': the aspect ratio must stay between 1:3 and 3:1.
Invalid size '1536 x 864'. Use 'auto', a preset, or WIDTHxHEIGHT such as '1536x864'.
```

**A local check, and that is the point.** These four rules are published by OpenAI, so the
server enforces them before the request leaves. A malformed size costs you a validation error
instead of a round trip you pay for and a refusal you then have to interpret.

**What to check, in order.**

1. Round both dimensions to the nearest multiple of 16. `1500x900` becomes `1504x896`.
2. Keep inside 3840 wide and 2160 high.
3. Keep the ratio between 1:3 and 3:1. A very wide banner has to be built at a legal ratio and
   cropped afterwards.
4. Write the value with no spaces and a lowercase `x`.

Note that only the documented rules are enforced here. Anything else is left to the API so its
own message reaches you rather than a guess made locally, which is why an exotic but legal size
can still be refused upstream. Sizes above 2560x1440 are experimental: legal, slower, and less
consistent.

**Read more.** [tools.md](tools.md), the sizes section.

## The model answered without producing an image

**What you see.**

```
The model answered without producing an image. Phrase the instruction as an explicit
request to draw or modify the picture.
```

**Only from `refine_image`.** A reasoning model drives that tool, and a reasoning model given
something that reads as a question will answer the question instead of drawing. No image call
happens, so there is nothing to save.

**What to check, in order.**

1. Whether the instruction is an imperative. "Warm the sky" draws. "Would this look better with
   a warmer sky?" gets you an opinion.
2. Whether the instruction is asking for something that is not a picture. "Describe what is
   wrong with the composition" is a reasonable request and a guaranteed failure of this tool.
3. Whether it is a refusal in disguise. If the instruction brushes against content policy, the
   model sometimes declines in prose rather than raising a policy error.

## OpenAI did not answer in time

**What you see.**

```
OpenAI did not answer in time: <the API's message>.
```

**What it means.** The call passed `GPT_IMAGE_TIMEOUT`, or `GPT_IMAGE_REFINE_TIMEOUT` for
`refine_image`. Both default to 300 seconds. gpt-image-2 plans before drawing and a complex
prompt at a large size can take a couple of minutes on its own.

**What to check, in order.**

1. The size. Anything above 2560x1440 is at the slow end by design. Try a preset and see whether
   the same prompt returns.
2. `n`. Ten images in one call take longer than one.
3. The timeout itself. Raise it if 4K sizes with long prompts are your normal workload.
4. Whether it happens twice on the same prompt. A repeated timeout is a prompt or size problem
   rather than a budget problem, and raising the number further just wastes more time per
   attempt.

**Read more.** [configuration.md](configuration.md), the timeouts section.

## Image file not found

**What you see.**

```
Image file not found: ~/pictures/banner.png
```

or one of its neighbours: an unsupported image type, a file over the 50 MB limit, a mask that is
not a PNG, or a mask over 4 MB.

**A local check.** Input paths are verified before the request goes out.

**What to check, in order.**

1. Tilde expansion. `~/pictures/banner.png` is a literal directory named `~` as far as this
   server is concerned. Pass the expanded absolute path.
2. Relative paths. They resolve against the server's working directory, which is your MCP
   client's, not your shell's. Absolute paths remove the question.
3. The extension. Inputs must be `.png`, `.jpg`, `.jpeg` or `.webp`. Masks must be `.png` with an
   alpha channel.
4. The size. Inputs cap at 50 MB each, masks at 4 MB.

The simplest way to get all of this right is to feed back the `path` a previous tool returned,
which is always absolute and always a supported format.

## The mask did nothing, or the edit ignored it

**What you see.** No error. The edit ran, and the masked region was not the region that changed.

**What it means.** Mask dimensions must match the first image in `image_paths`. That check
belongs to the API rather than to this server, because verifying it locally would mean decoding
the image, so a mismatch surfaces as a rejection or as an odd result rather than as a clean local
error.

**What to check, in order.**

1. That the mask is exactly the same pixel dimensions as the **first** image you passed, not as
   some other input.
2. That the mask really has an alpha channel. A PNG with no transparency marks nothing, and
   nothing about it looks wrong in a viewer.
3. Which way round it is. Transparent areas are repainted, opaque areas are kept.

## I cannot find the generated images

**What you see.** Calls succeed, results carry paths, and the folder you expected is empty.

**What it means.** `GPT_IMAGE_OUTPUT_DIR` defaults to `./generated-images`, which is relative to
the working directory of the server process. Your MCP client chooses that directory, and it is
rarely the one you are standing in.

**What to check, in order.**

1. The `path` field in the result. It is absolute, and it is where the file really is.
2. Set `GPT_IMAGE_OUTPUT_DIR` to an absolute path in your client config, then restart the client.
3. Remember that settings are read once per process, so a change to the variable needs a restart
   to take effect.

**Read more.** [configuration.md](configuration.md), where images go.

## Still stuck

The tools return the API's own message wherever there is one, so the text after the colon in
`OpenAI rejected the request:` is worth reading carefully before assuming the problem is here.
If a failure looks like a genuine bug in this server rather than a refusal from the API, open an
issue at [github.com/agelyhq/mcp-gpt-image/issues](https://github.com/agelyhq/mcp-gpt-image/issues)
with the tool name, the parameters and the exact message.
