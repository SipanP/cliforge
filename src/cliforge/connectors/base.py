from typing import Protocol, runtime_checkable

from cliforge.models.tool import Tool


@runtime_checkable
class Connector(Protocol):
    async def discover(self) -> list[Tool]: ...

    async def execute(self, tool_id: str, input_data: dict) -> dict: ...
