# GOLDEN MOTION Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent bounded subsystems; user directive explicitly authorizes parallel work and autonomous choices. Write meaningful failing behavior tests before implementation. Root owns integration and persistent state.

**Goal:** Deliver reproducible experiments and an executable native/web demonstration with shared semantics and honest provenance.

**Architecture:** Five independent implementations meet at the version 1 SDK contract in `docs/ARCHITECTURE.md`. A persistent bounded harness runs validations and records evidence.

**Tech Stack:** Python 3.12, Julia, Octave, TypeScript, React Native 0.76.9, Kotlin, Next.js 15, React 18, Three.js, WebSocket.

**Spec:** `docs/ARCHITECTURE.md` plus GM-ROOT-001 user directive.

## Global constraints

- Preserve real, recorded and synthetic evidence separately.
- Do not invent acoustic 3D positions or camera depth.
- Physical Galaxy A16 validation requires an actual connection.
- All runtime sensing is opt-in, stoppable and bounded; no retained raw media by default.
- Only root installs shared npm dependencies and writes root package manifest/lock.
- Each implementer owns its assigned subtree and writes a concise evidence report in `artifacts/<track>-report.md`.

## Review focus

- Invalid/nonfinite/stale input must not trigger actions.
- Dropout or modality change must release interaction state.
- No-confidence/no-intent controls must avoid accidental scrolling or select.
- Public or unauthenticated transport must not accept sensor streams.
- Build/simulation success must not turn into hardware or calibrated accuracy claims.

### Task 1: Scientific models and experiments

Files: `science/**`, `artifacts/science-report.md`.
Produces: reproducible commands, independent Julia/Octave kernels, machine-readable results and browser fixture. Consumes no SDK.

- [ ] Write and run failing repeatability, delay recovery, Doppler sign, unobservable geometry and noise/control tests.
- [ ] Implement explicit propagation model and estimators, perturbation studies and comparative experiments GM-001/004/005.
- [ ] Install local numerical tools when practical, execute Python/Julia/Octave parity; record versions and failure evidence.
- [ ] Emit results, fixture and measured numerical costs; never report physical validation.

### Task 2: Shared SDK

Files: `packages/isi/**`, `artifacts/isi-report.md`.
Produces: contract exports in architecture brief, adapter/replay APIs and distributable build. Consumed by web/native/relay.

- [ ] Write and run failing schema, inference, intent, hysteresis, dropout, ordering and bounded replay tests.
- [ ] Implement events/zones/inference/registrations/replay; document measurement units and semantics.
- [ ] Run tests and SDK compilation, summarize behavior and limitations.

### Task 3: Native Android

Files: `apps/android/**`, `artifacts/android-report.md`, optional APK.
Consumes shared SDK; produces React Native application plus Kotlin diagnostics/acquisition and native-to-web publisher.

- [ ] Define behavior/build validation and opt-in permission tests where executable.
- [ ] Implement actual synthetic/replay/semantic experience and hardware diagnostics/audio acquisition, camera reference if dependencies permit.
- [ ] Install local SDK/build tools through ordinary downloads; compile debug APK; inspect ADB and run available device tests.
- [ ] Document acquired versus requested rates, unverified hardware limitations and installation commands.

### Task 4: Spatial web laboratory

Files: `apps/web/**`, `artifacts/web-report.md`.
Consumes SDK; produces responsive interactive scene and signal-estimation laboratory.

- [ ] Create browser behavior assertions for start/stop/hover/scroll/perturbation/modality/replay/mobile layout.
- [ ] Build polished Three.js scene and controls, true deterministic signal/estimator displays, optical camera adapter, replay and authenticated relay client.
- [ ] Compile production application and run available browser QA, recording limitations.

### Task 5: Event transport

Files: `services/relay/**`, `artifacts/relay-report.md`.
Consumes shared events; produces loopback relay plus reusable clients/protocol docs.

- [ ] Write failing authentication, ordering, payload and rate bound tests.
- [ ] Implement authenticated relay and clients, reconnection and timestamp handling.
- [ ] Execute integration tests using deterministic synthetic native-shaped streams.

### Task 6: Autonomous harness and release integration

Files: `harness/**`, `scripts/**`, root manifests/state/reports, `tests/**`.
Consumes all track test/build commands; produces resumable execution graph and demo handoff.

- [ ] Write failing scheduler dependency, retry, timeout, fingerprint and checkpoint tests.
- [ ] Implement bounded runner, environment discovery and task registry, failure diagnosis and next-action selection.
- [ ] Integrate shared npm installation, bootstrap/verification/CI, sensing taxonomy and evidence inventory.
- [ ] Review all tracks independently, fix significant findings, execute full verification and package source plus APK if produced.
- [ ] Preserve final state, validation report and remaining physical experiments.
