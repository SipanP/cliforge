"""Output formatting for CLI results."""

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

_ERROR_FIELDS = ("message", "error", "detail", "description", "msg", "errorMessage", "error_description")


def output_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str, sort_keys=True))


def output_table(data: Any, title: str = "") -> None:
    if isinstance(data, list) and data and isinstance(data[0], dict):
        table = Table(title=title, show_header=True)
        columns = list(data[0].keys())
        for col in columns:
            table.add_column(col)
        for row in data:
            table.add_row(*[str(row.get(c, "")) for c in columns])
        console.print(table)
    elif isinstance(data, dict):
        table = Table(title=title, show_header=True)
        table.add_column("Key")
        table.add_column("Value")
        for key, value in sorted(data.items()):
            table.add_row(str(key), json.dumps(value, default=str))
        console.print(table)
    else:
        console.print(data)


def output_raw(data: Any) -> None:
    if isinstance(data, (dict, list)):
        print(json.dumps(data, default=str))
    else:
        print(data)


def print_error(message: str) -> None:
    err_console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_info(message: str) -> None:
    console.print(f"[blue]{message}[/blue]")


def format_result(data: Any, output_mode: str) -> None:
    match output_mode:
        case "json":
            output_json(data)
        case "table":
            output_table(data)
        case "raw":
            output_raw(data)
        case _:
            output_json(data)


def print_param_table(params: list[dict[str, Any]], c: Console | None = None) -> None:
    """Render a parameter table. Shared by --help rendering and pre-flight errors."""
    c = c or console
    if not params:
        c.print("  [dim]No parameters.[/dim]\n")
        return
    table = Table(box=box.SIMPLE_HEAD, show_header=True, padding=(0, 1))
    table.add_column("Flag", style="yellow", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("Required", style="red")
    table.add_column("Location", style="dim")
    table.add_column("Description")
    for p in params:
        req = "yes" if p["required"] else ""
        loc = p.get("location", "query")
        desc = escape(p.get("description") or "")
        if p.get("enum"):
            desc += f"  [dim]({', '.join(str(e) for e in p['enum'])})[/dim]"
        table.add_row(f"--{p['name']}", p["type"], req, loc, desc)
    c.print(Panel(table, title="[bold]Parameters[/bold]", border_style="dim"))


def format_execution_result(result: Any, output_mode: str, tool: Any) -> None:
    """Smart formatter: on success show just data; on error show a clear summary."""
    if not isinstance(result, dict) or "status_code" not in result:
        format_result(result, output_mode)
        return

    status: int = result.get("status_code", 0)
    success: bool = result.get("success", True)
    data: Any = result.get("data", {})

    if output_mode == "raw":
        output_raw(result)
        return

    if success:
        format_result(data, output_mode)
        return

    # Non-success response: extract a human-readable message and summarise.
    error_msg: str | None = None
    if isinstance(data, dict):
        for key in _ERROR_FIELDS:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                error_msg = val
                break

    err_console.print()
    err_console.print(f"[red bold]Error (HTTP {status})[/red bold]")
    if error_msg:
        truncated = error_msg[:300] + ("..." if len(error_msg) > 300 else "")
        err_console.print(f"\n  {escape(truncated)}\n")
    else:
        err_console.print()

    ns = getattr(tool, "namespace", "")
    name = getattr(tool, "name", "")
    if ns and name:
        err_console.print(
            f"  [dim]See parameters:[/dim]  [bold]cliforge {ns} {name} --help[/bold]"
        )
        err_console.print(
            f"  [dim]Full response:[/dim]   [bold]cliforge {ns} {name} --output raw[/bold]"
        )
    err_console.print()
