"""Tests for the forge command group."""

import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cliforge.cli.app import app
from cliforge.main import main

runner = CliRunner()


# ---------------------------------------------------------------------------
# forge create
# ---------------------------------------------------------------------------

def test_forge_creates_script(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
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
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])

    script = install_dir / "myapi-cmd"
    assert script.stat().st_mode & stat.S_IXUSR


def test_forge_refuses_overwrite_without_force(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 1
    assert "already forged" in result.output


def test_forge_refuses_overwrite_foreign_file(tmp_path, example_spec_path):
    """A file not created by cliforge gets a distinct error message."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"
    install_dir.mkdir(parents=True)
    foreign = install_dir / "myapi-cmd"
    foreign.write_text("#!/bin/sh\necho 'I am something else'\n")

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 1
    assert "not created by cliforge" in result.output


def test_forge_force_overwrites(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(
            app,
            ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir), "--force"],
        )

    assert result.exit_code == 0


def test_forge_unknown_namespace(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "create", "nope", "cmd"])
    assert result.exit_code == 1
    assert "not registered" in result.output


def test_forge_dry_run(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir), "--dry-run"]
        )

    assert result.exit_code == 0
    assert "cliforge myapi" in result.output
    assert not (install_dir / "myapi-cmd").exists()


def test_forge_script_content(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])

    script = install_dir / "myapi-cmd"
    content = script.read_text()
    assert "myapi" in content
    assert "myapi-cmd" in content


def test_forge_tracks_in_forged_json(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])

    import json
    forged_file = registry_dir / "forged.json"
    assert forged_file.exists()
    data = json.loads(forged_file.read_text())
    assert "myapi-cmd" in data
    assert data["myapi-cmd"]["namespace"] == "myapi"


# ---------------------------------------------------------------------------
# forge list
# ---------------------------------------------------------------------------

def test_forge_list_empty(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "list"])
    assert result.exit_code == 0
    assert "No forged commands" in result.output


def test_forge_list_shows_created(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(app, ["forge", "list"])

    assert result.exit_code == 0
    assert "myapi-cmd" in result.output
    assert "myapi" in result.output


def test_forge_list_json(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(app, ["forge", "list", "--output", "json"])

    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["command_name"] == "myapi-cmd"


# ---------------------------------------------------------------------------
# forge remove
# ---------------------------------------------------------------------------

def test_forge_remove(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(app, ["forge", "remove", "myapi-cmd"])

    assert result.exit_code == 0
    assert not (install_dir / "myapi-cmd").exists()


def test_forge_remove_untracked(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "remove", "nonexistent"])
    assert result.exit_code == 1
    assert "not tracked" in result.output


def test_forge_remove_keep_file(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(app, ["forge", "remove", "myapi-cmd", "--keep-file"])

    assert result.exit_code == 0
    assert (install_dir / "myapi-cmd").exists()


# ---------------------------------------------------------------------------
# forge config
# ---------------------------------------------------------------------------

def test_forge_config_show(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "config"])
    assert result.exit_code == 0
    assert "install dir" in result.output.lower()


def test_forge_config_set_default(tmp_path):
    registry_dir = tmp_path / ".cliforge"
    custom_dir = tmp_path / "custom-bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(
            app, ["forge", "config", "--default-install-dir", str(custom_dir)]
        )

    assert result.exit_code == 0
    assert str(custom_dir) in result.output

    import json
    cfg = json.loads((registry_dir / "config.json").read_text())
    assert cfg["forge"]["default_install_dir"] == str(custom_dir)


def test_forge_create_uses_configured_default(tmp_path, example_spec_path):
    registry_dir = tmp_path / ".cliforge"
    custom_dir = tmp_path / "custom-bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["forge", "config", "--default-install-dir", str(custom_dir)])
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd"])

    assert result.exit_code == 0, result.output
    assert (custom_dir / "myapi-cmd").exists()


def test_forge_set_default_via_create(tmp_path, example_spec_path):
    """--set-default on forge create saves the dir for future calls."""
    registry_dir = tmp_path / ".cliforge"
    custom_dir = tmp_path / "custom-bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(
            app,
            ["forge", "create", "myapi", "myapi-cmd",
             "--install-dir", str(custom_dir), "--set-default"],
        )
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd2"])

    assert (custom_dir / "myapi-cmd2").exists()


# ---------------------------------------------------------------------------
# Shorthand: namespace as default command name
# ---------------------------------------------------------------------------

def test_forge_namespace_as_default_command_name(tmp_path, example_spec_path):
    """forge create myapi (no command_name) creates a command called 'myapi'."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 0, result.output
    assert (install_dir / "myapi").exists()
    assert "cliforge myapi" in (install_dir / "myapi").read_text()


def test_forge_shorthand_routing(tmp_path, example_spec_path):
    """main() rewrites 'forge <namespace>' to 'forge create <namespace>' before typer."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        # Simulate what main() sees after rewriting: forge create myapi --install-dir ...
        # (The CliRunner invokes app directly, so we test the rewritten form.)
        result = runner.invoke(
            app,
            ["forge", "create", "myapi", "myapi",
             "--install-dir", str(install_dir)],
        )

    assert result.exit_code == 0, result.output
    assert (install_dir / "myapi").exists()


def test_forge_main_rewriting(tmp_path, example_spec_path, capsys):
    """main() arg rewriting: 'forge myapi' arrives at forge_create as 'forge create myapi'."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])

    from cliforge import main as main_module
    with (
        patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir),
        patch.object(sys, "argv", ["cliforge", "forge", "myapi", "--install-dir", str(install_dir)]),
    ):
        try:
            main_module.main()
        except SystemExit:
            pass

    assert (install_dir / "myapi").exists()


