# API Reference

Welcome to the Agentor API Reference. This section provides detailed documentation for all modules, classes, and functions in the Agentor framework.

## Core Modules

The core modules provide the fundamental building blocks for creating and managing AI agents:

- **[Agent](core/agent.md)** - Main agent implementation and orchestration
- **[LLM](core/llm.md)** - Language model integration and management
- **[Schema](core/schema.md)** - Data structures and schemas
- **[Tool Convertor](core/tool_convertor.md)** - Tool conversion utilities

## MCP (Model Context Protocol)

The MCP modules enable building FastAPI-compatible MCP servers:

- **[API Router](mcp/api_router.md)** - MCP API routing with decorator support
- **[Server](mcp/server.md)** - MCP server implementation
- **[Proxy](mcp/proxy.md)** - MCP proxy functionality

## Tools

The tools modules provide extensible tool registration and implementations:

- **[Registry](tools/registry.md)** - Tool registration system
- **[Base](tools/base.md)** - Base classes for tools

## Utilities

Helper modules for various functionalities:

- **[Type Helper](utils/type_helper.md)** - Type definitions and helpers
- **[Output Text Formatter](utils/output_text_formatter.md)** - Text formatting utilities
- **[Utils](utils/utils.md)** - General utility functions
