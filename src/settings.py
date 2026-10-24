"""Configuration sources: ``settings.toml``, and ``.env`` for the instance URL and token."""

import re
import tomllib
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PositiveFloat,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SETTINGS_PATH = Path("settings.toml")
ENV_FILE_NAME = ".env"
URL_VARIABLE = "GITLAB_URL"
TOKEN_VARIABLE = "GITLAB_TOKEN"
PREFIX_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?")


class SettingsError(Exception):
    """A settings file is missing, unreadable or invalid."""


class _Section(BaseModel):
    """Base for settings tables: immutable, and unknown keys are errors so typos surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GitLabSettings(_Section):
    """The ``[gitlab]`` table: how to talk to the instance.

    Attributes:
        timeout_seconds: Seconds to wait for each API response.
        verify_ssl: Whether to verify the instance's TLS certificate.
    """

    timeout_seconds: PositiveFloat = 60.0
    verify_ssl: bool = True


class Settings(_Section):
    """The whole ``settings.toml`` document.

    Attributes:
        seed: Seed for the random generators, so the same settings produce the same data.
        prefix: Slug prepended to the names of everything the seeder creates.
        gitlab: How to talk to the instance.
    """

    seed: int = 0
    prefix: str = "seed"
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)

    @field_validator("prefix")
    @classmethod
    def _require_slug(cls, prefix: str) -> str:
        if not PREFIX_PATTERN.fullmatch(prefix):
            raise ValueError(
                "use 1-32 lowercase letters, digits or hyphens, "
                "starting and ending with a letter or digit"
            )
        return prefix


class Connection(BaseSettings):
    """Where the GitLab instance is and the token to sign in with.

    Read from ``GITLAB_URL`` and ``GITLAB_TOKEN``. Variables set in the shell take precedence over
    the ``.env`` file, empty ones are ignored, and other variables in ``.env`` are left alone.

    Attributes:
        url: Base URL of the instance, without ``/api/v4``.
        token: Personal, project or group access token. Kept out of ``repr`` so it is not logged.
    """

    model_config = SettingsConfigDict(
        frozen=True, extra="ignore", env_ignore_empty=True, str_strip_whitespace=True
    )

    url: HttpUrl = Field(validation_alias=URL_VARIABLE)
    token: str = Field(validation_alias=TOKEN_VARIABLE, min_length=1, repr=False)


def load_settings(path: Path) -> Settings:
    """Read and validate a settings file.

    Args:
        path: The TOML file to read.

    Returns:
        The validated settings.

    Raises:
        SettingsError: If the file is missing, unreadable, not valid TOML, or fails validation.
    """
    document = _read_toml(path)
    try:
        return Settings.model_validate(document)
    except ValidationError as error:
        raise SettingsError(_describe_validation_errors(path, error)) from error


def read_connection(env_file: Path) -> Connection:
    """Read the instance URL and the access token.

    Args:
        env_file: The ``.env`` file to read. It may be missing if the shell sets both variables.

    Returns:
        The validated connection.

    Raises:
        SettingsError: If a variable is missing, blank or invalid.
    """
    try:
        return Connection(_env_file=env_file)
    except ValidationError as error:
        problems = _describe_validation_errors(env_file, error)
        raise SettingsError(f"{problems}\nStart from .env.example.") from error


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as settings_file:
            return tomllib.load(settings_file)
    except FileNotFoundError as error:
        raise SettingsError(
            f"{path} not found. Copy settings.example.toml to start from."
        ) from error
    except OSError as error:
        raise SettingsError(f"Cannot read {path}: {error.strerror}") from error
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"{path} is not valid TOML: {error}") from error


def _describe_validation_errors(path: Path, error: ValidationError) -> str:
    problems = [
        f"  {'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
        for issue in error.errors()
    ]
    return "\n".join([f"{path} has invalid settings:", *problems])
