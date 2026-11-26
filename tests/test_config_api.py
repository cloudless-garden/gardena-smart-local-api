# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from collections.abc import Mapping, Sequence
from typing import Any, cast
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from gardena_smart_local_api.client import (
    AuthenticationError,
    ConfigApiError,
    GatewayConfigApi,
)

HOST = "GARDENA-123456"
PASSWORD = "password"
FINGERPRINT = "ab" * 32
SESSION_HEADERS = {"X-session": "abc"}


class _Response:
    def __init__(self, status: int = 200, payload: Any = None) -> None:
        self.status = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                MagicMock(), (), status=self.status, message="error"
            )

    async def json(self) -> Any:
        return self._payload


class _Request:
    """What `session.post()` returns: usable with `async with` and `await`."""

    def __init__(self, outcome: _Response | Exception) -> None:
        self._outcome = outcome

    async def _run(self) -> _Response:
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    async def __aenter__(self) -> _Response:
        return await self._run()

    async def __aexit__(self, *args: object) -> None:
        return None

    def __await__(self):
        return self._run().__await__()


class _Session:
    """A gateway that answers each request with the next scripted outcome.

    The last outcome of a request repeats.
    """

    def __init__(
        self, script: Mapping[tuple[str, str], Sequence[_Response | Exception]]
    ):
        self._script = {key: list(value) for key, value in script.items()}
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.urls: list[str] = []

    def _request(self, method: str, url: Any, **kwargs: Any) -> _Request:
        self.requests.append((method, url.path, kwargs))
        self.urls.append(str(url))
        outcomes = self._script[(method, url.path)]
        return _Request(outcomes.pop(0) if len(outcomes) > 1 else outcomes[0])

    def post(self, url: Any, **kwargs: Any) -> _Request:
        return self._request("POST", url, **kwargs)

    def get(self, url: Any, **kwargs: Any) -> _Request:
        return self._request("GET", url, **kwargs)

    def put(self, url: Any, **kwargs: Any) -> _Request:
        return self._request("PUT", url, **kwargs)

    @property
    def calls(self) -> list[tuple[str, str]]:
        return [(method, path) for method, path, _ in self.requests]


def _gateway(
    cloud: list[_Response | Exception],
    *,
    put: list[_Response | Exception] | None = None,
    login: list[_Response | Exception] | None = None,
) -> _Session:
    return _Session(
        {
            ("POST", "/login"): login or [_Response(200, {"session": "abc"})],
            ("POST", "/logout"): [_Response(204)],
            ("GET", "/cloud_connection"): cloud,
            ("PUT", "/cloud_connection"): put or [_Response(204)],
        }
    )


def _enabled(value: bool) -> _Response:
    return _Response(200, {"enabled": value})


def _api(session: _Session, **kwargs: Any) -> GatewayConfigApi:
    return GatewayConfigApi(
        HOST, PASSWORD, session=cast(aiohttp.ClientSession, session), **kwargs
    )


@pytest.fixture
def no_sleep():
    with patch("gardena_smart_local_api.client.config_api.asyncio.sleep") as sleep:
        yield sleep


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.asyncio
async def test_get_cloud_connection(enabled: bool) -> None:
    session = _gateway([_enabled(enabled)])

    assert await _api(session).get_cloud_connection() is enabled

    assert session.calls == [
        ("POST", "/login"),
        ("GET", "/cloud_connection"),
        ("POST", "/logout"),
    ]
    assert session.requests[0][2]["json"] == {"password": PASSWORD}
    assert session.requests[1][2]["headers"] == SESSION_HEADERS
    assert session.requests[2][2]["headers"] == SESSION_HEADERS


@pytest.mark.asyncio
async def test_requests_go_to_the_port_of_the_gateway() -> None:
    session = _gateway([_enabled(True)])
    await _api(session, port=8080).get_cloud_connection()

    assert session.urls[0] == f"https://{HOST.lower()}:8080/login"


@pytest.mark.asyncio
async def test_certificate_is_not_checked_without_a_fingerprint() -> None:
    session = _gateway([_enabled(True)])

    await _api(session).get_cloud_connection()

    assert all(
        not isinstance(kwargs["ssl"], aiohttp.Fingerprint)
        for _, _, kwargs in session.requests
    )


@pytest.mark.asyncio
async def test_certificate_is_pinned_with_a_fingerprint() -> None:
    session = _gateway([_enabled(True)])

    await _api(session, fingerprint=FINGERPRINT).get_cloud_connection()

    assert all(
        isinstance(kwargs["ssl"], aiohttp.Fingerprint)
        for _, _, kwargs in session.requests
    )


def test_invalid_fingerprint() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        GatewayConfigApi(HOST, PASSWORD, fingerprint="1234")


def test_invalid_host() -> None:
    with pytest.raises(ValueError):
        GatewayConfigApi("", PASSWORD)


