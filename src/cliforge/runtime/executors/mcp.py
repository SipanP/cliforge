from typing import Any

from cliforge.models.tool import Tool


async def run(tool: Tool, input_data: dict[str, Any], connector: Any = None) -> dict[str, Any]:
    if connector is None:
        raise RuntimeError("MCP connector is required for MCP tool execution")
    return await connector.execute(tool.id, input_data)
