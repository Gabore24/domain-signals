"""HTTP API. For now it only has a health check."""

from fastapi import FastAPI

app = FastAPI(title="domain-signals")


@app.get("/health")
def health() -> dict[str, str]:
    """Tells a load balancer or Docker that the service is alive."""
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