@pytest.mark.asyncio
async def test_set_cloud_connection_changes_the_state() -> None:
    session = _gateway([_enabled(True)])

    await _api(session).set_cloud_connection(False)

    assert session.calls == [
        ("POST", "/login"),
        ("GET", "/cloud_connection"),
        ("PUT", "/cloud_connection"),
        ("POST", "/logout"),
    ]
    assert session.requests[2][2]["json"] == {"enabled": False}
    assert session.requests[2][2]["headers"] == SESSION_HEADERS


@pytest.mark.asyncio
async def test_set_cloud_connection_leaves_the_same_state_alone() -> None:
    session = _gateway([_enabled(False)])

    await _api(session).set_cloud_connection(False)

    assert ("PUT", "/cloud_connection") not in session.calls
    assert session.calls[-1] == ("POST", "/logout")


@pytest.mark.asyncio
async def test_wrong_password() -> None:
    session = _gateway([_enabled(True)], login=[_Response(401)])

    with pytest.raises(AuthenticationError):
        await _api(session).get_cloud_connection()

    assert session.calls == [("POST", "/login")]


@pytest.mark.parametrize(
    "login",
    [
        TimeoutError(),
        aiohttp.ClientConnectionError(),
        _Response(500),
        _Response(200, {}),
    ],
)
@pytest.mark.asyncio
async def test_login_that_fails(login: _Response | Exception) -> None:
    session = _gateway([_enabled(True)], login=[login])

    with pytest.raises(ConfigApiError):
        await _api(session).get_cloud_connection()


@pytest.mark.asyncio
async def test_failed_read_is_reported_and_logs_out() -> None:
    session = _gateway([_Response(500)])

    with pytest.raises(ConfigApiError):
        await _api(session).get_cloud_connection()

    assert session.calls[-1] == ("POST", "/logout")


@pytest.mark.asyncio
async def test_answer_without_the_state_is_reported() -> None:
    session = _gateway([_Response(200, {})])

    with pytest.raises(ConfigApiError):
        await _api(session).get_cloud_connection()


@pytest.mark.asyncio
async def test_failed_logout_is_not_an_error() -> None:
    session = _gateway([_enabled(True)])
    session._script[("POST", "/logout")] = [TimeoutError()]

    assert await _api(session).get_cloud_connection() is True


@pytest.mark.asyncio
async def test_refused_change_is_reported_without_confirming(no_sleep) -> None:
    session = _gateway([_enabled(True)], put=[_Response(422)])

    with pytest.raises(ConfigApiError, match="refused"):
        await _api(session).set_cloud_connection(False)

    assert session.calls.count(("GET", "/cloud_connection")) == 1
    no_sleep.assert_not_called()


@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ServerDisconnectedError()])
@pytest.mark.asyncio
async def test_change_without_an_answer_is_confirmed_by_the_state(
    no_sleep, error: Exception
) -> None:
    # The gateway applies the change, then it does not answer for a while.
    session = _gateway(
        [_enabled(False), _Response(500), _enabled(False), _enabled(True)],
        put=[error],
    )

    await _api(session).set_cloud_connection(True)

    assert session.calls.count(("GET", "/cloud_connection")) == 4
    assert no_sleep.await_count == 3


@pytest.mark.asyncio
async def test_change_that_never_shows_is_reported(no_sleep) -> None:
    session = _gateway([_enabled(False)], put=[TimeoutError()])

    with pytest.raises(ConfigApiError, match="did not confirm"):
        await _api(session).set_cloud_connection(True)

    # One read before the change, and one per attempt to confirm it.
    assert session.calls.count(("GET", "/cloud_connection")) == 6
    assert no_sleep.await_count == 5


@pytest.mark.asyncio
async def test_change_without_an_answer_and_a_rejected_password(no_sleep) -> None:
    session = _gateway(
        [_enabled(False)],
        put=[TimeoutError()],
        login=[_Response(200, {"session": "abc"}), _Response(401)],
    )

    with pytest.raises(AuthenticationError):
        await _api(session).set_cloud_connection(True)


@pytest.mark.asyncio
async def test_failed_read_before_the_change_is_reported(no_sleep) -> None:
    session = _gateway([_Response(500)])

    with pytest.raises(ConfigApiError):
        await _api(session).set_cloud_connection(True)

    assert ("PUT", "/cloud_connection") not in session.calls
    no_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_own_session_is_created_and_closed() -> None:
    session = _gateway([_enabled(True)])
    entered = []

    class _Own(_Session):
        async def __aenter__(self) -> "_Own":
            entered.append("enter")
            return self

        async def __aexit__(self, *args: object) -> None:
            entered.append("exit")

    own = _Own({})
    own._script = session._script

    with patch(
        "gardena_smart_local_api.client.config_api.aiohttp.ClientSession"
    ) as factory:
        factory.return_value = own
        assert await GatewayConfigApi(HOST, PASSWORD).get_cloud_connection() is True

    assert entered == ["enter", "exit"]
