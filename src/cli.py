"""The ``glseed`` command-line interface.

Command docstrings double as the ``--help`` text, so they stay one line long.
"""

from collections.abc import Callable
from enum import IntEnum
from pathlib import Path
from typing import Annotated, TypeVar

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from src import __version__
from src.client import create_client
from src.preflight import Preflight, PreflightReport, Status
from src.settings import (
    DEFAULT_SETTINGS_PATH,
    ENV_FILE_NAME,
    TOKEN_VARIABLE,
    URL_VARIABLE,
    SettingsError,
    load_settings,
    read_connection,
)

Loaded = TypeVar("Loaded")

app = typer.Typer(no_args_is_help=True)
# Soft wrapping keeps long paths in messages on one line so they can be copied.
console = Console(soft_wrap=True)
error_console = Console(stderr=True, soft_wrap=True)

STATUS_STYLES = {Status.PASS: "green", Status.WARN: "yellow", Status.FAIL: "red"}


class ExitCode(IntEnum):
    CHECKS_FAILED = 1
    INVALID_INPUT = 2


def _print_version(requested: bool) -> None:
    if requested:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_print_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Seed a GitLab instance with dummy data for testing and development."""


@app.command()
def validate(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help=f"Path to the settings file. {URL_VARIABLE} and {TOKEN_VARIABLE} are read from "
            f"the {ENV_FILE_NAME} file next to it.",
        ),
    ] = DEFAULT_SETTINGS_PATH,
    offline: Annotated[
        bool, typer.Option("--offline", help="Check only the files; do not contact GitLab.")
    ] = False,
) -> None:
    """Check settings.toml and .env, then check that GitLab and the token are ready for seeding."""
    env_file = config.with_name(ENV_FILE_NAME)
    settings = _load_or_exit(load_settings, config)
    connection = _load_or_exit(read_connection, env_file)
    console.print(f"[green]{escape(str(config))} and {escape(str(env_file))} are valid.[/]")
    if offline:
        return
    report = Preflight(create_client(connection, settings.gitlab)).run()
    _print_report(report)
    if report.failed:
        raise typer.Exit(ExitCode.CHECKS_FAILED)


def _load_or_exit(load: Callable[[Path], Loaded], path: Path) -> Loaded:
    try:
        return load(path)
    except SettingsError as error:
        error_console.print(f"[red]Error:[/] {escape(str(error))}")
        raise typer.Exit(ExitCode.INVALID_INPUT) from error


def _print_report(report: PreflightReport) -> None:
    table = Table("Check", "Status", "Detail", title="Preflight")
    for result in report.results:
        status = Text(result.status.name, style=STATUS_STYLES[result.status])
        table.add_row(result.name, status, Text(result.detail))
    console.print(table)
