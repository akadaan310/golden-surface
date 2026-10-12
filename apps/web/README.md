# GOLDEN MOTION browser laboratory

From the repository root, after the shared npm installation:

```sh
npm run dev --workspace @golden-motion/web
npm run test --workspace @golden-motion/web
npm run build --workspace @golden-motion/web
npm run start --workspace @golden-motion/web
node apps/web/tests/browser.mjs
node apps/web/tests/relay-browser.mjs
```

The preview binds to `127.0.0.1:3000`. Use `GM_WEB_URL` for browser checks against another local port. Browser checks require installed Playwright Chromium. Relay browser checks launch and stop a dedicated authenticated loopback relay on port 18987 with an ephemeral token held only in memory.

Next.js 15 uses the Pages Router so the requested React 18.3.1 and React Three Fiber 8.18 renderer share the same React runtime. The App Router internally uses React 19 and is incompatible with Fiber 8.

## Operation

1. Start acquisition. The acoustic model generates a 48 kHz chirp and delayed echo, measures a matched-filter peak and independently detects its presence against observed trailing-window noise. Its scalar output never contains xyz.
2. Arm intentional interaction. Hover and scroll consume shared ISI inference events. Change hand height or move the synthetic proxy to change an observable scalar range. Edit the measured range band in the zone editor.
3. Translation, rotation and avatar modes explicitly switch to the synthetic metric proxy adapter. Hold still to select; moving the selected proxy emits SDK drag/rotate events. They do not infer spatial motion from scalar acoustics.
4. Capture a reference to remove the measured scalar bias against a known synthetic reference. This is not a physical calibration. Replay uses bounded in-memory measurements and matching previously generated traces, preserving original source in event metadata.
5. Optical reference is opt-in. Local MediaPipe assets infer image-plane landmarks; zero z is a schema placeholder, never measured depth. Acquisition is bounded to five minutes and stops on visibility loss, page exit, modality changes, explicit stop and unmount. Raw camera frames are neither exported nor stored.
6. The dedicated RF laboratory consumes `@golden-motion/rf`. Configure transmitter, receiver, moving reflector, static paths, radio settings and nuisance terms. Raw CSI amplitude/phase, corrected Doppler spectrum and coarse RSSI are measured from the deterministic channel samples. Unsigned path-length rate does not localize a target. Optional continuous RF scrolling is an explicit user-selected trigger policy with a chosen direction, driven by shared inference hover; RSSI provides no directional gestures.
7. Connect the loopback event relay in Evidence & protocol. Tokens stay in memory. Monitoring retains event provenance. Fresh preview driving is separately opt-in, and requires armed acquisition, confidence, supported coordinate semantics and epoch clock alignment within one second. Old observations remain visible but cannot act.

The Evidence workspace loads executed Python experiment fixtures, including false activations. Software build and browser simulation establish no physical sensing accuracy or Galaxy A16 feasibility.

## Rendering and frame freshness

Live optical observations retain the epoch when a new decoded browser frame is first observed before inference. Processing completion is separate metadata; the browser cannot establish the hardware exposure timestamp. Only new acquired frame identities enter the SDK. The host clock calls dropout detection, so a frozen frame releases interaction after 350 ms and cannot be retimestamped or re-entered. No-hand frames withhold position and confidence immediately.

The scene renders on demand in standby. Active animation has a bounded scheduling clock, with field updates limited to 30 Hz. Automatic low power rendering applies to detected software renderers, small screens and reduced-motion preferences, using DPR 1, simpler lighting and no antialiasing or shadows. The Rendering quality control can override this tradeoff. Canvas data attributes expose actual renderer-frame counts and the selected policy for reproducible profiling; browser requestAnimationFrame cadence is not GPU render FPS. No Galaxy A16 performance is claimed.
