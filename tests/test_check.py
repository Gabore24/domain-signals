"""run_check with fake collectors: one fast, one slow, one that reports an error, one that crashes.
No network, and a short deadline keeps the test fast."""

import asyncio
import time

from domain_signals.check import run_check


async def fast(domain):
    return {"domain": domain, "error": None, "answer": 42}


async def slow(domain):
    await asyncio.sleep(5)
    return {"domain": domain, "error": None}


async def reports_error(domain):
    return {"domain": domain, "error": "NXDOMAIN"}


async def crashes(domain):
    raise RuntimeError("bug in collector")


async def test_all_ok_is_complete():
    report = await run_check("example.com", {"a": fast, "b": fast}, deadline=0.2)

    assert report["complete"] is True
    assert report["sources"]["a"]["status"] == "ok"
    assert report["sources"]["a"]["data"]["answer"] == 42


async def test_partial_report_when_sources_fail():
    collectors = {"fast": fast, "slow": slow, "error": reports_error, "crash": crashes}
    report = await run_check("example.com", collectors, deadline=0.2)

    statuses = {name: s["status"] for name, s in report["sources"].items()}
    assert statuses == {"fast": "ok", "slow": "timeout", "error": "error", "crash": "crashed"}
    assert report["complete"] is False
    assert report["sources"]["fast"]["data"]["answer"] == 42


async def test_sources_run_in_parallel():
    async def takes_a_while(domain):
        await asyncio.sleep(0.1)
        return {"error": None}

    start = time.perf_counter()
    await run_check("example.com", {f"s{i}": takes_a_while for i in range(5)}, deadline=1)
    elapsed = time.perf_counter() - start

    # Five sources of 0.1 s each: one after another would be 0.5 s, side by side ~0.1 s.
    assert elapsed < 0.3
