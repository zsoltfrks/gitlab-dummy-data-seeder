from pathlib import Path

import pytest

from src.settings import (
    ENV_FILE_NAME,
    TOKEN_VARIABLE,
    URL_VARIABLE,
    SettingsError,
    load_settings,
    read_connection,
)
from tests.support import (
    CONNECTION_ENV_FILE,
    ENV_EXAMPLE,
    GITLAB_URL,
    SETTINGS_EXAMPLE,
    TEST_TOKEN,
    FileWriter,
)

LONGEST_PREFIX = "a" * 32
SHELL_TOKEN = "glpat-from-shell"
SHELL_URL = "https://shell.example.com"


def test_settings_example_is_valid() -> None:
    settings = load_settings(SETTINGS_EXAMPLE)

    assert settings.seed == 42


def test_empty_settings_fall_back_to_defaults(write_settings: FileWriter) -> None:
    settings = load_settings(write_settings(""))

    assert (
        settings.seed,
        settings.prefix,
        settings.gitlab.timeout_seconds,
        settings.gitlab.verify_ssl,
    ) == (0, "seed", 60.0, True)


def test_missing_file_points_to_the_example(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match=r"settings\.example\.toml"):
        load_settings(tmp_path / "missing.toml")


def test_unreadable_path_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="Cannot read"):
        load_settings(tmp_path)


def test_invalid_toml_is_reported(write_settings: FileWriter) -> None:
    with pytest.raises(SettingsError, match="not valid TOML"):
        load_settings(write_settings("[gitlab\n"))


def test_misspelled_setting_is_rejected_with_its_location(write_settings: FileWriter) -> None:
    with pytest.raises(SettingsError, match=r"gitlab\.timeout: Extra inputs are not permitted"):
        load_settings(write_settings("[gitlab]\ntimeout = 5\n"))


def test_url_in_settings_is_rejected(write_settings: FileWriter) -> None:
    with pytest.raises(SettingsError, match=r"gitlab\.url: Extra inputs are not permitted"):
        load_settings(write_settings(f'[gitlab]\nurl = "{GITLAB_URL}"\n'))


def test_wrongly_typed_seed_is_rejected(write_settings: FileWriter) -> None:
    with pytest.raises(SettingsError, match="seed: Input should be a valid integer"):
        load_settings(write_settings('seed = "abc"\n'))


@pytest.mark.parametrize("timeout", [0, -1])
def test_non_positive_timeout_is_rejected(write_settings: FileWriter, timeout: int) -> None:
    with pytest.raises(SettingsError, match=r"gitlab\.timeout_seconds"):
        load_settings(write_settings(f"[gitlab]\ntimeout_seconds = {timeout}\n"))


@pytest.mark.parametrize("prefix", ["a", "seed", "team-42", LONGEST_PREFIX])
def test_slug_prefix_is_accepted(write_settings: FileWriter, prefix: str) -> None:
    settings = load_settings(write_settings(f'prefix = "{prefix}"\n'))

    assert settings.prefix == prefix


@pytest.mark.parametrize(
    "prefix", ["", "-seed", "seed-", "Seed", "seed_1", "seed.1", LONGEST_PREFIX + "a"]
)
def test_non_slug_prefix_is_rejected(write_settings: FileWriter, prefix: str) -> None:
    with pytest.raises(SettingsError, match="prefix: Value error"):
        load_settings(write_settings(f'prefix = "{prefix}"\n'))


def test_connection_is_read_from_the_env_file(write_env_file: FileWriter) -> None:
    connection = read_connection(write_env_file(CONNECTION_ENV_FILE))

    assert (str(connection.url), connection.token) == (f"{GITLAB_URL}/", TEST_TOKEN)


def test_shell_variables_take_precedence_over_the_env_file(
    monkeypatch: pytest.MonkeyPatch, write_env_file: FileWriter
) -> None:
    monkeypatch.setenv(URL_VARIABLE, SHELL_URL)
    monkeypatch.setenv(TOKEN_VARIABLE, SHELL_TOKEN)

    connection = read_connection(write_env_file(CONNECTION_ENV_FILE))

    assert (str(connection.url), connection.token) == (f"{SHELL_URL}/", SHELL_TOKEN)


def test_empty_shell_variable_falls_back_to_the_env_file(
    monkeypatch: pytest.MonkeyPatch, write_env_file: FileWriter
) -> None:
    monkeypatch.setenv(TOKEN_VARIABLE, "")

    assert read_connection(write_env_file(CONNECTION_ENV_FILE)).token == TEST_TOKEN


def test_shell_variables_work_without_an_env_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(URL_VARIABLE, SHELL_URL)
    monkeypatch.setenv(TOKEN_VARIABLE, SHELL_TOKEN)

    assert read_connection(tmp_path / ENV_FILE_NAME).token == SHELL_TOKEN


def test_token_whitespace_is_stripped(write_env_file: FileWriter) -> None:
    env_file = write_env_file(f'{URL_VARIABLE}={GITLAB_URL}\n{TOKEN_VARIABLE}="  {TEST_TOKEN}  "\n')

    assert read_connection(env_file).token == TEST_TOKEN


def test_other_variables_in_the_env_file_are_ignored(write_env_file: FileWriter) -> None:
    env_file = write_env_file(CONNECTION_ENV_FILE + "UNRELATED=value\n")

    assert read_connection(env_file).token == TEST_TOKEN


def test_token_is_kept_out_of_repr(write_env_file: FileWriter) -> None:
    connection = read_connection(write_env_file(CONNECTION_ENV_FILE))

    assert TEST_TOKEN not in repr(connection)


@pytest.mark.parametrize("missing", [URL_VARIABLE, TOKEN_VARIABLE])
def test_missing_variable_is_named(write_env_file: FileWriter, missing: str) -> None:
    present = [line for line in CONNECTION_ENV_FILE.splitlines() if not line.startswith(missing)]

    with pytest.raises(SettingsError, match=f"{missing}: Field required"):
        read_connection(write_env_file("\n".join(present)))


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_token_is_rejected(write_env_file: FileWriter, blank: str) -> None:
    env_file = write_env_file(f'{URL_VARIABLE}={GITLAB_URL}\n{TOKEN_VARIABLE}="{blank}"\n')

    with pytest.raises(SettingsError, match=TOKEN_VARIABLE):
        read_connection(env_file)


@pytest.mark.parametrize("url", ["localhost:8080", "ftp://gitlab.example.com"])
def test_non_http_url_is_rejected(write_env_file: FileWriter, url: str) -> None:
    env_file = write_env_file(f"{URL_VARIABLE}={url}\n{TOKEN_VARIABLE}={TEST_TOKEN}\n")

    with pytest.raises(SettingsError, match=URL_VARIABLE):
        read_connection(env_file)


def test_connection_errors_point_to_the_example(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match=r"\.env\.example"):
        read_connection(tmp_path / ENV_FILE_NAME)


def test_env_example_ships_without_a_token() -> None:
    with pytest.raises(SettingsError, match=f"{TOKEN_VARIABLE}: Field required"):
        read_connection(ENV_EXAMPLE)
