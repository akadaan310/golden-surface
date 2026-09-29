"""The twin: the relay-hosted virtual device profile.

Two parts:
  TwinModel   — the same tab model and state shape as the phone. ر/ن drive it
                through /cmd; the phone mirrors it. The sync model lives here
                and in docs/SYNC.md.
  TwinBrowser — a persistent headless Chromium profile (twin-profile/). Sessions
                Abed approves for sharing land in its cookie jar (never the DB,
                never git). session-health verifies logged-in state here.

SYNC MODEL (declared; see docs/SYNC.md for the full statement)
  * Replicas: phone P (truth for what is displayed) and twin T.
  * T mutations are ops with a monotonic twin_rev. Ops are delivered to P in
    rev order; P acknowledges with ackTwinRev (processed = applied or rejected).
    Delivery is at-least-once; P applies op r only if r == ackTwinRev + 1 and
    NACKs gaps, so redelivery is idempotent.
  * P mutations (Abed's fingers, page navigation) bump phone_rev; P posts its
    full state. T adopts P's state, then re-applies its still-pending ops.
  * Converged  <=>  link up  AND  no pending ops  AND  hash(T) == hash(P).
"""
import copy
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MUTATING = ("open", "newtab", "closetab")

# The three locked tabs (app/src/locked.ts) carry this id prefix. They are never
# closed, on any replica.
LOCK_PREFIX = "lock-"


def is_locked(tab_id):
    return isinstance(tab_id, str) and tab_id.startswith(LOCK_PREFIX)

# Divergence classes — every way P and T can disagree. Each is surfaced, none silently.
DIVERGENCE_CLASSES = {
    "link-down": "relay<->phone websocket is down; neither side can verify the other",
    "op-in-flight": "a twin op has not been acknowledged within the grace window",
    "op-lost": "phone ack is behind twin_rev with the link up (dropped message / gap)",
    "op-rejected": "phone refused a twin op (tab gone, unsupported scheme, ownership)",
    "state-mismatch": "no pending ops, yet twin and phone structural hashes differ",
    "session-mirror-only": "site signed in on the phone but its session is not in the twin",
}

GRACE_SECONDS = 10

SECRET_PARAM = re.compile(r"token|code|secret|pass|pwd|auth|session|sid|sig|key|state|otp|ticket|"
                          r"assertion|saml|nonce|credential", re.I)


def redact_url(url):
    """URLs leave the relay (telemetry, DB, events) without secrets: sensitive query and
    fragment values become REDACTED. The in-memory twin keeps the raw URL for sync."""
    if not url or "://" not in url:
        return url
    try:
        parts = urlsplit(url)
        q = urlencode([(k, "REDACTED" if SECRET_PARAM.search(k) else v)
                       for k, v in parse_qsl(parts.query, keep_blank_values=True)])
        frag = parts.fragment
        if "=" in frag:
            frag = urlencode([(k, "REDACTED" if SECRET_PARAM.search(k) else v)
                              for k, v in parse_qsl(frag, keep_blank_values=True)])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, q, frag))
    except ValueError:
        return url.split("?")[0]


def structural(state):
    """The part of state that must converge: tab ids, owners, urls, active tab.
    Titles and signedIn are observations from the phone, not synced fields."""
    tabs = sorted((t["id"], t["owner"], t.get("url") or "") for t in state.get("tabs", []))
    return {"tabs": tabs, "activeTabId": state.get("activeTabId")}


def state_hash(state):
    return hashlib.sha256(json.dumps(structural(state), sort_keys=True).encode()).hexdigest()[:16]


