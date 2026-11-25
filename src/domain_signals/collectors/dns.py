"""DNS collector: which records a domain publishes (A, AAAA, MX, NS, TXT)."""

import asyncio
from typing import Any, Protocol

import dns.asyncresolver
import dns.exception
import dns.resolver

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT")


class Resolver(Protocol):
    """Anything with dnspython's async `resolve` method. Tests pass in a fake one."""

    async def resolve(self, qname: str, rdtype: str) -> Any: ...


# Public resolvers instead of whatever the machine is set up with: the results are the
# same on every machine, and a dead home-router DNS can't slow every lookup down.
NAMESERVERS = ["1.1.1.1", "8.8.8.8"]


def _default_resolver() -> Resolver:
    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers = NAMESERVERS
    resolver.timeout = 1.0  # seconds to wait for one server before trying the next
    resolver.lifetime = 3.0  # seconds for the whole lookup, retries included
    return resolver


async def _lookup(resolver: Resolver, domain: str, rdtype: str) -> list[str]:
    try:
        answer = await resolver.resolve(domain, rdtype)
    except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return []
    return sorted(r.to_text() for r in answer)


async def collect_dns(domain: str, resolver: Resolver | None = None) -> dict[str, Any]:
    """Looks up every record type at the same time and returns the answers as strings.

    A missing record type is not an error (many domains have no AAAA), so it becomes an
    empty list. A domain that does not exist at all is reported once, in `error`.
    """
    resolver = resolver or _default_resolver()
    # All five lookups run side by side; return_exceptions collects errors as values
    # instead of stopping at the first one, so they can be sorted out below.
    answers = await asyncio.gather(
        *(_lookup(resolver, domain, rdtype) for rdtype in RECORD_TYPES),
        return_exceptions=True,
    )

    if any(isinstance(a, dns.resolver.NXDOMAIN) for a in answers):
        return {"domain": domain, "exists": False, "records": {}, "error": "NXDOMAIN"}

    records: dict[str, list[str]] = {}
    timed_out = False
    for rdtype, answer in zip(RECORD_TYPES, answers, strict=True):
        if isinstance(answer, dns.exception.Timeout):
            timed_out = True
            records[rdtype] = []
        elif isinstance(answer, BaseException):
            raise answer
        else:
            records[rdtype] = answer

    if timed_out:
        return {"domain": domain, "exists": None, "records": records, "error": "timeout"}
    return {"domain": domain, "exists": True, "records": records, "error": None}
