#!/usr/bin/env python3
"""Golden Surface relay — websocket to the app, HTTP for ر and ن, the bus, the twin.

  WS   /ws?token=APP                 the phone (one live connection; newest wins)
  POST /cmd   {cmd, ...params, token} ر/ن command, held until the app answers
  POST /state                        the app posts full browser state on every change
  GET  /state                        telemetry: tabs [{id, owner, url, title, signedIn}], activeTabId
  GET  /sessions                     the session map
  GET  /sync                         sync report (+ classes); POST /sync/resync {mode}
  GET  /bus/stream?since=N           SSE of the events table (Last-Event-ID honoured)
  POST /bus/event {kind, payload}    append a conference event
  GET  /events?since=N&kinds=a,b     ledger query over the events table
  GET/POST /suggested                suggested-accounts queue
  POST /twin/check {session_id}      session-health asks the twin to verify a session
  GET  /health                       heartbeat
  /testsite/*                        a password-less fixture site for watcher tests

Auth: every endpoint but /health and /testsite needs a seat token — in the JSON
body, ?token=, or "Authorization: Bearer". Tokens live in relay/.env (never
git). Seats: r, n, abed (the app), watcher.
"""
import asyncio
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path

from aiohttp import WSMsgType, web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "store"))
sys.path.insert(0, str(ROOT / "relay"))
import store  # noqa: E402
from twin import (MUTATING, DIVERGENCE_CLASSES, TwinBrowser, TwinModel,  # noqa: E402
                  classify, redact_url)

CONFERENCE_KINDS = ("round.opened", "turn.saved", "chair.direction", "scribe.note", "round.closed")
SPEAKERS = {"abed": "Abed", "r": "ر", "n": "ن"}
CMD_TIMEOUT = float(os.environ.get("GOLDEN_CMD_TIMEOUT", 30))
# Sites known to challenge sessions arriving from a VM: the phone stays the driver.
VM_CHALLENGED = ("google.com", "gmail.com", "youtube.com", "live.com", "microsoft.com",
                 "apple.com", "icloud.com")


def load_env():
    env = {}
    p = ROOT / "relay" / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("GOLDEN_")})
    return env


ENV = load_env()
TOKENS = {ENV[k]: seat for k, seat in (("GOLDEN_TOKEN_R", "r"), ("GOLDEN_TOKEN_N", "n"),
                                       ("GOLDEN_TOKEN_APP", "abed"),
                                       ("GOLDEN_TOKEN_WATCHER", "watcher")) if ENV.get(k)}


