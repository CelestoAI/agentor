# Agentor

## Project Overview

Agentor is an open-source framework for building AI agents with secure integrations across email, calendars, CRMs, and more. It connects LLMs to tools and services, and speaks both the Model Context Protocol (MCP) and Agent-to-Agent (A2A) protocols.

Since v0.1.0 it runs on its own agent engine; the `openai-agents` dependency is gone. See [`docs/dev/MIGRATION_PLAN.md`](docs/dev/MIGRATION_PLAN.md) for why.

**Key Features:**

- An agent loop the project owns end to end, emitting a typed event stream
- Durable runs: the event stream is persisted, so a run resumes after a crash
- Any OpenAI-compatible provider via `base_url`, with litellm as the escape hatch
- LiteMCP - FastAPI-compatible MCP server with decorator API
- A2A Protocol support for agent interoperability
- Tool registry and extensible tool system

## Repository Structure

```text
agentor/
├── src/agentor/           # Main package source code
│   ├── core/              # Agentor, the user-facing agent class
│   ├── engine/            # The agent loop: events, tools, models, store, tracing, mcp
│   ├── mcp/               # LiteMCP server, API router, proxy
│   ├── tools/             # Tool registry and implementations
│   ├── durable/           # Deprecation shim; durability moved into engine/store.py
│   ├── a2a.py             # Agent-to-Agent protocol
│   ├── skills.py          # Agent Skills loading
│   └── tool_search.py     # Tool Search API
├── tests/                 # Test suite
├── examples/              # Usage examples
├── docs/dev/              # Design and migration records
├── .github/               # GitHub configuration and workflows
└── pyproject.toml         # Project metadata and dependencies
```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager

### Installation

1. Clone the repository:

```bash
git clone https://github.com/CelestoAI/agentor.git
cd agentor
```

2. Install dependencies using uv (recommended):

```bash
pip install uv
uv venv
uv sync
```

Or using pip:

```bash
pip install -e .
```

3. Install development dependencies:

```bash
uv sync --group dev
# or with pip:
pip install -e ".[dev]"
```

### Environment Setup

- Python version is specified in `.python-version` (currently `>=3.11`)
- Use virtual environments for isolation

## Code Style and Linting

The project uses the following tools for code quality:

### Linting and Formatting

- **Ruff**: Fast Python linter and formatter (configured in `pyproject.toml`)
- **isort**: Import sorting (part of dev dependencies)
- **mdformat**: Markdown formatting

### Pre-commit Hooks

The project uses pre-commit hooks (configured in `.pre-commit-config.yaml`):

```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files
```

### Manual Linting

```bash
# Run ruff linter
uv run ruff check .

# Run ruff formatter
uv run ruff format .

# Auto-fix issues
uv run ruff check --fix .
```

### Code Style Guidelines

- Follow PEP 8 conventions
- Use type hints where applicable (see `src/agentor/type_helper.py` for custom types)
- Keep functions focused and single-purpose
- Document public APIs with docstrings
- Never use placeholders like `# ... rest of code ...` - always include complete implementations

### Running Tests

Run the full test suite:

```bash
uv run pytest
```

With coverage:

```bash
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report -m
```

### Test Structure

- Tests are located in the `tests/` directory
- Test files follow the pattern `test_*.py`
- Main test files:
  - `test_agents.py` - Agent functionality tests
  - `test_a2a.py` - Agent-to-Agent protocol tests
  - `test_memory.py` - Memory system tests
  - `test_sdk.py` - SDK client tests
  - `test_text_formatter.py` - Text formatting tests

### Writing Tests

- Use pytest conventions and fixtures
- Test files should mirror the source structure
- Include unit tests for new features
- Ensure tests are isolated and reproducible
- Prefer the functional style tests

## Build and Deployment

### Building the Package

```bash
# Build distribution packages
uv build

# Install from source
pip install -e .
```

### CLI Commands

This package ships no console script. A `celesto` command comes along today only
because `celesto` is still a core dependency, and it now covers sandboxes and
computer-use agents rather than agent deployment - `celesto deploy` and
`celesto ls` were retired with the hosted platform. Nothing under `src/` imports
the `celesto` package any more, so that dependency is a candidate for removal.

`tests/test_cli.py` and `tests/perf/test_init_time.py::test_cli_time` exercise
that CLI and skip when it is absent.

### Serving Agents

```python
from agentor import Agentor

agent = Agentor(name="My Agent", model="gpt-5-nano")
agent.serve(port=8000)  # Serves with A2A protocol enabled
```

## Architecture and Key Components

### 1. The Agent Loop

**Location:** `src/agentor/engine/loop.py`

