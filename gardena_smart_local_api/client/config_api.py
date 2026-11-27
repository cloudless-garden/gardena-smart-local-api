# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Client for the configuration API of a GARDENA smart Gateway.

The local WebSocket API has no setting for the cloud connection. The gateway
offers it in a separate JSON API over HTTPS, which uses the same password.
"""

import asyncio
import logging
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiohttp
from yarl import URL

from .certificate import no_verify_ssl_context, parse_fingerprint
from .errors import AuthenticationError, ConfigApiError

_LOGGER = logging.getLogger(__name__)

CONFIG_API_PORT = 443

# How long the gateway has to answer a request.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

# The gateway applies a changed cloud connection before it answers. Connecting
# to the cloud took 21 seconds on a gateway, disconnecting took 5. It may not
# answer at all while it restarts its services.
CHANGE_TIMEOUT = aiohttp.ClientTimeout(total=60)

# How often, and how long apart, the state is read to see whether a change that
# got no answer was applied.
CONFIRM_ATTEMPTS = 5
CONFIRM_DELAY = 3


class GatewayConfigApi:
    """Change settings of a gateway that its WebSocket API does not offer.

        config_api = GatewayConfigApi("GARDENA-123456", "password")
        await config_api.set_cloud_connection(False)

    Every call logs in and out again. A `session` of the caller is used and
    never closed, without one each call uses a session of its own. Without a
    `fingerprint` any certificate is accepted, so the password goes to
    whoever answers.
    """

    def __init__(
        self,
        host: str,
        password: str,
        *,
        port: int = CONFIG_API_PORT,
        session: aiohttp.ClientSession | None = None,
        fingerprint: str | None = None,
    ) -> None:
        """Raise `ValueError` for a host or a fingerprint that is not valid."""
        self._base = URL.build(scheme="https", host=host, port=port)
        self._host = host
        self._password = password
        self._session = session
        self._ssl: ssl.SSLContext | aiohttp.Fingerprint = (
            aiohttp.Fingerprint(parse_fingerprint(fingerprint))
            if fingerprint is not None
            else no_verify_ssl_context()
        )

    async def get_cloud_connection(self) -> bool:
        """Return whether the gateway is connected to the GARDENA cloud.

        Raises `AuthenticationError` if the gateway rejects the password, and
        `ConfigApiError` if it cannot be used.
        """
        async with self._logged_in() as (session, headers):
            return await self._read_cloud_connection(session, headers)

    async def set_cloud_connection(self, enabled: bool) -> None:
        """Connect the gateway to the GARDENA cloud, or disconnect it from there.

        Raises `AuthenticationError` if the gateway rejects the password, and
        `ConfigApiError` if it refuses the change or does not end up in the state.
        """
        async with self._logged_in() as (session, headers):
            try:
                if await self._read_cloud_connection(session, headers) == enabled:
                    return
                async with session.put(
                    self._base / "cloud_connection",
                    json={"enabled": enabled},
                    headers=headers,
                    ssl=self._ssl,
                    timeout=CHANGE_TIMEOUT,
                ) as response:
                    response.raise_for_status()
                return
            except aiohttp.ClientResponseError as err:
                raise ConfigApiError(
                    f"The gateway {self._host} refused the cloud connection "
                    f"change: {err}"
                ) from err
            except (aiohttp.ClientError, TimeoutError) as err:
                # The change may have been applied without an answer. Look at
                # the state of the gateway instead of guessing.
                _LOGGER.debug(
                    "No answer from %s to the cloud connection change: %r",
                    self._host,
                    err,
                )

        for _ in range(CONFIRM_ATTEMPTS):
            await asyncio.sleep(CONFIRM_DELAY)
            try:
                if await self.get_cloud_connection() == enabled:
                    return
            except ConfigApiError:
                _LOGGER.debug("Gateway %s is not reachable yet", self._host)
        raise ConfigApiError(
            f"The gateway {self._host} did not confirm the cloud connection change"
        )

    async def _read_cloud_connection(
        self, session: aiohttp.ClientSession, headers: dict[str, str]
    ) -> bool:
        try:
            async with session.get(
                self._base / "cloud_connection",
                headers=headers,
                ssl=self._ssl,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                return bool((await response.json())["enabled"])
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            raise ConfigApiError(
                f"Could not read the cloud connection of {self._host}: {err}"
            ) from err

    @asynccontextmanager
    async def _logged_in(
        self,
    ) -> AsyncIterator[tuple[aiohttp.ClientSession, dict[str, str]]]:
        if self._session is not None:
            async with self._login(self._session) as headers:
                yield self._session, headers
            return
        async with aiohttp.ClientSession() as session:
            async with self._login(session) as headers:
                yield session, headers

    @asynccontextmanager
    async def _login(
        self, session: aiohttp.ClientSession
    ) -> AsyncIterator[dict[str, str]]:
        try:
            async with session.post(
                self._base / "login",
                json={"password": self._password},
                ssl=self._ssl,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status == 401:
                    raise AuthenticationError(
                        f"The gateway {self._host} rejected the password"
                    )
                response.raise_for_status()
                headers = {"X-session": (await response.json())["session"]}
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
            raise ConfigApiError(f"Could not log in to {self._host}: {err}") from err

        try:
            yield headers
        finally:
            try:
                await session.post(
                    self._base / "logout",
                    headers=headers,
                    ssl=self._ssl,
                    timeout=REQUEST_TIMEOUT,
                )
            except (aiohttp.ClientError, TimeoutError):
                _LOGGER.debug("Could not log out of %s", self._host, exc_info=True)
