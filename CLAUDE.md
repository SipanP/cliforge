
# CliForge — Project Specification & Living Reference

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

The entire system operates around one internal abstraction: `Tool`. All connectors must normalize into this.

---

# Current State (as of May 2026)

## What is fully implemented and working

### Core architecture
- `Tool` Pydantic v2 model as the single IR for all protocols
- `Connector` Protocol (`discover() -> list[Tool]`, `execute(tool_id, input_data) -> dict`)
- Protocol-agnostic `Runtime` engine that dispatches via `match tool.execution.type`
- `jsonschema` input validation before every execution
- `ExecutionResult` model for normalized outputs

### OpenAPI connector
- Load specs from local YAML/JSON files and remote HTTP URLs
- OpenAPI 3.x path/operation parsing with `operationId`-based naming (deterministic fallback for unnamed operations)
- Full `$ref` resolution across `parameters`, `requestBody`, and `components/schemas`
- Merges query params + path params + requestBody into one flat JSON Schema per tool
- Each property carries `x-param-in` (`"query"`, `"path"`, `"body"`) so execution knows where to route it
- Relative server URLs (e.g. `/api/v3`) resolved against the remote source origin — fixes real-world specs like Petstore
- `--base-url` override stored in registry metadata
- httpx-based async execution with 3-attempt retry on transport errors

### MCP connector
- stdio transport via the official MCP SDK
- Discovers tools and preserves their JSON Schemas exactly as-is
- Executes tool calls and returns structured JSON

### Registry
- Persistent storage at `~/.cliforge/` (JSON files)
- `connectors.json` — registered connector configs
- `registry.json` — cached tool metadata (survives restarts)
- `credentials.json` — auth headers (mode 600)
- `forged.json` — tracks forged commands (command name → namespace + script path + install dir + created_at)
- `config.json` — user preferences (currently: `forge.default_install_dir`)
- Tools are cached on `add` and reloaded on every startup
- `refresh` re-discovers and overwrites cached tools

### Auth
- Bearer token, API key, and env-var providers
- Env var convention: `{NAMESPACE_UPPER}_TOKEN` or `{NAMESPACE_UPPER}_API_KEY`
- Credentials written to `~/.cliforge/credentials.json` and loaded automatically

### CLI layer

**Static commands:**
- `cliforge add openapi <namespace> <source> [--base-url] [--token] [--api-key]`
- `cliforge add mcp <namespace> <command>`
- `cliforge tools [--namespace] [--output]`
- `cliforge inspect <namespace> <tool>`
- `cliforge schema <namespace> <tool>` — deterministic JSON output
- `cliforge connectors list/remove/refresh`
- `cliforge namespaces` — quick overview with tool counts
- `cliforge refresh <namespace>`
- `cliforge forge <namespace> [command-name]` — primary shorthand (command-name defaults to namespace)
- `cliforge forge list [--output]`
- `cliforge forge remove <command-name> [--keep-file]`
- `cliforge forge config [--default-install-dir]`

**Dynamic dispatch** (the main UX path):
- `cliforge <namespace>` — lists all tools in that namespace
- `cliforge <namespace> --help` — same as above
- `cliforge <namespace> <tool> --help` — renders parameter table + usage example
- `cliforge <namespace> <tool> [--flags]` — executes the tool
- `--output json|table|raw` stripped before execution, defaults to `json`

**Forge (`forge_app` sub-group, consistent with `add_app`/`connectors_app` pattern):**
- Primary shorthand: `cliforge forge <namespace> [command-name]` — routed to `create` by `main.py` before typer sees it
- `create` (hidden from help): generates a `#!/bin/sh` wrapper (`.bat` on Windows), writes to configured or default dir, tracks in `forged.json`; `command-name` defaults to namespace when omitted
- `list`: table/JSON view of all tracked forged commands
- `remove`: deletes script and removes from `forged.json`; refuses to delete foreign files; `--keep-file` untracks without deleting; error message lists the commands that CAN be removed
- `config`: view or set `default_install_dir` persisted in `config.json`
- Forged command delegates entirely to `cliforge <namespace> "$@"` — stays in sync automatically
- Distinguishes own scripts (contain `# Forged by cliforge:` marker) from foreign files at conflict time
- Error messages throughout suggest the most likely correct action with exact commands

