# Agentor Documentation

This directory contains the documentation for Agentor, built using MKDocs with Material theme and automatic API reference generation.

## Development

### Prerequisites

- Python 3.10 or higher
- MKDocs dependencies (installed automatically)

### Installing Documentation Dependencies

```bash
# Using uv (recommended)
uv sync --group docs

# Or using pip
pip install mkdocs mkdocs-material "mkdocstrings[python]"
```

### Building Documentation

To build the documentation locally:

```bash
mkdocs build
```

The generated site will be in the `site/` directory.

### Serving Documentation Locally

To serve the documentation with live reload:

```bash
mkdocs serve
```

Then open http://127.0.0.1:8000/agentor/ in your browser.

### Deploying Documentation

Documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch via the `.github/workflows/docs.yml` workflow.

To manually deploy:

```bash
mkdocs gh-deploy
```

## Structure

- `index.md` - Main documentation homepage
- `api/` - Auto-generated API reference documentation
  - `core/` - Core modules (Agent, LLM, Schema, Tool Convertor)
  - `mcp/` - MCP modules (API Router, Server, Proxy)
  - `tools/` - Tools modules (Registry, Base)
  - `utils/` - Utility modules
- `mcp_context.md` - MCP Context guide (existing)

## Configuration

The documentation is configured via `mkdocs.yml` in the root directory. Key settings:

- **Theme**: Material for MKDocs
- **API Documentation**: mkdocstrings with Python handler
- **Docstring Style**: Google style
- **Features**: Navigation tabs, search, code highlighting

## Contributing

When adding new modules or making significant changes:

1. Ensure your code has proper docstrings (Google style)
2. Update the navigation in `mkdocs.yml` if adding new pages
3. Build and test locally before committing
4. The documentation will auto-deploy when merged to main
