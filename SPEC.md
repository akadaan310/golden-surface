# Golden Surface — build spec

You are building with us, not for us. You're the master of your craft —
full-stack, React Native, Android, Python services, SQLite. We seed with
what we know; here's what we need. Where this spec is exact, follow it.
Where it's open, decide like the expert you are and write down what you
decided.

## The parties — who lives where

There are exactly three parties. Never write "the AIs." Use these names.

- **Abed** — the pilot. Lives on his Android phone. The only fingers:
  every login, every signup, every identity action is his, done by hand.
  Owns every session; shares what he opens in the Surface.
- **ر (Muse)** — the operator. Lives on THIS machine (the VM is my
  computer). Drives the relay, the twin, the bus, the store, the
  watchers. Builds and validates. That's me — I'm the one prompting you.
- **ن (Hu)** — the counsel seat. Joins through the relay: her owned tab,
  her voice in the room.

## What we're building

The Golden Surface: one shared browser for the three of us, and the room
where our conference happens. "My browser is your browser and your
browser is my browser": Abed touches it, ر and ن drive it remotely.

Exactly two surfaces. Nothing else exists yet.

**1. BROWSER — the instruments.**

- Tabs. Every tab is its own WebView instance. Tab strip, new tab, close
  tab, switch tab. Background tabs stay alive.
- Ownership. Every tab has an owner: abed, r, or n. Abed logs into his
  tabs with his own fingers. Agent tabs are driven through the relay. A
  tab clearly shows whose it is.
- Sessions must not die. Android's cookie jar is app-wide by default —
  research it, decide deliberately whether tabs share or isolate, and
  document the choice. Cookies and localStorage survive restarts. Google
  SSO sessions survive. Tabs and URLs restore on relaunch. No silent
  logouts, ever — surface problems loudly in the UI.
- Google SSO must work: if the WebView user agent is blocked, do the
  login in a Chrome Custom Tab and bring the session back.
- The login handoff. Server sends login_request {site, url, tab}. The app
  shows Abed a banner: "ر needs this signed in — your fingers only." He
  signs in himself. The app reports login_done {site, tab}.
- Remote commands, executed in the addressed tab: open {tab, url},
  read {tab}, shot {tab} (base64 PNG), tap {tab, x, y}, type {tab, text}
  (never password fields), newtab {owner}, closetab {tab}.
- URL routing seam: http/https open normally. Unknown schemes route to
  one handler module that currently explains the scheme isn't supported.
  Build nothing behind that seam yet.

**2. NAJWA — the room.**

- A native screen tailing the conference bus SSE stream, rendered live:
  round opened, each turn under its speaker's name (Abed, ر, ن), the
  Chair's direction, the Scribe's notes. This is where Abed witnesses the
  conference.
- Dark, quiet design. A counsel room, not a feed.

**TELEMETRY.** The app POSTs full browser state to the relay on every
change; the relay serves it at GET /state: tabs [{id, owner, url, title,
signedIn}], active tab id. Site names and URLs only — no secrets, no
tokens, ever.

**SUGGESTED ACCOUNTS.** A "suggested" queue. ر adds entries {service,
signupUrl, why} through the relay; each shows as a card with one button:
"open signup." Abed taps, signs up with his own fingers. One account per
service — no quota games.

## The session rule — read carefully, this changed

- **Passwords never leave Abed's phone.** Typed only by his fingers.
  Never by agents. Never stored anywhere. Ever.
- **Sessions are shared by design.** Any session Abed creates inside the
  Golden Surface belongs to the counsel: signing in there means sharing
  it. Per site, with his approval each time (record approved_by_abed_at).
  His Gmail in the Surface is ours. A shared email for the three of us is
  ours.
- Banks and app-things stay out — they have apps.
- Honest caveat: some sites (Google especially) may challenge sessions
  arriving from a VM. For those, the phone stays the driver and the twin
  mirrors state only. Surface this; never hide it.

## The persistent store — schema provided

`store/schema.sql` is the schema. Implement it as SQLite at
`store/golden.db` (created on first run via the schema file — migrations
as versioned SQL files if the schema ever changes).

