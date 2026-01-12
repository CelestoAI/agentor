# Agentor Documentation

<p align="center">
  <img src="https://raw.githubusercontent.com/CelestoAI/agentor/main/assets/CelestoAI.png" alt="banner" width="500px"/>
</p>

Agentor is an open-source framework that makes it easy to build Agentic systems with secure integrations across email, calendars, CRMs, and more.

It lets you connect LLMs to tools — like email, calendar, CRMs, or any data stack.

## Features

| Feature | Description | Docs
|---------------------------|------------------------------------------|-----------------------|
| 🚀 LiteMCP | The only **full FastAPI compatible** MCP Server with decorator API | [Link](https://docs.celesto.ai/agentor/tools/LiteMCP)
| 🦾 A2A Protocol | Multi-agent communication | [Link](https://docs.celesto.ai/agentor/agent-to-agent)
| ☁️ Fast Agent deployment| One click (serverless) deployment | [Link](https://celesto.ai)
| 🔐 Secure integrations | Multi-tenancy and fine-grained authorization | [Link](https://docs.celesto.ai/agentor/tools/auth)
| 🔍 Tool Search API | Reduced tool context bloat | [Link](https://docs.celesto.ai/agentor/tools/tool-search)

## Quick Start

### Installation

The recommended method of installing `agentor` is with pip from PyPI.

```bash
pip install agentor
```

### Basic Usage

```python
from agentor import Agentor

# Create an agent
agent = Agentor(
    name="My Agent", model="gpt-4", instructions="You are a helpful assistant"
)

# Run the agent
response = agent.run("Hello, how are you?")
print(response)
```

## API Reference

Browse the [API Reference](api/index.md) to explore the complete documentation of all modules, classes, and functions in Agentor.

## Resources

- [GitHub Repository](https://github.com/CelestoAI/agentor)
- [Examples](https://github.com/celestoai/agentor/tree/main/docs/examples)
- [Discord Community](https://discord.gg/KNb5UkrAmm)

## License

Agentor is released under the Apache 2.0 License.
