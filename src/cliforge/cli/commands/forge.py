"""cliforge forge — generate and manage standalone namespace commands."""

import difflib
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

console = Console()

forge_app = typer.Typer(invoke_without_command=True)

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


@forge_app.callback(invoke_without_command=True)
def forge_root(ctx: typer.Context) -> None:
    """
    Generate a standalone command for a namespace, or manage existing ones.

    \b
    PRIMARY USAGE — forge a command:
      cliforge forge <namespace>
          Creates a command with the same name as the namespace.
          Example: cliforge forge github   →  run 'github listUsers'

      cliforge forge <namespace> <command-name>
          Creates a command with a custom name.
          Example: cliforge forge github gh  →  run 'gh listUsers'

    \b
    MANAGEMENT:
      cliforge forge list              Show all forged commands
      cliforge forge remove <name>     Delete a forged command
      cliforge forge config            View or change the default install dir

    \b
    OPTIONS (used with the primary usage above):
      --install-dir   Install to a specific directory instead of the default
      --set-default   Save --install-dir as the new default for future forges
      --force         Overwrite an existing command
      --dry-run       Preview the script without installing anything
    """
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


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


def _ranked_suggestions(word: str, possibilities: list[str], cutoff: float = 0.6) -> list[str]:
    """Return possibilities ordered by similarity to word.

    Uses difflib.get_close_matches for the top results; falls back to the full
    list (sorted) when nothing clears the similarity threshold.
    """
    close = difflib.get_close_matches(word, possibilities, n=5, cutoff=cutoff)
    return close if close else sorted(possibilities)


