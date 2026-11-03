# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import asyncio
import contextlib
import hashlib
import ssl

from cryptography import x509


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


def fingerprint_from_certificate(certificate: bytes) -> str:
    """Return the SHA-256 fingerprint (hex) of a DER certificate.

    Pass it as `fingerprint` to `GatewayClient` to pin the gateway.
    """
    return hashlib.sha256(certificate).hexdigest()


async def fetch_certificate(host: str, port: int, timeout: float = 10) -> bytes:
    """Return the DER certificate a gateway presents, without authenticating.

    Needs no password, so a setup flow can learn the fingerprint to pin and the
    hostname before it asks for one. The certificate is self-signed and not
    verified: trust it on first use only.

    Raises `TimeoutError` if the TLS handshake takes longer than `timeout`
    seconds, `OSError` if the gateway cannot be reached, and
    `ConnectionError` if it presents no certificate.
    """
    async with asyncio.timeout(timeout):
        _, writer = await asyncio.open_connection(
            host, port, ssl=no_verify_ssl_context()
        )
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        certificate = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
    if not certificate:
        raise ConnectionError("The gateway did not present a certificate")
    return certificate


def hostname_from_certificate(certificate: bytes) -> str | None:
    """Return the gateway's mDNS hostname from its DER certificate.

    The certificate lists the hostname (``GARDENA-xxxxxx.local``) as a DNS
    name in the subjectAltName. It derives from the gateway's MAC address and
    survives a certificate regeneration, so it identifies a gateway reliably.
    Returns the name without ``.local``, or None for firmware whose
    certificate has no such name.
    """
    parsed = x509.load_der_x509_certificate(certificate)
    try:
        alt_names = parsed.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )
    except x509.ExtensionNotFound:
        return None

    for dns_name in alt_names.value.get_values_for_type(x509.DNSName):
        if dns_name.endswith(".local"):
            return dns_name.removesuffix(".local")
    return None
