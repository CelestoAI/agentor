# deed.page MCP

Connect Agentor to [deed.page](https://deed.page), a keyless MCP server that
publishes HTML to a public `*.deed.page` URL. The example uses Agentor's
existing `MCPServer` with streamable HTTP and the `deed_page_` tool prefix, so
the publish tool appears as `deed_page_publish_site`. Each connection sends an
Agentor User-Agent and uses a 30-second HTTP timeout.

From the repository root, publish a sample page without an LLM or any API keys:

```bash
uv run python examples/deed_page.py --tools-only
```

To publish your own HTML file instead:

```bash
uv run python examples/deed_page.py --tools-only --file report.html
```

The example passes `ttl_seconds=3600`, so the page expires after an hour. Use
`--ttl 0` to keep it. The result includes the page `url` and, on a first
anonymous publish, a `token` that is shown only once. Keep that token to update
or delete the page (for example with the `delete_site` tool); without it the
page cannot be changed.

For an agent that writes the page and publishes it, set `OPENAI_API_KEY` in
your environment and run:

```bash
uv run python examples/deed_page.py "A one-page summary of Agentor's durable runs"
```

This mode selects `gpt-5-nano`; model inference is billed by your model
provider separately. The server exposes more tools than publishing, and the
instructions tell the agent to call only `deed_page_publish_site`.

Published pages are public. Do not publish secrets or private data. The
example sends no authorization header. Free pages carry a small deed.page
badge, and the server applies its own size and rate limits. Network,
rate-limit and tool errors propagate to the caller in tools-only mode.
