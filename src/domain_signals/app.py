"""HTTP API."""

from typing import Any

from fastapi import FastAPI, HTTPException

from domain_signals.collectors.dns import collect_dns
from domain_signals.collectors.tls import collect_tls
from domain_signals.domain import InvalidDomainError, normalize_domain

app = FastAPI(title="domain-signals")


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


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
