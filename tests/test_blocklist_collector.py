"""Blocklist collector: pure matching logic, plus the download/refresh rules with a fake server
and a fake clock (so "4 hours later" takes no time at all)."""

import httpx

from domain_signals.collectors.blocklist import (
    Blocklist,
    collect_blocklist,
    find_match,
    parse_list,
)

LIST_TEXT = """#
# Title: test list
#
evil.example
Phish.Vercel.App
"""


def test_parse_skips_comments_and_lowercases():
    assert parse_list(LIST_TEXT) == {"evil.example", "phish.vercel.app"}


def test_exact_and_subdomain_match():
    listed = parse_list(LIST_TEXT)
    assert find_match("evil.example", listed) == "evil.example"
    assert find_match("login.evil.example", listed) == "evil.example"


def test_parent_of_listed_domain_is_not_matched():
    listed = parse_list(LIST_TEXT)
    assert find_match("vercel.app", listed) is None
    assert find_match("good.example", listed) is None


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def counting_client(responses: list) -> tuple[httpx.AsyncClient, list]:
    """A fake server that answers with `responses` in order and counts the requests."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        answer = responses[min(len(calls), len(responses)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def test_list_is_downloaded_once_then_refreshed_when_old():
    clock = FakeClock()
    blocklist = Blocklist(url="https://list.test/", refresh_seconds=100, clock=clock)
    client, calls = counting_client([httpx.Response(200, text=LIST_TEXT)])

    await collect_blocklist("a.example", client, blocklist)
    await collect_blocklist("b.example", client, blocklist)
    assert len(calls) == 1  # second check used the copy in memory

    clock.now = 101
    await collect_blocklist("c.example", client, blocklist)
    assert len(calls) == 2  # list got old, downloaded again


async def test_old_copy_is_used_when_refresh_fails():
    clock = FakeClock()
    blocklist = Blocklist(url="https://list.test/", refresh_seconds=100, clock=clock)
    client, _ = counting_client(
        [httpx.Response(200, text=LIST_TEXT), httpx.ConnectError("list site down")]
    )

    await collect_blocklist("a.example", client, blocklist)
    clock.now = 101
    result = await collect_blocklist("evil.example", client, blocklist)

    assert result["listed"] is True
    assert result["error"] is None


async def test_no_list_at_all_becomes_error():
    blocklist = Blocklist(url="https://list.test/")
    client, _ = counting_client([httpx.Response(503)])

    result = await collect_blocklist("a.example", client, blocklist)

    assert result["listed"] is None
    assert result["error"] == "HTTPStatusError"
