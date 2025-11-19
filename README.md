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

Agentor is an open-source framework that makes it easy to build Agentic system with secure integrations across email, calendars, CRMs, and more.

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

### Build and Deploy an Agent

Build an Agent, connect external tools or MCP Server and serve as an API in just few lines of code:

```python
from agentor import Agentor, function_tool


@function_tool
def get_weather(city: str):
    """Get the weather of city"""
    return f"Weather in {city} is sunny"


agent = Agentor(
    name="Weather Agent",
    model="gpt-5-mini",  # Use any LLM provider - gemini/gemini/gemini-2.5-pro or anthropic/claude-3.5
    tools=[get_weather],  # Bring your own tool, or use Celesto ToolHub
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

## MCP Hub

Integrating multiple MCP servers usually means maintaining OAuth flows, tracking version drift, and wiring up streaming support before your agent can run.

Enable Agentor’s managed MCP Hub. Connectors arrive pre-authenticated, version-locked, and streaming-ready, while the hub takes care of discovery, retries, and lifecycle management.

```python
import asyncio, os
from agentor import Agentor, CelestoMCPHub


async def main() -> None:
    async with CelestoMCPHub() as hub:
        agent = Agentor(
            name="Weather Agent",
            model="gpt-5-mini",
            tools=[hub],  # Auto-registers 10+ managed connectors
        )
        result = await agent.arun("What is the weather in London?")
        print(result)


asyncio.run(main())
```

## LiteMCP - Build a custom MCP Server

Lightweight [Model Context Protocol](https://modelcontextprotocol.io) server with FastAPI-like decorators:

```python
from agentor.mcp import LiteMCP

app = LiteMCP(name="my-server", version="1.0.0")


@app.tool(description="Get weather")
def get_weather(location: str) -> str:
    return f"Weather in {location}: Sunny, 72°F"


if __name__ == "__main__":
    app.run()  # or: uvicorn server:app
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

The A2A Protocol defines standard specifications for agent communication and message formatting, enabling seamless interoperability between different AI agents. Agentor provides built-in A2A support, making it effortless to create agents that can discover, communicate, and collaborate with other A2A-compatible agents.

**Key Features:**

- **Standard Communication**: JSON-RPC based messaging with support for both streaming and non-streaming responses
- **Agent Discovery**: Automatic agent card generation at `/.well-known/agent-card.json` describing agent capabilities, skills, and endpoints
- **Rich Interactions**: Built-in support for tasks, status updates, and artifact sharing between agents

**Quick Example:**

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
