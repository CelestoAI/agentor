<p align="center">
  <img src="https://raw.githubusercontent.com/CelestoAI/agentor/main/assets/CelestoAI.png" alt="banner" width="500px"/>
</p>
<p align="center">
  Fastest way to build, prototype and deploy AI Agents with tools <mark><i>securely</i></mark>
</p>
<p align="center">
  <a href="https://docs.celesto.ai">Docs</a> |
  <a href="https://github.com/celestoai/agentor/tree/main/docs/examples">Examples</a>
</p>

[![💻 Try Celesto AI](https://img.shields.io/badge/%F0%9F%92%BB_Try_CelestoAI-Click_Here-ff6b2c?style=flat)](https://celesto.ai)
[![PyPI version](https://img.shields.io/pypi/v/agentor.svg?color=brightgreen&label=PyPI&style=flat)](https://pypi.org/project/agentor/)
[![Tests](https://github.com/CelestoAI/agentor/actions/workflows/test.yml/badge.svg)](https://github.com/CelestoAI/agentor/actions/workflows/test.yml)
![PyPI - Downloads](https://img.shields.io/pypi/dm/agentor)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-yellow?style=flat)](https://opensource.org/licenses/Apache-2.0)
[![Discord](https://img.shields.io/badge/Join%20Us%20on%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KNb5UkrAmm)

## Agentor

Agentor is an open-source framework that makes it easy to build Agentic systems with secure integrations across email, calendars, CRMs, and more.

It lets you connect LLMs to tools — like email, calendar, CRMs, or any data stack.

## Features

| Feature | Description |
|-----------------------------------------------|-----------------------------------------------|
| ✅ MCP Hub | Ready-to-use MCP Servers and Agents |
| 🚀 LiteMCP | The only **full FastAPI compatible** MCP Server with decorator API |
| 🦾 [A2A Protocol](https://a2a-protocol.org/latest/topics/what-is-a2a/) | [Docs](https://docs.celesto.ai/agentor/agent-to-agent) |
| ☁️ [Fast Agent deployment](https://github.com/CelestoAI/agentor/tree/main/examples/agent-server) | `celesto deploy` |
| 🔐 Secure integrations | Email, calendar, CRMs, and more |

## 🚅 Quick Start

### Installation

The recommended method of installing `agentor` is with pip from PyPI.

```bash
pip install agentor
```

<details>
  <summary>More ways...</summary>

You can also install the latest bleeding edge version (could be unstable) of `agentor`, should you feel motivated enough, as follows:

```bash
pip install git+https://github.com/celestoai/agentor@main
```

</details>

## Build and Deploy an Agent

Build an Agent, connect external tools or MCP Server and serve as an API in just a few lines of code:

```python
from agentor.tools import WeatherAPI
from agentor import Agentor

agent = Agentor(
    name="Weather Agent",
    model="gpt-5-mini",  # Use any LLM provider - gemini/gemini-2.5-pro or anthropic/claude-3.5
    tools=[WeatherAPI()]
)
result = agent.run("What is the weather in London?")  # Run the Agent
print(result)

# Serve Agent with a single line of code
agent.serve()
```

Run the following command to query the Agent server:

```bash
curl -X 'POST' \
  'http://localhost:8000/chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "What is the weather in London?"
}'
```

This agent can be deployed to any cloud environment. Celesto AI also offers a platform optimized for serverless agent hosting.

To deploy using Celesto, run:

```bash
celesto deploy
```

Once deployed, your agent will be accessible via a REST endpoint, for example:

```bash
https://api.celesto.ai/deploy/apps/<app-name>
```

## Build a custom MCP Server with LiteMCP

Agentor enables you to build a custom [MCP Server](https://modelcontextprotocol.io) using LiteMCP. You can run it inside a FastAPI application or as a standalone MCP server.

```python
from agentor.mcp import LiteMCP, get_token

mcp = LiteMCP(name="my-server", version="1.0.0")

@mcp.tool(description="Get weather for a given location")
def get_weather(location: str) -> str:

    # *********** Control authentication ***********
    token = get_token()
    if token != "SOME_SECRET":
        return "Not authorized"

    return f"Weather in {location}: Sunny, 72°F"

mcp.serve()
```

### LiteMCP vs FastMCP

**Key Difference:** LiteMCP is a native ASGI app that integrates directly with FastAPI using standard patterns. FastMCP requires mounting as a sub-application, diverging from standard FastAPI primitives.

| Feature | LiteMCP | FastMCP |
|---------|---------|---------|
| Integration | Native ASGI | Requires mounting |
| FastAPI Patterns | ✅ Standard | ⚠️ Diverges |
| Built-in CORS | ✅ | ❌ |
| Custom Methods | ✅ Full | ⚠️ Limited |
| With Existing Backend | ✅ Easy | ⚠️ Complex |

📖 [Learn more](https://docs.celesto.ai/agentor/tools/LiteMCP)

## Agent-to-Agent (A2A) Protocol

The A2A Protocol defines standard specifications for agent communication and message formatting, enabling seamless interoperability between different AI agents.

**Key Features:**
- **Standard Communication**: JSON-RPC based messaging with support for both streaming and non-streaming responses
- **Agent Discovery**: Automatic agent card generation at `/.well-known/agent-card.json` describing agent capabilities, skills, and endpoints
- **Rich Interactions**: Built-in support for tasks, status updates, and artifact sharing between agents


Agentor makes it easy to serve any agent as an A2A protocol.

```python
from agentor import Agentor

agent = Agentor(
    name="Weather Agent",
    model="gpt-5-mini",
    tools=["get_weather"],
)

# Serve agent with A2A protocol enabled automatically
agent.serve(port=8000)
# Agent card available at: http://localhost:8000/.well-known/agent-card.json
```

Any agent served with `agent.serve()` automatically becomes A2A-compatible with standardized endpoints for message sending, streaming, and task management.

📖 [Learn more](https://docs.celesto.ai/agentor/agent-to-agent)

## 🤝 Contributing

We'd love your help making Agentor even better! Please read our [Contributing Guidelines](.github/CONTRIBUTING.md) and [Code of Conduct](.github/CODE_OF_CONDUCT.md).

## 📄 License

Apache 2.0 License - see [LICENSE](LICENSE) for details.
