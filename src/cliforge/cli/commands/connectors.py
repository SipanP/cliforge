"""cliforge connector management commands."""

import anyio
import typer

from cliforge.cli.formatting import format_result, print_error, print_success

connectors_app = typer.Typer(help="Manage connectors.")


@connectors_app.command("list")
def list_connectors(
    output: str = typer.Option("json", "--output", "-o"),
) -> None:
    """List all registered connectors."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    data = [c.model_dump() for c in registry.get_connectors()]
    format_result(data, output)


@connectors_app.command("remove")
def remove_connector(
    namespace: str = typer.Argument(..., help="Namespace to remove"),
) -> None:
    """Remove a connector and its cached tools."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    if not registry.has_connector(namespace):
        print_error(f"Connector '{namespace}' not found.")
        raise typer.Exit(code=1)

    registry.remove_connector(namespace)
    print_success(f"Removed connector '{namespace}'.")


@connectors_app.command("refresh")
def refresh_connector(
    namespace: str = typer.Argument(..., help="Namespace to refresh"),
) -> None:
    """Re-discover tools for a connector."""
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    config = registry.get_connector(namespace)
    if not config:
        print_error(f"Connector '{namespace}' not found.")
        raise typer.Exit(code=1)

    async def _refresh() -> list:
        if config.type == "openapi":
            from cliforge.connectors.openapi import OpenApiConnector
            base_url = config.metadata.get("base_url")
            connector = OpenApiConnector(
                namespace=namespace,
                source=config.source,
                base_url=base_url,
            )
            return await connector.discover()
        elif config.type == "mcp":
            from cliforge.connectors.mcp import McpConnector
            connector = McpConnector(namespace=namespace, command=config.source)
            return await connector.discover()
        else:
            raise ValueError(f"Unknown connector type: {config.type}")

    try:
        tools = anyio.run(_refresh)
    except Exception as exc:
        print_error(f"Refresh failed: {exc}")
        raise typer.Exit(code=1) from exc

    registry.cache_tools(tools)
    print_success(f"Refreshed '{namespace}': {len(tools)} tools.")
