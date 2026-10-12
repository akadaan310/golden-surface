# GOLDEN MOTION relay evidence — 2026-10-12

Implemented in `services/relay/`: actual loopback-only authenticated WebSocket server, portable browser/React Native client, bounded synthetic native-shaped and CSI-derived publishers, protocol/USB pairing documentation, and 24 integration tests. `services/relay/README.md` contains the complete protocol, limits, commands and clock assumptions. No dependency installation, root manifest/lock changes, commits, purchases or external operations were performed by this track.

## Runtime behavior

The server's network interface is hardcoded to `127.0.0.1`; normal startup uses port 8787. It creates a 256-bit ephemeral pairing token and prints that token once when `GM_RELAY_TOKEN` is absent. User-supplied tokens are not printed. First-frame role/token authentication is required; rejected tokens, invalid roles, unauthenticated publication and subscriber publication cannot enter the sensor stream. Authentication compares equal-length UTF-8 token buffers with `timingSafeEqual`. Browser Origins are restricted to local HTTP(S) hosts; native clients may omit Origin. Query parameters, credentials and extra URL paths are rejected.

Every event calls the shared SDK's real runtime `validateEvent`. Derived RF `motion-presence` uses the identical schema and can retain scalar measurement coordinates with no position. Source and acquisition metadata are preserved; authentication does not establish that a publisher's claimed live acquisition is real.

Defaults: 32 connections, 5 s authentication timeout, 32 KiB WebSocket payload, 100 input frames/s/connection, 500 events/s globally, 16 devices/publisher, 128 device ordering records, 128 recent event ID hashes/device, and 64 KiB outgoing subscriber buffer. Compression is disabled. A subscriber closes with 1013 before an over-budget frame enters its queue. Bad frames, payload errors and closing peers do not crash the server. Authenticated peers use 15 s ping/pong liveness checks.

Per-device timestamps are nondecreasing across publisher reconnects. Duplicate recent event IDs and backward timestamps are rejected. Distinct event IDs sharing a timestamp are allowed. Sequence numbers are relay-wide; `receivedAt` is the host's epoch receive time. Device timestamps must be within -30/+5 s of the host. That tolerance is an admission/clock check, not a user-action freshness guarantee or latency estimate; downstream action consumers still need their own freshness policy. Restart clears all ordering/dedup state. Recent ID hashes are bounded replay protection rather than permanent deduplication.

The client reauthenticates after transport reconnect, uses capped 250 ms–5 s exponential retry, stops retrying bad authentication, validates subscriber envelopes and sequences, and clears timers/socket handlers on stop. It retains **no offline event queue**; publishing while disconnected returns false, preventing old queued actions after reconnect. Outgoing events are schema/payload/buffer bounded. Its client subpath has no Node, TextEncoder, Buffer or URL-getter dependency; React Native 0.76's incomplete URL getters are covered by a regression test. No full event history or raw media is persisted. In-flight packets can be lost; there is no publication acknowledgement or history replay.

## Verification performed

Tests were written against unavailable behavior and observed failing before implementation: initial seven authentication/role/JSON/schema/payload tests, four client lifecycle tests, nine advanced sequence/order/dedup/clock/rate/device/backpressure/auth-timeout/origin failures, and two synthetic publisher tests. A later command-cleanup regression reproduced a stray reconnect after command failure (`connections: 1`, expected 0); the fix moved pairing inside guaranteed cleanup. The React Native URL regression reproduced `URL.protocol is not implemented`; strict literal URL validation fixed it. Android compilation first reproduced four optional-timer type errors; timer guards fixed them.

Latest relay-specific verification at 10:30 UTC:

```text
npm test --workspace @golden-motion/relay
3 test files passed; 24 tests passed; exit 0
npm run typecheck --workspace @golden-motion/relay
exit 0
npm run typecheck --workspace @golden-motion/android
exit 0
```

The tests use real local WebSocket sockets and servers for authentication, wrong-role rejection, SDK schema rejection, the 32 KiB cap, ordered broadcasts, derived RF scalar provenance, duplicate/backward timestamp rejection across publisher reconnect, clock-window rejection, a 200-event storm, device-state bounds, subscriber send-buffer bounds, authentication timeout, hostile browser Origin refusal, restart/reauthentication, stop cleanup, synthetic provenance, and command-failure cleanup. The React Native URL dependency regression alone substitutes the incomplete URL getter behavior verified in the installed RN 0.76 source.

Actual CLI demonstration executed on the default port, using a generated ephemeral token passed only in process memory/environment to a subscriber and synthetic publisher:

```json
{"command":"real-cli-loopback-demo","address":"ws://127.0.0.1:8787","generatedTokenPrints":1,"publisherExitCode":0,"receivedEvents":5,"sequences":[1,2,3,4,5],"syntheticOnly":true,"publisherOutput":"Published 5 synthetic native-shaped ISI events. Physical acquisition: false."}
```

The relay and publisher both exited/cleaned up after that demonstration. The token was deliberately omitted from this report.

Full root-suite observations were reported to the integrator rather than concealed: at 10:26 UTC, 61 passed and one SDK lifecycle test failed (`adapter failure release`, expected `zone-exit`, received `hover`); at 10:30:54 UTC, that lifecycle suite passed, while 69 passed and one newly added SDK test failed (`synthetic timestamp contract`, expected default epoch timestamp >1e12, received 200). Every relay test passed in both whole-suite runs. Those SDK files are owned by another active track; no cross-track changes were made here. Vitest emits its environmental CJS Vite API deprecation warning; assertions and TypeScript checks otherwise complete successfully. The integrator owns final whole-project verification.

## Reproduction and remaining evidence

```sh
npm run relay
# In another shell, set GM_RELAY_TOKEN to the displayed session token.
npm run synthetic --workspace @golden-motion/relay
GM_DEMO_MODALITY=wifi-csi npm run synthetic --workspace @golden-motion/relay
npm test --workspace @golden-motion/relay
npm run typecheck --workspace @golden-motion/relay
```

For a real authorized Android USB connection, use `adb reverse tcp:8787 tcp:8787`, pair using the current token, and later remove the mapping with `adb reverse --remove tcp:8787`. The tests and command above are **software protocol evidence only**. This track has not physically validated a Galaxy A16, acquired ESP32 CSI, measured one-way latency, corrected phone clock drift or established sensor accuracy. No public networking or hosted relay was configured. Both demonstration paths retain `source: synthetic` and `metadata.physicalAcquisition: false`.
