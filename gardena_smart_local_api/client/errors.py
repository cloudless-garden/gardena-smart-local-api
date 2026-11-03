# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from ..devices import DeviceMap
from ..messages import IngressMessageList


class AuthenticationError(Exception):
    """The gateway rejected the configured password (HTTP 401)."""


class RequestError(Exception):
    """The gateway answered a request with an error or reported it as failed.

    `replies` holds all replies of the request, in the order of its messages,
    so the caller can tell which messages took effect.
    """

    def __init__(self, message: str, replies: IngressMessageList) -> None:
        super().__init__(message)
        self.replies = replies


class DiscoveryError(RequestError):
    """The gateway answered a discovery request with an error.

    `devices` holds the devices of the discovery requests that succeeded. It
    is not the full list, so a device missing from it may still exist.
    """

    def __init__(
        self, message: str, replies: IngressMessageList, devices: DeviceMap
    ) -> None:
        super().__init__(message, replies)
        self.devices = devices
