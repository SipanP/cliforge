"""
Dynamic CLI command builder.
Generates typer commands at runtime from tool schemas.
"""

import json
import sys
from typing import Any

import anyio
import typer

from cliforge.cli.formatting import (
    format_execution_result,
    format_result,
    print_error,
    print_param_table,
)
from cliforge.models.tool import Tool
from cliforge.runtime.validation import ValidationError, validate_input
from cliforge.schema.inspection import json_type_to_python, schema_to_cli_params

_EXAMPLE_VALUES: dict[str, str] = {
    "string": '"value"',
    "integer": "42",
    "number": "3.14",
    "boolean": "true",
    "array": '"[...]"',
    "object": '"{...}"',
}


def _coerce_value(value: str, json_type: str) -> Any:
    if json_type == "integer":
        return int(value)
    if json_type == "number":
        return float(value)
    if json_type == "boolean":
        return value.lower() in {"true", "1", "yes"}
    if json_type == "object":
        return json.loads(value)
    if json_type == "array":
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, ValueError):
            # Accept a bare string or comma-separated values as a string array.
            # Allows: --tags foo,bar  or  --photoUrls https://example.com/pic.jpg
            return [v.strip() for v in value.split(",")]
    return value


def build_dynamic_command(
    tool: Tool,
    connector: Any,
    output_mode: str = "json",
) -> Any:
    """
    Build a callable function that acts as a typer command for the given tool.
    Parameters are derived from the tool's input_schema.
    """
    params = schema_to_cli_params(tool.input_schema)

    def _command(**kwargs: Any) -> None:
        input_data: dict[str, Any] = {}
        for param in params:
            value = kwargs.get(param["name"])
            if value is not None:
                input_data[param["name"]] = _coerce_value(str(value), param["type"])

        async def _run() -> Any:
            return await connector.execute(tool.id, input_data)

        try:
            result = anyio.from_thread.run_sync(lambda: anyio.run(_run))
        except Exception:
            result = anyio.run(_run)

        format_result(result, output_mode)

    _command.__name__ = tool.name
    _command.__doc__ = tool.description or f"Execute {tool.name}"
    return _command


def dispatch_tool_command(
    tool: Tool,
    connector: Any,
    raw_args: list[str],
    output_mode: str = "json",
    dry_run: bool = False,
) -> None:
    """
    Parse raw CLI args (e.g. ['--title', 'Bug', '--limit', '10']) against the tool schema
    and execute the tool.
    """
    params = schema_to_cli_params(tool.input_schema)
    input_data: dict[str, Any] = {}

    i = 0
    positional_params = [p for p in params if p.get("location") == "path"]
    positional_idx = 0

    while i < len(raw_args):
        arg = raw_args[i]
        if arg.startswith("--"):
            key = arg.lstrip("-").replace("-", "_")
            if i + 1 < len(raw_args) and not raw_args[i + 1].startswith("--"):
                val = raw_args[i + 1]
                i += 2
            else:
                val = "true"
                i += 1

            matching = next((p for p in params if p["name"] == key), None)
            if matching:
                input_data[key] = _coerce_value(val, matching["type"])
            else:
                input_data[key] = val
        else:
            if positional_idx < len(positional_params):
                p = positional_params[positional_idx]
                input_data[p["name"]] = _coerce_value(arg, p["type"])
                positional_idx += 1
            i += 1

    # Pre-flight: validate required params before sending to the server.
    try:
        validate_input(tool, input_data)
    except ValidationError as exc:
        from rich.console import Console
        from rich.markup import escape
        err = Console(stderr=True)
        err.print(f"\n[red bold]Error:[/red bold] [bold]{tool.name}[/bold] — {len(exc.errors)} validation issue(s):")
        for msg in exc.errors:
            err.print(f"  [red]•[/red] {escape(msg)}")
        err.print()
        print_param_table(params)
        required_params = [p for p in params if p["required"]]
        example_parts = [f"cliforge {tool.namespace} {tool.name}"]
        for p in required_params[:3]:
            example_parts.append(f"--{p['name']} {_EXAMPLE_VALUES.get(p['type'], '\"value\"')}")
        if len(required_params) > 3:
            example_parts.append("...")
        err.print(f"  [dim]Example:[/dim]  [bold]{' '.join(example_parts)}[/bold]\n")
        raise typer.Exit(code=1)

    if dry_run:
        from cliforge.cli.formatting import print_dry_run
        from cliforge.connectors.openapi.executor import build_request_info
        auth_headers = getattr(connector, "auth_headers", None)
        req_info = build_request_info(tool, input_data, auth_headers, redact_auth=True)
        print_dry_run(req_info, tool)
        return

    async def _run() -> Any:
        return await connector.execute(tool.id, input_data)

    try:
        result = anyio.run(_run)
    except Exception as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    format_execution_result(result, output_mode, tool)
