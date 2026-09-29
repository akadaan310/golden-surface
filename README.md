# Golden Surface

One shared browser for a trusted counsel — Abed (pilot, phone, fingers),
ر (Muse, operator, this machine), ن (Hu, counsel seat, relay) — and the
Najwa room where our conference happens live.

- `SPEC.md` — the build spec. Read it first.
- `store/schema.sql` — the persistent store schema (SQLite).
- `relay/` — the relay server (websocket + HTTP).
- `bus/` — the conference event bus (SSE).
- `watchers/` — session-health, sync-convergence, relay-heartbeat.
- `app/` — the Expo React Native app (Golden Surface).
- `BUILDLOG.md` — the running build log. A fresh session resumes from here.

Rule zero: passwords never leave Abed's phone. Sessions are shared by
design, per site, with his approval.

## Run

- Units: `systemd/install.sh` installs golden-relay (:8490), golden-watch-{session-health,
  sync-convergence,relay-heartbeat}, and golden-metro (:8491, Expo Go). Tokens: `relay/setup-env.sh`.
- Store: `python3 store/store.py init|map`.
- Tests: `store/test_store.py`, `tests/test_relay.py`, `tests/test_watchers.py`, `tests/test_sync_loud.py`.
- Phone: Expo Go → `exp://40.64.120.87:8491`, or the APK (see BUILDLOG.md for the build).
- Docs: `docs/SYNC.md` (sync model), `docs/DECISIONS.md`, `docs/PROTOCOL.md`, `docs/ACCEPTANCE.md`.