### Output modes
- `json` (default) — pretty-printed, deterministic, LLM-friendly
- `table` — Rich table rendering
- `raw` — compact single-line JSON

### Tests
- 93 passing tests across: OpenAPI loading/parsing/schema conversion/execution, MCP discovery/execution, runtime validation/dispatch, CLI commands, registry persistence, forge (shorthand routing, create/list/remove/config, error messages), and end-to-end workflows
- Run with: `uv run pytest`

---

# Technical Decisions Made

## Entry point routes before typer sees arguments

`main.py:main()` intercepts `sys.argv` before handing off to typer. It handles two routing cases:

1. **Namespace dispatch:** Any first argument not in `_STATIC_COMMANDS` is routed to `handle_dynamic_dispatch()` in `cli/app.py`. This is what makes `cliforge github listUsers` work without `github` being a registered typer command.

2. **Forge shorthand:** `cliforge forge <namespace> [command-name]` is rewritten to `cliforge forge create <namespace> [command-name]` before typer sees it. This is necessary because typer resolves registered subcommand names (list, remove, config) before positional arguments — so without rewriting, `forge github` would fail with "No such command 'github'". The rewrite happens only when the second arg is not in `_FORGE_SUBCOMMANDS = {"create", "list", "remove", "config"}` and doesn't start with `-`.

**Critical:** The `pyproject.toml` entry point must be `cliforge.main:main`, NOT `cliforge.main:app`. Pointing to `app` bypasses the pre-dispatch and breaks namespace routing.

## `x-param-in` as schema metadata

Rather than keeping parameters and body fields in separate data structures throughout the stack, we merge everything into one flat JSON Schema and annotate each property with `x-param-in: "query" | "path" | "body"`. This lets the CLI layer, execution layer, and `--help` renderer all work from a single schema without knowing about HTTP.

## Pydantic discriminated union for execution types

```python
ExecutionDefinition = Annotated[
    OpenApiExecution | McpExecution,
    Field(discriminator="type"),
]
```

Serialization/deserialization through the registry (`model_dump()` / `Tool(**data)`) works correctly because Pydantic uses the `type` literal field to pick the right model. Adding new execution types only requires adding a new model here and a `case` branch in `runtime/engine.py`.

## Rich markup escaping

All user-supplied text (tool descriptions, parameter descriptions) that gets passed to `console.print()` must go through `rich.markup.escape()` first. Real-world API specs (Petstore, GitHub) contain `[required]`, `[...]` etc. that Rich interprets as markup tags and throws on.

## Relative server URL resolution

OpenAPI specs loaded from a remote URL may have `servers: [{url: /api/v3}]` — a relative path with no host. We resolve it against the origin of the source URL. Local files with relative server paths fall back to `http://localhost` and emit a warning to use `--base-url`.

## Connector metadata stored at registration time

`ConnectorConfig.metadata` is a freeform dict. Currently only `base_url` is stored there (when passed via `--base-url`). When executing tools from the registry, the connector is reconstructed from this config. New connector-specific options should go into `metadata` rather than adding new fields to `ConnectorConfig`.

## Forged commands are pure shell delegation

The forge script is deliberately minimal — a one-line `exec cliforge <namespace> "$@"`. No code generation, no schema baking, no copying of tool data. The forged command stays in sync with the registry automatically because it always calls the live `cliforge` binary.

## Forge is a sub-app, not a single command; `create` is hidden

`forge` follows the same pattern as `add`, `tools`, and `connectors` — a `typer.Typer()` sub-app registered via `app.add_typer(forge_app, name="forge")`. Subcommands: `create` (hidden), `list`, `remove`, `config`.

`create` is hidden from `--help` because the primary UX is `cliforge forge <namespace>` (not `forge create`). The arg rewriting in `main.py` translates the shorthand to `forge create` internally, so users never see or type "create". Hiding it keeps the help clean while preserving the explicit form as a working alias.

## Forge tracks state in `forged.json`

