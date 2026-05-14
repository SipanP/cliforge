"""Execute OpenAPI operations via httpx."""

import logging
from typing import Any

import httpx

from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.schema.conversion import split_input_by_location

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3


def _build_url(base_url: str, path: str, path_params: dict[str, Any]) -> str:
    url = base_url.rstrip("/") + path
    for key, value in path_params.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url


async def execute_openapi(
    tool: Tool,
    input_data: dict[str, Any],
    auth_headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    execution: OpenApiExecution = tool.execution  # type: ignore[assignment]

    path_params, query_params, body_params = split_input_by_location(
        input_data, tool.input_schema
    )

    url = _build_url(execution.base_url, execution.path, path_params)
    method = execution.method.upper()
    headers: dict[str, str] = {"Accept": "application/json"}
    if auth_headers:
        headers.update(auth_headers)

    last_error: Exception | None = None
    for attempt in range(DEFAULT_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                kwargs: dict[str, Any] = {
                    "headers": headers,
                    "params": query_params or None,
                }
                if body_params and method in {"POST", "PUT", "PATCH"}:
                    kwargs["json"] = body_params
                    headers["Content-Type"] = "application/json"

                response = await client.request(method, url, **kwargs)

            logger.debug("HTTP %s %s -> %s", method, url, response.status_code)

            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}

            return {
                "status_code": response.status_code,
                "data": data,
                "success": response.is_success,
            }

        except httpx.TransportError as exc:
            last_error = exc
            logger.warning("Attempt %d failed: %s", attempt + 1, exc)
            if attempt < DEFAULT_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2**attempt)

    raise RuntimeError(f"All {DEFAULT_RETRIES} attempts failed: {last_error}")
