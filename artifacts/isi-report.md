# ISI SDK implementation and recovery report

Status: complete for the hardware-independent SDK deliverable. Checked on 2026-10-12 UTC in `/workspace/golden-motion`. No installation, commits, deployment, or external messaging was performed by this track. Changes are confined to `packages/isi/**` and this report.

## Recovery and failure evidence

The original ISI agent was interrupted by selected-model capacity. Its files were preserved. The existing `src/index.ts` contained runtime casts, no-op inference/subscriptions and a simulator throwing `Not implemented`; types and 26 behavior tests were already present. At 10:20:20 UTC, `npx vitest run packages/isi/src/engine.test.ts --reporter=dot` reproduced **23 failing / 3 passing** tests. Failures were genuine missing validation/inference/simulation, not an integration or dependency problem.

Added safety tests first; at 10:21:10 UTC, **29 failing / 3 passing** tests established missing state release, device independence, stable dwell, image-plane observability, filters, mutation isolation and options/zone validation. Implemented schema, zones, engine and deterministic simulation; at 10:23:40 UTC, **32/32 passed** and the SDK TypeScript build passed.

Lifecycle tests reproduced missing bounded replay/calibration and missing adapter-stop zone releases at 10:24:57 UTC (**4 failing / 2 passing**). An additional adapter-failure regression at 10:26:17 UTC proved startup failure could leave subscribers active. Fixed attribution and release before cleanup. During asynchronous-stop serialization, a temporary unconditional `await undefined` delayed start invocation; the 10:26:55 UTC test run preserved the failure `adapter lifecycle > cleans up a start that resolves after stop and ignores late callbacks`, `release is not a function`. The root harness recorded this RED state at approximately 10:27:04. Fixed the cause by awaiting only an existing stop promise; asynchronous late-start cleanup remains tested. No failed experiment was erased or represented as a pass.

Root review identified activation boundaries and invalid subscriber release. At 10:29:17 UTC, three regression tests failed: outside-zone intentional motion emitted scroll/swipe, uncertain hysteresis emitted actions, and invalid data silently left subscribers selected. Fixed all three. Configured zones now require an observable interior activation for actions; the shell preserves hover without new actions. Invalid input returns `[]` under the original rejection contract, while subscribers receive cancel/zone-exit constructed solely from the last valid payload, with reason `invalid-input`.

A final timestamp regression at 10:30:28 UTC established that default simulator timestamps were elapsed values instead of epoch values. The simulator now uses reproducible fixture epoch `1700000000000 + elapsedMs` when timestamp is omitted; live demonstrations pass `Date.now()`. Generator output undergoes runtime validation.

## Delivered behavior

- Runtime measurement/event schemas validate finite values, dimensions, uncertainty standard deviations, confidence, source, intent, bounded JSON provenance, frames and scalar units. Image-plane depth and scalar spatial claims are rejected.
- Spatial sphere zones and scalar measurement intervals expose inside/outside/uncertain/unobservable quality. Engine entry, hysteresis, stable dwell, intent debounce, cooldown and bounded scroll enforce activation.
- Events support hover, approach, retreat, swipe, scroll, hold, select, cancel, drag, rotate, zone-enter, zone-exit, motion-3d and coarse motion-presence. Scalar range yields scalar measurement velocity and never fake 3D; RSSI yields only coarse presence.
- Device histories/order are independent. Low-confidence, stale/dropout, invalid payload, source/frame/modality/calibration changes, intent release, zone updates and adapter stop/failure release state.
- Filtered subscriptions clone payloads and isolate consumer exceptions/mutation. `release()` publishes host-stop releases; `reset()` remains silent for independent replay.
- Asynchronous adapters support registration, idempotent startup, explicit stop, late-callback suppression, deferred cleanup and disposal. Emissions are attributed to their adapter automatically.
- Replay caps samples, elapsed acquisition time and stored events; uses no timer fanout; preserves original provenance while marking recorded playback. History/zone/adapter/calibration limits are 256 entries.
- Explicit proper rigid calibration transforms preserve metric units, provenance and velocity; reflect/scale/image/scalar lifts are rejected. Uncertainty propagation documents independent input axes and marginal output deviations.
- Source exports remain compatible with the architecture contract. Added APIs/types are documented in `packages/isi/README.md`; source exports support Next.js/Metro and compilation emits JS/declarations. A package-local Vitest config makes the workspace test command independent of root include paths.

