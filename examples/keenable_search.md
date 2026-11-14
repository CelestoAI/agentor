# Keenable Search MCP

Connect Agentor to [Keenable](https://keenable.ai) web search and page fetch
through its hosted MCP server. No API key is needed: without `KEENABLE_API_KEY`
the example uses the keyless public endpoint (`https://api.keenable.ai/mcp-public`).
It uses Agentor's existing `MCPServer` with streamable HTTP and exposes
`keenable_search_web_pages` and `keenable_fetch_page_content` to the agent. The
prefix avoids collisions with other search tools. Each connection sends an
Agentor User-Agent and uses a 30-second HTTP timeout.

From the repository root, run a search without an LLM or any API keys:

```bash
uv run python examples/keenable_search.py --tools-only "Agentor durable agent runs"
```

To also fetch a specific page:

```bash
uv run python examples/keenable_search.py --tools-only "Agentor durable agent runs" --fetch-url https://github.com/CelestoAI/agentor
```

For an agent that chooses searches and produces an answer with source URLs,
set `OPENAI_API_KEY` in your environment and run:

```bash
uv run python examples/keenable_search.py "What does Agentor support for durable runs?"
```

This mode selects `gpt-5-nano`, Agentor's current default; model inference is
billed by your model provider separately. Agentor opens and closes the MCP
connection for each run. The tools-only mode manages the connection with an
async context manager and prints the search/fetch results directly.

Keyless access is rate-limited and meant for exploration and light use. For
higher limits, set `KEENABLE_API_KEY`; the example then switches to
`https://api.keenable.ai/mcp` and sends the key as an `X-API-Key` header. It reads
no other credentials. Both modes reuse one session ID across related search
and fetch calls. Network, rate-limit and tool errors propagate to the caller in
tools-only mode. Agent mode uses Agentor's existing tool failure budget.
