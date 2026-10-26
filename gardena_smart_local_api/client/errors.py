# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later


class AuthenticationError(Exception):
    """The gateway rejected the configured password (HTTP 401)."""


class DiscoveryError(Exception):
    """The gateway answered a discovery request with an error."""
