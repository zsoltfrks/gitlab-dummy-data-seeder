"""Read-only checks that the GitLab instance and the token are ready for seeding."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from functools import cached_property
from http import HTTPStatus
from typing import Any

import gitlab
import requests
from gitlab.exceptions import (
    GitlabAuthenticationError,
    GitlabError,
    GitlabHttpError,
    GitlabParsingError,
)

# Fail fast here; seeding requests keep python-gitlab's default of 10 retries.
PREFLIGHT_MAX_RETRIES = 1
REQUIRED_SCOPE = "api"
SUDO_SCOPE = "sudo"
INSTANCE_SIZE_LIMITS = {
    "receive_max_input_size": "max push size",
    "max_attachment_size": "max attachment size",
    "repository_size_limit": "repository size limit",
}
# Most specific first: SSLError and ConnectTimeout are also ConnectionErrors.
NETWORK_ERROR_HINTS: tuple[tuple[type[requests.RequestException], str], ...] = (
    (requests.Timeout, "{url} did not respond within gitlab.timeout_seconds"),
    (
        requests.exceptions.SSLError,
        "TLS verification failed for {url}. For a test instance with a self-signed "
        "certificate, set gitlab.verify_ssl = false",
    ),
    (
        requests.ConnectionError,
        "Cannot connect to {url}. Is GitLab running, and is GITLAB_URL right?",
    ),
)
GENERIC_NETWORK_ERROR_HINT = "Request to {url} failed: {error}"


class Status(Enum):
    PASS = auto()
    WARN = auto()
    FAIL = auto()


@dataclass(frozen=True)
class Finding:
    """What a single check found.

    Attributes:
        status: Whether the check passed, passed with a warning, or failed.
        detail: A one-line explanation for the person running the check.
    """

    status: Status
    detail: str


@dataclass(frozen=True)
class CheckResult:
    """A finding together with the name of the check that produced it.

    Attributes:
        name: Human-readable name of the check.
        status: Whether the check passed, passed with a warning, or failed.
        detail: A one-line explanation for the person running the check.
    """

    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """The results of one preflight run.

    Attributes:
        results: One result per check that ran, in the order they ran.
    """

    results: tuple[CheckResult, ...]

    @property
    def failed(self) -> bool:
        """Whether any check failed. Warnings do not count as failures."""
        return any(result.status is Status.FAIL for result in self.results)


class Preflight:
    """Read-only readiness checks against one GitLab instance.

    Checks run in order and stop at the first failure, because later checks build on earlier
    ones: nothing else works without authentication, for example.

    Args:
        client: A client for the instance to check, authenticated with the token to check.
    """

    def __init__(self, client: gitlab.Gitlab) -> None:
        self._client = client
        self._checks: tuple[tuple[str, Callable[[], Finding]], ...] = (
            ("Authentication", self._check_authentication),
            ("GitLab version", self._check_version),
            ("Token scopes", self._check_token_scopes),
            ("Administrator", self._check_administrator),
            ("Instance limits", self._check_instance_limits),
        )

    def run(self) -> PreflightReport:
        """Run the checks until one fails.

        Returns:
            The report. Network and API errors are reported as failed checks, not raised.
        """
        results: list[CheckResult] = []
        for name, check in self._checks:
            finding = self._run_safely(check)
            results.append(CheckResult(name, finding.status, finding.detail))
            if finding.status is Status.FAIL:
                break
        return PreflightReport(tuple(results))

    def _run_safely(self, check: Callable[[], Finding]) -> Finding:
        try:
            return check()
        except GitlabAuthenticationError as error:
            return Finding(Status.FAIL, f"GitLab rejected the access token ({error})")
        except GitlabError as error:
            return Finding(Status.FAIL, f"Request failed: {error}")
        except requests.RequestException as error:
            return Finding(Status.FAIL, self._describe_network_error(error))

    def _describe_network_error(self, error: requests.RequestException) -> str:
        hint = next(
            (hint for kind, hint in NETWORK_ERROR_HINTS if isinstance(error, kind)),
            GENERIC_NETWORK_ERROR_HINT,
        )
        return hint.format(url=self._client.url, error=error)

    def _check_authentication(self) -> Finding:
        return Finding(Status.PASS, f"Signed in as @{self._current_user['username']}")

    def _check_version(self) -> Finding:
        version = self._get("/version")
        return Finding(Status.PASS, f"GitLab {version['version']} (revision {version['revision']})")

    def _check_token_scopes(self) -> Finding:
        token = self._get_or_none("/personal_access_tokens/self", HTTPStatus.NOT_FOUND)
        if token is None:
            return Finding(
                Status.WARN,
                "Cannot inspect the scopes: only personal, project and group access tokens "
                "expose them",
            )
        scopes = set(token["scopes"])
        granted = ", ".join(sorted(scopes))
        if REQUIRED_SCOPE not in scopes:
            return Finding(
                Status.FAIL, f"The `{REQUIRED_SCOPE}` scope is required (has: {granted})"
            )
        if SUDO_SCOPE not in scopes:
            return Finding(
                Status.WARN,
                f"Without the `{SUDO_SCOPE}` scope, seeded content cannot be attributed to "
                f"seeded users (has: {granted})",
            )
        return Finding(Status.PASS, granted)

    def _check_administrator(self) -> Finding:
        if self._is_administrator:
            return Finding(Status.PASS, "The token belongs to an administrator")
        return Finding(
            Status.WARN,
            "Not an administrator: creating users and reading instance limits will fail",
        )

    def _check_instance_limits(self) -> Finding:
        if not self._is_administrator:
            return Finding(Status.WARN, "Skipped: reading them needs an administrator's token")
        application_settings = self._get_or_none("/application/settings", HTTPStatus.FORBIDDEN)
        if application_settings is None:
            return Finding(
                Status.WARN,
                "Forbidden. If Admin Mode is on, the token also needs the `admin_mode` scope",
            )
        limits = [
            f"{label}: {_describe_mebibytes(application_settings[key])}"
            for key, label in INSTANCE_SIZE_LIMITS.items()
            if key in application_settings
        ]
        return Finding(Status.PASS, ", ".join(limits) or "No size limits reported")

    @cached_property
    def _current_user(self) -> dict[str, Any]:
        return self._get("/user")

    @property
    def _is_administrator(self) -> bool:
        return bool(self._current_user.get("is_admin", False))

    def _get(self, path: str) -> dict[str, Any]:
        response = self._client.http_get(path, max_retries=PREFLIGHT_MAX_RETRIES)
        if not isinstance(response, dict):
            raise GitlabParsingError(
                f"{path} did not return JSON. Is {self._client.url} a GitLab instance?"
            )
        return response

    def _get_or_none(self, path: str, absent_status: HTTPStatus) -> dict[str, Any] | None:
        """Like ``_get``, but return None when GitLab answers with ``absent_status``."""
        try:
            return self._get(path)
        except GitlabHttpError as error:
            if error.response_code == absent_status:
                return None
            raise


def _describe_mebibytes(limit: int | None) -> str:
    """GitLab reports these limits in MiB, with 0 or null meaning no limit."""
    return f"{limit} MiB" if limit else "unlimited"
