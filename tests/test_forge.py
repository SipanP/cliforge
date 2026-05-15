"""Tests for the forge command."""

import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cliforge.cli.app import app

runner = CliRunner()


def test_forge_creates_script(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 0, result.output
    script = install_dir / "myapi-cmd"
    assert script.exists()
    content = script.read_text()
    assert "cliforge myapi" in content


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-only chmod test")
def test_forge_script_is_executable(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])

    script = install_dir / "myapi-cmd"
    assert script.stat().st_mode & stat.S_IXUSR


def test_forge_refuses_overwrite_without_force(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(
            app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_forge_force_overwrites(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(
            app,
            ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir), "--force"],
        )

    assert result.exit_code == 0


def test_forge_unknown_namespace(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "nope", "cmd"])
    assert result.exit_code == 1
    assert "not registered" in result.output


def test_forge_dry_run(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir), "--dry-run"]
        )

    assert result.exit_code == 0
    assert "cliforge myapi" in result.output
    assert not (install_dir / "myapi-cmd").exists()


def test_forge_script_content(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])

    script = install_dir / "myapi-cmd"
    content = script.read_text()
    assert "myapi" in content
    assert "myapi-cmd" in content
