"""The python-gitlab client factory."""

import gitlab

from src import __version__
from src.settings import Connection, GitLabSettings

USER_AGENT = f"gitlab-dummy-data-seeder/{__version__}"
MAX_PAGE_SIZE = 100


def create_client(connection: Connection, settings: GitLabSettings) -> gitlab.Gitlab:
    """Build a client that retries rate limits, transient errors and dropped connections.

    Args:
        connection: Where the instance is and the token to sign in with.
        settings: How to talk to the instance.

    Returns:
        A client for the instance's REST API.
    """
    return gitlab.Gitlab(
        url=str(connection.url),
        private_token=connection.token,
        timeout=settings.timeout_seconds,
        ssl_verify=settings.verify_ssl,
        per_page=MAX_PAGE_SIZE,
        retry_transient_errors=True,
        user_agent=USER_AGENT,
    )