`forge create` records `{command_name, namespace, script_path, install_dir, created_at}` in `~/.cliforge/forged.json`. `forge list` reads this. `forge remove` reads it to find the path and then deletes the entry. Scripts contain a `# Forged by cliforge:` header that lets us distinguish our files from foreign ones at conflict time, without needing to check `forged.json` (which may not have an entry for scripts created by older versions).

---

# Codebase Map

```
src/cliforge/
│
├── main.py                      Entry point. Pre-dispatch routing before typer.
│                                _STATIC_COMMANDS set must be kept in sync with
│                                all registered typer commands.
│
├── cli/
│   ├── app.py                   Main typer app + all static top-level commands.
│   │                            handle_dynamic_dispatch() lives here.
│   │                            _print_tool_help(), _print_namespace_tools() here.
│   ├── dynamic.py               dispatch_tool_command(): parses raw --flags against
│   │                            schema and calls connector.execute().
│   ├── formatting.py            format_result(), output_json/table/raw, print_error/success.
│   └── commands/
│       ├── add.py               cliforge add openapi / add mcp
│       ├── tools.py             cliforge tools / inspect / schema (as a typer sub-group)
│       ├── connectors.py        cliforge connectors list/remove/refresh
│       └── forge.py             forge_app sub-group: create/list/remove/config
│                                forge_app is registered via app.add_typer(), NOT
│                                app.command() — keeping the pattern consistent with
│                                add_app, connectors_app, tools_app.
│
├── connectors/
│   ├── base.py                  Connector Protocol definition (discover + execute)
│   ├── openapi/
│   │   ├── loader.py            load_spec(): YAML/JSON, local/remote
│   │   ├── parser.py            parse_spec(): paths → Tool objects, $ref resolution
│   │   ├── executor.py          execute_openapi(): httpx, retries, param routing
│   │   └── connector.py        OpenApiConnector. _detect_base_url() handles relative URLs.
│   └── mcp/
│       └── connector.py        McpConnector. stdio via official MCP SDK.
│                                Must import stdio_client + ClientSession at module level
│                                (not inside methods) so tests can patch them.
│
├── runtime/
│   ├── engine.py                Runtime.execute(): validate → dispatch → ExecutionResult
│   ├── validation.py            validate_input() using jsonschema.Draft7Validator
│   └── executors/
│       ├── openapi.py           Thin shim calling execute_openapi()
│       └── mcp.py               Thin shim calling connector.execute()
│
├── models/
│   ├── tool.py                  Tool, OpenApiExecution, McpExecution, ExecutionDefinition
│   ├── execution.py             ExecutionResult
│   └── schema.py                ConnectorConfig, RegistryEntry
│
├── registry/
│   ├── store.py                 Registry: load/save/get/cache tools and connectors
│   └── persistence.py           PersistenceManager: JSON r/w at ~/.cliforge/
│
├── auth/
│   ├── providers.py             BearerTokenProvider, ApiKeyProvider, EnvVarProvider
│   └── storage.py               CredentialStorage: read/write credentials.json (mode 600)
│
└── schema/
    ├── conversion.py            openapi_params_to_json_schema(): merges params + body
    │                            split_input_by_location(): routes input by x-param-in
    └── inspection.py            schema_to_cli_params(): schema → CLI flag descriptors
```

---

# What Needs Work Next

## High priority

### Auth applied at connector reconstruction
When a tool is executed via dynamic dispatch, the connector is rebuilt from the registry config in `_build_connector()`. Credentials are loaded from `CredentialStorage` and passed as `auth_headers`. This works for bearer/API key but there is no OAuth2 flow, no token refresh, and no per-request credential resolution. A proper `CredentialProvider` protocol that connectors call at execution time would be cleaner than pre-loading headers at construction.

### Output schema is stored but never used
`Tool.output_schema` is populated from the `200`/`201` response schema during OpenAPI parsing, but the runtime never validates or formats the response against it. The data just passes through. This should drive response rendering — e.g. knowing which fields to show in `--output table` mode.

### Dynamic dispatch arg parsing is naive
`dispatch_tool_command()` in `cli/dynamic.py` hand-rolls `--flag value` parsing. It does not handle:
- `--flag=value` (equals syntax)
- boolean flags without a value (`--verbose`)
- repeated flags for array params (`--tag foo --tag bar`)
- quoted strings with spaces passed as a single value

