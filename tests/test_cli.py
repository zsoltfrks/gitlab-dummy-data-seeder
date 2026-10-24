from http import HTTPStatus

import responses
from typer.testing import CliRunner

from src import __version__
from src.cli import ExitCode, app
from src.settings import URL_VARIABLE
from tests.support import (
    API_URL,
    CONNECTION_ENV_FILE,
    TEST_TOKEN,
    FileWriter,
    register_healthy_gitlab,
)

runner = CliRunner()


def test_version_option_prints_the_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.output.strip() == __version__


def test_validate_offline_accepts_valid_files(
    write_settings: FileWriter, write_env_file: FileWriter
) -> None:
    write_env_file(CONNECTION_ENV_FILE)

    result = runner.invoke(app, ["validate", "--config", str(write_settings("")), "--offline"])

    assert result.exit_code == 0


def test_validate_reports_invalid_settings(
    write_settings: FileWriter, write_env_file: FileWriter
) -> None:
    write_env_file(CONNECTION_ENV_FILE)

    result = runner.invoke(
        app, ["validate", "--config", str(write_settings("seed = 'x'\n")), "--offline"]
    )

    assert (result.exit_code, "seed" in result.output) == (ExitCode.INVALID_INPUT, True)


def test_validate_offline_still_checks_the_env_file(write_settings: FileWriter) -> None:
    result = runner.invoke(app, ["validate", "--config", str(write_settings("")), "--offline"])

    assert (result.exit_code, URL_VARIABLE in result.output) == (ExitCode.INVALID_INPUT, True)


def test_validate_sends_the_token_from_the_env_file_next_to_the_settings(
    api: responses.RequestsMock, write_settings: FileWriter, write_env_file: FileWriter
) -> None:
    register_healthy_gitlab(api)
    write_env_file(CONNECTION_ENV_FILE)

    runner.invoke(app, ["validate", "--config", str(write_settings(""))])

    assert api.calls[0].request.headers["PRIVATE-TOKEN"] == TEST_TOKEN


def test_validate_succeeds_when_preflight_passes(
    api: responses.RequestsMock, write_settings: FileWriter, write_env_file: FileWriter
) -> None:
    register_healthy_gitlab(api)
    write_env_file(CONNECTION_ENV_FILE)

    result = runner.invoke(app, ["validate", "--config", str(write_settings(""))])

    assert result.exit_code == 0


def test_validate_fails_when_preflight_fails(
    api: responses.RequestsMock, write_settings: FileWriter, write_env_file: FileWriter
) -> None:
    api.get(f"{API_URL}/user", status=HTTPStatus.UNAUTHORIZED)
    write_env_file(CONNECTION_ENV_FILE)

    result = runner.invoke(app, ["validate", "--config", str(write_settings(""))])

    assert result.exit_code == ExitCode.CHECKS_FAILED
