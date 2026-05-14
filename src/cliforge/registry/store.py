"""
Registry: stores connector configs and tool metadata.
Reloads connectors on startup and supports refresh.
"""

import logging
from pathlib import Path
from typing import Any

from cliforge.models.schema import ConnectorConfig
from cliforge.models.tool import Tool
from cliforge.registry.persistence import PersistenceManager

logger = logging.getLogger(__name__)

CONNECTORS_FILE = "connectors.json"
TOOLS_CACHE_FILE = "registry.json"


class Registry:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._persistence = PersistenceManager(base_dir)
        self._connectors: dict[str, ConnectorConfig] = {}
        self._tools: dict[str, Tool] = {}
        self._loaded = False

    def load(self) -> None:
        raw = self._persistence.load(CONNECTORS_FILE)
        for ns, data in raw.items():
            try:
                self._connectors[ns] = ConnectorConfig(**data)
            except Exception as exc:
                logger.warning("Skipping invalid connector config for %s: %s", ns, exc)

        cached = self._persistence.load(TOOLS_CACHE_FILE)
        for tool_id, tool_data in cached.items():
            try:
                self._tools[tool_id] = Tool(**tool_data)
            except Exception as exc:
                logger.warning("Skipping invalid cached tool %s: %s", tool_id, exc)

        self._loaded = True

    def save(self) -> None:
        connectors_raw = {ns: cfg.model_dump() for ns, cfg in self._connectors.items()}
        self._persistence.save(CONNECTORS_FILE, connectors_raw)

        tools_raw = {tid: tool.model_dump() for tid, tool in self._tools.items()}
        self._persistence.save(TOOLS_CACHE_FILE, tools_raw)

    def add_connector(self, config: ConnectorConfig) -> None:
        self._connectors[config.namespace] = config
        self.save()

    def remove_connector(self, namespace: str) -> None:
        self._connectors.pop(namespace, None)
        for tool_id in list(self._tools.keys()):
            if tool_id.startswith(f"{namespace}."):
                self._tools.pop(tool_id)
        self.save()

    def get_connectors(self) -> list[ConnectorConfig]:
        return list(self._connectors.values())

    def get_connector(self, namespace: str) -> ConnectorConfig | None:
        return self._connectors.get(namespace)

    def cache_tools(self, tools: list[Tool]) -> None:
        for tool in tools:
            self._tools[tool.id] = tool
        self.save()

    def get_tools(self, namespace: str | None = None) -> list[Tool]:
        tools = list(self._tools.values())
        if namespace:
            tools = [t for t in tools if t.namespace == namespace]
        return sorted(tools, key=lambda t: t.id)

    def get_tool(self, tool_id: str) -> Tool | None:
        return self._tools.get(tool_id)

    def get_tool_by_name(self, namespace: str, name: str) -> Tool | None:
        return self._tools.get(f"{namespace}.{name}")

    def has_connector(self, namespace: str) -> bool:
        return namespace in self._connectors

    @property
    def base_dir(self) -> Path:
        return self._persistence.base_dir
