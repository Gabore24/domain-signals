"""TLS collector: who issued the domain's HTTPS certificate, and how old it is.

Split in two on purpose:
- `fetch_certificate` talks to the network and does nothing clever.
- `summarize_certificate` is pure logic (no network), so it is easy to test.
"""

import asyncio
import ssl
from datetime import UTC, datetime
from typing import Any

import certifi


async def fetch_certificate(domain: str, port: int = 443, timeout: float = 5.0) -> dict:
    """Opens a TLS connection and returns the certificate the server presents.

    The default SSL context checks the certificate is valid and matches the domain,
    so an expired or self-signed certificate raises ssl.SSLCertVerificationError.
    """
    # certifi ships Mozilla's list of trusted certificate authorities, so the check works
    # the same on every machine (some Python builds can't find the OS list on Windows).
    context = ssl.create_default_context(cafile=certifi.where())
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(domain, port, ssl=context, server_hostname=domain),
        timeout=timeout,
    )
    cert = writer.get_extra_info("peercert")
    writer.close()
    try:
        await writer.wait_closed()
    except (ssl.SSLError, OSError):
        # Some servers (github.com) don't close TLS politely. We already have the
        # certificate, so an error while hanging up doesn't matter.
        pass
    return cert


def _name_field(name: tuple, key: str) -> str | None:
    """Certificate names are nested tuples like ((('organizationName', 'X'),),)."""
    for part in name:
        for field, value in part:
            if field == key:
                return value
    return None


def summarize_certificate(cert: dict, now: datetime) -> dict[str, Any]:
    """Turns the raw certificate into the few facts we care about."""
    not_before = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notBefore"]), UTC)
    not_after = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), UTC)
    issuer = cert.get("issuer", ())
    return {
        "issuer": _name_field(issuer, "organizationName") or _name_field(issuer, "commonName"),
        "valid_from": not_before.isoformat(),
        "valid_until": not_after.isoformat(),
        "age_days": (now - not_before).days,
        "days_left": (not_after - now).days,
        "names_covered": len(cert.get("subjectAltName", ())),
    }


async def collect_tls(domain: str) -> dict[str, Any]:
    """Fetches and summarizes the certificate; failures become an `error`, not a crash."""
    try:
        cert = await fetch_certificate(domain)
    except ssl.SSLCertVerificationError as exc:
        return {"domain": domain, "valid": False, "error": exc.verify_message}
    except (TimeoutError, OSError) as exc:
        return {"domain": domain, "valid": None, "error": type(exc).__name__}
    summary = summarize_certificate(cert, datetime.now(UTC))
    return {"domain": domain, "valid": True, "error": None, **summary}
