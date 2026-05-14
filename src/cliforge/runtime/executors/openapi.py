from typing import Any

from cliforge.connectors.openapi.executor import execute_openapi
from cliforge.models.tool import Tool


async def run(tool: Tool, input_data: dict[str, Any], auth_headers: dict[str, str] | None = None) -> dict[str, Any]:
    return await execute_openapi(tool, input_data, auth_headers)
