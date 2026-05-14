from typing import Annotated, Literal

from pydantic import BaseModel, Field


class OpenApiExecution(BaseModel):
    type: Literal["openapi"] = "openapi"
    base_url: str
    path: str
    method: str
    operation_id: str | None = None


class McpExecution(BaseModel):
    type: Literal["mcp"] = "mcp"
    server: str
    tool_name: str


ExecutionDefinition = Annotated[
    OpenApiExecution | McpExecution,
    Field(discriminator="type"),
]


class Tool(BaseModel):
    id: str
    namespace: str
    name: str
    description: str | None = None
    input_schema: dict
    output_schema: dict | None = None
    execution: ExecutionDefinition
    metadata: dict = {}
