"""Phase-2 validation against a live relay.

  python3 tests/test_relay.py [base_url]     (default http://127.0.0.1:8490)
Reads tokens from relay/.env. Uses a FakePhone as the app.
"""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from fake_phone import FakePhone  # noqa: E402

ENV = dict(l.split("=", 1) for l in (ROOT / "relay/.env").read_text().split() if "=" in l)
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8490"
R, N, APP = ENV["GOLDEN_TOKEN_R"], ENV["GOLDEN_TOKEN_N"], ENV["GOLDEN_TOKEN_APP"]


async def main():
    s = aiohttp.ClientSession()

    async def cmd(tok, **kw):
        async with s.post(f"{BASE}/cmd", json={"token": tok, **kw}) as r:
            return r.status, await r.json()

    async def get(path):
        async with s.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {R}"}) as r:
            return await r.json()

    phone = FakePhone(BASE, APP)
    await phone.connect()
    await asyncio.sleep(0.3)

    # /cmd round trips
    st, res = await cmd(R, cmd="newtab")
    assert st == 200 and res["ok"], res
    tab = res["tab"]
    st, res = await cmd(R, cmd="open", tab=tab, url="https://example.org/")
    assert st == 200 and res["ok"], res
    st, res = await cmd(R, cmd="read", tab=tab)
    assert res["data"]["text"] == "hello from https://example.org/", res
    st, res = await cmd(N, cmd="read", tab=tab)
    assert st == 200, "any seat may read"
    st, res = await cmd(N, cmd="open", tab=tab, url="https://x.org/")
    assert st == 403, "only the owner drives"
    st, res = await cmd(R, cmd="open", tab="abed1", url="https://x.org/")
    assert st == 403, "agents don't drive Abed's tabs"
    st, res = await cmd(R, cmd="open", tab=tab, url="ftp://x.org/")
    assert st == 422 and "scheme" in res["error"], res
    st, res = await cmd(R, cmd="shot", tab=tab)
    assert res["data"]["png"]
    print("cmd round-trips ok")

    # /state
    state = await get("/state")
    assert {t["id"] for t in state["tabs"]} == {"abed1", tab}, state
    assert set(state["tabs"][0]) == {"id", "owner", "url", "title", "signedIn"}
    print("state ok:", json.dumps(state)[:160])

    # /sessions
    assert "sessions" in await get("/sessions")
    print("sessions ok")

    # bus: SSE streams, every event in the events table
    async with s.post(f"{BASE}/bus/event", json={"token": R, "kind": "round.opened",
                                                 "payload": {"round": 1, "topic": "session sync"}}) as r:
        seq = (await r.json())["seq"]
    async with s.post(f"{BASE}/bus/event", json={"token": N, "kind": "turn.saved",
                                                 "payload": {"round": 1, "speaker": "n", "text": "I hear it."}}) as r:
        assert r.status == 200
    got = []
    async with s.get(f"{BASE}/state") as r:
        assert r.status == 401, "reads need a token"
    async with s.get(f"{BASE}/bus/stream?since={seq - 1}&token={R}") as r:
        async for line in r.content:
            if line.startswith(b"data: "):
                got.append(json.loads(line[6:]))
                if len(got) >= 2:
                    break
    assert got[0]["kind"] == "round.opened" and got[1]["kind"] == "turn.saved", got
    db = sqlite3.connect(ROOT / "store/golden.db")
    kinds = [k for (k,) in db.execute("SELECT kind FROM events WHERE seq >= ?", (seq,))]
    assert kinds[:2] == ["round.opened", "turn.saved"], kinds
    print("bus ok: streamed", [g["kind"] for g in got], "and persisted")

    # sync: converged, then a dropped op is loud, then replay heals
    rep = await get("/sync")
    assert rep["classes"] == [] and rep["twinHash"] == rep["phoneHash"], rep
    st, res = await cmd(R, cmd="desync", tab=tab)
    rep = await get("/sync")
    assert "op-lost" in rep["classes"], rep
    print("desync detected:", rep["classes"])
    async with s.post(f"{BASE}/sync/resync", json={"token": R, "mode": "replay"}) as r:
        assert r.status == 200
    await asyncio.sleep(0.3)
    rep = await get("/sync")
    assert rep["classes"] == [] and rep["twinHash"] == rep["phoneHash"], rep
    print("replay converged")

    # link down with queued op, reconnect redelivers
    await phone.close()
    await asyncio.sleep(0.3)
    st, res = await cmd(R, cmd="newtab")   # waits CMD_TIMEOUT then 202 queued
    assert st == 202 and res["queued"], res
    rep = await get("/sync")
    assert "link-down" in rep["classes"], rep
    phone2 = FakePhone(BASE, APP)
    phone2.tabs, phone2.active, phone2.ack, phone2.rev = phone.tabs, phone.active, phone.ack, phone.rev
    await phone2.connect()
    await asyncio.sleep(0.5)
    rep = await get("/sync")
    assert rep["classes"] == [] and any(t["id"] == res["tab"] for t in phone2.tabs), rep
    print("offline op redelivered on reconnect; converged")

    st, res = await cmd(R, cmd="closetab", tab=res["tab"])
    assert res["ok"]
    await phone2.close()
    await s.close()
    print("PHASE 2 OK")


asyncio.run(main())
