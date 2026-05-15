"""OpenAPI Connector: discover and execute tools from an OpenAPI 3.x spec."""

import logging
from typing import Any

from cliforge.connectors.openapi.executor import execute_openapi
from cliforge.connectors.openapi.loader import load_spec
from cliforge.connectors.openapi.parser import parse_spec
from cliforge.models.tool import Tool

logger = logging.getLogger(__name__)


def _detect_base_url(spec: dict[str, Any], source: str) -> str:
    from urllib.parse import urlparse

    servers: list[dict[str, Any]] = spec.get("servers", [])
    if servers:
        url = servers[0].get("url", "").rstrip("/")
        if url.startswith("http://") or url.startswith("https://"):
            return url
        # Relative server path (e.g. "/api/v3") — resolve against the source origin
        if url and (source.startswith("http://") or source.startswith("https://")):
            parsed = urlparse(source)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
        # Relative with no resolvable origin — warn and fall through
        if url:
            logger.warning(
                "Server URL '%s' is relative and source is a local file. "
                "Use --base-url to set an explicit base URL.",
                url,
            )

    if source.startswith("http://") or source.startswith("https://"):
        parsed = urlparse(source)
        return f"{parsed.scheme}://{parsed.netloc}"

    return "http://localhost"


class OpenApiConnector:
    def __init__(
        self,
        namespace: str,
        source: str,
        base_url: str | None = None,
        auth_headers: dict[str, str] | None = None,
    ) -> None:
        self.namespace = namespace
        self.source = source
        self._base_url = base_url
        self.base_url: str | None = base_url  # resolved after discover()
        self.auth_headers = auth_headers or {}
        self._tools: dict[str, Tool] = {}
        self._spec: dict[str, Any] | None = None

    async def discover(self) -> list[Tool]:
        self._spec = await load_spec(self.source)
        self.base_url = self._base_url or _detect_base_url(self._spec, self.source)
        tools = parse_spec(self._spec, self.namespace, self.base_url)
        self._tools = {t.id: t for t in tools}
        logger.info("Discovered %d tools from %s", len(tools), self.source)
        return tools

    async def execute(self, tool_id: str, input_data: dict) -> dict:
        if tool_id not in self._tools:
            raise KeyError(f"Tool not found: {tool_id}")
        tool = self._tools[tool_id]
        return await execute_openapi(tool, input_data, self.auth_headers)

    def get_tool(self, tool_id: str) -> Tool:
        return self._tools[tool_id]
