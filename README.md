# domain-signals

Give it a domain, get back public facts about it in one JSON report:

- **DNS:** A, AAAA, MX, NS, TXT records
- **TLS:** certificate issuer, age, days left
- **HTTP:** status code, redirects, page title, HSTS
- **Blocklist:** is it on a known phishing list?

All four are checked at the same time, each with a 1.5 s limit. If one is slow or
fails, you still get the other three.

## Example

`GET /check/example.com` (shortened):

```json
{
  "domain": "example.com",
  "complete": true,
  "elapsed_ms": 124,
  "sources": {
    "dns":       { "status": "ok", "elapsed_ms": 48,  "data": { "records": { "A": ["104.20.23.154"] } } },
    "tls":       { "status": "ok", "elapsed_ms": 124, "data": { "issuer": "SSL Corporation", "days_left": 89 } },
    "http":      { "status": "ok", "elapsed_ms": 79,  "data": { "status_code": 200, "title": "Example Domain" } },
    "blocklist": { "status": "ok", "elapsed_ms": 0,   "data": { "listed": false } }
  }
}
```

`status` is `ok`, `error` (the source said no, e.g. the domain doesn't exist), `timeout`
(over the limit) or `crashed` (a bug, logged). `complete` is `true` only if all are `ok`.

Each source also has its own endpoint: `/dns/`, `/tls/`, `/http/`, `/blocklist/`.

## How it works

- `asyncio.gather` runs the sources in parallel; `asyncio.wait_for` enforces the limit.
- Collectors return errors as data instead of raising, so one bad source can't break the report.
- The phishing list (~150k domains) is downloaded at startup and refreshed every 4 hours.
- Tests never touch the network: the HTTP client, DNS resolver and clock are passed in, so
  tests can use fake ones.

## Run

```
uv sync
uv run domain-signals    # API docs at http://localhost:8000/docs
uv run pytest
```

Or with Docker: `docker build -t domain-signals .` then `docker run -p 8000:8000 domain-signals`.

Phishing list: [Phishing Army](https://phishing.army/). Built with help from Claude Code.
