# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from ..devices import DeviceMap
from ..messages import IngressMessageList


class AuthenticationError(Exception):
    """The gateway rejected the configured password (HTTP 401)."""


class DiscoveryError(Exception):
    """The gateway answered a discovery request with an error.

    `replies` holds all replies of the discovery, in the order of its
    requests. `devices` holds the devices of the discovery requests that
    succeeded. It is not the full list, so a device missing from it may still
    exist.
    """

    def __init__(
        self, message: str, replies: IngressMessageList, devices: DeviceMap
    ) -> None:
        super().__init__(message)
        self.replies = replies
        self.devices = devices
