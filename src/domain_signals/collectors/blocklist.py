"""Blocklist collector: is the domain on a public list of known phishing domains?

The list (Phishing Army, ~150k domains) is downloaded once and kept in memory, then
refreshed when it gets old. Checking one domain against it is a set lookup, so it's
instant; only the download takes time.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx

LIST_NAME = "phishing_army"
LIST_URL = "https://phishing.army/download/phishing_army_blocklist.txt"
# The list itself says "Expires: 4 hours".
REFRESH_SECONDS = 4 * 60 * 60


def parse_list(text: str) -> frozenset[str]:
    """One domain per line; lines starting with # are comments."""
    domains = set()
    for line in text.splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            domains.add(line)
    return frozenset(domains)


def find_match(domain: str, listed: frozenset[str]) -> str | None:
    """Returns the list entry that covers `domain`, or None.

    A listed domain also covers its subdomains: if `evil.example` is listed, then
    `login.evil.example` is bad too. The other way round isn't true: a listed
    `evil.vercel.app` says nothing about `vercel.app` itself.
    """
    labels = domain.split(".")
    for i in range(len(labels) - 1):
        candidate = ".".join(labels[i:])
        if candidate in listed:
            return candidate
    return None


class Blocklist:
    """The downloaded list plus the time it was downloaded."""

    def __init__(
        self,
        url: str = LIST_URL,
        refresh_seconds: float = REFRESH_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self.refresh_seconds = refresh_seconds
        self.clock = clock
        self.domains: frozenset[str] | None = None
        self.loaded_at: float | None = None
        # Ten requests arriving at once with an old list should cause one download, not ten.
        self._lock = asyncio.Lock()

    def is_fresh(self) -> bool:
        return self.loaded_at is not None and self.clock() - self.loaded_at < self.refresh_seconds

    async def get(self, client: httpx.AsyncClient | None = None) -> frozenset[str]:
        """Returns the list, downloading it first if it's missing or old.

        If the download fails but an older copy exists, the old copy is used: a
        few-hours-old list is far more useful than no answer at all.
        """
        async with self._lock:
            if self.is_fresh():
                return self.domains
            try:
                text = await _download(self.url, client)
            except httpx.HTTPError:
                if self.domains is not None:
                    return self.domains
                raise
            self.domains = parse_list(text)
            self.loaded_at = self.clock()
            return self.domains


async def _download(url: str, client: httpx.AsyncClient | None) -> str:
    if client is not None:
        response = await client.get(url)
    else:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as own_client:
            response = await own_client.get(url)
    response.raise_for_status()
    return response.text


# One shared list for the whole app.
DEFAULT_BLOCKLIST = Blocklist()


async def collect_blocklist(
    domain: str,
    client: httpx.AsyncClient | None = None,
    blocklist: Blocklist = DEFAULT_BLOCKLIST,
) -> dict[str, Any]:
    """Checks the domain; a failed download becomes an `error`, not a crash."""
    try:
        listed = await blocklist.get(client)
    except httpx.HTTPError as exc:
        return {"domain": domain, "list": LIST_NAME, "listed": None, "error": type(exc).__name__}
    match = find_match(domain, listed)
    return {
        "domain": domain,
        "list": LIST_NAME,
        "listed": match is not None,
        "matched": match,
        "error": None,
    }
