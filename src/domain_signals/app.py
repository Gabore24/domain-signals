"""HTTP API."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException

from domain_signals.check import run_check
from domain_signals.collectors.blocklist import DEFAULT_BLOCKLIST, collect_blocklist
from domain_signals.collectors.dns import collect_dns
from domain_signals.collectors.http import collect_http
from domain_signals.collectors.tls import collect_tls
from domain_signals.domain import InvalidDomainError, normalize_domain

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at startup: downloads the blocklist now, so the first /check
    doesn't spend its time budget on the download."""
    try:
        await DEFAULT_BLOCKLIST.get()
    except httpx.HTTPError:
        logger.warning("blocklist download failed at startup; will retry on first use")
    yield


app = FastAPI(title="domain-signals", lifespan=lifespan)


@app.get("/check/{domain}")
async def check(domain: str) -> dict[str, Any]:
    """Asks every source at once and returns one report, even if some sources fail."""
    try:
        clean = normalize_domain(domain)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await run_check(clean)


@app.get("/health")
def health() -> dict[str, str]:
    """Tells a load balancer or Docker that the service is alive."""
    return {"status": "ok"}


@app.get("/dns/{domain}")
async def dns_signals(domain: str) -> dict[str, Any]:
    """Returns the DNS records of one domain."""
    try:
        clean = normalize_domain(domain)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await collect_dns(clean)


@app.get("/tls/{domain}")
async def tls_signals(domain: str) -> dict[str, Any]:
    """Returns who issued the domain's certificate and how old it is."""
    try:
        clean = normalize_domain(domain)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await collect_tls(clean)


@app.get("/http/{domain}")
async def http_signals(domain: str) -> dict[str, Any]:
    """Returns what the domain's homepage answers: status, redirects, title."""
    try:
        clean = normalize_domain(domain)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await collect_http(clean)


@app.get("/blocklist/{domain}")
async def blocklist_signals(domain: str) -> dict[str, Any]:
    """Returns whether the domain is on a public phishing blocklist."""
    try:
        clean = normalize_domain(domain)
    except InvalidDomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await collect_blocklist(clean)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
