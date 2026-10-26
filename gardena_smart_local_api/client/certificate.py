# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import hashlib
import ssl


def no_verify_ssl_context() -> ssl.SSLContext:
    """Return an SSL context that accepts the gateway's self-signed certificate.

    Used when no fingerprint is given: the connection is encrypted but the
    gateway is not authenticated.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def parse_fingerprint(fingerprint: str) -> bytes:
    """Return the SHA-256 digest for a hex fingerprint, with or without colons."""
    try:
        digest = bytes.fromhex(fingerprint.replace(":", ""))
    except ValueError:
        digest = b""
    if len(digest) != hashlib.sha256().digest_size:
        raise ValueError(
            "fingerprint must be a SHA-256 hash: 64 hexadecimal digits, "
            "optionally separated by colons"
        )
    return digest
