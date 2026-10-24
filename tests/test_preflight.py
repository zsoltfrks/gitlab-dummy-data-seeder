from http import HTTPStatus

import gitlab
import pytest
import requests
import responses

from src.preflight import CheckResult, Preflight, PreflightReport, Status
from tests.support import API_URL, GITLAB_URL, REGULAR_USER, register_healthy_gitlab

ALL_CHECKS = (
    "Authentication",
    "GitLab version",
    "Token scopes",
    "Administrator",
    "Instance limits",
)
TOKEN_URL = f"{API_URL}/personal_access_tokens/self"
APPLICATION_SETTINGS_URL = f"{API_URL}/application/settings"


def statuses(report: PreflightReport) -> dict[str, Status]:
    return {result.name: result.status for result in report.results}


def detail(report: PreflightReport, check: str) -> str:
    return next(result.detail for result in report.results if result.name == check)


@pytest.fixture
def healthy_api(api: responses.RequestsMock) -> responses.RequestsMock:
    register_healthy_gitlab(api)
    return api


def test_healthy_instance_passes_every_check(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    report = Preflight(client).run()

    assert statuses(report) == dict.fromkeys(ALL_CHECKS, Status.PASS)


def test_authentication_names_the_signed_in_user(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    report = Preflight(client).run()

    assert detail(report, "Authentication") == "Signed in as @root"


def test_version_reports_version_and_revision(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    report = Preflight(client).run()

    assert detail(report, "GitLab version") == "GitLab 19.5.1-ce (revision abc123)"


def test_rejected_token_fails_and_stops(api: responses.RequestsMock, client: gitlab.Gitlab) -> None:
    api.get(f"{API_URL}/user", status=HTTPStatus.UNAUTHORIZED, json={"message": "401 Unauthorized"})

    report = Preflight(client).run()

    assert statuses(report) == {"Authentication": Status.FAIL}


@pytest.mark.parametrize(
    ("network_error", "hint"),
    [
        (requests.ConnectionError(), f"Cannot connect to {GITLAB_URL}"),
        (requests.Timeout(), "did not respond within gitlab.timeout_seconds"),
        (requests.exceptions.SSLError(), "gitlab.verify_ssl = false"),
        (requests.exceptions.InvalidHeader("bad header"), "failed: bad header"),
    ],
)
def test_network_errors_fail_with_a_hint(
    api: responses.RequestsMock,
    client: gitlab.Gitlab,
    network_error: requests.RequestException,
    hint: str,
) -> None:
    api.get(f"{API_URL}/user", body=network_error)

    report = Preflight(client).run()

    assert hint in detail(report, "Authentication")


def test_non_json_answer_fails(api: responses.RequestsMock, client: gitlab.Gitlab) -> None:
    api.get(f"{API_URL}/user", body="<html></html>", content_type="text/html")

    report = Preflight(client).run()

    assert "did not return JSON" in detail(report, "Authentication")


def test_persistent_server_error_fails(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(
        responses.GET, f"{API_URL}/version", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    report = Preflight(client).run()

    assert statuses(report)["GitLab version"] is Status.FAIL


def test_missing_api_scope_fails_and_stops(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, TOKEN_URL, json={"scopes": ["read_api"]})

    report = Preflight(client).run()

    assert list(statuses(report)) == ["Authentication", "GitLab version", "Token scopes"]


def test_missing_sudo_scope_warns(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, TOKEN_URL, json={"scopes": ["api"]})

    report = Preflight(client).run()

    assert statuses(report)["Token scopes"] is Status.WARN


def test_token_without_scope_endpoint_warns(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, TOKEN_URL, status=HTTPStatus.NOT_FOUND)

    report = Preflight(client).run()

    assert statuses(report)["Token scopes"] is Status.WARN


def test_unexpected_scope_endpoint_error_fails(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, TOKEN_URL, status=HTTPStatus.BAD_REQUEST)

    report = Preflight(client).run()

    assert statuses(report)["Token scopes"] is Status.FAIL


def test_regular_user_warns_and_skips_instance_limits(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, f"{API_URL}/user", json=REGULAR_USER)

    report = Preflight(client).run()

    assert detail(report, "Instance limits").startswith("Skipped")


def test_instance_limits_describe_unlimited_and_sized_values(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    report = Preflight(client).run()

    assert (
        detail(report, "Instance limits")
        == "max push size: unlimited, max attachment size: 100 MiB"
    )


def test_instance_limits_handle_an_empty_answer(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, APPLICATION_SETTINGS_URL, json={})

    report = Preflight(client).run()

    assert detail(report, "Instance limits") == "No size limits reported"


def test_forbidden_instance_settings_hint_at_admin_mode(
    healthy_api: responses.RequestsMock, client: gitlab.Gitlab
) -> None:
    healthy_api.replace(responses.GET, APPLICATION_SETTINGS_URL, status=HTTPStatus.FORBIDDEN)

    report = Preflight(client).run()

    assert "admin_mode" in detail(report, "Instance limits")


def test_report_with_a_failure_has_failed() -> None:
    report = PreflightReport(
        (CheckResult("first", Status.PASS, ""), CheckResult("second", Status.FAIL, ""))
    )

    assert report.failed


def test_report_with_only_warnings_has_not_failed() -> None:
    report = PreflightReport((CheckResult("only", Status.WARN, ""),))

    assert not report.failed


def test_empty_report_has_not_failed() -> None:
    assert not PreflightReport(()).failed
