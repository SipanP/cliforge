"""End-to-end tests: full CLI workflow."""

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from cliforge.cli.app import app

runner = CliRunner()
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_full_workflow_openapi(tmp_path):
    """Full workflow: add connector, list tools, inspect, schema."""
    spec_path = FIXTURES_DIR / "example_api.yaml"
    registry_dir = tmp_path / ".cliforge"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        # Add connector
        result = runner.invoke(app, ["add", "openapi", "example", str(spec_path)])
        assert result.exit_code == 0, result.output

        # List tools
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        tools = json.loads(result.output)
        assert len(tools) > 0
        tool_names = [t["name"] for t in tools]
        assert "listUsers" in tool_names
        assert "createUser" in tool_names

        # Inspect a tool
        result = runner.invoke(app, ["inspect", "example", "listUsers"])
        assert result.exit_code == 0
        detail = json.loads(result.output)
        assert detail["name"] == "listUsers"
        assert "input_schema" in detail

        # Schema inspection
        result = runner.invoke(app, ["schema", "example", "createUser"])
        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "email" in schema["properties"]


def test_registry_persistence(tmp_path):
    """Connectors and tools persist across registry reloads."""
    spec_path = FIXTURES_DIR / "example_api.yaml"
    registry_dir = tmp_path / ".cliforge"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "persist_test", str(spec_path)])

    # Reload registry from disk
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        tools = json.loads(result.output)
        assert any(t["namespace"] == "persist_test" for t in tools)


def test_connector_reload(tmp_path):
    """Refreshing a connector re-discovers tools."""
    spec_path = FIXTURES_DIR / "example_api.yaml"
    registry_dir = tmp_path / ".cliforge"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(spec_path)])
        result = runner.invoke(app, ["refresh", "myapi"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["tools"])
        tools = json.loads(result.output)
        assert any(t["namespace"] == "myapi" for t in tools)


@respx.mock
def test_e2e_execute_tool(tmp_path):
    """Dynamic dispatch executes a tool against a mocked API."""
    from cliforge.cli.dynamic import dispatch_tool_command
    from cliforge.connectors.openapi import OpenApiConnector
    from cliforge.registry.store import Registry
    import anyio

    spec_path = FIXTURES_DIR / "example_api.yaml"
    registry_dir = tmp_path / ".cliforge"

    respx.get("https://api.example.com/v1/users").mock(
        return_value=httpx.Response(200, json={"users": [], "total": 0})
    )

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        registry = Registry()
        runner.invoke(app, ["add", "openapi", "example", str(spec_path),
                            "--base-url", "https://api.example.com/v1"])
        registry.load()
        tool = registry.get_tool_by_name("example", "listUsers")
        assert tool is not None

        connector = OpenApiConnector(
            namespace="example",
            source=str(spec_path),
            base_url="https://api.example.com/v1",
        )
        anyio.run(connector.discover)
        outputs = []

        import io
        import sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            dispatch_tool_command(tool, connector, [], "json")
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        data = json.loads(output)
        assert "status_code" in data or "data" in data
