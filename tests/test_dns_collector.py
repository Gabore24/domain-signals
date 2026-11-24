"""The DNS collector is tested with a fake resolver, so the tests never touch the network."""

import dns.exception
import dns.resolver

from domain_signals.collectors.dns import collect_dns


class FakeRecord:
    def __init__(self, text):
        self._text = text

    def to_text(self):
        return self._text


class FakeResolver:
    """Answers from a dict; a record type mapped to an exception raises it."""

    def __init__(self, answers):
        self.answers = answers

    async def resolve(self, qname, rdtype):
        result = self.answers.get(rdtype, dns.resolver.NoAnswer())
        if isinstance(result, Exception):
            raise result
        return [FakeRecord(t) for t in result]


async def test_collects_each_record_type():
    resolver = FakeResolver(
        {
            "A": ["93.184.215.14"],
            "MX": ["10 mail.example.com."],
            "NS": ["b.ns.example.com.", "a.ns.example.com."],
            "TXT": ['"v=spf1 -all"'],
        }
    )
    result = await collect_dns("example.com", resolver)

    assert result["exists"] is True
    assert result["error"] is None
    assert result["records"]["A"] == ["93.184.215.14"]
    assert result["records"]["AAAA"] == []  # missing type is an empty list, not an error
    assert result["records"]["NS"] == ["a.ns.example.com.", "b.ns.example.com."]  # sorted


async def test_nonexistent_domain_is_reported_once():
    resolver = FakeResolver({"A": dns.resolver.NXDOMAIN()})
    result = await collect_dns("no-such-domain.example", resolver)

    assert result == {
        "domain": "no-such-domain.example",
        "exists": False,
        "records": {},
        "error": "NXDOMAIN",
    }


async def test_timeout_stops_and_is_reported():
    resolver = FakeResolver({"A": ["1.2.3.4"], "AAAA": dns.exception.Timeout()})
    result = await collect_dns("slow.example", resolver)

    assert result["exists"] is None
    assert result["error"] == "timeout"
    assert result["records"]["A"] == ["1.2.3.4"]