class Relay:
    def __init__(self):
        self.db = store.init()
        ss = store.sync_state(self.db)
        tabs = [dict(r) for r in self.db.execute("SELECT * FROM tabs")]
        active = next((t["id"] for t in tabs if t["active"]), None)
        self.twin = TwinModel(rev=ss["twin_rev"],
                              tabs=[{"id": t["id"], "owner": t["owner"], "url": t["url"],
                                     "title": t["title"], "signedIn": False} for t in tabs],
                              active=active)
        self.twin.ack = self.twin.rev   # ops from a previous relay life are gone; declared
        self.browser = TwinBrowser(ROOT / "twin-profile")
        self.phone = None               # live WebSocketResponse
        self.waiting = {}               # cmd id -> Future
        self.subs = set()               # SSE queues
        self.last_seq = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
        self.login_queue = []           # login_requests awaiting a connected phone
        self.sync_status = {"status": "unknown", "classes": []}

    # ---- helpers ---------------------------------------------------------------
    def event(self, kind, actor, payload):
        payload = {k: redact_url(v) if k == "url" and isinstance(v, str) else v
                   for k, v in (payload or {}).items()}
        return store.append_event(self.db, kind, actor, payload)

    async def send_phone(self, msg):
        if self.phone is not None and not self.phone.closed:
            try:
                await self.phone.send_json(msg)
                return True
            except Exception:
                return False
        return False

    async def send_op(self, rec):
        ok = await self.send_phone({"type": "op", "rev": rec["rev"], "op": rec["op"],
                                    "params": rec["params"], "id": rec.get("cmd_id")})
        if ok:
            rec["sent_at"] = time.time()
        return ok

    def persist_revs(self):
        store.set_revs(self.db, phone_rev=self.twin.phone_rev, twin_rev=self.twin.rev)

    # ---- bus: the events table is the source; this loop fans it out -----------
    async def bus_loop(self):
        while True:
            try:
                rows = store.events_since(self.db, self.last_seq, limit=200)
                for ev in rows:
                    self.last_seq = ev["seq"]
                    for q in list(self.subs):
                        q.put_nowait(ev)
                    await self.react(ev)
            except Exception as e:
                print("bus_loop:", e, flush=True)
            await asyncio.sleep(0.4)

    async def react(self, ev):
        k, p = ev["kind"], ev["payload"]
        if k == "watcher.alert" and p.get("action") == "login_request":
            await self.login_request(p.get("site"), p.get("url"), p.get("tab"), p.get("by", "r"),
                                     reason=p.get("reason", "session died"))
        if k.startswith("session.") or k == "login.done":
            await self.send_phone({"type": "sessions", "sessions": store.session_map(self.db)})
        if k in ("sync.diverged", "sync.converged"):
            self.sync_status = {"status": "diverged" if k == "sync.diverged" else "converged",
                                "classes": p.get("classes", []), "detail": p.get("detail"),
                                "ts": ev["ts"]}
            await self.send_phone({"type": "sync", **self.sync_status})

    async def login_request(self, site, url, tab, by, reason=None):
        msg = {"type": "login_request", "site": site, "url": url, "tab": tab, "by": by,
               "reason": reason, "id": uuid.uuid4().hex[:8]}
        if not await self.send_phone(msg):
            self.login_queue.append(msg)
        return msg

    # ---- auth ------------------------------------------------------------------
    @staticmethod
    async def seat(request, body=None):
        tok = (body or {}).get("token") or request.query.get("token")
        auth = request.headers.get("Authorization", "")
        if not tok and auth.startswith("Bearer "):
            tok = auth[7:]
        return TOKENS.get(tok or "")

    # ---- websocket (the phone) ---------------------------------------------------
    async def ws(self, request):
        if await self.seat(request) != "abed":
            return web.Response(status=401, text="app token required")
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        if self.phone is not None and not self.phone.closed:
            # 4000 = replaced: the older client stops auto-reconnecting (no ping-pong)
            await self.phone.close(code=4000, message=b"replaced by a newer connection")
        self.phone = ws
        self.twin.link_up, self.twin.link_changed_at = True, time.time()
        self.event("link.up", "system", {"peer": request.remote})
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    await self.on_phone(json.loads(msg.data))
                except Exception as e:
                    print("on_phone:", repr(e), flush=True)
        finally:
            if self.phone is ws:
                self.phone = None
                self.twin.link_up, self.twin.link_changed_at = False, time.time()
                self.event("link.down", "system", {})
        return ws

    async def on_phone(self, m):
        t = m.get("type")
        if t == "hello":
            if m.get("state"):
                self.apply_phone_state(m["state"])
            await self.send_phone({"type": "welcome", "twinRev": self.twin.rev,
                                   "base": self.twin.base(),
                                   "sessions": store.session_map(self.db),
                                   "suggested": store.suggested(self.db),
                                   "sync": self.sync_status})
            # redeliver anything the phone hasn't processed, in order
            for rec in list(self.twin.pending):
                await self.send_op(rec)
            q, self.login_queue = self.login_queue, []
            for lr in q:
                await self.send_phone(lr)
        elif t == "state":
            self.apply_phone_state(m["state"])
        elif t == "ack":   # the phone processed twin op `rev` (applied, or rejected)
            self.twin.set_ack(int(m["rev"]))
            if m.get("rejected"):
                self.twin.reject(int(m["rev"]), m["rejected"])
                self.event("sync.conflict", "system", {"rev": m["rev"], "reason": m["rejected"]})
            if m.get("state"):
                self.apply_phone_state(m["state"])
            fut = self.waiting.pop(m.get("id"), None)
            if fut and not fut.done():
                fut.set_result({"ok": not m.get("rejected"), "error": m.get("rejected"),
                                "data": m.get("data")})
        elif t == "nack":   # the phone saw a gap: resend everything after its ack
            self.twin.set_ack(int(m.get("ack", 0)))
            if int(m.get("ack", 0)) < self.twin.base():
                await self.send_phone({"type": "rebase", "base": self.twin.base()})
            for rec in list(self.twin.pending):
                await self.send_op(rec)
        elif t == "result":
            fut = self.waiting.pop(m.get("id"), None)
            if fut and not fut.done():
                fut.set_result(m)
        elif t == "login_done":
            await self.login_done(m)
        elif t == "suggested_opened":
            store.mark_suggested(self.db, m["service"], "opened")
            self.event("suggested.opened", "abed", {"service": m["service"]})
        elif t == "signal" and m.get("kind") in ("session.signed_out", "login.custom_tab"):
            self.event(m["kind"], "abed", {k: v for k, v in m.items() if k not in ("type", "kind")})
        elif t == "probe_result":   # phone-side session check answer
            fut = self.waiting.pop(m.get("id"), None)
            if fut and not fut.done():
                fut.set_result(m)

    def apply_phone_state(self, state):
        self.twin.phone_state(state)
        store.save_tabs(self.db, [{**t, "url": redact_url(t.get("url"))} for t in state.get("tabs", [])],
                        state.get("activeTabId"))
        self.persist_revs()

    async def login_done(self, m):
        """Abed signed in with his own fingers. Record the map entry, never the keys."""
        site, url = m.get("site"), m.get("url") or ""
        tab = self.twin.tab(m.get("tab")) or {}
        owner = tab.get("owner") or m.get("owner") or "abed"
        approved = bool(m.get("approved"))
        check_via = "phone"
        host = store.site_id_for(url)
        challenged = any(host == d or host.endswith("." + d) for d in VM_CHALLENGED)
        cookies = m.get("cookies") or []
        if approved and cookies and not challenged:
            try:
                await self.browser.add_cookies(url, cookies)
                check_via = "twin"
            except Exception as e:
                print("twin add_cookies failed:", type(e).__name__, flush=True)
        if approved:
            sid = store.record_login(self.db, site or host, redact_url(url), owner, True, check_via)
        else:
            sid = None
        self.event("login.done", "abed", {
            "site": site, "url": url, "tab": m.get("tab"), "owner": owner, "session": sid,
            "shared": approved, "checkVia": check_via,
            "mirrorOnly": approved and check_via == "phone",
            "why": ("site challenges VM sessions" if challenged else
                    "cookies not exportable from this build" if approved and not cookies else None)})

    # ---- /cmd ------------------------------------------------------------------
    async def cmd(self, request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "bad json"}, status=400)
        seat = await self.seat(request, body)
        if seat not in ("r", "n"):
            return web.json_response({"ok": False, "error": "r or n token required"}, status=401)
        c = body.get("cmd")
        params = {k: v for k, v in body.items() if k not in ("cmd", "token")}

        if c == "login_request":
            msg = await self.login_request(params.get("site"), params.get("url"),
                                           params.get("tab"), seat)
            self.event("login.requested", seat, {k: msg[k] for k in ("site", "url", "tab")})
            return web.json_response({"ok": True, "delivered": self.phone is not None, "id": msg["id"]})
        if c == "resync":
            return await self._resync(seat, params.get("mode", "replay"))
        if c == "desync":   # test hook: drop one op on the floor to prove divergence is loud
            tab = params.get("tab") or (self.twin.model["tabs"][0]["id"] if self.twin.model["tabs"] else None)
            if not tab:
                return web.json_response({"ok": False, "error": "no tab"}, status=400)
            rec = self.twin.new_op("open", {"tab": tab, "url": params.get("url", "https://example.org/")})
            self.persist_revs()
            self.event("sync.test_drop", seat, {"rev": rec["rev"]})
            return web.json_response({"ok": True, "dropped": rec["rev"]})

        if c not in ("open", "read", "shot", "tap", "type", "newtab", "closetab"):
            return web.json_response({"ok": False, "error": f"unknown cmd {c}"}, status=400)

        # ownership: any seat may read/shot any tab; only a tab's owner drives it
        if c == "newtab":
            params["owner"] = params.get("owner") or seat
            if params["owner"] != seat:
                return web.json_response({"ok": False, "error": "you can only open tabs you own"}, status=403)
            params["tab"] = "t" + uuid.uuid4().hex[:8]
        else:
            tab = self.twin.tab(params.get("tab"))
            if not tab:
                return web.json_response({"ok": False, "error": "no such tab"}, status=404)
            if c in ("open", "tap", "type", "closetab") and tab["owner"] != seat:
                return web.json_response({"ok": False, "error": f"tab is owned by {tab['owner']}"}, status=403)
        if c == "open" and not params.get("url"):
            return web.json_response({"ok": False, "error": "url required"}, status=400)

        cid = uuid.uuid4().hex[:10]
        fut = asyncio.get_running_loop().create_future()
        self.waiting[cid] = fut
        rec = None
        if c in MUTATING:
            rec = self.twin.new_op(c, params)
            rec["cmd_id"] = cid
            self.persist_revs()
            await self.send_phone({"type": "op", "rev": rec["rev"], "op": c, "params": params, "id": cid})
            if self.phone is not None:
                rec["sent_at"] = time.time()
        else:
            if self.phone is None:
                self.waiting.pop(cid, None)
                return web.json_response({"ok": False, "error": "phone offline"}, status=503)
            await self.send_phone({"type": "cmd", "id": cid, "cmd": c, "params": params})
        self.event("cmd", seat, {"cmd": c, "tab": params.get("tab"),
                                 "url": params.get("url") if c == "open" else None})
        try:
            res = await asyncio.wait_for(fut, CMD_TIMEOUT)
        except asyncio.TimeoutError:
            self.waiting.pop(cid, None)
            if rec:
                return web.json_response({"ok": False, "queued": True, "rev": rec["rev"],
                                          "tab": params.get("tab"),
                                          "error": "phone did not answer; op stays queued"}, status=202)
            return web.json_response({"ok": False, "error": "phone did not answer"}, status=504)
        out = {"ok": bool(res.get("ok")), "cmd": c, "tab": params.get("tab")}
        if res.get("data") is not None:
            out["data"] = res["data"]
        if res.get("error"):
            out["error"] = res["error"]
        return web.json_response(out, status=200 if out["ok"] else 422)

    async def _resync(self, seat, mode):
        if mode == "adopt-phone":
            dropped = self.twin.adopt_phone()
            self.persist_revs()
            self.event("sync.resync", seat, {"mode": mode, "dropped": dropped})
            await self.send_phone({"type": "resync", "twinRev": self.twin.rev})
        else:
            for rec in list(self.twin.pending):
                await self.send_op(rec)
            self.event("sync.resync", seat, {"mode": "replay",
                                             "replayed": [p["rev"] for p in self.twin.pending]})
        return web.json_response({"ok": True, "sync": self.twin.sync_report()})

    # ---- state / sessions / sync -------------------------------------------------
    async def post_state(self, request):
        body = await request.json()
        if await self.seat(request, body) != "abed":
            return web.json_response({"ok": False}, status=401)
        state = body.get("state") or body
        state.pop("token", None)
        self.apply_phone_state(state)
        return web.json_response({"ok": True, "twinRev": self.twin.rev})

    async def get_state(self, request):
        return web.json_response(self.twin.telemetry())

    async def get_sessions(self, request):
        return web.json_response({"sessions": store.session_map(self.db)})

    async def get_sync(self, request):
        rep = self.twin.sync_report()
        rep["classes"] = classify(rep)
        rep["classDefinitions"] = DIVERGENCE_CLASSES
        rep["store"] = store.sync_state(self.db)
        rep["surfaced"] = self.sync_status
        return web.json_response(rep)

    async def post_resync(self, request):
        body = await request.json() if request.can_read_body else {}
        seat = await self.seat(request, body)
        if seat not in ("r", "n", "abed"):
            return web.json_response({"ok": False}, status=401)
        return await self._resync(seat, body.get("mode", "replay"))

    # ---- bus -------------------------------------------------------------------
    async def bus_stream(self, request):
        since = int(request.headers.get("Last-Event-ID") or request.query.get("since", 0))
        kinds = [k for k in request.query.get("kinds", "").split(",") if k]
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream",
                                           "Cache-Control": "no-cache",
                                           "Access-Control-Allow-Origin": "*",
                                           "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        q = asyncio.Queue()
        self.subs.add(q)

        async def emit(ev):
            if kinds and ev["kind"] not in kinds:
                return
            await resp.write(f"id: {ev['seq']}\nevent: {ev['kind']}\ndata: "
                             f"{json.dumps(ev, ensure_ascii=False)}\n\n".encode())
        try:
            hi = since
            for ev in store.events_since(self.db, since, kinds or None, limit=5000):
                await emit(ev)
                hi = ev["seq"]
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    await resp.write(b": keepalive\n\n")
                    continue
                if ev["seq"] > hi:
                    await emit(ev)
                    hi = ev["seq"]
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self.subs.discard(q)
        return resp

    async def bus_event(self, request):
        body = await request.json()
        seat = await self.seat(request, body)
        if seat not in ("r", "n", "watcher"):
            return web.json_response({"ok": False, "error": "token required"}, status=401)
        kind = body.get("kind")
        payload = body.get("payload") or {}
        if seat != "watcher" and kind not in CONFERENCE_KINDS:
            return web.json_response({"ok": False, "error": f"kind must be one of {CONFERENCE_KINDS}"},
                                     status=400)
        if kind == "turn.saved":
            sp = payload.get("speaker")
            if sp not in SPEAKERS:
                return web.json_response({"ok": False, "error": "turn.saved needs speaker abed|r|n"},
                                         status=400)
        actor = body.get("actor", seat) if seat == "watcher" else seat
        ev = self.event(kind, actor, payload)
        return web.json_response({"ok": True, "seq": ev["seq"]})

    async def get_events(self, request):
        kinds = [k for k in request.query.get("kinds", "").split(",") if k]
        evs = store.events_since(self.db, int(request.query.get("since", 0)), kinds or None,
                                 int(request.query.get("limit", 500)))
        return web.json_response({"events": evs})

    # ---- suggested accounts ------------------------------------------------------
    async def get_suggested(self, request):
        return web.json_response({"suggested": store.suggested(self.db)})

    async def post_suggested(self, request):
        body = await request.json()
        seat = await self.seat(request, body)
        if seat not in ("r", "n"):
            return web.json_response({"ok": False}, status=401)
        svc, url = (body.get("service") or "").strip().lower(), body.get("signupUrl")
        if not svc or not (url or "").startswith("https://"):
            return web.json_response({"ok": False, "error": "service and https signupUrl required"},
                                     status=400)
        if not store.suggest(self.db, svc, url, body.get("why"), seat):
            return web.json_response({"ok": False, "error": "one account per service: already queued"},
                                     status=409)
        self.event("suggested.added", seat, {"service": svc, "signupUrl": url, "why": body.get("why")})
        await self.send_phone({"type": "suggested", "suggested": store.suggested(self.db)})
        return web.json_response({"ok": True})

    # ---- twin checks (session-health) --------------------------------------------
    async def twin_check(self, request):
        body = await request.json()
        if await self.seat(request, body) != "watcher":
            return web.json_response({"ok": False}, status=401)
        row = next((s for s in store.approved_sessions(self.db) if s["id"] == body.get("session_id")), None)
        if not row:
            return web.json_response({"ok": False, "error": "no approved session"}, status=404)
        if row["check_via"] == "twin":
            res = await self.browser.check(row["base_url"])
            res["via"] = "twin"
            return web.json_response({"ok": True, **res})
        # phone-only session: ask the phone to probe with its own cookie jar
        if self.phone is None:
            return web.json_response({"ok": True, "status": "unknown", "via": "phone",
                                      "reason": "phone offline; twin mirrors state only"})
        cid = uuid.uuid4().hex[:10]
        fut = asyncio.get_running_loop().create_future()
        self.waiting[cid] = fut
        await self.send_phone({"type": "probe", "id": cid, "url": row["base_url"]})
        try:
            m = await asyncio.wait_for(fut, 40)
        except asyncio.TimeoutError:
            self.waiting.pop(cid, None)
            return web.json_response({"ok": True, "status": "unknown", "via": "phone",
                                      "reason": "phone probe timed out"})
        return web.json_response({"ok": True, "via": "phone", "status": m.get("status", "unknown"),
                                  "reason": m.get("reason"), "finalUrl": m.get("finalUrl")})

    async def health(self, request):
        return web.json_response({"ok": True, "phone": self.phone is not None,
                                  "twinRev": self.twin.rev, "lastSeq": self.last_seq})

    # ---- test fixture site ---------------------------------------------------------
    # A password-less site so watchers can be proven end to end without real accounts.
    testsite_sessions = set()

    async def ts_home(self, request):
        sid = request.cookies.get("ts_session")
        if sid not in self.testsite_sessions:
            raise web.HTTPFound("/testsite/login")
        return web.Response(text="<h1>testsite: signed in</h1>", content_type="text/html")

    async def ts_login(self, request):
        if request.method == "POST" or request.query.get("go"):
            sid = secrets.token_hex(8)
            self.testsite_sessions.add(sid)
            r = web.HTTPFound("/testsite/")
            r.set_cookie("ts_session", sid, httponly=True, max_age=30 * 86400, path="/testsite")
            raise r
        return web.Response(text="<form method=post><button>Sign in</button></form>",
                            content_type="text/html")

    async def ts_kill(self, request):
        if await self.seat(request) not in ("r", "watcher"):
            return web.json_response({"ok": False}, status=401)
        n = len(self.testsite_sessions)
        self.testsite_sessions.clear()
        return web.json_response({"ok": True, "killed": n})

    async def twin_testsite_login(self, request):
        """Fixture only: sign the twin into the password-less testsite."""
        if await self.seat(request) not in ("r", "watcher"):
            return web.json_response({"ok": False}, status=401)
        base = f"http://127.0.0.1:{request.url.port}/testsite/"
        await self.browser.start()
        page = await self.browser.ctx.new_page()
        await page.goto(base + "login?go=1")
        await page.close()
        return web.json_response({"ok": True, "base": base})


