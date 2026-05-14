# CliForge

[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-de5fe9?logo=python&logoColor=white)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/tests-61%20passing-brightgreen)](./tests)
[![Pydantic v2](https://img.shields.io/badge/pydantic-v2-e92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Typer](https://img.shields.io/badge/CLI-typer-009485)](https://typer.tiangolo.com/)
[![OpenAPI 3.x](https://img.shields.io/badge/OpenAPI-3.x-6BA539?logo=openapiinitiative&logoColor=white)](https://spec.openapis.org/oas/v3.1.0)
[![MCP](https://img.shields.io/badge/MCP-stdio-8A2BE2)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff)](https://github.com/astral-sh/ruff)
[![Async](https://img.shields.io/badge/async-anyio-orange)](https://anyio.readthedocs.io/)

A schema-driven runtime that dynamically converts OpenAPI specifications and MCP servers into production-quality CLI tools optimized for both humans and LLM agents.

> Think of it as `kubectl` for arbitrary APIs and AI tools.

---

## Features

- **OpenAPI 3.x support** — load local YAML/JSON specs or remote URLs
- **MCP support** — connect to any MCP server over stdio
- **Dynamic CLI generation** — flags, types, and help text are derived at runtime from schemas
- **Unified Tool abstraction** — all protocols normalize into one internal `Tool` model
- **Persistent registry** — connectors and tool metadata survive restarts
- **LLM-friendly output** — deterministic JSON output by default
- **Pluggable auth** — bearer token, API key, environment variable providers

---

## Architecture

```
┌────────────────────┐       ┌────────────────────┐
│    OpenAPI Spec    │       │     MCP Server     │
└─────────┬──────────┘       └─────────┬──────────┘
          │                            │
┌─────────▼──────────┐       ┌─────────▼──────────┐
│ OpenAPI Connector  │       │   MCP Connector    │
└─────────┬──────────┘       └─────────┬──────────┘
          │                            │
          └──────────────┬─────────────┘
                         ▼
              ┌────────────────────┐
              │  Unified Tool IR   │
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │   Runtime Engine   │
              └─────────┬──────────┘
                        ▼
              ┌────────────────────┐
              │ Dynamic CLI Layer  │
              └────────────────────┘
```

The core `Tool` model is the single abstraction all connectors normalize into:

```python
class Tool(BaseModel):
    id: str                        # "namespace.operationName"
    namespace: str                 # e.g. "github"
    name: str                      # e.g. "listUsers"
    description: str | None
    input_schema: dict             # JSON Schema
    output_schema: dict | None     # JSON Schema
    execution: OpenApiExecution | McpExecution
    metadata: dict
```

---

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

### Option 1 — Install globally as a tool (recommended)

This makes `cliforge` available on your `$PATH` as a normal command:

```bash
git clone https://github.com/sipanp/cliforge
cd cliforge
uv tool install .

cliforge --help
```

To update later after pulling changes:

```bash
uv tool install . --reinstall
```

### Option 2 — Activate the project venv

```bash
git clone https://github.com/sipanp/cliforge
cd cliforge
uv sync
source .venv/bin/activate   # on Windows: .venv\Scripts\activate

cliforge --help
```

### Option 3 — Run via uv (no install)

```bash
uv sync
uv run cliforge --help
```

> All examples below assume `cliforge` is on your `$PATH` (Option 1 or 2). If you prefer Option 3, prefix every command with `uv run`.

---

## Quick Start

### Add an OpenAPI connector

```bash
# From a local YAML/JSON spec
cliforge add openapi github ./github.yaml

# From a remote URL
cliforge add openapi petstore https://petstore3.swagger.io/api/v3/openapi.json

# With authentication
cliforge add openapi github ./github.yaml --token ghp_yourtoken
cliforge add openapi myapi ./spec.yaml --api-key sk-mykey
```

### Add an MCP connector

```bash
cliforge add mcp filesystem "npx @modelcontextprotocol/server-filesystem /tmp"
```

### Discover tools

```bash
# List all tools
cliforge tools

# Filter by namespace
cliforge tools --namespace github

# Table output
cliforge tools --output table
```

### Inspect a tool

```bash
cliforge inspect github listUsers

# Output:
# {
#   "id": "github.listUsers",
#   "name": "listUsers",
#   "namespace": "github",
#   "description": "List all users",
#   "input_schema": {...},
#   "execution": {"type": "openapi", ...}
# }
```

### Inspect a tool's input schema

```bash
cliforge schema github listUsers

# Output (deterministic JSON):
# {
#   "properties": {
#     "limit": {"type": "integer", "x-param-in": "query"},
#     "offset": {"type": "integer", "x-param-in": "query"}
#   },
#   "type": "object"
# }
```

### Execute a tool

```bash
# Dynamic dispatch: cliforge <namespace> <tool-name> [--flags]
cliforge github listUsers --limit 10

cliforge github createUser --name "Alice" --email "alice@example.com"

cliforge github getUser --userId "abc123"

cliforge github createIssue --title "Bug report" --body "Details here"
```

---

## Output Modes

```bash
# JSON (default) — LLM-compatible, deterministic
cliforge github listUsers --output json

# Rich table
cliforge github listUsers --output table

# Raw (compact JSON, no formatting)
cliforge github listUsers --output raw
```

---

## Connector Management

```bash
# List registered connectors
cliforge connectors list

# Re-discover tools for a connector (after spec update)
cliforge refresh github
# or
cliforge connectors refresh github

# Remove a connector and its cached tools
cliforge connectors remove github
```

---

## Authentication

CliForge supports three authentication strategies:

### Bearer Token (via flag)

```bash
cliforge add openapi github ./spec.yaml --token ghp_yourtoken
```

### API Key (via flag)

```bash
cliforge add openapi myapi ./spec.yaml --api-key sk-mykey
```

### Environment Variables

CliForge automatically reads from environment variables following the pattern `{NAMESPACE_UPPER}_TOKEN` or `{NAMESPACE_UPPER}_API_KEY`:

```bash
export GITHUB_TOKEN=ghp_yourtoken
cliforge add openapi github ./spec.yaml
```

Credentials are stored securely in `~/.cliforge/credentials.json` (permissions: `600`).

---

## Registry

CliForge maintains a persistent registry at `~/.cliforge/`:

```
~/.cliforge/
├── connectors.json    # Registered connector configs
├── registry.json      # Cached tool metadata
└── credentials.json   # Stored auth credentials (mode 600)
```

Tools are cached on `add` and reloaded on startup. Use `refresh` to re-discover after spec changes.

---

## Project Structure

```
src/cliforge/
├── main.py                    # Entry point + dynamic dispatch
├── cli/
│   ├── app.py                 # Typer app + static commands
│   ├── dynamic.py             # Runtime flag parsing + execution
│   ├── formatting.py          # JSON / table / raw output
│   └── commands/
│       ├── add.py             # cliforge add openapi/mcp
│       ├── tools.py           # cliforge tools / inspect / schema
│       └── connectors.py      # cliforge connectors list/remove/refresh
├── connectors/
│   ├── base.py                # Connector Protocol
│   ├── openapi/
│   │   ├── loader.py          # YAML/JSON/remote spec loader
│   │   ├── parser.py          # Spec → Tool objects
│   │   ├── executor.py        # httpx-based HTTP execution
│   │   └── connector.py       # OpenApiConnector
│   └── mcp/
│       └── connector.py       # McpConnector (stdio transport)
├── runtime/
│   ├── engine.py              # Protocol-agnostic Runtime
│   ├── validation.py          # jsonschema input validation
│   └── executors/
│       ├── openapi.py         # OpenAPI executor shim
│       └── mcp.py             # MCP executor shim
├── models/
│   ├── tool.py                # Tool, OpenApiExecution, McpExecution
│   ├── execution.py           # ExecutionResult
│   └── schema.py              # ConnectorConfig, RegistryEntry
├── registry/
│   ├── store.py               # Registry (tool + connector store)
│   └── persistence.py         # JSON file persistence
├── auth/
│   ├── providers.py           # BearerToken, ApiKey, EnvVar providers
│   └── storage.py             # Credential file storage
└── schema/
    ├── conversion.py          # OpenAPI → JSON Schema conversion
    └── inspection.py          # Schema → CLI param descriptors
```

---

## Testing

```bash
# Run all tests
uv run pytest

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/test_openapi.py -v

# With coverage (install pytest-cov first)
uv run pytest --cov=cliforge
```

Tests cover:

| Area | Coverage |
|------|----------|
| OpenAPI spec loading (YAML + JSON) | ✓ |
| OpenAPI operation parsing | ✓ |
| Schema conversion (params + requestBody + $ref) | ✓ |
| OpenAPI HTTP execution (respx mocks) | ✓ |
| MCP tool discovery (mock SDK) | ✓ |
| MCP tool execution (mock SDK) | ✓ |
| MCP schema preservation | ✓ |
| Runtime validation | ✓ |
| Runtime dispatch | ✓ |
| Registry persistence | ✓ |
| CLI commands | ✓ |
| End-to-end workflow | ✓ |

---

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Type check
uv run mypy src/

# Lint
uv run ruff check src/
```

---

## Adding a New Connector

CliForge is designed for extensibility. To add a new connector (e.g. GraphQL):

1. Create `src/cliforge/connectors/graphql/connector.py`
2. Implement the `Connector` Protocol:

```python
class GraphQLConnector:
    async def discover(self) -> list[Tool]:
        # Introspect the schema, return Tool objects
        ...

    async def execute(self, tool_id: str, input_data: dict) -> dict:
        # Run the query/mutation
        ...
```

3. Add a `GraphQLExecution` model in `models/tool.py`
4. Add a `case "graphql":` branch in `runtime/engine.py`
5. Register with `cliforge add graphql <namespace> <endpoint>`

The core runtime requires no other modification.

---

## Supported Execution Types

| Type | Status | Transport |
|------|--------|-----------|
| OpenAPI 3.x | ✓ MVP | HTTP (httpx) |
| MCP | ✓ MVP | stdio |
| GraphQL | Planned | HTTP |
| gRPC | Planned | gRPC |
| SQL | Planned | DB drivers |

---

## LLM Agent Usage

CliForge's JSON output mode is designed for LLM agent consumption:

```bash
# Discover available tools
cliforge tools --output json

# Get exact schema before calling
cliforge schema myapi createIssue

# Execute with precise inputs
cliforge myapi createIssue --title "Bug" --body "Details"
```

All output is deterministic, schema-validated, and exit-code driven (0 = success, 1 = error).
