"""Tests for the OpenAPI connector."""

import pytest

from cliforge.connectors.openapi.loader import _load_local
from cliforge.connectors.openapi.parser import parse_spec, _generate_operation_name
from cliforge.connectors.openapi.connector import OpenApiConnector
from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.schema.conversion import openapi_params_to_json_schema, split_input_by_location


# --- Loader tests ---

def test_load_yaml_spec(example_spec_path):
    spec = _load_local(str(example_spec_path))
    assert spec["openapi"] == "3.0.3"
    assert "paths" in spec
    assert "/users" in spec["paths"]


def test_load_json_spec(minimal_spec_path):
    spec = _load_local(str(minimal_spec_path))
    assert spec["openapi"] == "3.0.3"
    assert "listItems" == spec["paths"]["/items"]["get"]["operationId"]


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        _load_local("/nonexistent/path/spec.yaml")


# --- Parser tests ---

def test_parse_spec_discovers_operations(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "test", "https://api.example.com/v1")
    tool_names = {t.name for t in tools}
    assert "listUsers" in tool_names
    assert "createUser" in tool_names
    assert "getUser" in tool_names
    assert "updateUser" in tool_names
    assert "deleteUser" in tool_names
    assert "createIssue" in tool_names


def test_parse_spec_tool_ids(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "github", "https://api.example.com/v1")
    ids = {t.id for t in tools}
    assert "github.listUsers" in ids
    assert "github.createUser" in ids


def test_parse_spec_execution_type(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "test", "https://api.example.com/v1")
    for tool in tools:
        assert tool.execution.type == "openapi"
        assert isinstance(tool.execution, OpenApiExecution)


def test_parse_spec_list_users_schema(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "test", "https://api.example.com/v1")
    list_users = next(t for t in tools if t.name == "listUsers")
    props = list_users.input_schema.get("properties", {})
    assert "limit" in props
    assert "offset" in props
    assert props["limit"]["type"] == "integer"


def test_parse_spec_create_user_required(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "test", "https://api.example.com/v1")
    create_user = next(t for t in tools if t.name == "createUser")
    required = create_user.input_schema.get("required", [])
    assert "name" in required
    assert "email" in required


def test_parse_spec_path_param(example_spec_path):
    from cliforge.connectors.openapi.loader import _load_local
    spec = _load_local(str(example_spec_path))
    tools = parse_spec(spec, "test", "https://api.example.com/v1")
    get_user = next(t for t in tools if t.name == "getUser")
    props = get_user.input_schema.get("properties", {})
    assert "userId" in props
    assert props["userId"]["x-param-in"] == "path"
    assert "userId" in get_user.input_schema.get("required", [])


def test_generate_operation_name_deterministic():
    name1 = _generate_operation_name("get", "/users/{userId}/posts")
    name2 = _generate_operation_name("get", "/users/{userId}/posts")
    assert name1 == name2
    assert len(name1) > 0


def test_generate_operation_name_without_operation_id():
    name = _generate_operation_name("post", "/items")
    assert "post" in name.lower() or "items" in name.lower()


# --- Schema conversion tests ---

def test_schema_conversion_query_params():
    params = [
        {"name": "q", "in": "query", "schema": {"type": "string"}, "required": False},
        {"name": "limit", "in": "query", "schema": {"type": "integer"}, "required": False},
    ]
    schema = openapi_params_to_json_schema(params, None, {})
    assert schema["type"] == "object"
    assert "q" in schema["properties"]
    assert "limit" in schema["properties"]
    assert schema["properties"]["q"]["x-param-in"] == "query"


def test_schema_conversion_path_params():
    params = [
        {"name": "userId", "in": "path", "schema": {"type": "string"}, "required": True},
    ]
    schema = openapi_params_to_json_schema(params, None, {})
    assert "userId" in schema["properties"]
    assert schema["properties"]["userId"]["x-param-in"] == "path"
    assert "userId" in schema["required"]


def test_schema_conversion_request_body():
    request_body = {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                }
            }
        },
    }
    schema = openapi_params_to_json_schema([], request_body, {})
    assert "title" in schema["properties"]
    assert "body" in schema["properties"]
    assert "title" in schema["required"]
    assert schema["properties"]["title"]["x-param-in"] == "body"


def test_split_input_by_location():
    input_schema = {
        "type": "object",
        "properties": {
            "userId": {"type": "string", "x-param-in": "path"},
            "limit": {"type": "integer", "x-param-in": "query"},
            "name": {"type": "string", "x-param-in": "body"},
        },
    }
    input_data = {"userId": "123", "limit": 10, "name": "Alice"}
    path_p, query_p, body_p = split_input_by_location(input_data, input_schema)
    assert path_p == {"userId": "123"}
    assert query_p == {"limit": 10}
    assert body_p == {"name": "Alice"}


def test_ref_resolution_in_schema():
    components = {
        "schemas": {
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["id", "name"],
            }
        }
    }
    request_body = {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/User"}
            }
        },
    }
    schema = openapi_params_to_json_schema([], request_body, components)
    assert "id" in schema["properties"]
    assert "name" in schema["properties"]


# --- Connector integration tests ---

@pytest.mark.asyncio
async def test_connector_discover(example_spec_path):
    connector = OpenApiConnector(
        namespace="test",
        source=str(example_spec_path),
    )
    tools = await connector.discover()
    assert len(tools) > 0
    assert all(isinstance(t, Tool) for t in tools)


@pytest.mark.asyncio
async def test_connector_discover_sets_base_url(example_spec_path):
    connector = OpenApiConnector(
        namespace="test",
        source=str(example_spec_path),
    )
    tools = await connector.discover()
    for tool in tools:
        assert tool.execution.base_url  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_connector_execute(example_spec_path):
    import respx
    import httpx

    connector = OpenApiConnector(
        namespace="test",
        source=str(example_spec_path),
        base_url="https://api.example.com/v1",
    )
    await connector.discover()

    with respx.mock:
        respx.get("https://api.example.com/v1/users").mock(
            return_value=httpx.Response(200, json={"users": [], "total": 0})
        )
        result = await connector.execute("test.listUsers", {})

    assert result["status_code"] == 200
    assert result["success"] is True


@pytest.mark.asyncio
async def test_connector_execute_unknown_tool(example_spec_path):
    connector = OpenApiConnector(
        namespace="test",
        source=str(example_spec_path),
    )
    await connector.discover()

    with pytest.raises(KeyError):
        await connector.execute("test.nonexistent", {})