`AgentLoop` is the whole engine: call the model, run the tools it asked for, feed
the results back, repeat until it stops asking. Everything it does is emitted as
a typed event (`engine/events.py`) rather than logged, which is what makes
durability and tracing projections of one stream rather than separate features.

Bounded by `max_turns` and by `max_tool_failures` - a tool that keeps raising is
disabled rather than allowed to consume every turn. That budget is enforced at
execution, not just by withdrawing the schema, because a model will happily go on
calling a tool it can no longer see.

### 2. Models

**Location:** `src/agentor/engine/models.py`

One shape reaches almost every provider: an OpenAI-compatible
`/chat/completions` endpoint behind `base_url`. `LiteLLMModel` is the escape
hatch for providers that offer nothing compatible.

### 3. Durable Runs

**Location:** `src/agentor/engine/store.py`

An append-only event log, fsynced per event, with `replay_messages` to rebuild
the conversation. `FileStore` survives process death; `MemoryStore` is for tests.
Concurrent resume of one unfinished run is not safe - the bundled stores carry no
lease.

`fork_run` copies a log to a new id (full trace, reasoning included, plus a
`fork` marker naming the parent); `Agentor.fork` / `AgentLoop.afork` build on it
to branch a conversation - even a completed one, which `resume` refuses to
re-execute - into an independent run.

### 4. Tracing

**Location:** `src/agentor/engine/tracing.py`

A projection of the event stream onto Celesto's trace format. Opt-in: pass
`enable_tracing=True`, or `tracing=` on a single run. Holding `CELESTO_API_KEY`
is not consent to ship prompts and tool results to a remote endpoint.

The model's reasoning text, when a provider returns it, is persisted in run
logs and included in generation spans - even though streaming never surfaces
it to the client. Treat run logs and traces as holding everything the model
produced, not just what the caller saw.

### 5. Model Context Protocol (MCP)

**Location:** `src/agentor/mcp/api_router.py`, `src/agentor/mcp/server.py`, `src/agentor/engine/mcp.py`

- LiteMCP: native ASGI MCP server with FastAPI-like decorators
- Tool and resource registration, JSON-RPC, built-in CORS
- Client side (`engine/mcp.py`) runs on the official `mcp` package

### 6. Agent-to-Agent (A2A) Protocol

**Location:** `src/agentor/a2a.py`

- Standard agent communication specifications
- Automatic agent card generation at `/.well-known/agent-card.json`
- JSON-RPC-based messaging
- Support for streaming and non-streaming responses

### 7. Tool Registry

**Location:** `src/agentor/tools/registry.py`

- Extensible tool registration system
- Function decorators for tool creation

## Common Development Workflows

### Adding a New Tool

```python
from agentor import function_tool


@function_tool
def my_tool(param: str) -> str:
    """Tool description for LLM"""
    return f"Result: {param}"
```

### Creating a New Agent

```python
from agentor import Agentor

agent = Agentor(
    name="My Agent",
    model="gpt-5-nano",
    tools=[my_tool],
    instructions="Agent behavior instructions",
)
```

### Adding Tests

1. Create test file in `tests/` directory
1. Follow existing test patterns
1. Run tests locally before committing
1. Ensure coverage for new code paths

## Development Guidelines

- **Make minimal changes**: Only modify code directly relevant to the specific request
- **No placeholders**: Always include complete code, never use `# ... rest of processing ...`
- **Incremental approach**: Break problems into smaller steps, think through each separately
- **Evidence-based**: Provide complete PLAN with REASONING based on evidence from code and logs
- **Clear observations**: Explain OBSERVATIONS clearly, then provide REASONING to identify issues
- **Logging**: Add console logs when needed to gather more information

## CI/CD

### GitHub Actions Workflows

- **test.yml**: Runs pytest across multiple OS and Python versions (3.11-3.13)
- **release.yml**: Handles package releases to PyPI

There is no docs workflow. User-facing documentation is published from the
separate `mintlify-docs` repository to https://docs.celesto.ai/agentor.

### CI Test Matrix

- Operating Systems: Ubuntu, macOS, Windows
- Python Versions: 3.11, 3.12, 3.13

## Additional Resources

- **Documentation**: https://docs.celesto.ai/agentor
- **Examples**: the `examples/` directory
- **Discord Community**: https://discord.gg/KNb5UkrAmm

## Core Business Value

The system delivers value through:

- An owned agent loop, so behaviour and observability are not gated on a vendor SDK
- Durable runs that survive process death
- Secure Google Workspace integration
- Extensible tool registration and execution
- Standard protocol support (MCP, A2A) for interoperability

<!--
  This file is the single source of contributor guidance.
  .github/copilot-instructions.md points here rather than duplicating it: the
  two were kept "in sync" by hand, drifted anyway, and both went on describing
  subsystems (agenthub/, memory/) that had been deleted.
-->
