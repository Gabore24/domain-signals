"""Checks that user input is a plain domain name before we look anything up."""

import re

# Labels of letters, digits and hyphens, separated by dots, ending in a letter-only TLD.
_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


class InvalidDomainError(ValueError):
    """Raised when the input is not a plain domain name."""


def normalize_domain(raw: str) -> str:
    """Lower-cases the input, drops a trailing dot, and rejects anything that is not a domain.

    URLs, IP addresses, ports and paths are rejected on purpose: the service should only
    ever look up public domain names, never arbitrary addresses.
    """
    domain = raw.strip().lower().rstrip(".")
    if not _DOMAIN_RE.match(domain):
        raise InvalidDomainError(f"not a valid domain name: {raw!r}")
    return domain
