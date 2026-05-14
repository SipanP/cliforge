"""MCP Connector: discover and execute tools from an MCP server via stdio."""

import json
import logging
import shlex
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from cliforge.models.tool import McpExecution, Tool

logger = logging.getLogger(__name__)


def _make_tool_id(namespace: str, name: str) -> str:
    return f"{namespace}.{name}"


class McpConnector:
    """
    Connects to an MCP server over stdio using the official MCP SDK.
    The server command is passed as a shell string, e.g. "npx my-mcp-server".
    """

    def __init__(
        self,
        namespace: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.namespace = namespace
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._tools: dict[str, Tool] = {}

    def _get_server_params(self) -> StdioServerParameters:
        cmd_parts = shlex.split(self.command) + self.args
        return StdioServerParameters(
            command=cmd_parts[0],
            args=cmd_parts[1:],
            env=self.env or None,
        )

    async def discover(self) -> list[Tool]:
        server_params = self._get_server_params()
        tools: list[Tool] = []

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                for mcp_tool in result.tools:
                    input_schema = (
                        mcp_tool.inputSchema
                        if isinstance(mcp_tool.inputSchema, dict)
                        else mcp_tool.inputSchema.model_dump()
                    )
                    tool = Tool(
                        id=_make_tool_id(self.namespace, mcp_tool.name),
                        namespace=self.namespace,
                        name=mcp_tool.name,
                        description=mcp_tool.description,
                        input_schema=input_schema,
                        execution=McpExecution(
                            server=self.namespace,
                            tool_name=mcp_tool.name,
                        ),
                    )
                    tools.append(tool)
                    self._tools[tool.id] = tool

        logger.info("Discovered %d tools from MCP server %s", len(tools), self.namespace)
        return tools

    async def execute(self, tool_id: str, input_data: dict) -> dict[str, Any]:
        if tool_id not in self._tools:
            raise KeyError(f"Tool not found: {tool_id}")

        tool = self._tools[tool_id]
        execution: McpExecution = tool.execution  # type: ignore[assignment]
        server_params = self._get_server_params()

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(execution.tool_name, input_data)

        content = result.content
        if content and hasattr(content[0], "text"):
            try:
                return {"data": json.loads(content[0].text), "success": True}
            except (json.JSONDecodeError, ValueError):
                return {"data": content[0].text, "success": True}
        return {"data": [c.model_dump() for c in content], "success": True}

    def get_tool(self, tool_id: str) -> Tool:
        return self._tools[tool_id]
