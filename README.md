# domain-signals

A small service that collects public technical signals about a domain
(DNS, domain age, TLS certificate, HTTP behaviour) and returns them as JSON.
Work in progress.

## Run

    uv sync
    uv run domain-signals      # http://localhost:8000/health
    uv run pytest

Built with the help of Claude Code as a coding assistant.
