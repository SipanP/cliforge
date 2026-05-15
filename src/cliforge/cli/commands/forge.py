"""cliforge forge — generate a standalone command wrapper for a namespace."""

import os
import stat
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

console = Console()

_SHELL_SCRIPT = """\
#!/bin/sh
# Forged by cliforge: {namespace} -> {command_name}
# Usage: {command_name} [<tool>] [--flags]
#   {command_name}                  list available tools
#   {command_name} <tool> --help    show parameters for a tool
#   {command_name} <tool> [--flags] execute a tool
exec cliforge {namespace} "$@"
"""

_BAT_SCRIPT = """\
@echo off
rem Forged by cliforge: {namespace} -> {command_name}
cliforge {namespace} %*
"""


def _write_script(namespace: str, command_name: str, target: Path) -> None:
    if sys.platform == "win32":
        script = _BAT_SCRIPT.format(namespace=namespace, command_name=command_name)
    else:
        script = _SHELL_SCRIPT.format(namespace=namespace, command_name=command_name)

    target.write_text(script, encoding="utf-8")

    if sys.platform != "win32":
        current = target.stat().st_mode
        target.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _default_install_dir() -> Path:
    if sys.platform == "win32":
        # %LOCALAPPDATA%\Programs\cliforge  (usually on PATH after install)
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "Programs" / "cliforge"
    return Path.home() / ".local" / "bin"


def _is_on_path(directory: Path) -> bool:
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    return str(directory) in path_entries or str(directory.resolve()) in path_entries


def forge(
    namespace: str = typer.Argument(..., help="Registered namespace to wrap"),
    command_name: str = typer.Argument(..., help="Name for the generated command"),
    install_dir: str = typer.Option(
        None, "--install-dir", "-d",
        help="Directory to install into (default: ~/.local/bin)",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if already exists"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the script without installing"),
) -> None:
    """
    Generate a standalone command that wraps a registered namespace.

    \b
    Example:
        cliforge forge github gh
        gh listUsers --limit 10
        gh addPet --help
    """
    from cliforge.cli.formatting import print_error, print_info, print_success
    from cliforge.registry.store import Registry

    registry = Registry()
    registry.load()

    if not registry.has_connector(namespace):
        print_error(f"Namespace '{namespace}' is not registered.")
        console.print("  Run [bold]cliforge namespaces[/bold] to see registered namespaces.")
        raise typer.Exit(code=1)

    tools = registry.get_tools(namespace)
    script = _SHELL_SCRIPT if sys.platform != "win32" else _BAT_SCRIPT
    script = script.format(namespace=namespace, command_name=command_name)

    if dry_run:
        console.print(f"[dim]# Script that would be installed as '{command_name}':[/dim]\n")
        console.print(escape(script))
        return

    target_dir = Path(install_dir) if install_dir else _default_install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".bat" if sys.platform == "win32" else ""
    script_path = target_dir / f"{command_name}{suffix}"

    if script_path.exists() and not force:
        print_error(f"'{script_path}' already exists.")
        console.print("  Use [bold]--force[/bold] to overwrite.")
        raise typer.Exit(code=1)

    _write_script(namespace, command_name, script_path)

    print_success(f"Forged '{command_name}' → cliforge {namespace}")
    console.print(f"  [dim]Installed:[/dim]  [bold]{script_path}[/bold]")
    console.print(f"  [dim]Namespace:[/dim]  {namespace}  ({len(tools)} tools)\n")

    if not _is_on_path(target_dir):
        console.print(f"  [yellow]Warning:[/yellow] {target_dir} is not on your PATH.")
        if sys.platform != "win32":
            console.print(
                f"  Add it:  [bold]export PATH=\"{target_dir}:$PATH\"[/bold]  "
                f"[dim](or add to ~/.bashrc / ~/.zshrc)[/dim]\n"
            )

    console.print(f"  [dim]Try:[/dim]  [bold]{command_name}[/bold]              [dim]# list tools[/dim]")
    console.print(f"  [dim]Try:[/dim]  [bold]{command_name} <tool> --help[/bold]  [dim]# show parameters[/dim]")
    console.print(f"  [dim]Try:[/dim]  [bold]{command_name} <tool> [--flags][/bold]\n")
