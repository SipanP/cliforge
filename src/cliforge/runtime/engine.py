"""Protocol-agnostic runtime engine."""

import logging
from typing import Any

from cliforge.models.execution import ExecutionResult
from cliforge.models.tool import Tool
from cliforge.runtime.validation import ValidationError, validate_input

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self) -> None:
        self._connectors: dict[str, Any] = {}

    def register_connector(self, namespace: str, connector: Any) -> None:
        self._connectors[namespace] = connector

    async def execute(
        self,
        tool: Tool,
        input_data: dict[str, Any],
    ) -> ExecutionResult:
        try:
            validate_input(tool, input_data)
        except ValidationError as exc:
            return ExecutionResult(
                tool_id=tool.id,
                success=False,
                error=str(exc),
                data={"validation_errors": exc.errors},
            )

        try:
            result = await self._dispatch(tool, input_data)
            return ExecutionResult(
                tool_id=tool.id,
                success=result.get("success", True),
                data=result.get("data"),
                status_code=result.get("status_code"),
                metadata={"raw": result},
            )
        except Exception as exc:
            logger.exception("Execution failed for tool %s", tool.id)
            return ExecutionResult(
                tool_id=tool.id,
                success=False,
                error=str(exc),
            )

    async def _dispatch(self, tool: Tool, input_data: dict[str, Any]) -> dict[str, Any]:
        match tool.execution.type:
            case "openapi":
                from cliforge.runtime.executors.openapi import run
                connector = self._connectors.get(tool.namespace)
                auth_headers: dict[str, str] = {}
                if connector and hasattr(connector, "auth_headers"):
                    auth_headers = connector.auth_headers
                return await run(tool, input_data, auth_headers)

            case "mcp":
                from cliforge.runtime.executors.mcp import run
                connector = self._connectors.get(tool.namespace)
                return await run(tool, input_data, connector)

            case _:
                raise NotImplementedError(f"Unknown execution type: {tool.execution.type}")
