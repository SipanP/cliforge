"""
Main CLI application.
Handles both static commands and dynamic namespace.tool dispatch.
"""

import logging
import sys
from typing import Annotated

import typer

from cliforge.cli.commands.add import add_app
from cliforge.cli.commands.connectors import connectors_app
from cliforge.cli.commands.tools import tools_app

app = typer.Typer(
    name="cliforge",
    help="Schema-driven CLI runtime for OpenAPI and MCP tools.",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(add_app, name="add")
app.add_typer(tools_app, name="tools")
app.add_typer(connectors_app, name="connectors")


@app.command("inspect")
def inspect_cmd(
    namespace: str = typer.Argument(..., help="Namespace"),
    name: str = typer.Argument(..., help="Tool name"),
    output: str = typer.Option("json", "--output", "-o"),
) -> None:
    """Inspect a tool's full definition."""
    from cliforge.cli.commands.tools import inspect_tool
    inspect_tool(namespace=namespace, name=name, output=output)


@app.command("schema")
def schema_cmd(
    namespace: str = typer.Argument(..., help="Namespace"),
    name: str = typer.Argument(..., help="Tool name"),
) -> None:
    """Show the input schema for a tool."""
    from cliforge.cli.commands.tools import show_schema
    show_schema(namespace=namespace, name=name)


@app.command("refresh")
def refresh_cmd(
    namespace: str = typer.Argument(..., help="Namespace to refresh"),
) -> None:
    """Re-discover tools for a namespace."""
    from cliforge.cli.commands.connectors import refresh_connector
    refresh_connector(namespace=namespace)


def handle_dynamic_dispatch(args: list[str]) -> bool:
    """
    Handle dynamic namespace.tool dispatch: `cliforge <namespace> <tool> [--flags]`
    Returns True if handled.
    """
    if len(args) < 2:
        return False

    namespace = args[0]
    tool_name = args[1]
    raw_args = args[2:]

    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    tool = registry.get_tool_by_name(namespace, tool_name)
    if tool is None:
        return False

    config = registry.get_connector(namespace)
    if config is None:
        return False

    output_mode = "json"
    if "--output" in raw_args:
        idx = raw_args.index("--output")
        if idx + 1 < len(raw_args):
            output_mode = raw_args[idx + 1]
            raw_args = raw_args[:idx] + raw_args[idx + 2:]
    elif "-o" in raw_args:
        idx = raw_args.index("-o")
        if idx + 1 < len(raw_args):
            output_mode = raw_args[idx + 1]
            raw_args = raw_args[:idx] + raw_args[idx + 2:]

    connector = _build_connector(config, namespace, tool)

    from cliforge.cli.dynamic import dispatch_tool_command
    dispatch_tool_command(tool, connector, raw_args, output_mode)
    return True


def _build_connector(config: "ConnectorConfig", namespace: str, tool: "Tool") -> object:  # type: ignore[name-defined]
    from cliforge.models.schema import ConnectorConfig

    if config.type == "openapi":
        from cliforge.connectors.openapi import OpenApiConnector
        from cliforge.auth.storage import CredentialStorage
        from cliforge.registry.store import Registry

        registry = Registry()
        registry.load()
        storage = CredentialStorage(registry.base_dir)
        saved_auth = storage.get(namespace)

        connector = OpenApiConnector(
            namespace=namespace,
            source=config.source,
            base_url=config.metadata.get("base_url"),
            auth_headers=saved_auth or None,
        )
        connector._tools = {tool.id: tool}
        return connector

    elif config.type == "mcp":
        from cliforge.connectors.mcp import McpConnector
        connector = McpConnector(namespace=namespace, command=config.source)
        connector._tools = {tool.id: tool}
        return connector

    raise ValueError(f"Unknown connector type: {config.type}")