@forge_app.command("create", hidden=True)
def forge_create(
    namespace: str = typer.Argument(..., help="Registered namespace to wrap"),
    command_name: str = typer.Argument(
        None,
        help="Name for the generated command. Defaults to the namespace name.",
    ),
    install_dir: str = typer.Option(
        None, "--install-dir", "-d",
        help="Directory to install into. Overrides the configured default.",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if already exists"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the script without installing"),
    set_default: bool = typer.Option(
        False, "--set-default",
        help="Save --install-dir as the new default for future forges",
    ),
) -> None:
    """Generate a standalone command that wraps a registered namespace."""
    from cliforge.cli.formatting import print_error, print_success
    from cliforge.registry.store import Registry

    # Default command name to the namespace name when not specified.
    if command_name is None:
        command_name = namespace

    registry = Registry()
    registry.load()

    if not registry.has_connector(namespace):
        print_error(f"Namespace '{namespace}' is not registered.")
        connectors = registry.get_connectors()
        if connectors:
            ranked = _ranked_suggestions(namespace, [c.namespace for c in connectors])
            console.print("\n  [dim]Did you mean one of these?[/dim]")
            for ns in ranked:
                console.print(
                    f"    [bold]cliforge forge {ns}[/bold]"
                    f"  [dim]— creates a '{ns}' command[/dim]"
                )
        else:
            console.print("\n  [dim]No namespaces registered yet. Add one first:[/dim]")
            console.print("    [bold]cliforge add openapi <name> <spec-url-or-file>[/bold]")
            console.print("    [bold]cliforge add mcp <name> <command>[/bold]")
        console.print(f"\n  See all registered namespaces: [bold]cliforge namespaces[/bold]")
        raise typer.Exit(code=1)

    tools = registry.get_tools(namespace)
    script = _SHELL_SCRIPT if sys.platform != "win32" else _BAT_SCRIPT
    script = script.format(namespace=namespace, command_name=command_name)

    if dry_run:
        console.print(f"[dim]# Script that would be installed as '{command_name}':[/dim]\n")
        console.print(escape(script))
        console.print(
            f"[dim]# Run without --dry-run to install it, or add --install-dir to choose a location.[/dim]"
        )
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
            console.print(
                f"\n  To re-forge it (update the namespace or options):\n"
                f"    [bold]cliforge forge {namespace} {command_name} --force[/bold]"
            )
        else:
            print_error(f"'{script_path}' already exists and was not created by cliforge.")
            console.print(
                f"\n  To overwrite it anyway (replaces the existing file):\n"
                f"    [bold]cliforge forge {namespace} {command_name} --force[/bold]\n"
                f"\n  [yellow]Caution:[/yellow] this will replace a command that cliforge did not create."
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

    from cliforge.cli.formatting import print_success
    print_success(f"Forged '{command_name}' → cliforge {namespace}")
    console.print(f"  [dim]Installed:[/dim]  [bold]{script_path}[/bold]")
    console.print(f"  [dim]Namespace:[/dim]  {namespace}  ({len(tools)} tools)\n")

    if not _is_on_path(target_dir):
        console.print(f"  [yellow]Warning:[/yellow] {target_dir} is not on your PATH.")
        if sys.platform != "win32":
            console.print(
                f"  Add it:  [bold]export PATH=\"{target_dir}:$PATH\"[/bold]  "
                f"[dim](or add to ~/.bashrc / ~/.zshrc)[/dim]"
            )
        console.print()

    console.print(f"  [dim]Try it:[/dim]")
    console.print(f"    [bold]{command_name}[/bold]                  [dim]# list all tools[/dim]")
    console.print(f"    [bold]{command_name} <tool> --help[/bold]    [dim]# show parameters for a tool[/dim]")
    console.print(f"    [bold]{command_name} <tool> [--flags][/bold] [dim]# execute a tool[/dim]\n")
    console.print(
        f"  [dim]The command stays in sync automatically — no need to re-forge after registry changes.[/dim]\n"
    )


@forge_app.command("list")
def forge_list(
    output: str = typer.Option("table", "--output", "-o", help="Output format: json, table"),
) -> None:
    """List all forged commands and where they are installed."""
    forged = _load_forged()

    if not forged:
        console.print(
            "\n[dim]No forged commands yet.[/dim]\n"
            "\n  Create one:\n"
            "    [bold]cliforge forge <namespace>[/bold]          [dim]creates a command with the namespace name[/dim]\n"
            "    [bold]cliforge forge <namespace> <name>[/bold]   [dim]creates a command with a custom name[/dim]\n"
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
        "  [dim]Re-forge (update or move):[/dim]  "
        "[bold]cliforge forge <namespace> <command> --force[/bold]\n"
        "  [dim]Remove:[/dim]                      "
        "[bold]cliforge forge remove <command>[/bold]\n"
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
        if forged:
            ranked = _ranked_suggestions(command_name, list(forged.keys()))
            console.print("\n  [dim]Did you mean one of these?[/dim]")
            for name in ranked:
                entry = forged[name]
                console.print(
                    f"    [bold]cliforge forge remove {name}[/bold]"
                    f"  [dim]— removes '{entry['script_path']}'[/dim]"
                )
        else:
            console.print("  [dim]No forged commands exist yet.[/dim]")
        console.print(f"\n  See all:  [bold]cliforge forge list[/bold]")
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
                    "\n  Options:\n"
                    f"    [bold]cliforge forge remove {command_name} --keep-file[/bold]"
                    f"  [dim]— untrack without deleting the file[/dim]\n"
                    f"    Delete the file manually, then re-run remove."
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
        help="Set the default install directory for forge",
    ),
) -> None:
    """
    View or update forge configuration.

    \b
    Examples:
      cliforge forge config                              # show current settings
      cliforge forge config --default-install-dir ~/bin # set new default
    """
    cfg = _load_config()
    forge_cfg = cfg.get("forge", {})

    if default_install_dir is None:
        current = forge_cfg.get("default_install_dir")
        console.print()
        if current:
            console.print(
                f"  [dim]Default install dir:[/dim]  [bold]{current}[/bold]  [dim](configured)[/dim]"
            )
        else:
            console.print(
                f"  [dim]Default install dir:[/dim]  [bold]{_default_install_dir()}[/bold]  "
                "[dim](system default — not explicitly set)[/dim]"
            )
        console.print(
            "\n  Change it:\n"
            "    [bold]cliforge forge config --default-install-dir /your/path[/bold]\n"
            "\n  Or set it on the fly when forging:\n"
            "    [bold]cliforge forge <namespace> --install-dir /your/path --set-default[/bold]\n"
        )
        return

    p = Path(default_install_dir).expanduser()
    forge_cfg["default_install_dir"] = str(p)
    cfg["forge"] = forge_cfg
    _save_config(cfg)
    console.print(f"  [green]✓[/green] Default install dir set to: [bold]{p}[/bold]")
    console.print(
        f"  All future [bold]cliforge forge <namespace>[/bold] calls will install to this directory."
    )
