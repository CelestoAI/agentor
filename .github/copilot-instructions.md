# Agentor - GitHub Copilot Instructions

## Project Overview

Agentor is an open-source framework for building multi-agent AI systems with secure integrations across email, calendars, CRMs, and more. It enables connecting LLMs to tools and services, supporting Model Context Protocol (MCP) and Agent-to-Agent (A2A) communication protocols.

**Key Features:**

- Multi-agent orchestration with specialized agent roles
- Secure Google Workspace integration (Gmail, Calendar)
- LiteMCP - FastAPI-compatible MCP server with decorator API
- A2A Protocol support for agent interoperability
- Vector-based memory management for conversation context
- Tool registry and extensible tool system

## Repository Structure

```
agentor/
├── src/agentor/           # Main package source code
│   ├── agents/            # Agent core implementation (A2A protocol)
│   ├── agenthub/          # Specialized agents (Google, memory, web search)
│   ├── cli/               # Command-line interface
│   ├── mcp/               # Model Context Protocol server
│   ├── memory/            # Vector database and memory management
│   ├── sdk/               # Celesto AI SDK client
│   ├── tools/             # Tool registry and implementations
│   └── chat.py            # Main chat orchestration
├── tests/                 # Test suite
├── examples/              # Usage examples
├── .github/               # GitHub configuration and workflows
└── pyproject.toml         # Project metadata and dependencies
```

## Development Setup

### Prerequisites

- Python 3.10 or higher
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

- Python version is specified in `.python-version` (currently `>=3.10`)
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

## Testing

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

## Build and Deployment

### Building the Package

```bash
# Build distribution packages
uv build

# Install from source
pip install -e .
```

### CLI Commands

The package provides a CLI tool:

```bash
# After installation
agentor --help

# Deploy an agent
agentor deploy
```

### Serving Agents

```python
from agentor import Agentor

agent = Agentor(name="My Agent", model="gpt-4")
agent.serve(port=8000)  # Serves with A2A protocol enabled
```

## Architecture and Key Components

### 1. Multi-Agent Orchestration System

**Location:** `src/agentor/agenthub/main.py`

Hierarchical agent structure with specialized roles:

- **Concept Research Agent** - Topic research and information gathering
- **Coder Agent** - Code-related operations
- **Google Agent** - Workspace integration
- **Main Triage Agent** - Request routing and delegation

**Importance Score:** 85/100

### 2. Google Workspace Integration

**Location:** `src/agentor/agenthub/google/google_agent.py`

- Gmail and Calendar operations management
- Privacy-aware email and calendar data handling
- Consent-based access control
- Business rules for email processing
- Timezone-aware calendar management

**Importance Score:** 90/100

### 3. Memory Management System

**Location:** `src/agentor/memory/api.py`

- Vector database storage for conversation history (LanceDB)
- Semantic conversation context retrieval
- Conversation memory search capabilities
- Embeddings-based similarity search

**Importance Score:** 75/100

### 4. Model Context Protocol (MCP)

**Location:** `src/agentor/mcp/api_router.py`, `src/agentor/mcp/server.py`

- LiteMCP: Native ASGI MCP server with FastAPI-like decorators
- Tool and resource registration
- JSON-RPC communication protocol
- Agent communication routing
- Built-in CORS support

**Importance Score:** 80/100

### 5. Agent-to-Agent (A2A) Protocol

**Location:** `src/agentor/agents/a2a.py`

- Standard agent communication specifications
- Automatic agent card generation at `/.well-known/agent-card.json`
- JSON-RPC based messaging
- Support for streaming and non-streaming responses

### 6. Tool Registry

**Location:** `src/agentor/tools/registry.py`

- Extensible tool registration system
- Function decorators for tool creation
- Integration with Celesto AI Tool Hub

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
    model="gpt-4",
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

- **test.yml**: Runs pytest across multiple OS and Python versions (3.10-3.13)
- **release.yml**: Handles package releases to PyPI

### CI Test Matrix

- Operating Systems: Ubuntu, macOS, Windows
- Python Versions: 3.10, 3.11, 3.12, 3.13

## Additional Resources

- **Documentation**: https://docs.celesto.ai
- **Examples**: `examples/` directory and https://github.com/celestoai/agentor/tree/main/docs/examples
- **Discord Community**: https://discord.gg/KNb5UkrAmm
- **Tool Hub**: https://celesto.ai/toolhub

## Core Business Value

The system delivers value through:

- Task delegation via specialized agents
- Secure Google workspace integration
- Contextual memory management for persistent conversations
- Extensible tool registration and execution
- Standard protocol support (MCP, A2A) for interoperability
