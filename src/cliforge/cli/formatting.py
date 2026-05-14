"""Output formatting for CLI results."""

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


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
