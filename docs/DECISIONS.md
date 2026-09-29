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

## APK

- The debug APK is standalone. `app/plugins/withStandaloneDebug.js` sets
  `debuggableVariants = []`, so the JS bundle is embedded, and `useDevSupport = false`, so the app never
  looks for Metro. A stock debug APK tries to load JS from a dev server and shows a red
  "Unable to load script" screen on a phone. On this VM's emulator it would even reach
  client-portal's Metro on :8081. It is still a debug build: debuggable and debug-signed.
- One live phone link. A newer connection replaces the older one with close code 4000. The replaced
  client stops auto-reconnecting and stops posting state, and says so loudly ("Take it back"), so
  Expo Go and the APK on one phone can't ping-pong.

## Locked tabs

Three tabs are always present and always first: **Luna** (ر), **ACSP** (ن) and
**Trial** (Abed). They are defined in `app/src/locked.ts`. They can't be closed by
the close button, a remote `closetab`, or the twin model: every side checks the
`lock-` id prefix, so the rule holds without a schema change. Their pages can
be navigated like any tab. ⌂ returns a locked tab to its home URL. Home URLs are
overridable with `EXPO_PUBLIC_LUNA_URL`, `EXPO_PUBLIC_ACSP_URL` and
`EXPO_PUBLIC_TRIAL_URL`. The Trial home is the ACSP protocol page until the
trial resource exists.

## The map: the surface as URLs

`GET /map` is the first-approach document for an LLM. There is no sign-up: the
seat token says who the viewer is. It lists every tab with its **LLM natures**,
meaning what this viewer can do there, as URLs and `/cmd` bodies. It also lists
the navigation templates and the lifecycle touch points to follow on the bus.
`GET /map/tab/{id}?from=&len=` returns one window of a tab's text, with a `next`
URL. An LLM scrolls by changing values in the URL instead of pulling a whole page.
GET never changes the surface; acting stays `POST /cmd`.

"LLM natures" is a working term for these per-tab options.

## AI engagement and ?ask

A tab knows when it is on an AI surface (`app/src/ai.ts`: Google AI Mode
`udm=50`, Gemini, ChatGPT, Claude, Perplexity, Copilot, duck.ai). It marks the
tab ✦ and signals `llm.engaged`. `?question` in any address bar opens an
unsigned Google AI Mode query in a new tab, with the current tab's address,
title and a window of its text in the URL. A tab on a shared (signed-in)
session contributes only its address and title, never its page text.

## Lifecycle touch points

The app signals `app.lifecycle` (active/background/inactive) alongside
`llm.engaged` and `llm.asked`. `/map` lists the bus stream that carries them.

## The engine

Every move an LLM makes on the Surface is a URL, and the Surface is always compiled.

- **Addresses: `seurl://golden/…`.** `map`, `tab/{id}`, `tab/{id}/scroll?from=&len=`,
  `tab/{id}/open?url=`. The same grammar lives in `app/src/seurl.ts` and `relay/seurl.py`.
  - On the phone, an address resolves from the address bar only.
  - A page that navigates to `seurl://` is refused by the engine, so no website can drive the Surface.
  - On the relay, `GET /seurl?u=` answers reads directly. `open` answers with the `/cmd` body to
    POST: GET never changes the Surface.
- **The shard.** Every structural change the phone reports (tabs opened or closed, URLs
  changed, the active tab) is compiled into one entry, as are `llm.*`, `app.lifecycle` and
  every bridge step.
  - Entries use Luna's record format (`{seq, ts, kind, from, text, id}`) and are hash-chained (`prev`,
    `hash`), append-only with triggers refusing update and delete (migration 004).
  - `GET /shard?cursor=&len=` scrolls it. `GET /shard/verify` recomputes the chain.
  - `relay/shard.log` mirrors it for Luna.
- **Structures and act.** `structures` returns a tab's affordances, indexed: links, fields,
  buttons, selects. Values are never read, and password fields are `fingersOnly`. `act {index,
  kind: tap|fill|submit}` works by index. Both go through `/cmd` under the usual ownership rules.
- **The bridge.** `POST /bridge {tab, goal, steps≤8}` runs Luna's loop on a real tab: observe
  (structures + a text window + domain class), decide (one action), execute (through
  `run_cmd`, the same path as `/cmd`), record (a `bridge.step` shard entry).
  - The decider is an OpenAI-compatible chat endpoint set by `GOLDEN_AI_URL` / `GOLDEN_AI_KEY` / `GOLDEN_AI_MODEL`.
    There is no default. Without one, `/bridge` answers 503.
  - It refuses locked tabs, tabs the seat doesn't own, and tabs on a shared session (their page is never sent to a decider).
- **Lunar natures in the map.** `/map` asks Lunar Foundry (`LUNA_FOUNDRY_URL`, default
  https://lunar-foundry.vercel.app; empty turns it off) for each tab's natures, cached 60 s.
  Tabs on a shared session are withheld: their URLs never leave the relay.
- **Domain-oriented navigation.** Every map tab carries `domain: {tld, class}`
  (`relay/domains.py`, `app/src/domains.ts`, the same table as the Foundry lens). `?ask` adds the
  class to its context. The bridge sees it in every observation.
- **Luna partners.** With `LUNA_SHELL_URL`, the relay joins the Luna shell as partner
  `golden-surface` on start. With `LUNA_LOOM_URL`, pages ر opens are also opened in Loom. Both are
  optional and never block.
- `/state` keeps the spec's tab shape `{id, owner, url, title, signedIn}`. `locked` and `ai`
  appear on `/map` only.
- The Luna locked tab's home is https://lunar-foundry.vercel.app/.
