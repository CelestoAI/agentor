# Parallel Search MCP

Connect Agentor to [Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp)
for web search and page excerpts without a Parallel API key. The example uses
Agentor's existing `MCPServer` with streamable HTTP and exposes
`parallel_web_search` and `parallel_web_fetch` to the agent. The prefix avoids
collisions with other search tools. Each connection sends an Agentor User-Agent
and uses a 30-second HTTP timeout.

From the repository root, run a search without an LLM or any API keys:

```bash
uv run python examples/parallel_search.py --tools-only "Agentor durable agent runs"
```

To also fetch a specific page:

```bash
uv run python examples/parallel_search.py --tools-only "Agentor durable agent runs" --fetch-url https://github.com/CelestoAI/agentor
```

For an agent that chooses searches and produces an answer with source URLs,
set `OPENAI_API_KEY` in your environment and run:

```bash
uv run python examples/parallel_search.py "What does Agentor support for durable runs?"
```

This mode selects `gpt-5-nano`, Agentor's current default; model inference is billed by
your model provider separately. Agentor opens and closes the MCP connection for
each run. The tools-only mode manages the connection with an async context
manager and prints the search/fetch excerpts directly.

The example sends no authorization header and does not read Parallel credentials.
Anonymous access is intended for exploration and light use, with server-managed
rate limits and search settings. It is not unlimited. Both modes reuse one
session ID across related search and fetch calls. Network, rate-limit and tool
errors propagate to the caller in tools-only mode. Agent mode uses Agentor's
existing tool failure budget.
