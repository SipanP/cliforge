"""
Main CLI application.
Handles both static commands and dynamic namespace.tool dispatch.
"""

import sys
from typing import Any

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from cliforge.cli.commands.add import add_app
from cliforge.cli.commands.connectors import connectors_app
from cliforge.cli.commands.tools import tools_app

console = Console()

app = typer.Typer(
    name="cliforge",
    help="Schema-driven CLI runtime for OpenAPI and MCP tools.",
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
)

app.add_typer(add_app, name="add")
app.add_typer(tools_app, name="tools")
app.add_typer(connectors_app, name="connectors")


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    """Schema-driven CLI runtime for OpenAPI and MCP tools."""
    if ctx.invoked_subcommand is not None:
        return
    console.print(ctx.get_help())
    _print_namespace_panel()
    raise typer.Exit()


def _print_namespace_panel() -> None:
    """Print registered namespaces as dynamic commands below the standard help."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()
    connectors = registry.get_connectors()

    if not connectors:
        console.print(
            "\n[dim]No connectors registered yet. "
            "Add one with:[/dim] [bold]cliforge add openapi <name> <spec>[/bold]\n"
        )
        return

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("namespace", style="bold cyan", no_wrap=True)
    table.add_column("type", style="dim")
    table.add_column("tools", style="green", justify="right")

    for cfg in connectors:
        tools = registry.get_tools(cfg.namespace)
        table.add_row(cfg.namespace, cfg.type, f"{len(tools)} tools")

    panel = Panel(
        table,
        title="[bold]Registered Namespaces[/bold]  [dim](dynamic commands)[/dim]",
        subtitle="[dim]cliforge [cyan]<namespace>[/cyan] [green]<tool>[/green] [yellow][--flags][/yellow][/dim]",
        border_style="blue",
        padding=(0, 1),
    )
    console.print()
    console.print(panel)
    console.print(
        "  [dim]List tools:[/dim]  [bold]cliforge tools[/bold]"
        "   [dim]Tool help:[/dim]  [bold]cliforge [cyan]<namespace>[/cyan] [green]<tool>[/green] [yellow]--help[/yellow][/bold]\n"
    )


def _print_tool_help(namespace: str, tool_name: str) -> None:
    """Render --help for a dynamic tool: description, parameters, usage example."""
    from cliforge.registry.store import Registry
    from cliforge.schema.inspection import schema_to_cli_params

    registry = Registry()
    registry.load()
    tool = registry.get_tool_by_name(namespace, tool_name)
    if not tool:
        from cliforge.cli.formatting import print_error
        print_error(f"Tool '{tool_name}' not found in namespace '{namespace}'.")
        sys.exit(1)

    # Header
    console.print()
    console.print(f"[bold cyan]{namespace}[/bold cyan] [bold white]{tool.name}[/bold white]")
    if tool.description:
        console.print(f"  {escape(tool.description)}\n")
    else:
        console.print()

    # Execution details
    ex = tool.execution
    if ex.type == "openapi":
        console.print(f"  [dim]Type:[/dim]  openapi   [dim]Method:[/dim]  [yellow]{ex.method}[/yellow]   [dim]Path:[/dim]  [white]{ex.path}[/white]")  # type: ignore[union-attr]
        console.print(f"  [dim]Base:[/dim]  {ex.base_url}\n")  # type: ignore[union-attr]
    elif ex.type == "mcp":
        console.print(f"  [dim]Type:[/dim]  mcp   [dim]Server:[/dim]  {ex.server}\n")  # type: ignore[union-attr]

    # Parameters table
    params = schema_to_cli_params(tool.input_schema)
    if params:
        table = Table(box=box.SIMPLE_HEAD, show_header=True, padding=(0, 1))
        table.add_column("Flag", style="yellow", no_wrap=True)
        table.add_column("Type", style="cyan")
        table.add_column("Required", style="red")
        table.add_column("Location", style="dim")
        table.add_column("Description")

        for p in params:
            flag = f"--{p['name']}"
            req = "yes" if p["required"] else ""
            loc = p.get("location", "query")
            desc = escape(p.get("description") or "")
            if p.get("enum"):
                desc += f"  [dim]({', '.join(str(e) for e in p['enum'])})[/dim]"
            table.add_row(flag, p["type"], req, loc, desc)

        console.print(Panel(table, title="[bold]Parameters[/bold]", border_style="dim"))
    else:
        console.print("  [dim]No parameters.[/dim]\n")

    # Usage example
    required_params = [p for p in params if p["required"]]
    example_parts = [f"cliforge {namespace} {tool_name}"]
    for p in required_params[:3]:
        example_val = _example_value(p["type"])
        example_parts.append(f"--{p['name']} {example_val}")
    if len(required_params) > 3:
        example_parts.append("...")
    console.print(f"  [dim]Example:[/dim]  [bold]{escape(' '.join(example_parts))}[/bold]")
    console.print(f"  [dim]Schema: [/dim]  [bold]cliforge schema {namespace} {tool_name}[/bold]\n")


def _example_value(json_type: str) -> str:
    return {"string": '"value"', "integer": "42", "number": "3.14",
            "boolean": "true", "array": '"[...]"', "object": '"{...}"'}.get(json_type, '"value"')


@app.command("inspect")
def inspect_cmd(
    namespace: str = typer.Argument(..., help="Namespace — run 'cliforge connectors list' to see options"),
    name: str = typer.Argument(..., help="Tool name — run 'cliforge tools' to list all"),
    output: str = typer.Option("json", "--output", "-o", help="Output format: json, table, raw"),
) -> None:
    """Inspect a tool's full definition."""
    from cliforge.cli.commands.tools import inspect_tool
    inspect_tool(namespace=namespace, name=name, output=output)


