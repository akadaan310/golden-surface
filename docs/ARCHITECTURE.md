# GOLDEN MOTION GM-ROOT-001 implementation brief

This is an architectural research and application project, authorized for autonomous implementation by the master directive. Its ordinary design and execution choices do not need further approval. Work happens in a fresh local repository on `gm-foundation`. No hosting, credentials, purchases, or external infrastructure operations are included.

## Deliverable and evidence

Build an executable Python scientific laboratory, independent Julia/Octave kernels, a framework-independent TypeScript ISI engine, an installable React Native Android app with Kotlin diagnostics/audio, a responsive Next.js/Three.js laboratory, and an authenticated loopback event relay. Complete the hardware-independent lifecycle and preserve pending experiments. Synthetic evidence never becomes physical evidence. Camera-image coordinates are not spatial reconstruction; scalar acoustic range does not determine 3D position.

## Boundaries

- `science/`: deterministic acoustic forward model, estimators, observability, comparative experiments, fixtures, numerical parity, and results. Python is orchestration authority. Julia and Octave independently implement selected kernels.
- `packages/isi/`: event schema, validation, measurement-space and spatial zones, intentional gesture inference, subscriptions, adapters, bounded replay, coordinate metadata. No rendering dependencies.
- `apps/android/`: React Native experience and Kotlin capability/audio/camera-ready modules. Runtime permissions; audio is stopped explicitly and automatically on lifecycle transitions. Acoustic experiments bounded at low playback amplitude. Build does not establish hardware feasibility.
- `apps/web/`: Three.js phone, hand proxy, field/zone visualization, calibrated semantic demonstrations, actual deterministic signal generation/estimation, replay, optical reference when camera available, uncertainty and provenance.
- `services/relay/`: loopback-only authenticated WebSocket relay, bounded payloads/rates, per-device ordering, reconnect and synthetic protocol tests. Native and browser clients consume identical schema.
- `harness/`: bounded dependency graph runner, atomic persistent state, append-only execution evidence, fingerprints to skip successful unchanged tasks, timeout/retry and disk/resource budgets, corrective-action classification.

## Integration contract version 1

Epoch timestamps use milliseconds. Coordinates in `phone-local-m` use metres: x right, y away along screen, z above screen. Velocity uses m/s. `camera-image-normalized` uses normalized image coordinates and no measured depth. A scalar measurement uses `measurement-space` and no position. `source` is `synthetic`, `recorded`, or `live`. `modality` names the sensor, and `metadata.evidence` may add acquisition provenance; replay preserves original source there.

`ISIEvent`: user-specified fields plus optional `interactionState` and `relative: {kind:string,value:number,unit:string}`. `uncertainty` is nonnegative standard deviations in the corresponding position or measurement units, explicitly documented. Confidence is [0,1], a quality heuristic unless an experiment demonstrates calibration.

SDK exports from `@golden-motion/isi`:

```ts
type Vec3 = [number, number, number];
type MeasurementSource = 'synthetic'|'recorded'|'live';
interface Measurement {
  timestamp:number; source:MeasurementSource; modality:string; deviceId:string;
  coordinateFrame:string; confidence:number; position?:Vec3; velocity?:Vec3;
  relative?:{kind:string;value:number;unit:string}; uncertainty?:number[];
  calibrationId?:string; intent?:boolean; metadata?:Record<string,unknown>;
}
interface Zone { id:string; frame:string; center?:Vec3; radius?:number;
  measurement?:{kind:string;min:number;max:number}; }
class InteractionEngine {
  constructor(options?:{zones?:Zone[];minConfidence?:number;dwellMs?:number;
    cooldownMs?:number;hysteresis?:number;dropoutMs?:number});
  ingest(measurement:Measurement):ISIEvent[];
  subscribe(listener:(event:ISIEvent)=>void):()=>void;
  updateZones(zones:Zone[]):void;
  reset():void;
}
function validateEvent(input:unknown):ISIEvent;
function validateMeasurement(input:unknown):Measurement;
function syntheticMeasurement(elapsedMs:number, options?:{noise?:number;
  seed?:number;deviceId?:string;timestamp?:number;intent?:boolean}):Measurement;
```

Agents may extend this contract compatibly and document additions. Never change existing names without notifying integration. SDK `main`/exports point to TypeScript source for Metro/Next.js, compilation also emits distributable JS/type declarations. Root npm installation is controlled by the integrator; agents may edit only their own package manifests and request dependency additions before installation.

## Tests and limits

Test first for safety, inference, observability, repeatability and transport. Include no-hand/dropout/unobservable controls, drift/noise/multipath perturbations, schema rejection, hysteresis and intent, replay storms, connection auth/order, production web build and Android assembly. Browser QA uses available Playwright when feasible. No ADB connection implies pending hardware test. Run at most two automatic retries for transient tasks and preserve failed scientific hypotheses.

Initial budgets: individual tests 120 s, numerical suites 300 s, builds 900 s; Android initial dependency build up to 1800 s; 2 GiB child RSS monitoring where applicable and 2 GiB disk reserve. Overall harness run is bounded and reports work remaining.
