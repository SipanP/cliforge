"""Load and parse OpenAPI 3.x specs from local files or remote URLs."""

import json
from pathlib import Path
from typing import Any

import httpx
import yaml


async def load_spec(source: str) -> dict[str, Any]:
    """Load an OpenAPI spec from a file path or HTTP URL."""
    if source.startswith("http://") or source.startswith("https://"):
        return await _load_remote(source)
    return _load_local(source)


def _load_local(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    content = p.read_text(encoding="utf-8")
    if p.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(content)
    return json.loads(content)


async def _load_remote(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "yaml" in content_type or url.endswith((".yaml", ".yml")):
            return yaml.safe_load(response.text)
        return response.json()


def get_openapi_version(spec: dict[str, Any]) -> tuple[int, int]:
    version_str = spec.get("openapi", "3.0.0")
    parts = version_str.split(".")
    major = int(parts[0]) if parts else 3
    minor = int(parts[1]) if len(parts) > 1 else 0
    return major, minor
