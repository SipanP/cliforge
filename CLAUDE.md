
# CliForge — Detailed Implementation Specification

## Vision

CliForge is a schema-driven runtime that dynamically converts OpenAPI specifications and MCP servers into production-quality CLI tools optimized for both humans and LLM agents.

The platform should:
- Discover tools dynamically
- Normalize schemas into one internal representation
- Expose tools as typed CLI commands
- Execute tools through a unified runtime
- Provide deterministic machine-readable outputs
- Be extensible to future protocols

The implementation must prioritize:
- Reliability
- Deterministic behavior
- Async architecture
- Strong typing
- LLM usability
- Testability

---

# Core Product Philosophy

CliForge is NOT:
- a workflow engine
- an autonomous agent framework
- a code generator
- a static CLI generator

CliForge IS:
- a schema-driven runtime
- a dynamic CLI system
- a protocol abstraction layer
- an AI-native command execution layer

The entire system should operate around one internal abstraction:

```python
Tool
```

All connectors must normalize into this abstraction.

---

# Supported Protocols (MVP)

## OpenAPI
Required capabilities:
- Parse local JSON/YAML specs
- Parse remote specs
- Support OpenAPI 3.x
- Discover operations
- Extract parameters
- Extract request body schemas
- Execute HTTP requests

---

## MCP
Required capabilities:
- Connect to MCP servers
- Discover tools
- Call tools
- Support stdio transport initially
- Preserve MCP JSON Schemas

---

# Architecture

```text
             ┌────────────────────┐
             │    OpenAPI Spec    │
             └─────────┬──────────┘
                       │
             ┌─────────▼──────────┐
             │ OpenAPI Connector  │
             └─────────┬──────────┘

             ┌────────────────────┐
             │     MCP Server     │
             └─────────┬──────────┘
                       │
             ┌─────────▼──────────┐
             │   MCP Connector    │
             └─────────┬──────────┘

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

---

# Technical Stack

## Required

- Python 3.12+
- uv
- typer
- rich
- pydantic v2
- jsonschema
- httpx
- pytest
- pytest-asyncio
- respx
- anyio
- pyyaml

---

## Optional

- official MCP SDK
- or lightweight MCP client implementation

---

# Dependency Management

The project MUST use:

```bash
uv init
uv add ...
uv sync
uv run pytest
```

The implementation should never rely on pip directly.

---

# Project Structure

```text
cliforge/
├── pyproject.toml
├── README.md
├── uv.lock
├── src/
│   └── cliforge/
│       ├── __init__.py
│       ├── main.py
│       ├── cli/
│       │   ├── app.py
│       │   ├── dynamic.py
│       │   ├── formatting.py
│       │   └── commands/
│       ├── connectors/
│       │   ├── base.py
│       │   ├── openapi/
│       │   └── mcp/
│       ├── runtime/
│       │   ├── engine.py
│       │   ├── executors/
│       │   └── validation.py
│       ├── models/
│       │   ├── tool.py
│       │   ├── execution.py
│       │   └── schema.py
│       ├── registry/
│       │   ├── store.py
│       │   └── persistence.py
│       ├── auth/
│       │   ├── providers.py
│       │   └── storage.py
│       ├── schema/
│       │   ├── conversion.py
│       │   └── inspection.py
│       └── utils/
│
├── tests/
│   ├── fixtures/
│   ├── integration/
│   ├── e2e/
│   ├── test_openapi.py
│   ├── test_mcp.py
│   ├── test_cli.py
│   └── test_runtime.py
```

---

# Internal Tool Abstraction

This is the MOST IMPORTANT component.

Everything must normalize into this.

```python
from typing import Literal
from pydantic import BaseModel

class OpenApiExecution(BaseModel):
    type: Literal["openapi"]
    base_url: str
    path: str
    method: str
    operation_id: str | None = None


class McpExecution(BaseModel):
    type: Literal["mcp"]
    server: str
    tool_name: str


ExecutionDefinition = OpenApiExecution | McpExecution


class Tool(BaseModel):
    id: str
    namespace: str
    name: str

    description: str | None = None

    input_schema: dict
    output_schema: dict | None = None

    execution: ExecutionDefinition

    metadata: dict = {}
```

---

# Connector Interface

All connectors MUST implement:

```python
from typing import Protocol

class Connector(Protocol):

    async def discover(self) -> list[Tool]:
        ...

    async def execute(
        self,
        tool_id: str,
        input_data: dict,
    ) -> dict:
        ...
```

---

# Important Architectural Rules

## DO
- Normalize all protocols into Tool
- Use JSON Schema everywhere internally
- Keep runtime protocol-agnostic
- Keep execution logic isolated
- Use async everywhere possible

---

## DO NOT
- Leak HTTP concepts into runtime core
- Generate static CLI code
- Hardcode APIs
- Mix rendering with execution
- Couple CLI generation to OpenAPI

---

# OpenAPI Connector Requirements

## Discovery

The connector must:
- Parse YAML and JSON
- Support OpenAPI 3.x
- Iterate through paths and operations
- Build Tool objects

---

## Operation Naming

Rules:
- Use operationId if available
- Otherwise generate deterministic names

Example:

```yaml
/users:
  get:
    operationId: listUsers
