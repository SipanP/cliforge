"""cliforge tools and inspect commands."""

import json

import typer

from cliforge.cli.formatting import format_result, print_error

tools_app = typer.Typer(help="List and inspect registered tools.")


@tools_app.callback(invoke_without_command=True)
def list_tools(
    ctx: typer.Context,
    namespace: str = typer.Option(None, "--namespace", "-n", help="Filter by namespace"),
    output: str = typer.Option("json", "--output", "-o", help="Output format: json, table, raw"),
) -> None:
    """List all registered tools."""
    if ctx.invoked_subcommand is not None:
        return

    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    tool_list = registry.get_tools(namespace=namespace)
    data = [
        {
            "id": t.id,
            "namespace": t.namespace,
            "name": t.name,
            "description": (t.description or "")[:80],
            "type": t.execution.type,
        }
        for t in tool_list
    ]
    format_result(data, output)


@tools_app.command("inspect")
def inspect_tool(
    namespace: str = typer.Argument(..., help="Namespace — run 'cliforge connectors list'"),
    name: str = typer.Argument(..., help="Tool name — run 'cliforge tools' to list all"),
    output: str = typer.Option("json", "--output", "-o", help="Output format"),
) -> None:
    """Inspect a tool's full definition."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    tool = registry.get_tool_by_name(namespace, name)
    if not tool:
        print_error(f"Tool not found: {namespace}.{name}")
        raise typer.Exit(code=1)

    format_result(tool.model_dump(), output)


@tools_app.command("schema")
def show_schema(
    namespace: str = typer.Argument(..., help="Namespace — run 'cliforge connectors list'"),
    name: str = typer.Argument(..., help="Tool name — run 'cliforge tools' to list all"),
) -> None:
    """Show the input schema for a tool as deterministic JSON."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    tool = registry.get_tool_by_name(namespace, name)
    if not tool:
        print_error(f"Tool not found: {namespace}.{name}")
        raise typer.Exit(code=1)

    print(json.dumps(tool.input_schema, indent=2, sort_keys=True))
