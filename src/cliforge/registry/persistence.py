"""Persistent storage for the CliForge registry."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path.home() / ".cliforge"


class PersistenceManager:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or DEFAULT_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        return self.base_dir / filename

    def load(self, filename: str) -> dict[str, Any]:
        p = self._path(filename)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s: %s", p, exc)
            return {}

    def save(self, filename: str, data: dict[str, Any]) -> None:
        p = self._path(filename)
        p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def delete(self, filename: str) -> None:
        p = self._path(filename)
        if p.exists():
            p.unlink()