@app.command("schema")
def schema_cmd(
    namespace: str = typer.Argument(..., help="Namespace — run 'cliforge connectors list' to see options"),
    name: str = typer.Argument(..., help="Tool name — run 'cliforge tools' to list all"),
) -> None:
    """Show the input schema for a tool as deterministic JSON."""
    from cliforge.cli.commands.tools import show_schema
    show_schema(namespace=namespace, name=name)


@app.command("refresh")
def refresh_cmd(
    namespace: str = typer.Argument(..., help="Namespace to refresh"),
) -> None:
    """Re-discover tools for a namespace."""
    from cliforge.cli.commands.connectors import refresh_connector
    refresh_connector(namespace=namespace)


@app.command("namespaces")
def namespaces_cmd(
    output: str = typer.Option("table", "--output", "-o", help="Output format: json, table, raw"),
) -> None:
    """List registered namespaces and their tool counts."""
    from cliforge.cli.formatting import format_result
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()
    data = [
        {
            "namespace": cfg.namespace,
            "type": cfg.type,
            "source": cfg.source,
            "tools": len(registry.get_tools(cfg.namespace)),
        }
        for cfg in registry.get_connectors()
    ]
    format_result(data, output)


def handle_dynamic_dispatch(args: list[str]) -> bool:
    """
    Handle dynamic namespace.tool dispatch: `cliforge <namespace> <tool> [--flags]`
    Returns True if handled.
    """
    if len(args) < 1:
        return False

    namespace = args[0]

    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    # `cliforge <namespace>` — list tools in that namespace
    if len(args) == 1 and registry.has_connector(namespace):
        _print_namespace_tools(registry, namespace)
        return True

    if len(args) < 2:
        return False

    tool_name = args[1]
    raw_args = args[2:]

    # `cliforge <namespace> <tool> --help` — show tool help
    if "--help" in raw_args or "-h" in raw_args:
        if registry.has_connector(namespace):
            _print_tool_help(namespace, tool_name)
            return True

    tool = registry.get_tool_by_name(namespace, tool_name)
    if tool is None:
        if registry.has_connector(namespace):
            from cliforge.cli.formatting import print_error
            print_error(f"Tool '{tool_name}' not found in namespace '{namespace}'.")
            console.print(f"  Run [bold]cliforge tools --namespace {namespace}[/bold] to list available tools.\n")
            sys.exit(1)
        return False

    config = registry.get_connector(namespace)
    if config is None:
        return False

    output_mode = "json"
    filtered_args = []
    i = 0
    while i < len(raw_args):
        if raw_args[i] in ("--output", "-o") and i + 1 < len(raw_args):
            output_mode = raw_args[i + 1]
            i += 2
        else:
            filtered_args.append(raw_args[i])
            i += 1

    connector = _build_connector(config, namespace, tool)

    from cliforge.cli.dynamic import dispatch_tool_command
    dispatch_tool_command(tool, connector, filtered_args, output_mode)
    return True


def _print_namespace_tools(registry: Any, namespace: str) -> None:
    """List all tools in a namespace with a one-line description each."""
    tools = registry.get_tools(namespace)
    if not tools:
        console.print(
            f"[yellow]No tools cached for '{namespace}'. Run:[/yellow] "
            f"[bold]cliforge refresh {namespace}[/bold]"
        )
        return

    console.print(f"\n[bold cyan]{namespace}[/bold cyan] — {len(tools)} tool(s)\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("name", style="bold white", no_wrap=True)
    table.add_column("desc", style="dim")

    for t in tools:
        # escape so Rich doesn't interpret brackets in descriptions as markup
        desc = escape((t.description or "").split("\n")[0][:80])
        table.add_row(t.name, desc)

    console.print(table)
    console.print(
        f"  [dim]Run:[/dim]    [bold]cliforge {namespace} [green]<tool>[/green] [yellow][--flags][/yellow][/bold]\n"
        f"  [dim]Help:[/dim]   [bold]cliforge {namespace} [green]<tool>[/green] [yellow]--help[/yellow][/bold]\n"
        f"  [dim]Schema:[/dim] [bold]cliforge schema {namespace} [green]<tool>[/green][/bold]\n"
    )


def _build_connector(config: Any, namespace: str, tool: Any) -> Any:
    if config.type == "openapi":
        from cliforge.auth.storage import CredentialStorage
        from cliforge.connectors.openapi import OpenApiConnector
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
