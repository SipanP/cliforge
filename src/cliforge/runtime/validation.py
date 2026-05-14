"""Input validation against JSON Schema."""

import jsonschema

from cliforge.models.tool import Tool


class ValidationError(Exception):
    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message)
        self.errors = errors


def validate_input(tool: Tool, input_data: dict) -> None:
    """Validate input_data against the tool's input_schema. Raises ValidationError on failure."""
    schema = tool.input_schema
    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(input_data))
    if errors:
        messages = [f"{'.'.join(str(p) for p in e.absolute_path) or 'root'}: {e.message}" for e in errors]
        raise ValidationError(
            f"Input validation failed for tool '{tool.id}': {'; '.join(messages)}",
            messages,
        )
