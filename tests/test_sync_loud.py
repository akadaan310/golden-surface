"""Acceptance 7 on this machine: break sync, and the live sync-convergence unit
detects it and the relay pushes it to the phone (the app turns it into the red
OUT OF SYNC banner). Then resync, and converged is pushed.

  python3 tests/test_sync_loud.py      (needs golden-relay + golden-watch-sync-convergence running)
"""
import asyncio
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from fake_phone import FakePhone  # noqa: E402

ENV = dict(l.split("=", 1) for l in (ROOT / "relay/.env").read_text().split() if "=" in l)
BASE = "http://127.0.0.1:8490"
R = ENV["GOLDEN_TOKEN_R"]


async def wait_for(phone, status, timeout=20):
    for _ in range(timeout * 4):
        got = [m for m in phone.inbox if m["type"] == "sync" and m["status"] == status]
        if got:
            return got[-1]
        await asyncio.sleep(0.25)
    raise AssertionError(f"no sync {status} pushed; inbox={[m['type'] for m in phone.inbox]}")


async def main():
    s = aiohttp.ClientSession()
    phone = FakePhone(BASE, ENV["GOLDEN_TOKEN_APP"])
    await phone.connect()
    await asyncio.sleep(0.5)
    async with s.post(f"{BASE}/cmd", json={"token": R, "cmd": "newtab"}) as r:
        tab = (await r.json())["tab"]
    await asyncio.sleep(6)   # let the watcher see a converged pair first
    phone.inbox.clear()

    async with s.post(f"{BASE}/cmd", json={"token": R, "cmd": "desync", "tab": tab}) as r:
        print("broke sync:", await r.json())
    m = await wait_for(phone, "diverged")
    print("phone was told:", m["status"], m["classes"])
    assert "op-lost" in m["classes"]

    async with s.post(f"{BASE}/sync/resync", json={"token": ENV["GOLDEN_TOKEN_APP"], "mode": "replay"}) as r:
        assert r.status == 200
    m = await wait_for(phone, "converged")
    print("phone was told:", m["status"])

    async with s.post(f"{BASE}/cmd", json={"token": R, "cmd": "closetab", "tab": tab}) as r:
        assert (await r.json())["ok"]
    await phone.close()
    await s.close()
    print("SYNC LOUD OK")


asyncio.run(main())
