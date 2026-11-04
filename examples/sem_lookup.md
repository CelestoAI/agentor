# Repository lookup with Sem

An optional example using Agentor's existing `MCPServer` to locate source entities
through [Sem](https://github.com/Ataraxy-Labs/sem). It performs no model call and
requires no model credentials. Install Sem separately, then from a terminal:

```bash
export SEM_REPO=/absolute/path/to/git-checkout
export SEM_MCP_HTTP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
SEM_LOCAL=1 SEM_NO_NETWORK=1 SEM_NO_TELEMETRY=1 sem mcp --http 127.0.0.1:8787
```

In another terminal, set `SEM_MCP_HTTP_TOKEN` to that **same** token through your
secret manager/environment (do not generate another token). From the Agentor clone:

```bash
uv run python examples/sem_lookup.py parse_config
```

The client and server must share a network namespace: loopback in a separate
container refers to that container. The fixed local URL avoids accidentally
sending the token to another host; the client also ignores environment proxy settings. Stop the Sem process to disconnect.

This uses Sem's read-only HTTP discovery surface, not Weave editing or Sem's
stdio command-running tools. Sem can create local indexes; its local controls
are not an OS sandbox. Returned source is printed. If you connect this server
to an Agentor agent, that source can reach its model provider and stored run
history; choose repositories and providers accordingly. No defaults are changed.
