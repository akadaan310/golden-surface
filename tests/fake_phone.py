"""A protocol-faithful stand-in for the app, for validating the relay on this machine.

Implements the phone side of the sync model exactly as app/src/sync.ts does:
ops applied only in rev order (gap -> nack), ack after processing, full state
posted on every change.
"""
import asyncio
import json
import uuid

import aiohttp


class FakePhone:
    def __init__(self, base, token):
        self.base, self.token = base, token
        self.tabs = [{"id": "abed1", "owner": "abed", "url": "https://example.com/", "title": "Example",
                      "signedIn": False}]
        self.active = "abed1"
        self.rev = 0
        self.ack = 0
        self.inbox = []           # everything the relay pushed
        self.drop_next_op = False
        self.ws = None
        self.structures_seen = []  # tabs whose structures were asked for
        self.acts = []             # act commands received

    def state(self):
        return {"rev": self.rev, "ackTwinRev": self.ack, "tabs": self.tabs, "activeTabId": self.active}

    async def connect(self):
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect(f"{self.base}/ws?token={self.token}")
        await self.ws.send_json({"type": "hello", "state": self.state()})
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        self.task.cancel()
        await self.ws.close()
        await self.session.close()

    async def post_state(self):
        async with self.session.post(f"{self.base}/state", json={"token": self.token, "state": self.state()}) as r:
            assert r.status == 200, await r.text()

    async def local_change(self, fn):
        fn(self)
        self.rev += 1
        await self.post_state()

    def tab(self, tid):
        return next((t for t in self.tabs if t["id"] == tid), None)

    async def loop(self):
        async for msg in self.ws:
            m = json.loads(msg.data)
            self.inbox.append(m)
            if m["type"] in ("welcome", "rebase"):
                self.ack = max(self.ack, m["base"])
            elif m["type"] == "op":
                if self.drop_next_op:
                    self.drop_next_op = False
                    continue
                if m["rev"] <= self.ack:
                    continue                                  # duplicate delivery
                if m["rev"] != self.ack + 1:
                    await self.ws.send_json({"type": "nack", "ack": self.ack})
                    continue
                rejected = self.apply(m["op"], m["params"])
                self.ack = m["rev"]
                self.rev += 1
                await self.ws.send_json({"type": "ack", "rev": m["rev"], "id": m.get("id"),
                                         "rejected": rejected, "state": self.state()})
            elif m["type"] == "cmd":
                p = m["params"]
                t = self.tab(p.get("tab"))
                if not t:
                    res = {"ok": False, "error": "no such tab"}
                elif m["cmd"] == "read":
                    res = {"ok": True, "data": {"url": t["url"], "title": t["title"], "text": "hello from " + t["url"]}}
                elif m["cmd"] == "shot":
                    res = {"ok": True, "data": {"png": "iVBORw0KGgo="}}
                elif m["cmd"] == "type":
                    res = {"ok": True, "data": {"typed": len(p["text"])}}
                elif m["cmd"] == "structures":
                    self.structures_seen.append(p["tab"])
                    res = {"ok": True, "data": {"url": t["url"], "title": t["title"], "count": 3, "items": [
                        {"i": 0, "kind": "field", "label": "Search", "name": "q", "type": "search"},
                        {"i": 1, "kind": "button", "label": "Go"},
                        {"i": 2, "kind": "field", "label": "Password", "name": "pw", "type": "password",
                         "fingersOnly": True}]}}
                elif m["cmd"] == "act":
                    self.acts.append(p)
                    if int(p.get("index", -1)) == 2:
                        res = {"ok": False, "error": "refused: password field — Abed types these himself"}
                    else:
                        res = {"ok": True, "data": {"done": p.get("kind"), "index": p.get("index")}}
                else:
                    res = {"ok": True, "data": {}}
                await self.ws.send_json({"type": "result", "id": m["id"], **res})
            elif m["type"] == "probe":
                await self.ws.send_json({"type": "probe_result", "id": m["id"], "status": "alive",
                                         "reason": "fake", "finalUrl": m["url"]})

    def apply(self, op, p):
        if op == "newtab":
            self.tabs.append({"id": p["tab"], "owner": p["owner"], "url": p.get("url") or "about:blank",
                              "title": "", "signedIn": False})
            self.active = p["tab"]
        elif op == "open":
            t = self.tab(p["tab"])
            if not t:
                return "no such tab"
            if not p["url"].startswith(("http://", "https://", "about:")):
                return "scheme not supported"
            t["url"] = p["url"]
        elif op == "closetab":
            if not self.tab(p["tab"]):
                return "no such tab"
            self.tabs = [t for t in self.tabs if t["id"] != p["tab"]]
            if self.active == p["tab"]:
                self.active = self.tabs[-1]["id"] if self.tabs else None
        return None
