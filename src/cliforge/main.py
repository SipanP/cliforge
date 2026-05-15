"""Entry point for cliforge CLI."""

import logging
import sys

from cliforge.cli.app import app, handle_dynamic_dispatch

_log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"

_STATIC_COMMANDS = {
    "add", "tools", "inspect", "schema", "connectors",
    "refresh", "namespaces", "forge", "--help", "-h", "--version",
}

# Subcommands of `forge` that are NOT namespace names.
# Anything else after `forge` is treated as a namespace shorthand.
_FORGE_SUBCOMMANDS = {"create", "list", "remove", "config"}


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

    # Forge shorthand: `cliforge forge <namespace> [command-name] [--opts]`
    # Rewrites to:     `cliforge forge create <namespace> [command-name] [--opts]`
    # so typer sees the explicit subcommand while users get the short form.
    if (
        len(args) >= 2
        and args[0] == "forge"
        and args[1] not in _FORGE_SUBCOMMANDS
        and not args[1].startswith("-")
    ):
        args = ["forge", "create"] + args[1:]

    # Route to dynamic dispatch if the first arg isn't a static command.
    # This handles: cliforge <namespace> <tool> [--flags]
    #           and: cliforge <namespace>   (lists tools in that namespace)
    if args and args[0] not in _STATIC_COMMANDS and not args[0].startswith("-"):
        try:
            if handle_dynamic_dispatch(args):
                return
        except SystemExit as exc:
            sys.exit(exc.code)
        except Exception as exc:
            import typer
            typer.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    sys.argv = [sys.argv[0]] + args
    app()
