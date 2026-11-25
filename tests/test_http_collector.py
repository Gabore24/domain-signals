"""The HTTP collector against a fake server: httpx.MockTransport answers instead of the internet."""

import httpx

from domain_signals.collectors.http import collect_http, extract_title


def fake_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_title_is_tidied():
    html = "<html><head><title>\n  Example   Domain \n</title></head></html>"
    assert extract_title(html) == "Example Domain"


def test_missing_title_is_none():
    assert extract_title("<html><body>hi</body></html>") is None


async def test_follows_redirect_and_reads_page():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(301, headers={"location": "https://www.example.com/"})
        return httpx.Response(
            200,
            headers={"server": "nginx", "strict-transport-security": "max-age=31536000"},
            html="<title>Welcome</title>",
        )

    result = await collect_http("example.com", fake_client(handler))

    assert result["reachable"] is True
    assert result["status_code"] == 200
    assert result["redirects"] == 1
    assert result["final_url"] == "https://www.example.com/"
    assert result["server"] == "nginx"
    assert result["hsts"] is True
    assert result["title"] == "Welcome"


async def test_connection_failure_becomes_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    result = await collect_http("down.example", fake_client(handler))

    assert result == {"domain": "down.example", "reachable": False, "error": "ConnectError"}
