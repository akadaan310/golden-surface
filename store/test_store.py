"""Phase-1 validation: python3 store/test_store.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import store

p = os.path.join(tempfile.mkdtemp(), "t.db")
c = store.init(p)
assert c.execute("PRAGMA user_version").fetchone()[0] == 2
store.init(p)  # idempotent
sid = store.record_login(c, "Gmail", "https://mail.google.com/", "abed")
store.record_login(c, "GitHub", "https://github.com/login", "r")
m = store.session_map(c)
assert [r["site"] for r in m] == ["GitHub", "Gmail"], m
assert m[1]["status"] == "alive" and m[1]["approved_by_abed_at"]
store.record_check(c, sid, "dead", False)
assert store.session_map(c)[1]["check_failures"] == 1
e = store.append_event(c, "round.opened", "r", {"round": 1})
assert store.events_since(c, 0)[0]["seq"] == e["seq"]
assert store.suggest(c, "proton", "https://proton.me/signup", "shared mail", "r")
assert not store.suggest(c, "proton", "https://x", "dup", "n")
cols = {r[1] for t in ("sites", "sessions", "tabs") for r in c.execute(f"PRAGMA table_info({t})")}
assert not any(k in cols for k in ("cookie", "token", "password", "value")), cols
print("store ok:", len(m), "sessions in map")
