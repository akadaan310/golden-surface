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