```

Becomes:

```text
namespace: github
name: listUsers
```

---

# Schema Conversion

Convert:
- query parameters
- path parameters
- request body schemas

Into one merged JSON Schema.

Example:

```json
{
  "type": "object",
  "properties": {
    "title": {
      "type": "string"
    },
    "limit": {
      "type": "integer"
    }
  },
  "required": ["title"]
}
```

---

# OpenAPI Execution

Use:
- httpx.AsyncClient

Requirements:
- Handle query params
- Handle path params
- Handle JSON body
- Handle headers
- Handle auth
- Support timeouts
- Support retries

---

# MCP Connector Requirements

## Discovery

The connector must:
- connect to MCP server
- call tools/list
- normalize tools into Tool objects

---

## Execution

The connector must:
- call tools/call
- validate input against schema
- return structured JSON

---

## Transport

Initial MVP:
- stdio transport

Future-compatible architecture:
- websocket transport
- HTTP transport

---

# Runtime Engine

Implement:

```python
class Runtime:

    async def execute(
        self,
        tool: Tool,
        input_data: dict,
    ) -> dict:

        match tool.execution.type:

            case "openapi":
                ...

            case "mcp":
                ...
```

The runtime must:
- validate inputs
- dispatch execution
- normalize outputs
- handle errors consistently

---

# JSON Schema Validation

Requirements:
- Validate all user inputs
- Validate before execution
- Produce deterministic errors

Use:
```python
jsonschema.validate()
```

or equivalent validator class.

---

# CLI Requirements

Use:
```python
typer
```

---

# Dynamic Command Generation

Commands must be generated dynamically at runtime.

Example:

```bash
cliforge github issues.create --title "Bug"
```

The CLI should:
- inspect schema
- derive flags
- validate types
- generate help text automatically

---

# CLI Commands

## Connector Management

```bash
cliforge add openapi ./github.yaml
cliforge add mcp github-server
```

---

## Discovery

```bash
cliforge tools
cliforge inspect github issues.create
```

---

## Execution

```bash
cliforge github issues.create   --title "Bug"   --body "Example"
```

---

## Schema Inspection

```bash
cliforge schema github issues.create
```

Must output deterministic JSON.

---

# Output Modes

Support:

```bash
--output json
--output table
--raw
```

Default:
```text
json
```

LLM compatibility is higher priority than terminal aesthetics.

---

# Registry Requirements

Implement persistent registry storage.

Recommended path:

```text
~/.cliforge/
```

Suggested files:

```text
registry.json
connectors.json
credentials.json
```

---

# Registry Responsibilities

The registry must:
- store connectors
- store namespaces
- store tool metadata
- reload tools on startup
- refresh discovery

---

# Authentication

Implement pluggable authentication.

Supported:
- bearer token
- API key
- environment variable

---

# Credential Interface

```python
class CredentialProvider(Protocol):

    async def get(
        self,
        namespace: str,
    ) -> dict:
        ...
```

---

# Error Handling

Requirements:
- consistent error format
- useful validation errors
- deterministic JSON errors
- proper exit codes

---

# Logging

Requirements:
- structured logging
- debug mode
- trace execution mode

Optional:
- JSON logs

---

# Testing Requirements

Tests are mandatory.

The implementation is incomplete if tests fail.

---

# Required Test Coverage

## OpenAPI
- spec loading
- operation parsing
- schema conversion
- execution
- invalid requests

---

## MCP
- tool discovery
- tool execution
- schema preservation

---

## Runtime
- dispatching
- validation
- error handling

---

## CLI
- help generation
- dynamic commands
- schema inspection
- JSON output
- invalid flags

---

## End-to-End
- full CLI workflow
- registry persistence
- connector reload

---

# Testing Commands

All tests must pass with:

```bash
uv run pytest
```

---

# Fixtures

Include:
- sample OpenAPI specs
- mock MCP servers
- mock HTTP APIs

---

# Example OpenAPI Fixture

Include fixture similar to:

```yaml
openapi: 3.0.0
info:
  title: Example API
  version: 1.0.0

paths:
  /users:
    get:
      operationId: listUsers
```

---

# CLI Validation Examples

These MUST work:

```bash
cliforge tools

cliforge inspect github listUsers

cliforge schema github listUsers

cliforge github listUsers --limit 10
```

---

# Performance Requirements

The CLI should:
- start quickly
- lazily load connectors
- cache tool discovery

---

# Extensibility Requirements

The architecture must support future connectors:

Potential future connectors:
- GraphQL
- gRPC
- SQL
- Terraform
- Kubernetes
- Python functions
- Docker containers

The core runtime should not require modification to support new connectors.

---

# README Requirements

Generate comprehensive README including:
- installation
- architecture
- examples
- testing
- development
- adding connectors

---

# pyproject.toml Requirements

Must include:
- dependencies
- dev dependencies
- pytest config
- Ruff config
- mypy config

---

# Quality Requirements

The generated code should:
- be fully typed
- use async patterns
- use modern Python
- avoid global state
- avoid duplicated logic

---

# Final Validation Checklist

The implementation is complete only if:

- uv sync works
- uv run pytest passes
- CLI commands execute correctly
- schemas validate correctly
- help text renders correctly
- OpenAPI execution works
- MCP execution works
- JSON output is deterministic
- registry persists correctly
- all examples in README work

---

# Final Goal

The resulting product should feel like:

```text
kubectl for arbitrary APIs and AI tools
```

with strong support for:
- LLM agents
- deterministic execution
- schema inspection
- extensibility
