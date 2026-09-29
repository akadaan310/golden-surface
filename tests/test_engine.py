"""The engine, end to end, on this machine: addresses, the compiled shard, structures
and acts, the bridge, Lunar natures in the map.

  python3 tests/test_engine.py

Self-contained: starts two relays on a throwaway store (one with a decider, one
without), a stub decider, a stub Lunar Foundry, and a FakePhone.
"""
import asyncio
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import aiohttp
from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from fake_phone import FakePhone  # noqa: E402

A, B, DECIDER, FOUNDRY = 8494, 8495, 8497, 8498
R, N, APP = (secrets.token_urlsafe(16) for _ in range(3))

decider_calls = []
decider_script = []
foundry_urls = []


async def decider(request):
    body = await request.json()
    decider_calls.append(body)
    action = decider_script.pop(0) if decider_script else {"action": "done", "result": "nothing left"}
    return web.json_response({"choices": [{"message": {"content": "Here: " + json.dumps(action)}}]})


async def foundry(request):
    foundry_urls.append(request.query.get("u"))
    return web.json_response({"ok": True, "lens": {"natures": [{"kind": "search", "template": "https://x/?q={query}"}],
                                                   "luna": "https://luna/lens", "domain": {"tld": "com"}}})


def start_relay(port, db, **env):
    e = {**os.environ, "GOLDEN_PORT": str(port), "GOLDEN_HOST": "127.0.0.1", "GOLDEN_DB": db,
         "GOLDEN_TOKEN_R": R, "GOLDEN_TOKEN_N": N, "GOLDEN_TOKEN_APP": APP,
         "GOLDEN_TOKEN_WATCHER": secrets.token_urlsafe(8), "GOLDEN_CMD_TIMEOUT": "5", **env}
    log = open(Path(db).with_suffix(f".{port}.log"), "w")
    return subprocess.Popen([sys.executable, str(ROOT / "relay" / "relay.py")], env=e, stdout=log, stderr=log)


async def wait_up(s, port):
    for _ in range(100):
        try:
            async with s.get(f"http://127.0.0.1:{port}/health") as r:
                if r.status == 200:
                    return
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(0.1)
    raise RuntimeError(f"relay on {port} did not start")


