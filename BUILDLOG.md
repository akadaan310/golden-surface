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
- Phase 5 DONE: APK at app/android/app/build/outputs/apk/debug/app-debug.apk
  (android/ is generated and gitignored; rebuild with the commands below).
  Verified on the emulator (AVD "golden", stored on /mnt/apkbuild because / has
  no room): debug-signed, installs, launches, connects, commands round-trip.
  Build: cd app && npx expo prebuild --platform android --no-install
         && cd android && ./gradlew assembleDebug
  Emulator: sg kvm -c "~/Android/Sdk/emulator/emulator -avd golden -no-window
            -no-audio -no-snapshot -gpu swiftshader_indirect -memory 3072"
  (azureuser was added to the kvm group; `sg kvm` works until next login.)
- Bugs found only on a real Android runtime, all fixed: open on a fresh
  tab (now navigates via source keyed on src.n and waits for a
  non-blank load); bidi layout of "ر needs…" (LRM prefix); Najwa speaker row;
  link ping-pong between two clients (close code 4000).
- Observed once, not reproduced in 3 retries: a freshly opened r-tab missing
  after force-stop right after install -r. Keep an eye on it.
- Test sessions created during validation are retired (approved_by_abed_at
  NULL); test events stay in the append-only events table.

## STATUS — all 8 acceptance items run; one needs Abed

See docs/ACCEPTANCE.md. Remaining is human-only: Abed signs in to Google with
his own fingers on his phone (Expo Go exp://40.64.120.87:8491, or the APK),
then ر reads the page back. If Google refuses the WebView, the app offers the
Chrome Custom Tab path; its limit is in docs/DECISIONS.md.

## NEXT (not started)
- TLS in front of the relay (tokens are in cleartext over plain HTTP today).
- Hand the APK to Abed (e.g. adb install, or a private download).
- Retune session-health's expiring heuristic once real sessions exist.