## Final verification

All commands below completed with exit code 0 after final source changes:

| Command | Evidence |
| --- | --- |
| `npm run build --workspace @golden-motion/isi` | Strict TypeScript JS/declaration compilation passed, 10:31:29 UTC run |
| `npm test --workspace @golden-motion/isi` | **46/46 passed**, two files (39 engine, 7 lifecycle), 10:31:29 UTC |
| `npm test -- --reporter=dot` | **70/70 passed**, five files, 10:31:30 UTC; includes ISI and all current relay/client/synthetic tests |
| `npm run build:sdk` | Both ISI and RF TypeScript builds passed, final verification |

The root suite emits Vite's existing CJS Node API deprecation notice; it is not a test failure. The package-local suite does not emit that notice.

## Integration and limits

The web and native agents were notified when the core API built and later when `engine.release()` became available. Native/browser hosts should call `release()` on explicit stop/disarm/background/sensor switch and periodically call `tick()` during acquisition. Subscribers receive lifecycle releases even when rejected ingestion returns no inferred events.

With no configured zones, intentional global scroll/swipe is permitted for a valid confident observation; hold/select/drag/rotate require zones. With configured zones, all actions require observable interior activation. Replay's event cap bounds its returned storage; each ingestion can still notify subscribers of its bounded zone batch. Adapter promises must settle promptly because the SDK cannot forcibly terminate host hardware acquisition or unresolved adapter promises.

Confidence and uncertainty envelopes are heuristics, not empirically calibrated probabilities. Calibration carries output marginal standard deviations without covariance correlations; correlated/chained uncertainty needs an upstream covariance model. No SDK test establishes acoustic spatial observability, RF hand identity, live hardware feasibility, or Android lifecycle behavior on a device. Those remain separate evidence tracks.

## Independent review follow-up: live epoch safety and camera intervals

The independent foundations review identified a temporal defect after the initial final verification: `maxAgeMs` defaulted to Infinity and only past age was checked. Old live samples and far-future live samples could activate state; a future timestamp could advance ordering and defer dropout. At 10:38:48 UTC, six additional regression tests failed: both old/future live offsets, trusted-time release/order recovery, live limits independent of replay Infinity, finite configurable clock tolerance, and the native camera interval contract.

Fixed with compatible `EngineOptions.liveMaxAgeMs` and `maxFutureMs`. Both default to 1000 ms, must remain finite/nonnegative, and apply to live epoch observations independently of `maxAgeMs`. Setting global `maxAgeMs = Infinity` never disables live freshness. Finite global maxAge additionally bounds both temporal directions for all sources. Synthetic/recorded streams remain wall-clock independent under the default replay policy; injected `now` supports explicit simulation clocks. Timestamp rejection occurs before ordering/history updates; an existing selection releases using only the prior validated observation and trusted host time. Reason is `stale` or `future-timestamp`. Rejected timestamps never poison a subsequent valid sample or dropout history.

Native also reported that camera scalar regions were rejected by spatial-versus-measurement validation. Camera image-x/image-y scalar measurements and interval zones now retain `camera-image-normalized`, require `normalized` units and [0,1] bounds, and remain position/velocity-free. Intentional normalized scrolling is allowed only under the same reliable interior activation policy; these scalars never produce radial approach or 3D reconstruction. The native agent received the verified API update.

Verification after these final source changes:

- `npm run build --workspace @golden-motion/isi`: passed strict TypeScript compilation.
- `npm test --workspace @golden-motion/isi`: **52/52 passed**, 45 engine and 7 lifecycle tests, 10:39:32 UTC.
- `npm test -- --reporter=dot`: **76/76 passed**, all five root test files, 10:40:06 UTC.
- `npm run build:sdk`: ISI and RF builds both passed.

The earlier counts above accurately describe their earlier verification snapshots; this follow-up supersedes them as the final SDK status.
