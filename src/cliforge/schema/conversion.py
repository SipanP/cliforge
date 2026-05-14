"""
Converts OpenAPI parameter lists and requestBody into a single merged JSON Schema object.
"""

from typing import Any


def _resolve_ref(ref: str, components: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref like '#/components/schemas/Foo' against the components dict."""
    if not ref.startswith("#/"):
        return {}
    parts = ref.lstrip("#/").split("/")
    node: Any = {"components": components}
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return dict(node) if isinstance(node, dict) else {}


def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], components)
        return _resolve_schema(resolved, components)
    return schema


def openapi_params_to_json_schema(
    parameters: list[dict[str, Any]],
    request_body: dict[str, Any] | None,
    components: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge OpenAPI parameters and requestBody into one flat JSON Schema.

    Path and query parameters become top-level properties.
    JSON requestBody properties are merged in at the top level.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in parameters:
        if "$ref" in param:
            param = _resolve_schema(param, components)

        name: str = param.get("name", "")
        location: str = param.get("in", "query")
        param_required: bool = param.get("required", False)
        schema: dict[str, Any] = param.get("schema", {"type": "string"})
        schema = _resolve_schema(schema, components)

        prop: dict[str, Any] = dict(schema)
        if param.get("description"):
            prop["description"] = param["description"]
        prop["x-param-in"] = location

        properties[name] = prop
        if param_required or location == "path":
            required.append(name)

    if request_body:
        content: dict[str, Any] = request_body.get("content", {})
        body_required: bool = request_body.get("required", False)

        json_content = content.get("application/json", {})
        body_schema = json_content.get("schema", {})
        body_schema = _resolve_schema(body_schema, components)

        if body_schema.get("type") == "object" or "properties" in body_schema:
            body_props: dict[str, Any] = body_schema.get("properties", {})
            body_req: list[str] = body_schema.get("required", [])
            for prop_name, prop_schema in body_props.items():
                prop_schema = _resolve_schema(prop_schema, components)
                prop_entry = dict(prop_schema)
                prop_entry["x-param-in"] = "body"
                properties[prop_name] = prop_entry
                if prop_name in body_req:
                    required.append(prop_name)
        elif body_schema:
            properties["body"] = {**_resolve_schema(body_schema, components), "x-param-in": "body"}
            if body_required:
                required.append("body")

    schema_out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema_out["required"] = sorted(set(required))
    return schema_out


def split_input_by_location(
    input_data: dict[str, Any],
    input_schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Given flat input_data and the merged input_schema, split into:
      (path_params, query_params, body_params)
    """
    path_params: dict[str, Any] = {}
    query_params: dict[str, Any] = {}
    body_params: dict[str, Any] = {}

    properties = input_schema.get("properties", {})

    for key, value in input_data.items():
        location = properties.get(key, {}).get("x-param-in", "query")
        if location == "path":
            path_params[key] = value
        elif location == "body":
            body_params[key] = value
        else:
            query_params[key] = value

    return path_params, query_params, body_params
