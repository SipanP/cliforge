"""Tests for the runtime engine."""

import pytest

from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.runtime.engine import Runtime
from cliforge.runtime.validation import ValidationError, validate_input


def make_tool(input_schema: dict, **kwargs) -> Tool:
    defaults = {
        "id": "test.op",
        "namespace": "test",
        "name": "op",
        "description": "Test operation",
        "input_schema": input_schema,
        "execution": OpenApiExecution(
            base_url="https://api.example.com",
            path="/test",
            method="GET",
        ),
    }
    defaults.update(kwargs)
    return Tool(**defaults)


# --- Validation tests ---

def test_validate_passes_valid_input():
    tool = make_tool(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    validate_input(tool, {"name": "Alice"})  # Should not raise


def test_validate_raises_on_missing_required():
    tool = make_tool(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        validate_input(tool, {})
    assert exc_info.value.errors


def test_validate_raises_on_wrong_type():
    tool = make_tool(
        {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        }
    )
    with pytest.raises(ValidationError):
        validate_input(tool, {"limit": "not-an-integer"})


def test_validate_passes_empty_schema():
    tool = make_tool({"type": "object"})
    validate_input(tool, {})


def test_validate_error_has_messages():
    tool = make_tool(
        {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        validate_input(tool, {})
    assert len(exc_info.value.errors) >= 1


# --- Runtime dispatch tests ---

@pytest.mark.asyncio
async def test_runtime_execute_openapi():
    import respx
    import httpx

    tool = make_tool(
        {"type": "object", "properties": {}},
        execution=OpenApiExecution(
            base_url="https://api.example.com/v1",
            path="/users",
            method="GET",
        ),
    )
    runtime = Runtime()

    with respx.mock:
        respx.get("https://api.example.com/v1/users").mock(
            return_value=httpx.Response(200, json={"users": []})
        )
        result = await runtime.execute(tool, {})

    assert result.success is True
    assert result.tool_id == "test.op"


@pytest.mark.asyncio
async def test_runtime_execute_validation_failure():
    tool = make_tool(
        {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
    )
    runtime = Runtime()
    result = await runtime.execute(tool, {})
    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_runtime_execute_http_error():
    import respx
    import httpx

    tool = make_tool(
        {"type": "object"},
        execution=OpenApiExecution(
            base_url="https://api.example.com/v1",
            path="/items",
            method="GET",
        ),
    )
    runtime = Runtime()

    with respx.mock:
        respx.get("https://api.example.com/v1/items").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        result = await runtime.execute(tool, {})

    assert result.status_code == 404


@pytest.mark.asyncio
async def test_runtime_register_connector():
    runtime = Runtime()
    mock_connector = object()
    runtime.register_connector("test", mock_connector)
    assert runtime._connectors["test"] is mock_connector


@pytest.mark.asyncio
async def test_runtime_unknown_execution_type():
    from unittest.mock import MagicMock
    tool = make_tool({"type": "object"})
    tool_mock = MagicMock(spec=tool)
    tool_mock.execution.type = "unknown"
    tool_mock.input_schema = {"type": "object"}
    tool_mock.id = "test.op"
    tool_mock.namespace = "test"

    runtime = Runtime()
    result = await runtime.execute(tool_mock, {})
    assert result.success is False
