<p align="center">
  <picture>
    <img src="https://raw.githubusercontent.com/CelestoAI/agentor/main/assets/CelestoAI.png" alt="project logo" width="500px"/>
  </picture>
</p>

<div align="center">
  
[![PyPI version](https://img.shields.io/pypi/v/agentor.svg?color=brightgreen&label=PyPI&style=flat)](https://pypi.org/project/agentor/)
[![Tests](https://github.com/CelestoAI/agentor/actions/workflows/test.yml/badge.svg)](https://github.com/CelestoAI/agentor/actions/workflows/test.yml)
![PyPI - Downloads](https://img.shields.io/pypi/dm/agentor)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-yellow?style=flat)](https://opensource.org/licenses/Apache-2.0)
<a href="https://discord.gg/KNb5UkrAmm">
    <img src="https://img.shields.io/static/v1?label=Chat%20on&message=Discord&color=blue&logo=Discord&style=flat-square" alt="Discord">
</a>

</div>

<p align="center">
  Fastest way to build and deploy long-running AI agents—with durability, observability, and security.
</p>
<p align="center">
  <a href="https://docs.celesto.ai">Docs</a> |
  <a href="https://github.com/celestoai/agentor/tree/main/docs/examples">Examples</a>
</p>


## Features

|        Feature            |            Description                   |         Docs
|---------------------------|------------------------------------------|-----------------------|
|   🚀 MCP & tool security  | The only **full FastAPI compatible** MCP Server with decorator API | [Link](https://docs.celesto.ai/agentor/tools/LiteMCP)
|   🦾 Agent-to-agent       | Multi-agent communication                | [Link](https://docs.celesto.ai/agentor/agent-to-agent)
|   ☁️ Deployment           | Fast serverless deployment               | [Link](https://celesto.ai)
|   📊 Observability        | Agent tracing and monitoring             | [Link](https://celesto.ai)
|   🔍 Tool Search API      | Reduced tool context bloat               | [Link](https://docs.celesto.ai/agentor/tools/tool-search)


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
from agentor.tools import GetWeatherTool
from agentor import Agentor

agent = Agentor(
    name="Weather Agent",
    model="gpt-5-mini",  # Use any LLM provider - gemini/gemini-2.5-pro or anthropic/claude-3.5
    tools=[GetWeatherTool()]
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

Celesto AI provides a developer-first platform for deployment of Agents, MCP Servers, any LLM application.

To deploy using Celesto, run:

```bash
celesto deploy
```

Once deployed, your agent will be accessible via a REST endpoint, for example:

```bash
https://api.celesto.ai/deploy/apps/<app-name>
```

## Agent Skills

Skills are folders of instructions, scripts, and resources that Claude loads dynamically to improve performance on specialized tasks.

Agent Skills help agents pull just the right context from simple Markdown files. The agent first sees only a skill’s name and short description. When the task matches, it loads the rest of `SKILL.md`, follows the steps, and can call a shell environment to run the commands the skill points to.

- **Starts light**: discover skills by name/description only
- **Loads on demand**: pull full instructions from `SKILL.md` when relevant
- **Executes safely**: run skill-driven commands in an isolated shell

Skill layout example:

```
example-skill/
├── SKILL.md        # required instructions + metadata
├── scripts/        # optional helpers the agent can call
├── assets/         # optional templates/resources
└── references/     # optional docs or checklists
```

Using a skill to create a GIF:

```python
from agentor.tools import ShellTool
from agentor import Agentor

agent = Agentor(
    name="Assistant",
    model="gemini/gemini-3-flash-preview",
    instructions="Your job is to create GIFs. Lean on the shell tool and any available skills.",
    skills=[".skills/slack-gif-creator"],
    tools=[ShellTool()],
)

async for chunk in await agent.chat("produce a cat gif", stream=True):
    print(chunk)
```

## Create an Agent from Markdown

Bootstrap an Agent directly from a markdown file with metadata for name, tools, model, and temperature:

```markdown
---
name: WeatherBot
tools: [get_weather]
model: gpt-4o-mini
temperature: 0.3
---
You are a concise weather assistant.
```

Load it with:

```python
from agentor import Agentor

agent = Agentor.from_md("agent.md")
result = agent.run("Weather in Paris?")
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
