# GOLDEN MOTION ISI SDK

Framework-independent TypeScript measurement validation and intentional interaction inference. No React, rendering, sensor, network, or platform dependencies. Package exports point to source for Next.js and Metro; `npm run build --workspace @golden-motion/isi` additionally emits JavaScript and declarations into `dist`.

```ts
import { InteractionEngine, syntheticMeasurement } from '@golden-motion/isi';

const engine = new InteractionEngine({
  zones: [{ id: 'target', frame: 'phone-local-m', center: [0, 0, 0.14], radius: 0.22 }],
  dwellMs: 350, debounceMs: 80, dropoutMs: 500,
});
const unsubscribe = engine.subscribe(event => console.log(event), {
  types: ['select', 'scroll', 'cancel', 'zone-exit'],
});
engine.ingest(syntheticMeasurement(200, { timestamp: Date.now(), intent: true }));
// Feed successive observations; one sample does not authorize a gesture.
// Call tick from the host's lifecycle clock to detect silent dropout.
engine.tick(Date.now());
// On acquisition stop, disarm, background, or sensor switch:
engine.release(Date.now());
unsubscribe();
```

## Coordinates, observability and provenance

Timestamps are nonnegative epoch milliseconds. `phone-local-m` uses metres: x right, y away along the screen, z above the screen. Metric frames end in `-m`. Spatial velocities use m/s. `camera-image-normalized` uses normalized x/y in [0,1] and a strictly zero z; it never emits `motion-3d`. Image-plane deltas retain normalized units.

Scalar observations use `measurement-space`, a `relative` value with an explicit unit, and no position or spatial velocity. Camera image-axis scalars instead retain `camera-image-normalized`, kind `image-x`/`image-y`, unit `normalized`, and value in [0,1]. Range values must be nonnegative metres. Scalar uncertainty has one component; spatial uncertainty has three. Each is a standard deviation in its corresponding measurement/position unit. Zone evaluation uses a conservative `uncertaintySigma * norm(uncertainty)` boundary margin (default sigma 2); this is a heuristic uncertainty envelope, not an experimentally calibrated probability.

Sources are `synthetic`, `recorded` or `live`. Modality and device id are required. Confidence must be finite and in [0,1]; it is a quality heuristic. JSON-compatible metadata is copied and validated for finite values, unsafe keys, nesting depth and node count. Consumers cannot mutate engine history or another subscriber's events. `metadata.evidence` may preserve acquisition evidence. Synthetic data and replay do not establish physical feasibility.

## Interaction policy

`Zone` defines either a metric sphere (center, radius, frame) or a measurement interval (`measurement: {kind,min,max}`, frame `measurement-space`, or normalized image-x/image-y intervals in `camera-image-normalized`). Scalar interval units follow the declared measurement kind; distance/range kinds are metres. Mismatched frames and kinds are unobservable. RSSI cannot activate a zone.

Entry requires a confidently interior observation. An active zone remains visible through its hysteresis shell; uncertainty and motion restart stable dwell. Hold requires stable dwell; select also requires explicit `intent: true` maintained for the debounce interval. Drag and rotate require intentional selection. With configured zones, scroll/swipe/drag/rotate/select require an observable interior activation zone; uncertain or exterior observations do not authorize new actions. With no zones, intentional scroll/swipe may use any valid, confident spatial or metric scalar observation. Hold/select/drag/rotate still require a zone. Action cooldowns suppress repeated select, scroll, swipe and rotate; scroll output is clamped by `maxScrollDelta`.

Spatial observations may produce passive approach, retreat and `motion-3d`. Metric scalar changes produce approach/retreat plus `metadata.measurementVelocity` in m/s and intentional scroll; they never gain a position. Normalized image-axis changes may scroll under the same intent/zone rules, without radial approach or 3D motion. RSSI differences produce only coarse `motion-presence` and retain dBm. They never imply distance, direction, hand identity or 3D motion.

Live measurements must match the host epoch clock: default `liveMaxAgeMs = 1000` and `maxFutureMs = 1000` are finite backward/forward tolerances. Both options reject Infinity and can be set to explicit finite tolerances. `maxAgeMs = Infinity` preserves deterministic synthetic/recorded replay; it never disables live freshness. A finite `maxAgeMs` additionally bounds both past and future timestamps for every source. Simulation callers may inject `now` to align an explicit simulation clock. Rejected temporal data never enters ordering history; active state releases use the trusted host time rather than the rejected timestamp.

Device histories are independent. Duplicate and out-of-order observations are ignored. Low confidence, stale input, dropout, provenance/frame/modality/calibration discontinuities, zone updates, intent release and adapter stop release interaction state. Invalid input returns `[]`; if its device id matches existing state, subscriptions receive `cancel`/`zone-exit` built entirely from the last validated payload with `metadata.reason = 'invalid-input'`. This preserves a rejection return contract while releasing consumers. `release(timestamp?, reason?)` publishes explicit host-stop releases and clears history. `reset()` silently clears history for independent replay. Hosts must call `tick()` while observing input to detect a silent sensor dropout; the SDK creates no background timer.

## Reusable integrations

- `subscribe(listener, filter?)` returns an unsubscribe function. Filters accept event types, device, zone, modality, source and minimum confidence. Subscriber exceptions are isolated.
- `registerAdapter({id,start,stop?})` returns an asynchronous unregister function. `startAdapter(id)`, `stopAdapter(id)` and `dispose()` handle asynchronous starts, late callbacks and cleanup. Emissions carry SDK-added `metadata.adapterId`; stop/failure releases attributed device state. Adapters should settle `start` and `stop` promptly and stop physical acquisition in their cleanup.
- `applyCalibration(measurement, transform)` and `CalibrationRegistry` apply explicit proper rigid rotations/translations between metric frames. Reflection, scaling, frame mismatch and image/scalar lifting are rejected. Position and velocity rotate; independent input-axis uncertainty propagates to output marginal standard deviations. Covariance correlations are not represented, so chained transforms with correlated uncertainty need a richer upstream estimator.
- `replayMeasurements(engine, iterable, {maxSamples,maxDurationMs,maxEvents,reset})` performs deterministic synchronous replay with sample, acquisition-time and returned-event bounds. Defaults are 1000 samples, 60 seconds and 10000 events; hard limits are 100000 samples/events and 24 hours. Replay marks source `recorded`, sets `metadata.replay`, and preserves `metadata.originalSource` and evidence. It preserves input order and creates no scheduled callbacks. Each ingested batch may still publish up to the bounded zone count to subscribers; event budget limits returned storage. Inputs must be valid; invalid replay observations throw.
- Device histories, zones, adapters and calibration registry each cap at 256 entries. Oldest device history is released on capacity eviction. Replay has no infinite stream loop beyond its configured sample limit.

`syntheticMeasurement(elapsedMs, options?)` uses a seeded deterministic trajectory/noise model. Without an explicit timestamp it uses fixture epoch `1700000000000 + elapsedMs`; live demonstrations should pass `Date.now()`.

## Verification

```sh
npm run build --workspace @golden-motion/isi
npm test --workspace @golden-motion/isi
npm test
```

Tests cover schema rejection, units/provenance, uncertainty, scalar and RSSI observability, activation boundaries, hysteresis, dwell/debounce/cooldown, intent release, invalid/stale/dropout, per-device ordering, filtered subscriptions, bounded replay, calibration and adapter failures/races. Hardware feasibility remains unverified by this SDK.
