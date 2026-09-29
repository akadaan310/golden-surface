"""Phase-3 validation: kill a test session and watch the alert fire.

  python3 tests/test_watchers.py
Uses the relay's password-less /testsite fixture, signed into the twin.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "store"))
import store  # noqa: E402
from fake_phone import FakePhone  # noqa: E402

ENV = dict(l.split("=", 1) for l in (ROOT / "relay/.env").read_text().split() if "=" in l)
BASE = "http://127.0.0.1:8490"
W = ENV["GOLDEN_TOKEN_WATCHER"]


def watcher(name):
    out = subprocess.run([sys.executable, str(ROOT / "watchers/watchers.py"), name, "--once"],
                         capture_output=True, text=True, timeout=120)
    print("  ", out.stdout.strip() or out.stderr.strip())
    return out.stdout


async def main():
    con = store.init()
    s = aiohttp.ClientSession(headers={"Authorization": f"Bearer {W}"})
    async with s.post(f"{BASE}/twin/testsite-login", json={}) as r:
        assert r.status == 200, await r.text()
    sid = store.record_login(con, "testsite", f"{BASE}/testsite/", "r", True, "twin")
    seq0 = con.execute("SELECT MAX(seq) FROM events").fetchone()[0]

    phone = FakePhone(BASE, ENV["GOLDEN_TOKEN_APP"])
    await phone.connect()
    await asyncio.sleep(0.3)

    print("1. healthy session")
    watcher("session-health")
    row = next(r for r in store.session_map(con) if r["session_id"] == sid)
    assert row["status"] == "alive" and row["check_failures"] == 0, row

    print("2. kill the test session")
    async with s.delete(f"{BASE}/testsite/sessions") as r:
        print("  ", await r.json())
    watcher("session-health")
    row = next(r for r in store.session_map(con) if r["session_id"] == sid)
    assert row["status"] == "dead" and row["check_failures"] == 1, row
    kinds = [e["kind"] for e in store.events_since(con, seq0)]
    assert "session.dead" in kinds and "watcher.alert" in kinds, kinds

    print("3. relay turns the alert into a login handoff on the phone")
    for _ in range(20):
        await asyncio.sleep(0.25)
        lr = [m for m in phone.inbox if m["type"] == "login_request"]
        if lr:
            break
    assert lr and lr[-1]["site"] == "testsite", phone.inbox
    print("   phone got:", {k: lr[-1][k] for k in ("site", "url", "reason")})

    print("4. Abed signs back in (fixture) -> alive again")
    async with s.post(f"{BASE}/twin/testsite-login", json={}) as r:
        assert r.status == 200
    watcher("session-health")
    row = next(r for r in store.session_map(con) if r["session_id"] == sid)
    assert row["status"] == "alive", row

    print("5. sync-convergence + relay-heartbeat")
    assert "ok" in watcher("sync-convergence")
    assert "ok" in watcher("relay-heartbeat")

    # retire the fixture session so the scheduled watcher doesn't keep probing it
    con.execute("UPDATE sessions SET approved_by_abed_at=NULL, notes='test fixture, retired' WHERE id=?", (sid,))
    await phone.close()
    await s.close()
    print("PHASE 3 OK")


asyncio.run(main())