Replacing this with a proper click/typer argument parser built from the schema would fix all of these.

### `--base-url` is mandatory for local specs without a `servers` block
If you load a local spec with no `servers:` entry, the base URL falls back to `http://localhost` silently (the warning only appears in logs at WARNING level, which is suppressed by default). The `add openapi` command should detect this and prompt/warn interactively.

## Medium priority

### No support for `allOf` / `oneOf` / `anyOf` in schema conversion
`schema/conversion.py` does not handle composed schemas. A spec that uses `allOf` to merge a base schema will produce an empty properties dict. This is common in real-world specs.

### MCP connector reconnects on every execute
Each `connector.execute()` call opens a new stdio process, initializes the session, calls the tool, and closes. This is slow and wasteful for repeated calls. The connector should maintain a persistent session and reconnect on failure.

### No streaming support
Both OpenAPI (chunked/SSE) and MCP (streaming results) can produce streamed responses. The executor returns only after the full response is received. For LLM agent use cases this matters.

### `cliforge tools --output table` is unreadable at scale
With 19+ tools (e.g. Petstore), the table is very long. Pagination, filtering, or grouping by tag would help. The `metadata.tags` field is already populated from the spec.

## Lower priority / future connectors

The runtime `_dispatch` method uses a `match` statement on `tool.execution.type`. Adding a new connector requires:
1. A new `*Execution` model in `models/tool.py`
2. A new `case` branch in `runtime/engine.py`
3. A new connector class implementing the `Connector` protocol
4. A new `cliforge add <type>` subcommand

Planned connector types (in rough priority order):
- **GraphQL** — introspect schema, expose queries/mutations as tools
- **Python functions** — import a module and expose annotated functions
- **gRPC** — use protobuf reflection
- **SQL** — expose queries as tools from a schema definition

---

# Technical Stack

```
Python      3.13+
uv          dependency management and virtual env
typer       CLI framework (static commands)
rich        terminal output and formatting
pydantic v2 all models, validation, serialization
jsonschema  input validation against JSON Schema
httpx       async HTTP for OpenAPI execution
mcp         official MCP SDK (stdio transport)
anyio       async runner
pyyaml      YAML spec loading
pytest      test runner
respx       httpx mock for tests
```

---

# Development Commands

```bash
uv sync --dev          # install all dependencies
uv run pytest          # run all 93 tests
uv run pytest -v       # verbose
uv run mypy src/       # type check
uv run ruff check src/ # lint
uv tool install .      # install cliforge globally
uv tool install . --reinstall  # update after code changes
```

---

# Invariants to Preserve

1. **`main.py:_STATIC_COMMANDS` must stay in sync** with every command added to the typer app. If a new command is added without adding its name to `_STATIC_COMMANDS`, `cliforge <new-command>` will be silently routed to dynamic dispatch and fail with a confusing "namespace not found" error.

2. **All description strings printed via Rich must be escaped** with `rich.markup.escape()`. Real-world API specs contain brackets that Rich parses as markup.

3. **MCP connector-level imports** (`stdio_client`, `ClientSession`) must be at module level, not inside methods. Test patching via `unittest.mock.patch` only works on module-level names.

4. **The entry point must be `cliforge.main:main`**, not `cliforge.main:app`. The `app` object bypasses `main()`'s pre-dispatch routing, breaking all namespace commands.

5. **`x-param-in` is internal metadata** — it should never appear in user-facing output like `cliforge schema`. It exists solely to route parameters during execution. Consider stripping it from `schema` command output in future.

6. **`forge` is a sub-app (`add_typer`), not a command (`app.command`)** — this is required for `forge list`, `forge remove`, `forge config` to work as subcommands. Reverting to `app.command("forge")(forge_fn)` would break the sub-group routing.

7. **`_FORGE_SUBCOMMANDS` in `main.py` must stay in sync** with the actual subcommand names in `forge_app`. If a new forge subcommand is added (e.g. `forge rename`) without adding it to `_FORGE_SUBCOMMANDS`, then `cliforge forge rename <arg>` would be misrouted to `forge create rename` instead of `forge rename`.
