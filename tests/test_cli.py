"""Tests for the CLI layer."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cliforge.cli.app import app
from cliforge.main import app as main_app


runner = CliRunner()


def test_help_output():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "cliforge" in result.output.lower() or "usage" in result.output.lower()


def test_tools_help():
    result = runner.invoke(app, ["tools", "--help"])
    assert result.exit_code == 0


def test_add_help():
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0


def test_add_openapi_help():
    result = runner.invoke(app, ["add", "openapi", "--help"])
    assert result.exit_code == 0


def test_tools_empty_registry(tmp_path):
    with patch("cliforge.registry.persistence.DEFAULT_DIR", tmp_path / ".cliforge"):
        result = runner.invoke(app, ["tools"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 0


def test_add_openapi_and_list_tools(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        assert result.exit_code == 0, result.output

        result = runner.invoke(app, ["tools"])
        assert result.exit_code == 0
        tools = json.loads(result.output)
        assert any(t["namespace"] == "myapi" for t in tools)
        assert any(t["name"] == "listUsers" for t in tools)


def test_inspect_tool(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["inspect", "myapi", "listUsers"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "listUsers"
        assert data["namespace"] == "myapi"


def test_schema_command(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["schema", "myapi", "listUsers"])
        assert result.exit_code == 0
        schema = json.loads(result.output)
        assert schema["type"] == "object"
        assert "properties" in schema


def test_inspect_nonexistent_tool(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["inspect", "nons", "nontool"])
        assert result.exit_code == 1


def test_schema_nonexistent_tool(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["schema", "nons", "nontool"])
        assert result.exit_code == 1


def test_tools_output_json(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["tools", "--output", "json"])
        assert result.exit_code == 0
        tools = json.loads(result.output)
        assert isinstance(tools, list)


def test_connectors_list(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["connectors", "list"])
        assert result.exit_code == 0
        connectors = json.loads(result.output)
        assert any(c["namespace"] == "myapi" for c in connectors)


def test_connectors_remove(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])

        result = runner.invoke(app, ["connectors", "remove", "myapi"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["tools"])
        tools = json.loads(result.output)
        assert not any(t["namespace"] == "myapi" for t in tools)


def test_schema_output_deterministic(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result1 = runner.invoke(app, ["schema", "myapi", "listUsers"])
        result2 = runner.invoke(app, ["schema", "myapi", "listUsers"])
        assert result1.output == result2.output


def test_add_openapi_persists_base_url_in_metadata(tmp_path, example_spec_path):
    """add openapi always stores the resolved base_url in connector metadata."""
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])

    import json
    connectors = json.loads((registry_dir / "connectors.json").read_text())
    assert "base_url" in connectors["myapi"]["metadata"]
    assert connectors["myapi"]["metadata"]["base_url"].startswith("http")


def test_executor_fails_fast_on_invalid_url():
    """Executor raises immediately (no retries) when the URL has no http/https scheme."""
    import pytest
    import asyncio
    from cliforge.connectors.openapi.executor import execute_openapi
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="test.bad",
        namespace="test",
        name="bad",
        input_schema={"type": "object", "properties": {}},
        execution=OpenApiExecution(
            base_url="/api/v3",  # missing scheme — simulates stale cache
            path="/pet",
            method="GET",
        ),
    )

    with pytest.raises(RuntimeError, match="missing an http/https scheme"):
        asyncio.run(execute_openapi(tool, {}))


def test_root_help_shows_direct_execution_hint(tmp_path, example_spec_path):
    """Root help output explains direct namespace execution when connectors are registered."""
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "directly" in result.output.lower() or "namespace" in result.output.lower()
    assert "myapi" in result.output
