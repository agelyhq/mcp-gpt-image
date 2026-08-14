# mcp-gpt-image documentation

The [project README](../README.md) says what this server is and why it exists. These pages say
how to drive it.

## The set

**[getting-started.md](getting-started.md)** takes you from an empty machine to a file on disk:
install, key, client config, a first generation, then the same image edited and refined. Read
it first. Everything else assumes you have seen one image come out.

**[tools.md](tools.md)** is the reference for `generate_image`, `edit_image` and
`refine_image`: every parameter with its type, its allowed values, its default and what it
actually does, plus the exact shape of what comes back. Open it when you know what you want and
need the signature.

**[refinement.md](refinement.md)** covers the part that has no equivalent in a plain image API:
sessions, the multi-turn loop, what a turn costs, when `refine_image` beats `edit_image` and
when it does not, and how to carry on after a session has expired.

**[configuration.md](configuration.md)** lists every environment variable, explains how
settings are loaded and in which order, and helps you choose between the floating model id and
the pinned snapshot. It also says what the two timeouts are actually protecting you from.

**[troubleshooting.md](troubleshooting.md)** is organised by symptom rather than by cause,
because the symptom is what you have when something breaks. A refused transparent background, a
file with the wrong extension, an expired session, a 401, a rate limit, a size this server
rejects before OpenAI sees it, a model that answers without drawing anything.

## When something goes wrong

Go to [troubleshooting.md](troubleshooting.md) first. Most failures here are one of a small
number of known ones, and several of them are properties of gpt-image-2 rather than mistakes in
your call, so the fix is to change the approach rather than to retry.

## What is not here

There is no deployment guide, because there is nothing to deploy: the server speaks MCP over
stdio and your client starts it. There is no HTTP mode, no container image and no port. If you
were looking for one of those, [the README](../README.md) explains the choice.
