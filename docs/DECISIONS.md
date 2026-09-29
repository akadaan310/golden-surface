# Decisions

Where the spec was open, what was decided and why.

## Cookie isolation: tabs share one jar

Android's `CookieManager` is a single, process-wide jar. react-native-webview has no
per-WebView profile API. androidx.webkit `Profile` / MULTI_PROFILE exists, but
react-native-webview doesn't expose it.

**Decision: all tabs share one cookie jar, deliberately.** This is the session rule:
a site Abed signs into once is signed in for every tab and every seat. Ownership is
a tab attribute (who drives it), not a cookie partition.

- Consequence: one account per site at a time. This matches “one account per service.”
- `incognito` is never set. On Android it calls `removeAllCookies`, which wipes the whole jar.
- Persistence: react-native-webview flushes the jar on every `onPageFinished`. The app also
  calls `CookieManager.flush()` on background, through the local `golden-cookies` module (APK only).
  localStorage lives in the same WebView profile directory and survives restarts.
- Tabs and URLs persist to AsyncStorage on every change, and each tab reloads its last URL on relaunch.
  Back/forward history is not restored.

## Engine seam

`app/src/engine/` is the only place that imports react-native-webview. An engine is
`{name, TabView}`. A `TabView` registers a `TabHandle` (`evaluate`, `screenshot`,
`waitForLoad`, `reload`, `goBack`, `goForward`). A GeckoView engine, with per-tab contexts and real
isolation, would implement the same interface; nothing else changes.

## Google SSO

1. Primary: WebView with a Chrome-mobile user agent, so there's no `; wv` marker. Unverified: whether
   Google also keys on WebView's client-hint brand. Step 2 covers it if so.
2. If Google still refuses (`disallowed_useragent` / “browser or app may not be secure”),
   the page is detected and the app offers **Sign in via Chrome**. That opens a Chrome Custom Tab
   (`expo-web-browser.openAuthSessionAsync`, return URL `goldensurface://sso?url=…`).
3. Honest limit: a Custom Tab's cookies are Chrome's, not the Surface's. The session
   comes back only when the flow returns to `goldensurface://sso`. Otherwise the app says so in a red
   notice, and that site stays phone-driven.

## Sessions ⇄ twin

- `login_done` with approval records the session in the store (`approved_by_abed_at`).
- If the build has the cookie bridge (the APK) and the site is not VM-challenged, the cookies
  for that URL go over the websocket straight into the twin browser's jar (`twin-profile/`, mode 0700,
  gitignored). They are never written to the DB or logs. `check_via = twin`.
- Otherwise (Expo Go, or google/gmail/youtube/microsoft/apple/icloud) → `check_via = phone`, which is
  mirror-only: session-health asks the phone to probe. RN `fetch` on Android shares the
  WebView jar, so the probe sees the same session the tabs do.

## Ownership rules on `/cmd`

- Any seat may `read` / `shot` any tab. The browser is shared.
- Only a tab's owner may `open` / `tap` / `type` / `closetab` it. `newtab` creates a tab owned by the caller.
- Abed's fingers drive every tab on the phone.
- `type` refuses password fields in the page (type=password, autocomplete *password*,
  name/id like pass/pin/otp) before any keystroke.

## Relay

- One process (aiohttp, :8490) hosts the websocket, HTTP API, bus, twin model and twin browser.
  The twin browser is headless Chromium via Playwright with a persistent profile, started lazily.
- Auth: seat tokens in `relay/.env` (r, n, app, watcher). Every endpoint except `/health` and
  the `/testsite` fixture needs one. Port 8490 is open in the Azure NSG (`golden-relay-8490`),
  following this machine's per-port pattern.
- `/cmd` for a mutating op while the phone is offline: the op is queued in the twin, and the request waits up
  to 30 s, then returns `202 {queued:true}`. Non-mutating commands return `503` at once.
- Transport is plain HTTP/WS on the public IP. Tokens travel unencrypted; putting TLS in front
  (a named Cloudflare tunnel or a cert on the relay) is the next hardening step.

## Bus

- The `events` table is the bus. Everything appends there: the relay, the watchers, and `/bus/event`. One loop
  in the relay fans new rows out to SSE subscribers and reacts to them (`watcher.alert` → login
  handoff; `sync.*` → phone banner; `session.*` → session map push). That's why every event
  lands in the table: by construction.
- `/bus/event` accepts only conference kinds from r/n, and `turn.saved` needs `speaker ∈ {abed,r,n}`.
- The pre-existing `najwa-bus.service` (:8476, jsonl file) is left untouched and not bridged.

## Watchers

- Long-running loops, one systemd unit each (`Restart=always`), like the other services here.
  Intervals live in the `watchers` table (session-health 900 s, sync-convergence 5 s,
  relay-heartbeat 30 s). Set `enabled=0` to pause one.
- session-health verdicts: redirected to a login URL or a visible password field → `dead`;
  an httpOnly cookie for the site expiring within 24 h → `expiring`; a network error → `unknown`, which
  counts a failure but gives no death verdict. `watcher.alert` fires once per death.

## App

- Expo SDK 57, TypeScript, no router. There are only two surfaces, switched by a segmented control, and both
  stay mounted so background tabs and the room never stop.
- Websocket reconnect: exponential backoff from 1 s to 30 s with ±20% jitter, reset on success, and an immediate retry
  on foreground.
- Relay URL and app token come from `app/.env` (gitignored) and can be edited in the panel (☰).
- Metro for Expo Go runs as `golden-metro.service` on :8491. :8081 belongs to client-portal.
