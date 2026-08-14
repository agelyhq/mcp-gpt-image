# Multi-turn refinement

`generate_image` and `edit_image` are stateless. Each call is a fresh request with no memory of
the last one, which is fine for a single picture and painful for the tenth correction: you end
up re-uploading the image and rewriting the whole prompt every time, and the model still has no
idea what it drew before.

`refine_image` is the answer to that. It holds a conversation with the model about one image, so
turn one is a description and turn two is "make the sky darker".

## How it works

`generate_image` and `edit_image` go through the Images API, which forgets everything between
calls. `refine_image` goes through the Responses API instead, using OpenAI's built-in
`image_generation` tool, driven by the mainline model `gpt-5.6`. An image model cannot be the
primary model of a Responses call, so a reasoning model sits in front and decides what to draw.

That is where the memory comes from. The Responses API keeps the conversation on OpenAI's side
and hands you an id for it. Passing that id on the next call continues the same thread: the
model still has the image, the instructions that shaped it, and its own reasoning about both.
The instruction alone travels over the wire, and nothing is re-uploaded.

It is also where the cost comes from. See [What it costs](#what-it-costs).

## The session lifecycle

**Turn one starts a session.** Call `refine_image` with an `instruction` and no `session_id`.
Optionally pass `image_paths` to start from pictures you already have; leave them out and the
model draws the first image from the instruction alone.

**Every turn returns a session id.** It looks like `resp_0a1b2c3d...`. It is an OpenAI response
id, not something this server invents.

**Later turns pass the newest id.** Not the first one. Each turn produces its own id and that is
the head of the conversation; passing an older id branches from an older state, which is
occasionally useful and usually a mistake.

**`image_paths` is ignored when `session_id` is given.** The session already holds the image,
so sending it again would be paying twice for the same picture. The parameter is not an error
in that position, it simply has no effect.

**Sessions last about 30 days.** After that the id is gone and the tool says so. Recovery is
cheap, see [When a session expires](#when-a-session-expires).

The id shape is checked locally before any request: an id that does not start with `resp_`, or
is too short to be one, is rejected with a message telling you to omit it and start fresh. That
catches the common agent failure of inventing a plausible-looking id.

## A worked example

Start from nothing and get to a finished banner in four turns.

**Turn 1.** Draw the first version.

```
refine_image(
  instruction="A wide cinematic banner: a lighthouse on a rocky headland at dusk, "
              "heavy storm clouds, waves breaking on the rocks, muted blue palette"
)
```

```json
{
  "path": "/home/you/images/20260814_142233_051182_a_wide_cinematic_banner_a_lighthous_1.png",
  "session_id": "resp_0a1b2c3d4e5f60718293a4b5c6d7e8f9",
  "output_format": "png",
  "revised_prompt": null
}
```

**Turn 2.** Look at it, then say what is wrong. Nothing about the lighthouse, the palette or the
storm needs repeating.

```
refine_image(
  instruction="make the sea rougher and the waves higher",
  session_id="resp_0a1b2c3d4e5f60718293a4b5c6d7e8f9"
)
```

```json
{
  "path": "/home/you/images/20260814_142811_339045_make_the_sea_rougher_and_the_waves_1.png",
  "session_id": "resp_1b2c3d4e5f60718293a4b5c6d7e8f9a0",
  "output_format": "png",
  "revised_prompt": null
}
```

**Turn 3.** Carry the new id forward.

```
refine_image(
  instruction="darken the sky and put a small fishing boat on the left, far out",
  session_id="resp_1b2c3d4e5f60718293a4b5c6d7e8f9a0"
)
```

**Turn 4.** Corrections can refer to what you just asked for, which is the part a stateless API
cannot do at all.

```
refine_image(
  instruction="the boat is too big, make it half that size",
  session_id="resp_2c3d4e5f60718293a4b5c6d7e8f9a0b1"
)
```

"the boat" and "half that size" only mean something because the model remembers the boat it
drew. Through `edit_image` the same request would be a full description of the scene plus a
description of the boat, sent with the image, every single turn.

Four files are on disk at the end, one per turn, so any intermediate version is still there if
turn 4 went the wrong way.

## When it beats edit_image

The dividing line is the number of turns you expect, not the difficulty of the change.

**Use `edit_image`** for a single instruction on files you have: add a logo, swap a background,
merge three product shots, repaint a masked region. One round trip, no session to carry, and no
reasoning model in the price. If you know what the final image should be and can say it once,
this is the cheaper tool.

**Use `refine_image`** when you will be looking at the result and reacting to it. Iterating on a
composition, tuning a mood, fixing something you cannot name until you see it. The first turn is
more expensive than the `edit_image` equivalent, and by the third correction the arithmetic has
gone the other way, because you are sending an instruction rather than an image plus a prompt.

**Use `edit_image` anyway** when you need a specific `size` or `output_format`, or a mask, or
several variations from `n`. `refine_image` has none of those. It takes an instruction, an
optional starting image and `quality`, and that is the entire surface.

A common shape that works well: `generate_image` with `n=4` to get options cheaply, pick one,
then `refine_image` from that file to polish it.

## What it costs

More than `generate_image`, on every turn including the first. There is a reasoning model in
front of the drawing, and you pay for its tokens as well as for the image.

It pays off from the second turn on, and the reason is what stops travelling. Through
`edit_image`, correction number three sends the image again and the whole scene description
again. Through `refine_image` it sends one sentence. The saving grows with the length of the
conversation and with the size of the image, which is exactly when the manual loop hurts most.

For a single picture, `generate_image` is cheaper and just as good. Decide per task rather than
per project, and do not route everything through refinement because it is the newest tool here.

`quality` is worth setting when you are iterating hard. `quality="low"` on exploratory turns and
one final turn at `high` costs a fraction of running everything at `high`, and the composition
decisions you are making early do not need the pixels.

## When a session expires

You will see:

```
Session resp_0a1b... is unknown or expired. Sessions last about 30 days.
Call refine_image without session_id to start a new one.
```

It arrives as a tool error, and it means exactly what it says. There is no way to revive a dead
id, and there is no need: you still have every image the session produced, because each turn
wrote a file to disk.

Start again from the last one:

```
refine_image(
  instruction="continue from this: warm up the light on the horizon",
  image_paths=["/home/you/images/20260814_143901_772104_the_boat_is_too_big_make_it_half_th_1.png"]
)
```

The new session begins with that picture in hand. What is lost is the conversation, not the
work: the model no longer knows about the boat you shrank, so the next few instructions have to
name what they refer to instead of pointing at it. After a turn or two the new session has its
own memory and you are back to one-line corrections.

The same recovery applies to an id that was never valid, which is what a hallucinated session id
looks like from the server's side.

## The other failure worth knowing

Occasionally the reasoning model answers in text instead of drawing anything, and the tool fails
with:

```
The model answered without producing an image. Phrase the instruction as an explicit
request to draw or modify the picture.
```

This is almost always an instruction that reads as a question. "Would this look better with a
warmer sky?" invites an opinion, and the model gives one. "Warm the sky" produces an image. Say
what to change, in the imperative, and the tool call reliably draws.

## Next

- [tools.md](tools.md), the exact parameters of all three tools
- [troubleshooting.md](troubleshooting.md), organised by symptom
- [configuration.md](configuration.md), including `GPT_IMAGE_REFINE_TIMEOUT`