# ---------------------------------------------------------------------------
# Error message suggestions
# ---------------------------------------------------------------------------

def test_forge_unknown_namespace_suggests_alternatives(tmp_path, example_spec_path):
    """Error for unknown namespace lists registered namespaces as suggestions."""
    registry_dir = tmp_path / ".cliforge"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(app, ["forge", "create", "nope", "cmd"])

    assert result.exit_code == 1
    assert "not registered" in result.output
    assert "myapi" in result.output  # falls back to full list when no close match


def test_forge_unknown_namespace_fuzzy_orders_by_similarity(tmp_path, example_spec_path):
    """A near-typo of a registered namespace appears as the top suggestion."""
    registry_dir = tmp_path / ".cliforge"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["add", "openapi", "petstore", str(example_spec_path)])
        # 'myap' is a near-match for 'myapi'; 'petstore' should not appear before it
        result = runner.invoke(app, ["forge", "create", "myap", "cmd"])

    assert result.exit_code == 1
    myapi_pos = result.output.find("myapi")
    petstore_pos = result.output.find("petstore")
    assert myapi_pos != -1
    # myapi should appear before petstore (or petstore may not appear at all)
    assert myapi_pos < petstore_pos or petstore_pos == -1


def test_forge_unknown_namespace_no_connectors(tmp_path):
    """Error for unknown namespace explains how to add one when registry is empty."""
    registry_dir = tmp_path / ".cliforge"
    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        result = runner.invoke(app, ["forge", "create", "nope", "cmd"])

    assert result.exit_code == 1
    assert "not registered" in result.output
    assert "add" in result.output.lower()  # suggests cliforge add


def test_forge_remove_unknown_suggests_alternatives(tmp_path, example_spec_path):
    """Error for unknown remove target lists tracked commands as suggestions."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(app, ["forge", "remove", "nope"])

    assert result.exit_code == 1
    assert "not tracked" in result.output
    assert "myapi-cmd" in result.output  # falls back to full list when no close match


def test_forge_remove_fuzzy_orders_by_similarity(tmp_path, example_spec_path):
    """A near-typo of a tracked command appears as the top suggestion."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "gh", "--install-dir", str(install_dir)])
        runner.invoke(app, ["forge", "create", "myapi", "petstore", "--install-dir", str(install_dir)])
        # 'g' is closer to 'gh' than to 'petstore'
        result = runner.invoke(app, ["forge", "remove", "gx"])

    assert result.exit_code == 1
    gh_pos = result.output.find("gh")
    petstore_pos = result.output.find("petstore")
    assert gh_pos != -1
    assert gh_pos < petstore_pos or petstore_pos == -1


def test_forge_already_forged_error_shows_reforge_hint(tmp_path, example_spec_path):
    """Re-forge error message shows the exact --force command to run."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        runner.invoke(app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 1
    assert "--force" in result.output


def test_forge_foreign_file_error_shows_force_hint(tmp_path, example_spec_path):
    """Overwrite-foreign-file error message shows the --force command with a caution note."""
    registry_dir = tmp_path / ".cliforge"
    install_dir = tmp_path / "bin"
    install_dir.mkdir(parents=True)
    (install_dir / "myapi-cmd").write_text("#!/bin/sh\necho foreign\n")

    with patch("cliforge.registry.persistence.DEFAULT_DIR", registry_dir):
        runner.invoke(app, ["add", "openapi", "myapi", str(example_spec_path)])
        result = runner.invoke(
            app, ["forge", "create", "myapi", "myapi-cmd", "--install-dir", str(install_dir)]
        )

    assert result.exit_code == 1
    assert "--force" in result.output
    assert "caution" in result.output.lower() or "Caution" in result.output
