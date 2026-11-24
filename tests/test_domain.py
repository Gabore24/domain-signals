import pytest

from domain_signals.domain import InvalidDomainError, normalize_domain


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "example.com"),
        ("  Example.COM.  ", "example.com"),
        ("sub.domain.co.uk", "sub.domain.co.uk"),
    ],
)
def test_valid_domains_are_normalized(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "localhost",
        "127.0.0.1",
        "http://example.com",
        "example.com/path",
        "example.com:8080",
        "-bad.com",
        "exa mple.com",
    ],
)
def test_non_domains_are_rejected(raw):
    with pytest.raises(InvalidDomainError):
        normalize_domain(raw)
