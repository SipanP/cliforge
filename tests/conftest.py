"""Shared test fixtures."""

import json
from pathlib import Path

import pytest
import pytest_asyncio

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_spec_path() -> Path:
    return FIXTURES_DIR / "example_api.yaml"


@pytest.fixture
def minimal_spec_path() -> Path:
    return FIXTURES_DIR / "minimal_api.json"


@pytest.fixture
def tmp_registry_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".cliforge"
    d.mkdir()
    return d


@pytest.fixture
def example_tool_data() -> dict:
    return {
        "id": "test.listUsers",
        "namespace": "test",
        "name": "listUsers",
        "description": "List all users",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "x-param-in": "query"},
                "offset": {"type": "integer", "x-param-in": "query"},
            },
        },
        "output_schema": None,
        "execution": {
            "type": "openapi",
            "base_url": "https://api.example.com/v1",
            "path": "/users",
            "method": "GET",
            "operation_id": "listUsers",
        },
        "metadata": {},
    }
