"""Parse OpenAPI 3.x spec into Tool objects."""

import re
from typing import Any

from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.schema.conversion import openapi_params_to_json_schema

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def _make_tool_id(namespace: str, name: str) -> str:
    return f"{namespace}.{name}"


def _generate_operation_name(method: str, path: str) -> str:
    """Generate a deterministic name for operations without operationId."""
    clean = re.sub(r"[{}]", "", path)
    parts = [p for p in clean.split("/") if p]
    name_parts = [method.lower()] + parts
    camel = name_parts[0] + "".join(p.capitalize() for p in name_parts[1:])
    return re.sub(r"[^a-zA-Z0-9_]", "_", camel)


def parse_spec(
    spec: dict[str, Any],
    namespace: str,
    base_url: str,
) -> list[Tool]:
    tools: list[Tool] = []
    paths: dict[str, Any] = spec.get("paths", {})
    components: dict[str, Any] = spec.get("components", {})

    path_level_servers = None

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_parameters: list[dict[str, Any]] = path_item.get("parameters", [])

        for method in HTTP_METHODS:
            operation: dict[str, Any] | None = path_item.get(method)
            if not operation or not isinstance(operation, dict):
                continue

            operation_id: str | None = operation.get("operationId")
            name = operation_id or _generate_operation_name(method, path)

            all_parameters = list(path_parameters) + list(operation.get("parameters", []))
            request_body = operation.get("requestBody")

            input_schema = openapi_params_to_json_schema(
                all_parameters, request_body, components
            )

            responses: dict[str, Any] = operation.get("responses", {})
            output_schema: dict[str, Any] | None = _extract_output_schema(
                responses, components
            )

            tool_base_url = base_url
            if operation.get("servers"):
                tool_base_url = operation["servers"][0].get("url", base_url)

            tool = Tool(
                id=_make_tool_id(namespace, name),
                namespace=namespace,
                name=name,
                description=operation.get("description") or operation.get("summary"),
                input_schema=input_schema,
                output_schema=output_schema,
                execution=OpenApiExecution(
                    base_url=tool_base_url,
                    path=path,
                    method=method.upper(),
                    operation_id=operation_id,
                ),
                metadata={
                    "tags": operation.get("tags", []),
                    "deprecated": operation.get("deprecated", False),
                    "summary": operation.get("summary", ""),
                },
            )
            tools.append(tool)

    return tools


def _extract_output_schema(
    responses: dict[str, Any],
    components: dict[str, Any],
) -> dict[str, Any] | None:
    for status_code in ("200", "201", "default"):
        response = responses.get(status_code)
        if not response:
            continue
        if "$ref" in response:
            ref = response["$ref"]
            parts = ref.lstrip("#/").split("/")
            node: Any = {"components": components}
            for part in parts:
                node = node.get(part, {}) if isinstance(node, dict) else {}
            response = node

        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema")
        if schema:
            return schema
    return None
