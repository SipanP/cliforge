"""cliforge forge — generate and manage standalone namespace commands."""

import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()

forge_app = typer.Typer(help="Generate and manage standalone namespace commands.")

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

_MARKER_UNIX = "# Forged by cliforge:"
_MARKER_WIN = "rem Forged by cliforge:"


def _write_script(namespace: str, command_name: str, target: Path) -> None:
    if sys.platform == "win32":
        script = _BAT_SCRIPT.format(namespace=namespace, command_name=command_name)
    else:
        script = _SHELL_SCRIPT.format(namespace=namespace, command_name=command_name)

    target.write_text(script, encoding="utf-8")

    if sys.platform != "win32":
        current = target.stat().st_mode
        target.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _is_forged_by_us(path: Path) -> bool:
    """Return True if path looks like a script we created."""
    try:
        header = path.read_text(encoding="utf-8", errors="ignore")[:300]
        return _MARKER_UNIX in header or _MARKER_WIN in header
    except OSError:
        return False


def _default_install_dir() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "Programs" / "cliforge"
    return Path.home() / ".local" / "bin"


def _is_on_path(directory: Path) -> bool:
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    return str(directory) in path_entries or str(directory.resolve()) in path_entries


def _load_config() -> dict:
    from cliforge.registry.persistence import PersistenceManager
    return PersistenceManager().load("config.json")


def _save_config(data: dict) -> None:
    from cliforge.registry.persistence import PersistenceManager
    PersistenceManager().save("config.json", data)


def _get_configured_install_dir() -> Path | None:
    dir_str = _load_config().get("forge", {}).get("default_install_dir")
    return Path(dir_str).expanduser() if dir_str else None


def _load_forged() -> dict:
    from cliforge.registry.persistence import PersistenceManager
    return PersistenceManager().load("forged.json")


def _save_forged(data: dict) -> None:
    from cliforge.registry.persistence import PersistenceManager
    PersistenceManager().save("forged.json", data)


@forge_app.command("create")
def forge_create(
    namespace: str = typer.Argument(..., help="Registered namespace to wrap"),
    command_name: str = typer.Argument(..., help="Name for the generated command"),
    install_dir: str = typer.Option(
        None, "--install-dir", "-d",
        help="Directory to install into (overrides configured default)",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if already exists"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the script without installing"),
    set_default: bool = typer.Option(
        False, "--set-default",
        help="Save --install-dir as the new default for future forges",
    ),
) -> None:
    """
    Generate a standalone command that wraps a registered namespace.

    \b
    Example:
        cliforge forge create github gh
        gh listUsers --limit 10
        gh addPet --help
    """
    from cliforge.cli.formatting import print_error, print_success
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

    if install_dir:
        target_dir = Path(install_dir).expanduser()
        if set_default:
            cfg = _load_config()
            cfg.setdefault("forge", {})["default_install_dir"] = str(target_dir)
            _save_config(cfg)
            console.print(f"  [dim]Default install dir updated to:[/dim]  [bold]{target_dir}[/bold]")
    else:
        target_dir = _get_configured_install_dir() or _default_install_dir()

    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".bat" if sys.platform == "win32" else ""
    script_path = target_dir / f"{command_name}{suffix}"

    if script_path.exists() and not force:
        if _is_forged_by_us(script_path):
            print_error(f"'{command_name}' is already forged at '{script_path}'.")
            console.print("  Use [bold]--force[/bold] to re-forge it.")
        else:
            print_error(f"'{script_path}' already exists and was not created by cliforge.")
            console.print(
                "  Use [bold]--force[/bold] to overwrite it "
                "[dim](caution: this will replace an existing command)[/dim]."
            )
        raise typer.Exit(code=1)

    _write_script(namespace, command_name, script_path)

    forged = _load_forged()
    forged[command_name] = {
        "namespace": namespace,
        "command_name": command_name,
        "script_path": str(script_path),
        "install_dir": str(target_dir),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_forged(forged)

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


@forge_app.command("list")
def forge_list(
    output: str = typer.Option("table", "--output", "-o", help="Output format: json, table"),
) -> None:
    """List all forged commands."""
    forged = _load_forged()

    if not forged:
        console.print(
            "\n[dim]No forged commands yet. Create one with:[/dim] "
            "[bold]cliforge forge create <namespace> <command>[/bold]\n"
        )
        return

    if output == "json":
        from cliforge.cli.formatting import format_result
        format_result(list(forged.values()), output)
        return

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Namespace", style="green")
    table.add_column("Location", style="dim")
    table.add_column("Created", style="dim")

    for entry in sorted(forged.values(), key=lambda e: e["command_name"]):
        created = entry.get("created_at", "")[:10]
        table.add_row(
            entry["command_name"],
            entry["namespace"],
            entry["script_path"],
            created,
        )

    console.print()
    console.print(table)
    console.print(
        "  [dim]Re-forge:[/dim]  [bold]cliforge forge create <namespace> <command> --force[/bold]\n"
        "  [dim]Remove:[/dim]    [bold]cliforge forge remove <command>[/bold]\n"
    )


@forge_app.command("remove")
def forge_remove(
    command_name: str = typer.Argument(..., help="Name of the forged command to remove"),
    keep_file: bool = typer.Option(
        False, "--keep-file",
        help="Untrack the command without deleting the script file",
    ),
) -> None:
    """Remove a forged command and delete its script."""
    from cliforge.cli.formatting import print_error, print_success

    forged = _load_forged()

    if command_name not in forged:
        print_error(f"'{command_name}' is not tracked as a forged command.")
        console.print("  Run [bold]cliforge forge list[/bold] to see forged commands.")
        raise typer.Exit(code=1)

    entry = forged[command_name]
    script_path = Path(entry["script_path"])

    if not keep_file:
        if script_path.exists():
            if not _is_forged_by_us(script_path):
                print_error(
                    f"'{script_path}' doesn't look like a cliforge script — refusing to delete."
                )
                console.print(
                    "  Use [bold]--keep-file[/bold] to untrack without deleting, "
                    "or delete the file manually."
                )
                raise typer.Exit(code=1)
            script_path.unlink()
        else:
            console.print(f"  [dim]Script '{script_path}' already gone.[/dim]")

    del forged[command_name]
    _save_forged(forged)
    print_success(f"Removed forged command '{command_name}'.")


@forge_app.command("config")
def forge_config(
    default_install_dir: str = typer.Option(
        None, "--default-install-dir",
        help="Set the default install directory for 'forge create'",
    ),
) -> None:
    """View or update forge configuration."""
    cfg = _load_config()
    forge_cfg = cfg.get("forge", {})

    if default_install_dir is None:
        current = forge_cfg.get("default_install_dir")
        if current:
            console.print(
                f"\n  [dim]Default install dir:[/dim]  [bold]{current}[/bold]  [dim](configured)[/dim]"
            )
        else:
            console.print(
                f"\n  [dim]Default install dir:[/dim]  [bold]{_default_install_dir()}[/bold]  "
                "[dim](system default — not explicitly set)[/dim]"
            )
        console.print(
            "\n  Set with: [bold]cliforge forge config --default-install-dir /your/path[/bold]\n"
        )
        return

    p = Path(default_install_dir).expanduser()
    forge_cfg["default_install_dir"] = str(p)
    cfg["forge"] = forge_cfg
    _save_config(cfg)
    console.print(f"  [green]✓[/green] Default install dir set to: [bold]{p}[/bold]")
