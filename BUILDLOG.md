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
- Phase 4 (code complete, needs a device for acceptance 5/6): app/ is
  Expo SDK 57 + TypeScript. Browser (tabs, ownership, login handoff,
  suggested cards, session list) and Najwa (SSE room). Sync/link/session
  banners. Engine seam in app/src/engine/, URL seam in
  app/src/routing.ts + schemes.ts. Local native module
  app/modules/golden-cookies (APK only). `npx tsc --noEmit` is clean and
  `npx expo export --platform android` bundles.
  Metro for Expo Go: golden-metro.service on :8491 (CI mode, so restart the
  unit after JS edits). Expo Go URL: exp://40.64.120.87:8491
  NSG rules opened: golden-relay-8490, golden-metro-8491.
  app/.env (gitignored) holds EXPO_PUBLIC_RELAY_URL + EXPO_PUBLIC_APP_TOKEN
  (from relay/.env).
- Relay hardening: every endpoint except /health and /testsite needs a
  token. URLs are redacted of secret-looking params before telemetry, the
  DB, and events.
- Docs: docs/SYNC.md (sync model + divergence classes), docs/DECISIONS.md,
  docs/PROTOCOL.md, docs/ACCEPTANCE.md.
- Phase 5 (in progress): app/plugins/withStandaloneDebug.js embeds the JS
  bundle in debug and turns dev support off, so the debug APK never
  looks for Metro. That was the likely failure mode of earlier APKs.
  Build: cd app && npx expo prebuild --platform android --no-install
  && cd android && ./gradlew assembleDebug
  Emulator: AVD "golden" (android-35 google_apis x86_64); run it with
  `sg kvm -c "~/Android/Sdk/emulator/emulator -avd golden -no-window ..."`.
- NEXT: finish the APK build, install and launch on the emulator, and run
  acceptance 5–7 against the emulator where possible.
