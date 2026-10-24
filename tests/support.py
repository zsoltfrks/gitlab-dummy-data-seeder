from collections.abc import Callable
from pathlib import Path
from typing import Any

import responses

from src.settings import TOKEN_VARIABLE, URL_VARIABLE

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_EXAMPLE = REPOSITORY_ROOT / "settings.example.toml"
ENV_EXAMPLE = REPOSITORY_ROOT / ".env.example"

GITLAB_URL = "https://gitlab.example.com"
API_URL = f"{GITLAB_URL}/api/v4"
TEST_TOKEN = "glpat-test-token"
CONNECTION_ENV_FILE = f"{URL_VARIABLE}={GITLAB_URL}\n{TOKEN_VARIABLE}={TEST_TOKEN}\n"

ADMIN_USER: dict[str, Any] = {"username": "root", "is_admin": True}
REGULAR_USER: dict[str, Any] = {"username": "jane"}
SERVER_VERSION: dict[str, Any] = {"version": "19.5.1-ce", "revision": "abc123"}
FULL_SCOPES_TOKEN: dict[str, Any] = {"scopes": ["api", "sudo"]}
APPLICATION_SETTINGS: dict[str, Any] = {"receive_max_input_size": 0, "max_attachment_size": 100}

FileWriter = Callable[[str], Path]


def register_healthy_gitlab(api: responses.RequestsMock) -> None:
    """Answer every preflight request as a correctly configured instance would.

    Tests change single endpoints afterwards with ``api.replace``.
    """
    api.get(f"{API_URL}/user", json=ADMIN_USER)
    api.get(f"{API_URL}/version", json=SERVER_VERSION)
    api.get(f"{API_URL}/personal_access_tokens/self", json=FULL_SCOPES_TOKEN)
    api.get(f"{API_URL}/application/settings", json=APPLICATION_SETTINGS)
