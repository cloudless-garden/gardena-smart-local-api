# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""WebSocket transport and request/reply lifecycle for a GARDENA smart Gateway.

Callers only deal with Request/Reply objects and pushed Events; connection,
authentication, framing, reconnects, and request/reply correlation live
here.

The client runs on aiohttp. A caller that already has an aiohttp.ClientSession
(e.g. Home Assistant's shared, pooled session) can hand it in and the client
reuses it. Without one (the CLI examples), the client creates and owns a
session.
"""

from .errors import AuthenticationError, DiscoveryError
from .gateway import GatewayClient

__all__ = [
    "AuthenticationError",
    "DiscoveryError",
    "GatewayClient",
]
