#!/usr/bin/env python3
"""Golden Surface store — stdlib sqlite3 over store/schema.sql.

Holds the map, not the keys: site names, URLs, owners, health, provenance.
Cookie/session values live only in browser cookie jars and never enter here.

CLI:
  python3 store/store.py init        create/migrate store/golden.db
  python3 store/store.py map         print the session map as JSON
"""
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "schema.sql"
MIGRATIONS = HERE / "migrations"
DB_PATH = Path(os.environ.get("GOLDEN_DB", HERE / "golden.db"))

OWNERS = ("abed", "r", "n")
STATUSES = ("alive", "expiring", "dead", "unknown")
WATCHERS = (
    ("session-health", "approved sessions: load in twin, verify logged-in", 900),
    ("sync-convergence", "phone_rev vs twin_rev", 30),
    ("relay-heartbeat", "relay up and answering", 60),
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=None):
    con = sqlite3.connect(str(path or DB_PATH), timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    return con


def init(path=None):
    """Create from schema.sql on first run, then apply versioned migrations."""
    con = connect(path)
    version = con.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        con.executescript(SCHEMA.read_text())
        con.execute("PRAGMA user_version=1")
        version = 1
    for f in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        n = int(f.name[:3])
        if n > version:
            con.executescript("BEGIN;" + f.read_text() + f"; PRAGMA user_version={n}; COMMIT;")
            version = n
    con.execute("INSERT OR IGNORE INTO sync_state (id) VALUES (1)")
    for wid, watches, every in WATCHERS:
        con.execute(
            "INSERT OR IGNORE INTO watchers (id, watches, every_seconds) VALUES (?,?,?)",
            (wid, watches, every),
        )
    return con


# ---- events (append-only) -------------------------------------------------

def append_event(con, kind, actor=None, payload=None):
    ts = now()
    cur = con.execute(
        "INSERT INTO events (ts, kind, actor, payload) VALUES (?,?,?,?)",
        (ts, kind, actor, json.dumps(payload or {}, ensure_ascii=False)),
    )
    return {"seq": cur.lastrowid, "ts": ts, "kind": kind, "actor": actor, "payload": payload or {}}


def events_since(con, seq=0, kinds=None, limit=500):
    q = "SELECT * FROM events WHERE seq > ?"
    args = [seq]
    if kinds:
        q += " AND kind IN (%s)" % ",".join("?" * len(kinds))
        args += list(kinds)
    q += " ORDER BY seq LIMIT ?"
    args.append(limit)
    return [_ev(r) for r in con.execute(q, args)]


def _ev(r):
    return {"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "actor": r["actor"],
            "payload": json.loads(r["payload"] or "{}")}


# ---- sites & sessions -----------------------------------------------------

def site_id_for(url_or_name):
    host = re.sub(r"^[a-z]+://", "", url_or_name.lower()).split("/")[0].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def upsert_site(con, name, base_url, added_by, category=None):
    sid = site_id_for(base_url)
    con.execute(
        "INSERT OR IGNORE INTO sites (id, name, base_url, category, added_at, added_by) "
        "VALUES (?,?,?,?,?,?)", (sid, name, base_url, category, now(), added_by))
    return sid


def find_session(con, site_id, owner):
    return con.execute("SELECT * FROM sessions WHERE site_id=? AND owner=?",
                       (site_id, owner)).fetchone()


def record_login(con, site_name, base_url, owner, approved=True):
    """Abed signed in by hand (login_done). Sharing is per site, approved each time."""
    assert owner in OWNERS
    sid = upsert_site(con, site_name, base_url, "abed")
    row = find_session(con, sid, owner)
    t = now()
    if row:
        con.execute(
            "UPDATE sessions SET status='alive', last_seen_alive_at=?, last_checked_at=?, "
            "check_failures=0, approved_by_abed_at=COALESCE(?, approved_by_abed_at) WHERE id=?",
            (t, t, t if approved else None, row["id"]))
        return row["id"]
    sess_id = uuid.uuid4().hex[:12]
    con.execute(
        "INSERT INTO sessions (id, site_id, owner, status, created_at, last_seen_alive_at, "
        "last_checked_at, approved_by_abed_at) VALUES (?,?,?,?,?,?,?,?)",
        (sess_id, sid, owner, "alive", t, t, t, t if approved else None))
    return sess_id


def approved_sessions(con):
    return [dict(r) for r in con.execute(
        "SELECT se.*, s.name AS site_name, s.base_url FROM sessions se "
        "JOIN sites s ON s.id=se.site_id WHERE se.approved_by_abed_at IS NOT NULL")]


def record_check(con, session_id, status, alive):
    assert status in STATUSES
    t = now()
    if alive:
        con.execute("UPDATE sessions SET status=?, last_checked_at=?, last_seen_alive_at=?, "
                    "check_failures=0 WHERE id=?", (status, t, t, session_id))
    else:
        con.execute("UPDATE sessions SET status=?, last_checked_at=?, "
                    "check_failures=check_failures+1 WHERE id=?", (status, t, session_id))


def session_map(con):
    """Here's what we have available: site, owner, status, last seen alive, failures."""
    return [dict(r) for r in con.execute(
        "SELECT s.name AS site, s.id AS site_id, s.base_url, se.id AS session_id, se.owner, "
        "se.status, se.last_seen_alive_at, se.last_checked_at, se.check_failures, "
        "se.approved_by_abed_at FROM sessions se JOIN sites s ON s.id = se.site_id "
        "ORDER BY s.name, se.owner")]


# ---- tabs (mirror of the last state the phone reported) -------------------

def save_tabs(con, tabs, active_id):
    t = now()
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM tabs")
        for tab in tabs:
            con.execute(
                "INSERT INTO tabs (id, owner, url, title, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (tab["id"], tab["owner"], tab["url"], tab.get("title"),
                 1 if tab["id"] == active_id else 0, tab.get("createdAt") or t, t))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


