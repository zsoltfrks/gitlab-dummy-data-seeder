from collections.abc import Iterator
from pathlib import Path

import gitlab
import pytest
import responses

from src.client import create_client
from src.settings import (
    DEFAULT_SETTINGS_PATH,
    ENV_FILE_NAME,
    TOKEN_VARIABLE,
    URL_VARIABLE,
    Connection,
    GitLabSettings,
)
from tests.support import GITLAB_URL, TEST_TOKEN, FileWriter


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """python-gitlab sleeps between retries; tests should not."""
    monkeypatch.setattr("gitlab.utils.time.sleep", lambda _seconds: None)


@pytest.fixture(autouse=True)
def no_connection_in_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep GITLAB_URL and GITLAB_TOKEN from the developer's shell out of the tests."""
    monkeypatch.delenv(URL_VARIABLE, raising=False)
    monkeypatch.delenv(TOKEN_VARIABLE, raising=False)


@pytest.fixture
def connection() -> Connection:
    return Connection.model_validate({URL_VARIABLE: GITLAB_URL, TOKEN_VARIABLE: TEST_TOKEN})


@pytest.fixture
def client(connection: Connection) -> gitlab.Gitlab:
    return create_client(connection, GitLabSettings())


@pytest.fixture
def api() -> Iterator[responses.RequestsMock]:
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture
def write_settings(tmp_path: Path) -> FileWriter:
    return _file_writer(tmp_path / DEFAULT_SETTINGS_PATH)


@pytest.fixture
def write_env_file(tmp_path: Path) -> FileWriter:
    return _file_writer(tmp_path / ENV_FILE_NAME)


def _file_writer(path: Path) -> FileWriter:
    def write(content: str) -> Path:
        path.write_text(content, encoding="utf-8")
        return path

    return write
