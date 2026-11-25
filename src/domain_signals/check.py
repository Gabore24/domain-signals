"""Runs every collector at the same time, each under its own deadline, and builds one report.

Rules:
- Sources run in parallel, so the whole check takes as long as the slowest source,
  not the sum of all of them.
- Each source gets the same deadline. A source that misses it is reported as
  "timeout" and the rest of the report still comes back (a partial answer).
- A collector that crashes with an unexpected exception is reported as "crashed";
  it can't take the other sources down with it.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from domain_signals.collectors.blocklist import collect_blocklist
from domain_signals.collectors.dns import collect_dns
from domain_signals.collectors.http import collect_http
from domain_signals.collectors.tls import collect_tls

logger = logging.getLogger(__name__)

Collector = Callable[[str], Awaitable[dict[str, Any]]]

DEFAULT_COLLECTORS: dict[str, Collector] = {
    "dns": collect_dns,
    "tls": collect_tls,
    "http": collect_http,
    "blocklist": collect_blocklist,
}

# Seconds each source may take.
DEFAULT_DEADLINE = 1.5


def _ms_since(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


async def run_source(name: str, collector: Collector, domain: str, deadline: float) -> dict:
    """Runs one collector and wraps its result with a status and how long it took."""
    start = time.perf_counter()
    try:
        data = await asyncio.wait_for(collector(domain), timeout=deadline)
    except TimeoutError:
        return {"status": "timeout", "elapsed_ms": _ms_since(start), "data": None}
    except Exception:
        # Collectors are written to return errors, not raise them. Getting here means a
        # bug, so it's logged with the full traceback, but the report still goes out.
        logger.exception("collector %s crashed on %s", name, domain)
        return {"status": "crashed", "elapsed_ms": _ms_since(start), "data": None}
    status = "ok" if data.get("error") is None else "error"
    return {"status": status, "elapsed_ms": _ms_since(start), "data": data}


async def run_check(
    domain: str,
    collectors: dict[str, Collector] | None = None,
    deadline: float = DEFAULT_DEADLINE,
) -> dict[str, Any]:
    """Checks one domain with every collector and returns the combined report."""
    collectors = collectors if collectors is not None else DEFAULT_COLLECTORS
    start = time.perf_counter()
    results = await asyncio.gather(
        *(run_source(name, fn, domain, deadline) for name, fn in collectors.items())
    )
    sources = dict(zip(collectors, results, strict=True))
    return {
        "domain": domain,
        "complete": all(r["status"] == "ok" for r in results),
        "elapsed_ms": _ms_since(start),
        "sources": sources,
    }