OPEN_PATHS = ("/health", "/testsite/")


@web.middleware
async def cors(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response()
    elif request.method == "GET" and not request.path.startswith(OPEN_PATHS) and \
            not await Relay.seat(request):
        resp = web.json_response({"ok": False, "error": "token required"}, status=401)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


def make_app():
    r = Relay()
    app = web.Application(middlewares=[cors], client_max_size=32 * 1024 * 1024)
    app.add_routes([
        web.get("/ws", r.ws), web.post("/cmd", r.cmd),
        web.get("/state", r.get_state), web.post("/state", r.post_state),
        web.get("/sessions", r.get_sessions),
        web.get("/sync", r.get_sync), web.post("/sync/resync", r.post_resync),
        web.get("/bus/stream", r.bus_stream), web.post("/bus/event", r.bus_event),
        web.get("/events", r.get_events),
        web.get("/suggested", r.get_suggested), web.post("/suggested", r.post_suggested),
        web.post("/twin/check", r.twin_check), web.post("/twin/testsite-login", r.twin_testsite_login),
        web.get("/health", r.health),
        web.get("/testsite/", r.ts_home), web.get("/testsite/login", r.ts_login),
        web.post("/testsite/login", r.ts_login), web.delete("/testsite/sessions", r.ts_kill),
    ])

    async def start_bg(app):
        app["bus"] = asyncio.create_task(r.bus_loop())

    async def stop_bg(app):
        app["bus"].cancel()
        await r.browser.stop()
    app.on_startup.append(start_bg)
    app.on_cleanup.append(stop_bg)
    app["relay"] = r
    return app


if __name__ == "__main__":
    if not TOKENS:
        sys.exit("relay/.env missing tokens — run relay/setup-env.sh")
    web.run_app(make_app(), host=ENV.get("GOLDEN_HOST", "0.0.0.0"),
                port=int(ENV.get("GOLDEN_PORT", 8490)), access_log=None)
