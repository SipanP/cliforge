"""Entry point for cliforge CLI."""

import logging
import sys

import typer

from cliforge.cli.app import app, handle_dynamic_dispatch

_log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"


def _configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(level=level, format=_log_format)


def main() -> None:
    args = sys.argv[1:]

    debug = "--debug" in args
    if debug:
        args = [a for a in args if a != "--debug"]
        _configure_logging(debug=True)
    else:
        _configure_logging()

    static_commands = {"add", "tools", "inspect", "schema", "connectors", "refresh", "--help", "-h", "--version"}
    if args and args[0] not in static_commands:
        if handle_dynamic_dispatch(args):
            return

    sys.argv = [sys.argv[0]] + args
    app()
