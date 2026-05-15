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


def test_executor_retry_hint_on_transport_failure():
    """All-retries-failed error includes cliforge refresh hint."""
    import asyncio
    import httpx
    from cliforge.connectors.openapi.executor import execute_openapi
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="test.flaky",
        namespace="mynamespace",
        name="flaky",
        input_schema={"type": "object", "properties": {}},
        execution=OpenApiExecution(
            base_url="http://localhost:19999",
            path="/flaky",
            method="GET",
        ),
    )

    with patch("httpx.AsyncClient.request", side_effect=httpx.ConnectError("refused")):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(execute_openapi(tool, {}))

    assert "mynamespace" in str(exc_info.value)
    assert "refresh" in str(exc_info.value)


def test_preflight_missing_required_exits_code_1():
    """dispatch_tool_command exits 1 before sending HTTP when required params are missing."""
    from cliforge.cli.dynamic import dispatch_tool_command
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="t.createUser",
        namespace="t",
        name="createUser",
        input_schema={
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string", "x-param-in": "body"},
                "email": {"type": "string", "x-param-in": "body"},
            },
        },
        execution=OpenApiExecution(
            base_url="https://api.example.com/v1", path="/users", method="POST"
        ),
    )
    import click
    # Passing None as connector — if we reach execute() the test will blow up,
    # confirming the pre-flight intercepted it first.
    with pytest.raises(click.exceptions.Exit) as exc_info:
        dispatch_tool_command(tool, None, [], "json")
    assert exc_info.value.exit_code == 1


def test_preflight_passes_when_no_required_params():
    """dispatch_tool_command does not exit pre-flight when all params are optional."""
    from cliforge.cli.dynamic import dispatch_tool_command
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="t.listUsers",
        namespace="t",
        name="listUsers",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "x-param-in": "query"},
            },
        },
        execution=OpenApiExecution(
            base_url="https://api.example.com/v1", path="/users", method="GET"
        ),
    )

    class FakeConnector:
        async def execute(self, tool_id: str, input_data: dict) -> dict:
            return {"status_code": 200, "data": {"users": []}, "success": True}

    import io, sys
    buf = io.StringIO()
    old_stdout, sys.stdout = sys.stdout, buf
    try:
        dispatch_tool_command(tool, FakeConnector(), [], "json")
    finally:
        sys.stdout = old_stdout
    # If we got here without SystemExit, pre-flight passed correctly


def test_format_execution_result_success_shows_only_data(capsys):
    """Successful execution result shows just the data, not the status_code wrapper."""
    from cliforge.cli.formatting import format_execution_result
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="t.op",
        namespace="t",
        name="op",
        input_schema={"type": "object", "properties": {}},
        execution=OpenApiExecution(base_url="https://api.example.com/v1", path="/x", method="GET"),
    )
    result = {"status_code": 200, "data": {"users": [], "total": 0}, "success": True}
    format_execution_result(result, "json", tool)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "users" in data
    assert "status_code" not in data


def test_format_execution_result_error_shows_status_and_message():
    """Non-success response is summarised: status + message, nothing dumped to stdout."""
    from io import StringIO
    from rich.console import Console
    from cliforge.cli.formatting import format_execution_result
    from cliforge.models.tool import Tool, OpenApiExecution

    tool = Tool(
        id="t.op",
        namespace="t",
        name="op",
        input_schema={"type": "object", "properties": {}},
        execution=OpenApiExecution(base_url="https://api.example.com/v1", path="/x", method="POST"),
    )
    result = {
        "status_code": 400,
        "data": {"message": "name is required", "code": 400},
        "success": False,
    }
    err_buf = StringIO()
    fake_err = Console(file=err_buf, highlight=False, markup=False)
    with patch("cliforge.cli.formatting.err_console", fake_err):
        import io, sys
        out_buf = io.StringIO()
        old_stdout, sys.stdout = sys.stdout, out_buf
        try:
            format_execution_result(result, "json", tool)
        finally:
            sys.stdout = old_stdout

    err_text = err_buf.getvalue()
    assert "400" in err_text
    assert "name is required" in err_text
    assert out_buf.getvalue().strip() == ""


def test_coerce_array_json_syntax():
    """_coerce_value parses a proper JSON array string."""
    from cliforge.cli.dynamic import _coerce_value
    result = _coerce_value('["https://example.com/a.jpg", "b.jpg"]', "array")
    assert result == ["https://example.com/a.jpg", "b.jpg"]


def test_coerce_array_bare_string():
    """_coerce_value wraps a bare string as a single-element array."""
    from cliforge.cli.dynamic import _coerce_value
    result = _coerce_value("https://example.com/pic.jpg", "array")
    assert result == ["https://example.com/pic.jpg"]


def test_coerce_array_comma_separated():
    """_coerce_value splits comma-separated values into an array."""
    from cliforge.cli.dynamic import _coerce_value
    result = _coerce_value("foo,bar,baz", "array")
    assert result == ["foo", "bar", "baz"]


def test_coerce_array_single_quoted_falls_back():
    """_coerce_value treats single-quoted Python-style lists as bare strings (no crash)."""
    from cliforge.cli.dynamic import _coerce_value
    # Single-quoted JSON is invalid; should not raise
    result = _coerce_value("['url']", "array")
    assert isinstance(result, list)
    assert len(result) == 1


def test_preflight_exit_produces_no_spurious_error_line():
    """A pre-flight validation failure must not print a bare 'Error:' line via main()."""
    import io, sys
    from unittest.mock import patch as _patch
    from cliforge.models.tool import Tool, OpenApiExecution
    from cliforge.registry.store import Registry

    tool = Tool(
        id="t.createUser",
        namespace="t",
        name="createUser",
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string", "x-param-in": "body"}},
        },
        execution=OpenApiExecution(
            base_url="https://api.example.com/v1", path="/users", method="POST"
        ),
    )

    # Patch handle_dynamic_dispatch to simulate the pre-flight Exit being raised.
    import click
    def _fake_dispatch(args):
        raise click.exceptions.Exit(code=1)

    stderr_buf = io.StringIO()
    with _patch("cliforge.main.handle_dynamic_dispatch", _fake_dispatch):
        with _patch("sys.argv", ["cliforge", "t", "createUser"]):
            with pytest.raises(SystemExit) as exc_info:
                with _patch("sys.stderr", stderr_buf):
                    from cliforge.main import main
                    main()
    assert exc_info.value.code == 1
    # The generic "Error: " line must NOT appear
    assert stderr_buf.getvalue().strip() == ""


def test_root_help_shows_direct_execution_hint(tmp_path, example_spec_path):
    """Root help output explains direct namespace execution when connectors are registered."""
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "directly" in result.output.lower() or "namespace" in result.output.lower()
    assert "myapi" in result.output
