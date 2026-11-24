from fastapi.testclient import TestClient

from domain_signals.app import app

client = TestClient(app)


def test_dns_endpoint_rejects_non_domains():
    response = client.get("/dns/127.0.0.1")
    assert response.status_code == 422
