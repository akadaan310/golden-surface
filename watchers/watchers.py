#!/usr/bin/env python3
"""Golden Surface watchers. One file, three watchers, each its own systemd unit.

  python3 watchers/watchers.py session-health   [--once]
  python3 watchers/watchers.py sync-convergence [--once]
  python3 watchers/watchers.py relay-heartbeat  [--once]

Every run writes watchers.last_run_at / last_result. Findings are appended to
the events table (the relay's bus fans them out and reacts to watcher.alert).
Intervals come from watchers.every_seconds; enabled=0 pauses a watcher.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "store"))
import store  # noqa: E402

ENV = {}
for line in (ROOT / "relay" / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip()
RELAY = f"http://127.0.0.1:{ENV.get('GOLDEN_PORT', '8490')}"
TOKEN = ENV["GOLDEN_TOKEN_WATCHER"]
LINK_DOWN_GRACE = 30   # seconds a dropped phone link may flap before it counts


def http(method, path, body=None, timeout=10):
    data = json.dumps({**(body or {}), "token": TOKEN}).encode() if method == "POST" else None
    req = urllib.request.Request(RELAY + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def last_result(con, wid):
    row = con.execute("SELECT last_result FROM watchers WHERE id=?", (wid,)).fetchone()
    return row[0] if row else None


# ---- session-health -------------------------------------------------------------

def tab_for(con, base_url, owner):
    host = store.site_id_for(base_url)
    rows = [dict(r) for r in con.execute("SELECT id, owner, url FROM tabs")]
    rows = [r for r in rows if store.site_id_for(r["url"]) == host]
    rows.sort(key=lambda r: r["owner"] != owner)
    return rows[0]["id"] if rows else None


def session_health(con):
    sessions = store.approved_sessions(con)
    problems = []
    for s in sessions:
        try:
            res = http("POST", "/twin/check", {"session_id": s["id"]}, timeout=60)
        except Exception as e:
            problems.append(f"{s['site_name']}: relay unreachable ({type(e).__name__})")
            continue
        status = res.get("status", "unknown")
        base = {"session": s["id"], "site": s["site_name"], "url": s["base_url"], "owner": s["owner"],
                "via": res.get("via"), "reason": res.get("reason")}
        if status in ("alive", "expiring"):
            store.record_check(con, s["id"], status, True)
            store.append_event(con, f"session.{status}", "watcher", base)
            if status == "expiring":
                problems.append(f"{s['site_name']}: expiring")
        elif status == "dead":
            was = s["status"]
            store.record_check(con, s["id"], "dead", False)
            store.append_event(con, "session.dead", "watcher", base)
            problems.append(f"{s['site_name']}: dead")
            if was != "dead":   # alert once per death; the relay turns it into a login handoff
                store.append_event(con, "watcher.alert", "watcher", {
                    **base, "watcher": "session-health", "action": "login_request",
                    "tab": tab_for(con, s["base_url"], s["owner"]), "by": "r",
                    "reason": f"{s['site_name']} session died — {res.get('reason')}"})
        else:
            store.record_check(con, s["id"], "unknown", False)
            fails = s["check_failures"] + 1
            problems.append(f"{s['site_name']}: unknown x{fails} ({res.get('reason')})")
    result = "ok" if not problems else "alert:" + "; ".join(problems)
    return result, f"{len(sessions)} checked"


# ---- sync-convergence -------------------------------------------------------------

def sync_convergence(con):
    try:
        rep = http("GET", "/sync")
    except Exception as e:
        return f"alert:relay unreachable ({type(e).__name__})", None
    classes = rep["classes"]
    if classes == ["link-down"] and rep["linkChangedAgo"] < LINK_DOWN_GRACE:
        classes = []   # brief reconnects are not divergence
    store.set_revs(con, phone_rev=rep["phoneRev"], twin_rev=rep["twinRev"])
    prev = last_result(con, "sync-convergence") or "ok"
    detail = {"classes": classes, "twinRev": rep["twinRev"], "phoneRev": rep["phoneRev"],
              "ackTwinRev": rep["ackTwinRev"], "pending": rep["pending"], "link": rep["link"],
              "twinHash": rep["twinHash"], "phoneHash": rep["phoneHash"],
              "detail": {c: rep["classDefinitions"][c] for c in classes}}
    if classes:
        now_result = "alert:" + ",".join(classes)
        if now_result != prev:
            store.mark_diverged(con)
            store.append_event(con, "sync.diverged", "watcher", detail)
        return now_result, None
    store.mark_converged(con)
    if prev != "ok":
        store.append_event(con, "sync.converged", "watcher", detail)
    return "ok", None


# ---- relay-heartbeat ----------------------------------------------------------------

def relay_heartbeat(con):
    prev = last_result(con, "relay-heartbeat") or "ok"
    try:
        h = http("GET", "/health", timeout=5)
        assert h.get("ok")
        if prev != "ok":
            store.append_event(con, "relay.recovered", "watcher", {"watcher": "relay-heartbeat"})
        return "ok", None
    except Exception as e:
        detail = f"relay not answering ({type(e).__name__})"
        if prev == "ok":
            store.append_event(con, "watcher.alert", "watcher",
                               {"watcher": "relay-heartbeat", "reason": detail})
        return "alert:" + detail, None


WATCHERS = {"session-health": session_health, "sync-convergence": sync_convergence,
            "relay-heartbeat": relay_heartbeat}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in WATCHERS:
        sys.exit(__doc__)
    wid, once = sys.argv[1], "--once" in sys.argv
    con = store.init()
    fn = WATCHERS[wid]
    while True:
        row = con.execute("SELECT every_seconds, enabled FROM watchers WHERE id=?", (wid,)).fetchone()
        if row["enabled"] or once:
            try:
                result, note = fn(con)
            except Exception as e:
                result, note = f"alert:watcher crashed ({type(e).__name__}: {e})", None
            store.watcher_result(con, wid, result)
            print(f"{wid}: {result}" + (f" ({note})" if note else ""), flush=True)
        if once:
            return
        time.sleep(row["every_seconds"])


if __name__ == "__main__":
    main()
