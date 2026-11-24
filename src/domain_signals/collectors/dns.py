"""DNS collector: which records a domain publishes (A, AAAA, MX, NS, TXT)."""

from typing import Any, Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT")


class Resolver(Protocol):
    """Anything with dnspython's async `resolve` method. Tests pass in a fake one."""

    async def resolve(self, qname: str, rdtype: str) -> Any: ...


def _default_resolver() -> Resolver:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 5.0  # seconds for the whole lookup, retries included
    return resolver


async def collect_dns(domain: str, resolver: Resolver | None = None) -> dict[str, Any]:
    """Looks up each record type and returns the answers as plain strings.

    A missing record type is not an error (many domains have no AAAA), so it becomes an
    empty list. A domain that does not exist at all is reported once, in `error`.
    """
    resolver = resolver or _default_resolver()
    records: dict[str, list[str]] = {}

    for rdtype in RECORD_TYPES:
        try:
            answer = await resolver.resolve(domain, rdtype)
            records[rdtype] = sorted(r.to_text() for r in answer)
        except dns.resolver.NXDOMAIN:
            return {"domain": domain, "exists": False, "records": {}, "error": "NXDOMAIN"}
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            records[rdtype] = []
        except dns.exception.Timeout:
            records[rdtype] = []
            return {"domain": domain, "exists": None, "records": records, "error": "timeout"}

    return {"domain": domain, "exists": True, "records": records, "error": None}
