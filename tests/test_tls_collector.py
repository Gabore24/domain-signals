"""Only the pure part is tested here: a hand-written certificate in, a summary out."""

from datetime import UTC, datetime

from domain_signals.collectors.tls import summarize_certificate

CERT = {
    "issuer": (
        (("countryName", "US"),),
        (("organizationName", "Let's Encrypt"),),
        (("commonName", "R11"),),
    ),
    "notBefore": "Nov  1 00:00:00 2026 GMT",
    "notAfter": "Jan 30 00:00:00 2027 GMT",
    "subjectAltName": (("DNS", "example.com"), ("DNS", "www.example.com")),
}


def test_summary_reads_issuer_and_dates():
    now = datetime(2026, 11, 25, tzinfo=UTC)
    summary = summarize_certificate(CERT, now)

    assert summary["issuer"] == "Let's Encrypt"
    assert summary["age_days"] == 24
    assert summary["days_left"] == 66
    assert summary["names_covered"] == 2


def test_issuer_falls_back_to_common_name():
    cert = {**CERT, "issuer": ((("commonName", "Some CA"),),)}
    summary = summarize_certificate(cert, datetime(2026, 11, 25, tzinfo=UTC))
    assert summary["issuer"] == "Some CA"
