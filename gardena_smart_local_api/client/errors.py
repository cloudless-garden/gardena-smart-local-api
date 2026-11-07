# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later


class AuthenticationError(Exception):
    """The gateway rejected the configured password (HTTP 401)."""


class RequestError(Exception):
    """The gateway answered a request with an error or reported it as failed."""


class DiscoveryError(RequestError):
    """The gateway answered a discovery request with an error."""
