"""HTTP collector: what the website answers when you open it.

Same split as the TLS collector:
- `fetch_homepage` talks to the network.
- `summarize_response` and `extract_title` are pure logic, easy to test.
"""

from html.parser import HTMLParser
from typing import Any

import httpx

# Only the start of the page is read: the <title> is near the top, and a huge page
# shouldn't eat our time budget or memory.
MAX_BODY_BYTES = 64 * 1024

USER_AGENT = "domain-signals/0.1 (+https://github.com/Gabore24/domain-signals)"


class _TitleParser(HTMLParser):
    """Collects the text inside the first <title> tag."""

    def __init__(self) -> None:
        super().__init__()
        self._inside = False
        self._done = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "title" and not self._done:
            self._inside = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._inside:
            self._inside = False
            self._done = True

    def handle_data(self, data: str) -> None:
        if self._inside:
            self.parts.append(data)


def extract_title(html: str) -> str | None:
    """Returns the page title with whitespace tidied, or None if there isn't one."""
    parser = _TitleParser()
    parser.feed(html)
    title = " ".join("".join(parser.parts).split())
    return title or None


def summarize_response(response: httpx.Response, body: str) -> dict[str, Any]:
    """Turns the response into the few facts we care about."""
    return {
        "status_code": response.status_code,
        "final_url": str(response.url),
        "redirects": len(response.history),
        "https": response.url.scheme == "https",
        "server": response.headers.get("server"),
        "hsts": "strict-transport-security" in response.headers,
        "title": extract_title(body),
    }


async def fetch_homepage(
    domain: str, client: httpx.AsyncClient | None = None, timeout: float = 5.0
) -> tuple[httpx.Response, str]:
    """Opens https://<domain>/, follows redirects, returns the response and the page start.

    `client` can be passed in, so tests can hand over a fake one that never touches
    the network.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
    try:
        async with client.stream("GET", f"https://{domain}/") as response:
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_BODY_BYTES:
                    break
            raw = b"".join(chunks)[:MAX_BODY_BYTES]
            body = raw.decode(response.encoding or "utf-8", errors="replace")
            return response, body
    finally:
        if own_client:
            await client.aclose()


async def collect_http(domain: str, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Fetches and summarizes the homepage; failures become an `error`, not a crash."""
    try:
        response, body = await fetch_homepage(domain, client)
    except httpx.TooManyRedirects:
        return {"domain": domain, "reachable": True, "error": "TooManyRedirects"}
    except httpx.HTTPError as exc:
        return {"domain": domain, "reachable": False, "error": type(exc).__name__}
    return {
        "domain": domain,
        "reachable": True,
        "error": None,
        **summarize_response(response, body),
    }
