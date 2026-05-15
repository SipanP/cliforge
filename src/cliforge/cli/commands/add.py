"""cliforge add openapi/mcp commands."""

import anyio
import typer

from cliforge.cli.formatting import print_error, print_info, print_success

add_app = typer.Typer(help="Add a connector (openapi or mcp).")


@add_app.command("openapi")
def add_openapi(
    namespace: str = typer.Argument(..., help="Namespace name for this connector"),
    source: str = typer.Argument(..., help="Path or URL to the OpenAPI spec"),
    base_url: str = typer.Option(None, help="Override base URL from spec"),
    token: str = typer.Option(None, envvar="CLIFORGE_TOKEN", help="Bearer token for auth"),
    api_key: str = typer.Option(None, envvar="CLIFORGE_API_KEY", help="API key for auth"),
) -> None:
    """Add an OpenAPI connector and discover its tools."""
    from cliforge.connectors.openapi import OpenApiConnector
    from cliforge.models.schema import ConnectorConfig
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    auth_headers: dict[str, str] = {}
    if token:
        auth_headers["Authorization"] = f"Bearer {token}"
    elif api_key:
        auth_headers["X-API-Key"] = api_key

    async def _discover() -> tuple[list, str]:
        connector = OpenApiConnector(
            namespace=namespace,
            source=source,
            base_url=base_url or None,
            auth_headers=auth_headers or None,
        )
        tools = await connector.discover()
        return tools, connector.base_url  # base_url is resolved inside discover()

    try:
        tools, resolved_base_url = anyio.run(_discover)
    except Exception as exc:
        print_error(f"Failed to load spec: {exc}")
        raise typer.Exit(code=1) from exc

    # Always persist the resolved base URL so execution never has to re-detect it.
    metadata: dict = {"base_url": resolved_base_url}

    config = ConnectorConfig(
        type="openapi",
        namespace=namespace,
        source=source,
        metadata=metadata,
    )
    registry.add_connector(config)
    registry.cache_tools(tools)

    if auth_headers:
        from cliforge.auth.storage import CredentialStorage
        storage = CredentialStorage(registry.base_dir)
        storage.save(namespace, auth_headers)

    print_success(f"Added OpenAPI connector '{namespace}' with {len(tools)} tools.")
    print_info(f"Source: {source}")


@add_app.command("mcp")
def add_mcp(
    namespace: str = typer.Argument(..., help="Namespace name for this MCP server"),
    command: str = typer.Argument(..., help="Command to launch the MCP server"),
) -> None:
    """Add an MCP server connector and discover its tools."""
    from cliforge.connectors.mcp import McpConnector
    from cliforge.models.schema import ConnectorConfig
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    config = ConnectorConfig(
        type="mcp",
        namespace=namespace,
        source=command,
    )

    async def _discover() -> list:
        connector = McpConnector(namespace=namespace, command=command)
        return await connector.discover()

    try:
        tools = anyio.run(_discover)
    except Exception as exc:
        print_error(f"Failed to connect to MCP server: {exc}")
        raise typer.Exit(code=1) from exc

    registry.add_connector(config)
    registry.cache_tools(tools)

    print_success(f"Added MCP connector '{namespace}' with {len(tools)} tools.")