# ---- sync -----------------------------------------------------------------

def sync_state(con):
    return dict(con.execute("SELECT * FROM sync_state WHERE id=1").fetchone())


def set_revs(con, phone_rev=None, twin_rev=None):
    if phone_rev is not None:
        con.execute("UPDATE sync_state SET phone_rev=? WHERE id=1", (phone_rev,))
    if twin_rev is not None:
        con.execute("UPDATE sync_state SET twin_rev=? WHERE id=1", (twin_rev,))


def mark_converged(con):
    con.execute("UPDATE sync_state SET last_converged_at=? WHERE id=1", (now(),))


def mark_diverged(con):
    con.execute("UPDATE sync_state SET divergences=divergences+1 WHERE id=1")


# ---- watchers ---------------------------------------------------------------

def watcher_result(con, wid, result):
    con.execute("UPDATE watchers SET last_run_at=?, last_result=? WHERE id=?", (now(), result, wid))


def watchers(con):
    return [dict(r) for r in con.execute("SELECT * FROM watchers ORDER BY id")]


# ---- suggested accounts ---------------------------------------------------

def suggest(con, service, signup_url, why, added_by):
    """One account per service: a second suggestion for the same service is refused."""
    try:
        con.execute("INSERT INTO suggested (service, signup_url, why, added_by, added_at) "
                    "VALUES (?,?,?,?,?)", (service, signup_url, why, added_by, now()))
        return True
    except sqlite3.IntegrityError:
        return False


def suggested(con):
    return [dict(r) for r in con.execute("SELECT * FROM suggested ORDER BY added_at")]


def mark_suggested(con, service, status):
    con.execute("UPDATE suggested SET status=?, opened_at=COALESCE(opened_at, ?) WHERE service=?",
                (status, now(), service))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "map"
    c = init()
    if cmd == "init":
        print(f"store ready: {DB_PATH} (user_version="
              f"{c.execute('PRAGMA user_version').fetchone()[0]})")
    elif cmd == "map":
        print(json.dumps(session_map(c), indent=2))
    else:
        sys.exit(__doc__)
