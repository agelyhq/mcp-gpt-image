# Tool reference

Three tools. `generate_image` draws from a prompt alone, `edit_image` changes or combines local
files in a single call, `refine_image` works on one image across several turns while the model
remembers what it drew.

Every tool returns file paths and never image bytes. A path returned by one tool is valid input
to another, which is how an image moves through a workflow without entering the conversation.

## Choosing between them

| You want to | Use | Why |
|---|---|---|
| Create a picture from a description | `generate_image` | Cheapest per image, and `n` gives you variations in one call. |
| Make one specific change to files you have | `edit_image` | One round trip, and a mask if the change is local to a region. |
| Merge several pictures into one | `edit_image` | Up to 16 inputs, the prompt decides what each contributes. |
| Correct the same picture repeatedly | `refine_image` | The session remembers, so turn two is an instruction rather than a prompt. |

The dividing line between `edit_image` and `refine_image` is the number of turns you expect, not
the difficulty of the change. One instruction: `edit_image`. Three or more: `refine_image`.
[refinement.md](refinement.md) works through the trade-off in full.

## generate_image

Draws one or more images from text and saves them.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `prompt` | string | up to 32,000 characters | required | What to draw. Detail helps: gpt-image-2 follows long, specific prompts better than short ones. |
| `size` | string | `auto`, a preset, or `WIDTHxHEIGHT` | `auto` | See [Sizes](#sizes) below. |
| `quality` | string | `auto`, `low`, `medium`, `high` | `auto` | Higher quality costs more and takes longer. `auto` lets the model decide from the prompt. |
| `output_format` | string | `png`, `jpeg`, `webp` | `png` | The format requested. What lands on disk can differ, see [Results](#results). |
| `output_compression` | integer | 0 to 100 | `100` | Only sent for `jpeg` and `webp`. Silently irrelevant for `png`, which is lossless. |
| `background` | string | `auto`, `opaque` | `auto` | `opaque` forces a filled background. **There is no `transparent`**, see below. |
| `moderation` | string | `auto`, `low` | `auto` | `low` relaxes the default filtering. Useful when legitimate prompts keep being refused. |
| `n` | integer | 1 to 10 | `1` | Variations drawn in one call. Each one is saved as its own file. |

Returns a **list** of results, one per image, in the order the API produced them.

## edit_image

Modifies local images, or composes several of them into one, and saves the result.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `prompt` | string | up to 32,000 characters | required | What to change, add, remove, or how to combine the inputs. |
| `image_paths` | list of strings | 1 to 16 paths | required | Local files, `.png` `.jpg` `.jpeg` `.webp`, each under 50 MB. Checked before the call. |
| `mask_path` | string or null | a PNG under 4 MB | `null` | Transparent areas mark what to repaint. Must match the dimensions of the first image. |
| `size` | string | `auto`, a preset, or `WIDTHxHEIGHT` | `auto` | See [Sizes](#sizes). |
| `quality` | string | `auto`, `low`, `medium`, `high` | `auto` | Same meaning as on `generate_image`. |
| `output_format` | string | `png`, `jpeg`, `webp` | `png` | The format requested, see [Results](#results). |
| `output_compression` | integer | 0 to 100 | `100` | Only sent for `jpeg` and `webp`. |
| `background` | string | `auto`, `opaque` | `auto` | No `transparent`, same as above. |
| `n` | integer | 1 to 10 | `1` | Variations produced in one call. |

Returns a **list** of results, same shape as `generate_image`.

There is no `moderation` parameter here, because the edit endpoint does not accept one. There is
also no `input_fidelity`: gpt-image-2 always processes input images at high fidelity, so faces,
logos and lettering survive an edit without anything to switch on. On the previous generation
that was a setting you had to remember, and forgetting it was the usual reason a logo came back
smudged.

Passing one image means "change this image". Passing several means "build one image out of
these", and the prompt is what says which contributes what: name them by their content ("put
the logo from the second image in the corner of the first"), because the model has no filenames
to reason about.

A mask is only worth it when the change is confined to a region and the rest must be untouched
pixel for pixel. It is an ordinary PNG with an alpha channel, where transparent means repaint
and opaque means keep. Dimensions must match the first input image, and that check belongs to
the API rather than to this server, because verifying it locally would mean decoding the image.

## refine_image

Refines an image over several turns, keeping the thread with the model.

| Parameter | Type | Allowed values | Default | Behaviour |
|---|---|---|---|---|
| `instruction` | string | up to 32,000 characters | required | What to draw, or what to change since the last turn. |
| `session_id` | string or null | an id from a previous call | `null` | Continues that session. Omit it to start a new one. Must start with `resp_`. |
| `image_paths` | list of strings or null | 1 to 16 paths | `null` | Local images to start the session from. **Ignored when `session_id` is given**, because the session already holds the image. |
| `quality` | string | `auto`, `low`, `medium`, `high` | `auto` | Only sent when it is not `auto`, so `auto` means "let the model decide" rather than a value on the wire. |

Returns a **single object**, not a list. There is no `n`: a conversation refines one image.

Turn one takes an `instruction` and optionally `image_paths`. Turn two and after take an
`instruction` and the `session_id` from the previous turn. Every turn returns a fresh
`session_id`, and it is the newest one you should carry forward. The full workflow is in
[refinement.md](refinement.md).

Framing and format are deliberately absent here. `size` and `output_format` belong to
`generate_image` and `edit_image`, where the API contract documents them; the image tool inside
the Responses API only documents `quality` as a configuration key, and this server does not send
parameters it cannot vouch for.

## Sizes

`generate_image` and `edit_image` both accept the same three shapes of value.

| Form | Examples | Notes |
|---|---|---|
| `auto` | `auto` | The model picks a size from the prompt. The default. |
| A preset | `1024x1024`, `1536x1024`, `1024x1536` | Square, landscape, portrait. Always accepted. |
| Any `WIDTHxHEIGHT` | `1536x864`, `2048x1152`, `3840x2160` | Subject to the four rules below. |

A custom size must satisfy all of:

- both dimensions are multiples of 16
- neither exceeds 3840 wide or 2160 high
- the aspect ratio stays between 1:3 and 3:1
- both parts parse as integers, so `1536 x 864` and `1536X864` are not accepted

These are checked in this server, before the request leaves, so a malformed size costs a
validation error rather than a billed round trip. The message names the rule you broke. Anything
not on that list is left to the API, so its own message reaches you rather than a guess made
here.

Anything above 2560x1440 is experimental at the API level: it works, it is slow, and the results
are less consistent than at the presets. Budget for it in `GPT_IMAGE_TIMEOUT`.

## Backgrounds, and the missing one

`background` takes `auto` or `opaque`. That is the whole list, and it is shorter than it used to
be: gpt-image-2 does not support transparent backgrounds and the API refuses
`background="transparent"`. The value is left out of the schema on purpose, so a client asking
for it gets a schema error immediately instead of a refusal from OpenAI after a round trip.

If you need a cut-out subject, the picture has to be produced opaque and separated afterwards,
either with a mask through `edit_image` or with a background remover outside this server. There
is no way to get an alpha channel out of this model.

## Results

`generate_image` and `edit_image` return a list of these. `refine_image` returns one, with an
extra field.

| Field | Type | Present on | Meaning |
|---|---|---|---|
| `path` | string | all three | Absolute path to the saved file. Valid input to any tool here. |
| `output_format` | string | all three | `png`, `jpeg` or `webp`: what the bytes on disk actually are. |
| `revised_prompt` | string or null | all three | The prompt the model rewrote for itself, when the API supplies one. Often `null`. |
| `session_id` | string | `refine_image` | The OpenAI response id to pass to the next turn. |

**`output_format` describes the file, not the request.** The API has been known to answer a webp
request with PNG bytes. Naming the file `.webp` anyway would produce a file that lies about its
own contents and breaks the next program that opens it, so the server reads the magic bytes of
what arrived and names the file after that. Read `output_format` from the result and you will
always be right; assume it matches your request and you will occasionally be wrong.

Files are written into `GPT_IMAGE_OUTPUT_DIR`, created on first use, and named
`{YYYYMMDD_HHMMSS_ffffff}_{prompt slug}_{index}.{ext}`. The timestamp is UTC with microsecond
precision and the slug is the first 40 characters of the prompt reduced to lowercase
alphanumerics, so two concurrent calls with the same prompt cannot overwrite each other.

## Errors

Failures arrive as MCP tool errors carrying a readable message, not as a successful result with
an error field inside it. That distinction matters for an agent: a tool error is something it
can react to, while a success payload containing an error string usually gets treated as an
image that exists.

| Message starts with | Cause | What to do |
|---|---|---|
| `Rate limited by OpenAI:` | Too many requests or too many tokens per minute. | Wait and retry. Lower `n` if you are batching. |
| `OpenAI rejected the request:` | Bad parameters, or a content policy refusal. | The rest of the message is the API's own words. |
| `OpenAI refused the credentials:` | 401 or 403. | Check `OPENAI_API_KEY` and image model access on the organisation. |
| `OpenAI did not answer in time:` | The call exceeded the timeout. | Raise `GPT_IMAGE_TIMEOUT`, or ask for a smaller size. |
| `Session ... is unknown or expired` | The `session_id` is dead or was never valid. | Start a new session from the last saved file. |
| `The model answered without producing an image` | The reasoning model replied in text instead of drawing. | Phrase the instruction as an explicit request to draw. |
| `Invalid size ...` | Local validation, before any request. | The message names the rule. See [Sizes](#sizes). |
| `Image file not found:` | A path in `image_paths` or `mask_path` does not exist. | Use the absolute paths the tools return. |

Every one of these is worked through, with the full symptom, in
[troubleshooting.md](troubleshooting.md).
