from http import HTTPStatus

import gitlab
import responses

from src.client import MAX_PAGE_SIZE, USER_AGENT, create_client
from src.settings import Connection, GitLabSettings
from tests.support import API_URL, SERVER_VERSION, TEST_TOKEN


def test_client_targets_the_api_below_the_configured_url(client: gitlab.Gitlab) -> None:
    assert client.api_url == API_URL


def test_client_applies_connection_settings(connection: Connection) -> None:
    settings = GitLabSettings(timeout_seconds=5, verify_ssl=False)

    client = create_client(connection, settings)

    assert (client.timeout, client.ssl_verify, client.per_page) == (5, False, MAX_PAGE_SIZE)


def test_client_sends_the_token_and_user_agent(
    api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    api.get(f"{API_URL}/version", json=SERVER_VERSION)

    client.http_get("/version")

    headers = api.calls[0].request.headers
    assert (headers["PRIVATE-TOKEN"], headers["User-Agent"]) == (TEST_TOKEN, USER_AGENT)


def test_client_retries_transient_errors(
    api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    api.get(f"{API_URL}/version", status=HTTPStatus.BAD_GATEWAY)
    api.get(f"{API_URL}/version", json=SERVER_VERSION)

    assert client.http_get("/version") == SERVER_VERSION