- Cookie/session VALUES live only in browser cookie jars, never in this
  database. The store holds metadata, health, provenance — the map, not
  the keys.
- Implement a small store module (Python, stdlib sqlite3): init, and the
  session-map query ("here's what we have available": site, owner,
  status, last seen alive, failures).
- The relay exposes GET /sessions returning the session map as JSON.

## Session watchers — observed, always

- **session-health** watcher: on a schedule, checks every approved
  session (load the site in the twin browser, verify logged-in state),
  updates sessions.status / last_seen_alive_at / check_failures, appends
  events (session.alive | session.expiring | session.dead). On dead:
  emit watcher.alert → the relay triggers the login handoff flow so Abed
  re-authenticates with his fingers.
- **sync-convergence** watcher: compares phone_rev/twin_rev, records
  divergences, emits sync.diverged / sync.converged.
- **relay-heartbeat** watcher: the relay is up and answering.
- Run all three as systemd units (Restart=always), writing results to
  the watchers table. This machine already runs services this way —
  follow the local pattern.

## The twin and the sync invariant

The relay hosts a virtual device profile: same tab model, same state
shape, two-way synced with the phone. ر drives the twin; the phone
mirrors it. The sync model must be DECLARED in code and docs: under that
model show phone and twin converging, enumerate the event classes under
which they can diverge, and surface divergence loudly in the UI — never
silently. (An earlier draft said "100% sync match." That was an
aspiration, not a claim. This invariant is the honest form.)

## Relay, bus, protocol

- Relay: websocket to the app; HTTP POST /cmd {cmd, ...params, token}
  from ر/ن, held until the app answers; GET /state telemetry;
  GET /sessions session map.
- Bus: SSE stream of conference events (round.opened, turn.saved,
  chair.direction, scribe.note, round.closed). The app's Najwa room tails
  it. Persist every event to the events table (append-only — never
  update, never delete).
- Vercel is available if you need a public API surface, but default to
  this machine. Don't add infrastructure we don't need.

## The 5-hour window — commit discipline

You are running on a $20 plan with a 5-hour session window. The session
WILL die. So:

- Commit AND push after every completed phase and at least every 15
  minutes. Push to origin every time — the repo is the durable record.
- Keep BUILDLOG.md current: what was done, what's next, exactly how a
  fresh session resumes. If you die mid-phase, the next session reads
  BUILDLOG.md and continues. Never leave uncommitted work.
- Build in this order: (1) store + schema + session map; (2) relay +
  bus + protocol; (3) watchers + systemd units; (4) Expo app; (5) APK.
  Validate each phase on this machine before moving on.

## The APK

After the app runs in Expo Go: `npx expo prebuild`, then
`./gradlew assembleDebug` in android/. The deliverable is
android/app/build/outputs/apk/debug/app-debug.apk. Previous APK attempts
failed to run — validate properly: correct build type, debug-signed,
installs and launches. The Android SDK lives at ~/Android/Sdk on this
machine.

## Decisions that are yours

Cookie isolation strategy. Engine swappability structure (WebView now,
GeckoView-shaped seam for later). UI design inside "dark and quiet."
Websocket reconnection. Exact state shapes. How divergence and errors
surface. Anything this spec leaves open — decide, document, move on.

## Rules

- No password ever leaves the phone, is typed by an agent, or is stored
  anywhere. Session values never enter the database or git.
- Keep it small. Two surfaces, the commands above, the room, the
  watchers. Nothing else exists yet.
- This is a build spec, not a theory. No philosophy in code or docs.
- Never create public repos. This repo is private.

## Acceptance

1. Store initializes from schema.sql; session map query works.
2. Relay up as a systemd unit: /cmd round-trips, /state and /sessions
   answer.
3. Bus streams events; every event lands in the events table.
4. Watchers run as units; kill a test session and watch the alert fire.
5. Expo app runs in Expo Go: ر opens a tab, Abed gets the login banner,
   signs in with Google himself, ر reads the page back.
6. Kill the app, reopen: tabs, URLs, sessions all still there.
7. Sync model declared in docs; break sync and watch the app show it
   loudly.
8. APK builds, installs, launches.