async def main():
    tmp = tempfile.mkdtemp()
    stubs = web.Application()
    stubs.add_routes([web.post("/v1/chat/completions", decider)])
    fstub = web.Application()
    fstub.add_routes([web.get("/lens", foundry)])
    runners = []
    for app, port in ((stubs, DECIDER), (fstub, FOUNDRY)):
        rn = web.AppRunner(app)
        await rn.setup()
        await web.TCPSite(rn, "127.0.0.1", port).start()
        runners.append(rn)

    pa = start_relay(A, f"{tmp}/a.db", GOLDEN_AI_URL=f"http://127.0.0.1:{DECIDER}/v1/chat/completions",
                     LUNA_FOUNDRY_URL=f"http://127.0.0.1:{FOUNDRY}")
    pb = start_relay(B, f"{tmp}/b.db", LUNA_FOUNDRY_URL="")
    s = aiohttp.ClientSession()
    base = f"http://127.0.0.1:{A}"
    hdr = {"Authorization": f"Bearer {R}"}

    async def get(path, port=A):
        async with s.get(f"http://127.0.0.1:{port}{path}", headers=hdr) as r:
            return r.status, await r.json()

    async def post(path, body, port=A, tok=R):
        async with s.post(f"http://127.0.0.1:{port}{path}", json={"token": tok, **body}) as r:
            return r.status, await r.json()

    try:
        await wait_up(s, A)
        await wait_up(s, B)
        phone = FakePhone(base, APP)
        phone.tabs += [
            {"id": "lock-luna", "owner": "r", "url": "https://lunar-foundry.vercel.app/", "title": "Luna", "signedIn": False},
            {"id": "mail1", "owner": "abed", "url": "https://mail.google.com/mail/u/0/", "title": "Inbox", "signedIn": True},
            {"id": "rsign", "owner": "r", "url": "https://www.perplexity.ai/", "title": "Perplexity", "signedIn": True},
        ]
        await phone.connect()
        await asyncio.sleep(0.5)

        # --- the map: addresses, domains, Lunar natures; shared sessions withheld --------------------
        st, m = await get("/map")
        assert st == 200, m
        tabs = {t["id"]: t for t in m["tabs"]}
        assert tabs["abed1"]["seurl"] == "seurl://golden/tab/abed1"
        assert tabs["abed1"]["domain"]["tld"] == "com"
        assert tabs["abed1"]["lunar"]["natures"][0]["kind"] == "search", tabs["abed1"]
        assert tabs["mail1"]["lunar"] == {"withheld": "shared session"}
        assert not any("mail.google" in (u or "") or "perplexity" in (u or "") for u in foundry_urls), foundry_urls
        assert m["bridge"]["decider"] is True
        print("map ok: seurl, domain classes, Lunar natures; shared sessions never sent to the Foundry")

        # --- seurl://golden --------------------------------------------------------------------------
        st, r = await get("/seurl?u=seurl://golden/map")
        assert st == 200 and len(r["tabs"]) == 4
        st, r = await get("/seurl?u=seurl://golden/tab/abed1")
        assert r["tab"]["id"] == "abed1" and r["seurl"] == "seurl://golden/tab/abed1"
        st, r = await get("/seurl?u=seurl://golden/tab/abed1/scroll%3Ffrom%3D6%26len%3D4")
        assert st == 200 and r["text"] == "from", r
        st, r = await get("/seurl?u=seurl://golden/tab/abed1/open%3Furl%3Dhttps://x.org/")
        assert r["act"]["body"]["cmd"] == "open" and r["allowed"] is False, r
        st, r = await get("/seurl?u=seurl://elsewhere/map")
        assert st == 400
        print("seurl ok: map, tab, scroll window, open answers with the /cmd to POST, foreign addresses refused")

        # --- the shard compiles every change ---------------------------------------------------------
        st, r = await post("/cmd", {"cmd": "newtab"})
        assert st == 200, r
        tab = r["tab"]
        await asyncio.sleep(0.3)
        st, sh = await get("/shard?cursor=0&len=100")
        opened = [e for e in sh["entries"] if e["kind"] == "surface.compiled"
                  and any(o["tab"] == tab for o in e["text"]["changes"].get("opened", []))]
        assert opened, sh
        st, v = await get("/shard/verify")
        assert v["valid"] and v["checked"] >= 2, v
        st, w = await get("/shard?cursor=0&len=1")
        assert len(w["entries"]) == 1 and w["next"] == "/shard?cursor=1&len=1", w
        print(f"shard ok: {v['checked']} entries, chain valid, scrolls by cursor")

        # --- structures and act ----------------------------------------------------------------------
        st, r = await post("/cmd", {"cmd": "structures", "tab": tab})
        assert st == 200 and r["data"]["items"][2]["fingersOnly"], r
        st, r = await post("/cmd", {"cmd": "act", "tab": tab, "index": 2, "kind": "fill", "text": "x"})
        assert st == 422 and "password" in r["error"], r
        st, r = await post("/cmd", {"cmd": "act", "tab": "abed1", "index": 0, "kind": "tap"})
        assert st == 403, "agents don't act on Abed's tabs"
        print("structures/act ok: indexed items, password refused, ownership held")

        # --- the bridge ------------------------------------------------------------------------------
        decider_script[:] = [{"action": "open", "url": "https://example.org/next"},
                             {"action": "act", "index": 0, "kind": "fill", "text": "microburst"},
                             {"action": "done", "result": "searched for microburst"}]
        st, br = await post("/bridge", {"tab": tab, "goal": "search for microburst"})
        assert st == 200 and br["ok"] and br["result"] == "searched for microburst", br
        assert [t["action"]["action"] for t in br["trace"]] == ["open", "act", "done"], br["trace"]
        assert phone.tab(tab)["url"] == "https://example.org/next"
        assert phone.acts[-1]["text"] == "microburst"
        first = json.loads(decider_calls[0]["messages"][2]["content"].split("\n", 1)[1])
        assert first["items"][0]["label"] == "Search" and first["domain"] is None, first  # a blank new tab
        second = json.loads(decider_calls[1]["messages"][4]["content"].split("\n", 1)[1])
        assert second["url"] == "https://example.org/next" and second["domain"]["tld"] == "org", second
        st, sh = await get("/shard?cursor=0&len=200")
        steps = [e for e in sh["entries"] if e["kind"] == "bridge.step"]
        assert len(steps) == 3, steps
        st, v = await get("/shard/verify")
        assert v["valid"], v
        print("bridge ok: open → act → done on the real tab, every step in the shard, chain valid")

        for body, code, why in (({"tab": "lock-luna", "goal": "x"}, 403, "locked"),
                                ({"tab": "abed1", "goal": "x"}, 403, "owned by abed"),
                                ({"tab": "rsign", "goal": "x"}, 403, "shared session"),
                                ({"tab": tab, "goal": ""}, 400, "goal required")):
            st, r = await post("/bridge", body)
            assert st == code and why.split()[0] in r["error"], (body, st, r)
        calls = len(decider_calls)
        st, r = await post("/bridge", {"tab": "x", "goal": "x"}, port=B)
        assert st == 503 and "decider" in r["error"], r
        assert len(decider_calls) == calls
        print("bridge refusals ok: locked, not owned, shared session, no goal; 503 with no decider")

        st, r = await post("/cmd", {"cmd": "closetab", "tab": "lock-luna"})
        assert st == 403
        await phone.close()
        print("ALL ENGINE CHECKS PASSED")
    finally:
        await s.close()
        for p in (pa, pb):
            p.kill()
            p.wait(5)
        for rn in runners:
            await rn.cleanup()


if __name__ == "__main__":
    t0 = time.time()
    asyncio.run(main())
    print(f"({time.time() - t0:.1f}s)")
