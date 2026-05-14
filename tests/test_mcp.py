"""Tests for the MCP connector using mocks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cliforge.models.tool import McpExecution, Tool


def _make_mock_tool(name: str, description: str, schema: dict) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.description = description
    t.inputSchema = schema
    return t


def _make_mock_result(text: str) -> MagicMock:
    content_item = MagicMock()
    content_item.text = text
    result = MagicMock()
    result.content = [content_item]
    return result


@pytest.mark.asyncio
async def test_mcp_discover():
    from cliforge.connectors.mcp.connector import McpConnector

    mock_tool = _make_mock_tool(
        "search",
        "Search for items",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    mock_list_result = MagicMock()
    mock_list_result.tools = [mock_tool]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_list_result)

    async def _fake_stdio_client(params):
        reader = AsyncMock()
        writer = AsyncMock()
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            yield reader, writer

        return _ctx()

    with (
        patch("cliforge.connectors.mcp.connector.stdio_client") as mock_stdio,
        patch("cliforge.connectors.mcp.connector.ClientSession") as mock_cls,
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _fake_stdio(params):
            yield AsyncMock(), AsyncMock()

        @asynccontextmanager
        async def _fake_session(r, w):
            yield mock_session

        mock_stdio.side_effect = _fake_stdio
        mock_cls.side_effect = _fake_session

        connector = McpConnector(namespace="myserver", command="my-mcp-server")
        tools = await connector.discover()

    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "search"
    assert tool.namespace == "myserver"
    assert tool.id == "myserver.search"
    assert tool.execution.type == "mcp"
    assert isinstance(tool.execution, McpExecution)
    assert tool.execution.server == "myserver"
    assert tool.execution.tool_name == "search"


@pytest.mark.asyncio
async def test_mcp_schema_preserved():
    from cliforge.connectors.mcp.connector import McpConnector

    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }
    mock_tool = _make_mock_tool("search", "Search", input_schema)
    mock_list_result = MagicMock()
    mock_list_result.tools = [mock_tool]

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_list_result)

    with (
        patch("cliforge.connectors.mcp.connector.stdio_client") as mock_stdio,
        patch("cliforge.connectors.mcp.connector.ClientSession") as mock_cls,
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _fake_stdio(params):
            yield AsyncMock(), AsyncMock()

        @asynccontextmanager
        async def _fake_session(r, w):
            yield mock_session

        mock_stdio.side_effect = _fake_stdio
        mock_cls.side_effect = _fake_session

        connector = McpConnector(namespace="myserver", command="my-mcp-server")
        tools = await connector.discover()

    assert tools[0].input_schema == input_schema


@pytest.mark.asyncio
async def test_mcp_execute():
    import json
    from cliforge.connectors.mcp.connector import McpConnector

    mock_tool_model = _make_mock_tool(
        "search", "Search", {"type": "object", "properties": {"query": {"type": "string"}}}
    )
    mock_list_result = MagicMock()
    mock_list_result.tools = [mock_tool_model]

    response_data = {"results": ["item1", "item2"]}
    mock_call_result = _make_mock_result(json.dumps(response_data))

    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=mock_list_result)
    mock_session.call_tool = AsyncMock(return_value=mock_call_result)

    with (
        patch("cliforge.connectors.mcp.connector.stdio_client") as mock_stdio,
        patch("cliforge.connectors.mcp.connector.ClientSession") as mock_cls,
    ):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _fake_stdio(params):
            yield AsyncMock(), AsyncMock()

        @asynccontextmanager
        async def _fake_session(r, w):
            yield mock_session

        mock_stdio.side_effect = _fake_stdio
        mock_cls.side_effect = _fake_session

        connector = McpConnector(namespace="myserver", command="my-mcp-server")
        await connector.discover()
        result = await connector.execute("myserver.search", {"query": "test"})

    assert result["success"] is True
    assert result["data"] == response_data


@pytest.mark.asyncio
async def test_mcp_execute_unknown_tool():
    from cliforge.connectors.mcp.connector import McpConnector
    connector = McpConnector(namespace="myserver", command="my-mcp-server")
    with pytest.raises(KeyError):
        await connector.execute("myserver.nonexistent", {})
