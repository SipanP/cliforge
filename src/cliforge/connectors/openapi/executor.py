"""Execute OpenAPI operations via httpx."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from cliforge.models.tool import OpenApiExecution, Tool
from cliforge.schema.conversion import split_input_by_location

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

# Auth header names whose values should be redacted in dry-run / log output.
_SENSITIVE_HEADERS = {"authorization", "x-api-key", "api-key", "x-auth-token"}


def _build_url(base_url: str, path: str, path_params: dict[str, Any]) -> str:
    url = base_url.rstrip("/") + path
    for key, value in path_params.items():
        url = url.replace(f"{{{key}}}", str(value))
    return url


def build_request_info(
    tool: Tool,
    input_data: dict[str, Any],
    auth_headers: dict[str, str] | None = None,
    redact_auth: bool = False,
) -> dict[str, Any]:
    """Return the request that would be sent, without executing it."""
    execution: OpenApiExecution = tool.execution  # type: ignore[assignment]
    path_params, query_params, body_params = split_input_by_location(
        input_data, tool.input_schema
    )
    url = _build_url(execution.base_url, execution.path, path_params)
    method = execution.method.upper()

    headers: dict[str, str] = {"Accept": "application/json"}
    if auth_headers:
        headers.update(auth_headers)
    if body_params and method in {"POST", "PUT", "PATCH"}:
        headers["Content-Type"] = "application/json"

    if redact_auth:
        headers = {
            k: ("[redacted]" if k.lower() in _SENSITIVE_HEADERS else v)
            for k, v in headers.items()
        }

    return {
        "method": method,
        "url": url,
        "query_params": query_params or None,
        "headers": headers,
        "body": body_params or None,
    }


def _log_request(
    tool: Tool,
    method: str,
    url: str,
    status_code: int,
    success: bool,
    duration_ms: float,
) -> None:
    """Append a one-line JSON entry to ~/.cliforge/logs/<namespace>/YYYY-MM-DD.log."""
    try:
        from cliforge.registry.persistence import DEFAULT_DIR
        log_dir = DEFAULT_DIR / "logs" / tool.namespace
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{datetime.now(timezone.utc).date()}.log"
        entry = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool.id,
            "method": method,
            "url": url,
            "status_code": status_code,
            "success": success,
            "duration_ms": round(duration_ms, 1),
        })
        with log_file.open("a") as f:
            f.write(entry + "\n")
    except Exception:
        pass  # logging must never break execution


async def execute_openapi(
    tool: Tool,
    input_data: dict[str, Any],
    auth_headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    req = build_request_info(tool, input_data, auth_headers, redact_auth=False)

    url = req["url"]
    if not url.startswith(("http://", "https://")):
        raise RuntimeError(
            f"Invalid URL for '{tool.name}': '{url}' is missing an http/https scheme.\n"
            f"  The connector's base URL may be stale. Fix it with:\n"
            f"    cliforge refresh {tool.namespace}"
        )

    method = req["method"]
    headers = req["headers"]

    last_error: Exception | None = None
    for attempt in range(DEFAULT_RETRIES):
        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                kwargs: dict[str, Any] = {
                    "headers": headers,
                    "params": req["query_params"],
                }
                if req["body"] and method in {"POST", "PUT", "PATCH"}:
                    kwargs["json"] = req["body"]

                response = await client.request(method, url, **kwargs)

            duration_ms = (time.monotonic() - t0) * 1000
            logger.debug("HTTP %s %s -> %s", method, url, response.status_code)
            _log_request(tool, method, url, response.status_code, response.is_success, duration_ms)

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
            logger.debug("Attempt %d failed: %s", attempt + 1, exc)
            if attempt < DEFAULT_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2**attempt)

    raise RuntimeError(
        f"All {DEFAULT_RETRIES} attempts failed: {last_error}\n"
        f"  If the connector's base URL is stale, run: cliforge refresh {tool.namespace}"
    )

