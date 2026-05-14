"""
Utilities for inspecting JSON Schemas and deriving CLI flag information.
"""

from typing import Any


def schema_to_cli_params(input_schema: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Derive CLI parameter descriptors from a JSON Schema object.
    Returns a list of param dicts with: name, type, required, description, default.
    """
    params: list[dict[str, Any]] = []
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    for name, prop in properties.items():
        json_type = prop.get("type", "string")
        params.append(
            {
                "name": name,
                "type": json_type,
                "required": name in required,
                "description": prop.get("description", ""),
                "default": prop.get("default"),
                "enum": prop.get("enum"),
                "location": prop.get("x-param-in", "query"),
            }
        )
    return params


def json_type_to_python(json_type: str) -> type:
    mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, str)