class TwinModel:
    def __init__(self, rev=0, tabs=None, active=None):
        self.rev = rev                      # twin_rev
        self.model = {"tabs": tabs or [], "activeTabId": active}
        self.pending = []                   # [{rev, op, params, sent_at}]
        self.phone = None                   # last full state posted by the phone
        self.phone_rev = 0
        self.ack = 0                        # phone's ackTwinRev
        self.link_up = False
        self.link_changed_at = time.time()
        self.rejected = []                  # recent op-rejected records

    # -- ops ------------------------------------------------------------------
    def tab(self, tab_id):
        return next((t for t in self.model["tabs"] if t["id"] == tab_id), None)

    def new_op(self, op, params):
        self.rev += 1
        rec = {"rev": self.rev, "op": op, "params": params, "sent_at": None}
        self.pending.append(rec)
        self._apply(self.model, rec)
        return rec

    @staticmethod
    def _apply(model, rec):
        op, p = rec["op"], rec["params"]
        tabs = model["tabs"]
        if op == "newtab":
            if not any(t["id"] == p["tab"] for t in tabs):
                tabs.append({"id": p["tab"], "owner": p["owner"], "url": p.get("url") or "about:blank",
                             "title": "", "signedIn": False})
            model["activeTabId"] = p["tab"]
        elif op == "open":
            for t in tabs:
                if t["id"] == p["tab"]:
                    t["url"] = p["url"]
        elif op == "closetab" and not is_locked(p["tab"]):
            model["tabs"] = [t for t in tabs if t["id"] != p["tab"]]
            if model["activeTabId"] == p["tab"]:
                model["activeTabId"] = model["tabs"][-1]["id"] if model["tabs"] else None

    # -- phone side -----------------------------------------------------------
    def phone_state(self, state):
        """Adopt the phone's state, drop acknowledged ops, re-apply the rest."""
        self.phone = state
        self.phone_rev = int(state.get("rev", 0))
        self.set_ack(int(state.get("ackTwinRev", 0)))
        m = {"tabs": copy.deepcopy(state.get("tabs", [])), "activeTabId": state.get("activeTabId")}
        for rec in self.pending:
            self._apply(m, rec)
        self.model = m

    def set_ack(self, ack):
        if ack > self.ack:
            self.ack = ack
        self.pending = [p for p in self.pending if p["rev"] > self.ack]

    def base(self):
        """Every op at or below base is settled (acked, or lost with a previous relay life).
        A phone whose ack is below base fast-forwards to it (declared: rebase)."""
        return self.pending[0]["rev"] - 1 if self.pending else self.rev

    def reject(self, rev, reason):
        self.rejected.append({"rev": rev, "reason": reason, "at": time.time()})
        self.rejected = self.rejected[-20:]

    def adopt_phone(self):
        """Resync mode adopt-phone: drop pending twin ops; the phone's state wins."""
        dropped = [p["rev"] for p in self.pending]
        self.ack = self.rev
        self.pending = []
        if self.phone:
            self.model = {"tabs": copy.deepcopy(self.phone.get("tabs", [])),
                          "activeTabId": self.phone.get("activeTabId")}
        return dropped

    # -- report -----------------------------------------------------------------
    def telemetry(self):
        """GET /state: what the phone last reported (the displayed truth), plus sync."""
        src = self.phone or self.model
        return {
            "tabs": [{"id": t.get("id"), "owner": t.get("owner"), "url": redact_url(t.get("url")),
                      "title": t.get("title"), "signedIn": bool(t.get("signedIn")),
                      "locked": is_locked(t.get("id")), "ai": t.get("ai")}
                     for t in src.get("tabs", [])],
            "activeTabId": src.get("activeTabId"),
            "phoneRev": self.phone_rev,
            "twinRev": self.rev,
            "link": "up" if self.link_up else "down",
        }

    def sync_report(self):
        now = time.time()
        return {
            "twinRev": self.rev,
            "phoneRev": self.phone_rev,
            "ackTwinRev": self.ack,
            "link": "up" if self.link_up else "down",
            "linkChangedAgo": round(now - self.link_changed_at, 1),
            "pending": [{"rev": p["rev"], "op": p["op"],
                         "age": round(now - p["sent_at"], 1) if p["sent_at"] else None}
                        for p in self.pending],
            "twinHash": state_hash(self.model),
            "phoneHash": state_hash(self.phone) if self.phone else None,
            "rejected": [r for r in self.rejected if now - r["at"] < 300],
            "graceSeconds": GRACE_SECONDS,
        }


def classify(report):
    """Given a sync report, return the list of active divergence classes (empty = converged)."""
    out = []
    if report["link"] == "down":
        if report["phoneHash"] is not None or report["pending"]:
            out.append("link-down")
        return out
    stale = [p for p in report["pending"] if p["age"] is None or p["age"] > report["graceSeconds"]]
    unsent = [p for p in report["pending"] if p["age"] is None]
    if unsent:
        out.append("op-lost")
    if stale and len(stale) > len(unsent):
        out.append("op-in-flight")
    # op-rejected is surfaced as a sync.conflict event (and a 422 to the caller) at the
    # moment it happens; once the twin adopts the phone's state the replicas agree again.
    if not report["pending"] and report["phoneHash"] and report["twinHash"] != report["phoneHash"]:
        out.append("state-mismatch")
    return out


# ---------------------------------------------------------------------------

LOGIN_MARKERS = ("/login", "/signin", "/sign_in", "/sign-in", "/auth", "servicelogin",
                 "accounts.google.com/v3/signin", "/session/new")


class TwinBrowser:
    """Headless Chromium with a persistent profile. Lazily started."""

    UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/130.0.0.0 Mobile Safari/537.36")

    def __init__(self, profile_dir):
        self.profile_dir = Path(profile_dir)
        self._pw = None
        self.ctx = None

    async def start(self):
        if self.ctx:
            return
        from playwright.async_api import async_playwright
        self.profile_dir.mkdir(mode=0o700, exist_ok=True)
        self._pw = await async_playwright().start()
        self.ctx = await self._pw.chromium.launch_persistent_context(
            str(self.profile_dir), headless=True, user_agent=self.UA,
            viewport={"width": 412, "height": 915})

    async def stop(self):
        if self.ctx:
            await self.ctx.close()
            await self._pw.stop()
            self.ctx = None

    async def add_cookies(self, url, cookies):
        """Place Abed-approved session cookies into the twin jar. Values are not logged."""
        await self.start()
        await self.ctx.add_cookies([{"name": c["name"], "value": c["value"], "url": url}
                                    for c in cookies if c.get("name")])

    async def check(self, url):
        """Load url, decide logged-in state. Returns {status, reason, finalUrl}."""
        await self.start()
        page = await self.ctx.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            final = page.url
            low = final.lower()
            if any(m in low for m in LOGIN_MARKERS):
                return {"status": "dead", "reason": "redirected to login", "finalUrl": final}
            if await page.locator("input[type=password]:visible").count():
                return {"status": "dead", "reason": "password field shown", "finalUrl": final}
            soon = time.time() + 24 * 3600
            host = low.split("/")[2] if "://" in low else low
            exp = [c["expires"] for c in await self.ctx.cookies(final)
                   if c.get("httpOnly") and c.get("expires", -1) > 0 and c["domain"].lstrip(".") in host]
            if exp and min(exp) < soon:
                return {"status": "expiring", "reason": "auth cookie expires within 24h",
                        "finalUrl": final}
            return {"status": "alive", "reason": "no login wall", "finalUrl": final}
        except Exception as e:  # network / timeout — not a verdict on the session
            return {"status": "unknown", "reason": f"check failed: {type(e).__name__}", "finalUrl": url}
        finally:
            await page.close()
