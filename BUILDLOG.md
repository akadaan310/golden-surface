# BUILDLOG — Golden Surface

Resume protocol: a fresh session reads SPEC.md, then this file, then
continues from "NEXT" below. Commit AND push after every phase and at
least every 15 minutes. The 5-hour plan window WILL kill the session;
the repo is the durable record.

## 2026-09-28 — session 1 (ر prompting headless Claude Code)

- Repo created (private: akadaan310/golden-surface). SPEC.md, schema,
  README seeded by ر.
- Phase 1 DONE: store/store.py (init from schema.sql + versioned
  migrations store/migrations/NNN_*.sql via PRAGMA user_version; now v3:
  002 suggested queue, 003 sessions.check_via). `python3 store/test_store.py`.
- Phase 2 DONE: relay/relay.py (aiohttp, port 8490) + relay/twin.py
  (twin model, sync model, twin browser). systemd unit golden-relay
  (systemd/golden-relay.service, installed + enabled). Tokens in
  relay/.env (gitignored; create with relay/setup-env.sh).
  Bus = events table fanned out over SSE at /bus/stream. Validate:
  `python3 tests/test_relay.py` (FakePhone stands in for the app).
  Note: the pre-existing najwa-bus.service (:8476) is left untouched.
- Phase 3 DONE: watchers/watchers.py (session-health, sync-convergence,
  relay-heartbeat), one systemd unit each (systemd/golden-watch-*.service,
  Restart=always; install all with systemd/install.sh). Intervals live in
  the watchers table. Validate: `python3 tests/test_watchers.py` (kills a
  /testsite session -> session.dead -> watcher.alert -> login_request on
  the phone). Heartbeat verified by stopping golden-relay.
- NEXT: Phase 4 — Expo app (app/).
