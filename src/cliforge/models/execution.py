from pydantic import BaseModel


class ExecutionResult(BaseModel):
    tool_id: str
    success: bool
    data: dict | list | str | None = None
    error: str | None = None
    status_code: int | None = None
    metadata: dict = {}
