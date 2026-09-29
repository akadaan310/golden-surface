"""The surface shard: the Golden Surface, always compiled.

Every structural change the phone reports becomes one entry: which tabs
appeared or went, which URLs changed, which tab became active. Bridge steps,
llm.* signals and lifecycle events are entries too. Entries use Luna's record
format ({seq, ts, kind, from, text, id}) and are hash-chained, so the whole
record can be verified and replayed. Read it in windows: a cursor, never the
whole log.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from twin import redact_url


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hash(prev, seq, ts, kind, frm, text):
    return hashlib.sha256("|".join([prev, str(seq), ts, kind, frm, text]).encode()).hexdigest()


def structure(state):
    """The part of a state the shard compiles: {tab id: {owner, url}}, and the active tab."""
    if not state:
        return {"tabs": {}, "active": None}
    return {"tabs": {t["id"]: {"owner": t.get("owner"), "url": redact_url(t.get("url") or "")}
                     for t in state.get("tabs", [])},
            "active": state.get("activeTabId")}


def diff(before, after):
    """Structural difference between two compiled structures. Empty when nothing moved."""
    b, a = before["tabs"], after["tabs"]
    out = {}
    opened = [{"tab": k, **a[k]} for k in a if k not in b]
    closed = [k for k in b if k not in a]
    moved = [{"tab": k, "from": b[k]["url"], "to": a[k]["url"]} for k in a if k in b and a[k]["url"] != b[k]["url"]]
    if opened:
        out["opened"] = opened
    if closed:
        out["closed"] = closed
    if moved:
        out["navigated"] = moved
    if before["active"] != after["active"]:
        out["active"] = after["active"]
    return out


class Shard:
    def __init__(self, db, mirror=None):
        self.db = db
        self.mirror = Path(mirror) if mirror else None
        self.last = None  # last compiled structure

    def head(self):
        row = self.db.execute("SELECT seq, hash FROM shard ORDER BY seq DESC LIMIT 1").fetchone()
        return (row[0], row[1]) if row else (0, "0")

    def append(self, kind, frm, body):
        text = json.dumps(body, ensure_ascii=False, sort_keys=True)
        ts = _now()
        ident = hashlib.sha256(f"{time.time_ns()}|{text}".encode()).hexdigest()[:16]
        seq, prev = self.head()
        seq += 1
        h = _hash(prev, seq, ts, kind, frm, text)
        self.db.execute("INSERT INTO shard (seq, ts, kind, frm, text, id, prev, hash) VALUES (?,?,?,?,?,?,?,?)",
                        (seq, ts, kind, frm, text, ident, prev, h))
        entry = {"seq": seq, "ts": ts, "kind": kind, "from": frm, "text": body, "id": ident,
                 "prev": prev, "hash": h}
        if self.mirror:
            try:
                with open(self.mirror, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as e:
                print("shard mirror:", e, flush=True)
        return entry

    def compile(self, state, frm="abed"):
        """Compile a phone state. Appends one surface.compiled entry if the structure moved."""
        now = structure(state)
        if self.last is None:
            self.last = self._last_compiled()
        d = diff(self.last, now)
        self.last = now
        if not d:
            return None
        return self.append("surface.compiled", frm, {"changes": d, "tabs": len(now["tabs"]),
                                                     "rev": state.get("rev")})

    def _last_compiled(self):
        """Rebuild the last structure from the shard itself, so a relay restart doesn't re-log everything."""
        tabs, active = {}, None
        for (text,) in self.db.execute("SELECT text FROM shard WHERE kind='surface.compiled' ORDER BY seq"):
            ch = json.loads(text).get("changes", {})
            for o in ch.get("opened", []):
                tabs[o["tab"]] = {"owner": o.get("owner"), "url": o.get("url")}
            for k in ch.get("closed", []):
                tabs.pop(k, None)
            for m in ch.get("navigated", []):
                if m["tab"] in tabs:
                    tabs[m["tab"]]["url"] = m["to"]
            if "active" in ch:
                active = ch["active"]
        return {"tabs": tabs, "active": active}

    def window(self, cursor=0, size=50):
        rows = self.db.execute("SELECT seq, ts, kind, frm, text, id, prev, hash FROM shard WHERE seq > ? "
                               "ORDER BY seq LIMIT ?", (cursor, size)).fetchall()
        entries = [{"seq": r[0], "ts": r[1], "kind": r[2], "from": r[3], "text": json.loads(r[4]), "id": r[5],
                    "prev": r[6], "hash": r[7]} for r in rows]
        head, _ = self.head()
        last = entries[-1]["seq"] if entries else cursor
        return {"cursor": cursor, "entries": entries, "head": head,
                "next": f"/shard?cursor={last}&len={size}" if last < head else None}

    def verify(self):
        prev, n = "0", 0
        for seq, ts, kind, frm, text, p, h in self.db.execute(
                "SELECT seq, ts, kind, frm, text, prev, hash FROM shard ORDER BY seq"):
            if p != prev or _hash(p, seq, ts, kind, frm, text) != h:
                return {"valid": False, "brokenAt": seq, "checked": n}
            prev, n = h, n + 1
        return {"valid": True, "checked": n, "head": prev}
