# GOLDEN MOTION

GOLDEN MOTION is a local, executable research laboratory for **Universal Invisible
Surfaces**, commissioned by GM-ROOT-001 and expanded by GM-RF-001. It includes a
shared ISI engine, native React Native/Kotlin Android instrument, responsive
Next.js/Three.js laboratory, authenticated device relay, and reproducible
Python/Julia/Octave acoustic and RF experiments.

**Simulation and build evidence are separate from physical sensing evidence.**
Galaxy A16 and ESP32 physical validation remain pending. CSI is a primary
research pillar; ordinary Android Wi-Fi RSSI is never treated as CSI or precise
hand position. See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for final measured
outcomes and [BLOCKERS.md](BLOCKERS.md) for physical prerequisites.

## Bootstrap and verify

Requirements: Linux x86_64 for bundled numerical/tool installers, Python 3.12,
Node 24, npm 11, Java 21, HTTPS access for pinned dependency/tool downloads, and
about 12 GiB free disk for the scientific/native build toolchain. Other platforms
can use compatible Julia/Octave/Android installations documented in each track.

```sh
python3 scripts/bootstrap.py
npm run verify
```

Bootstrap installs locked npm packages, a pinned `.venv`, local Julia/Octave,
Android SDK/Gradle and Chromium. It uses inherited network proxy settings without
reading credentials. Verification automatically uses `.venv/bin/python` when
installed, runs the dependency graph, emits bounded logs, retains failures and
skips successful unchanged tasks. `npm run verify -- --force` repeats all checks;
`npm run verify -- --quick` excludes native, browser and language-parity checks.
The CI workflow is provided locally; no remote CI run or publication is claimed.
For individual Python commands in track guides, use `.venv/bin/python` or
activate the environment with `source .venv/bin/activate`.

## Run the demonstrations

```sh
npm run dev:web
# Open http://127.0.0.1:3000
```

Start acquisition, arm the intentional interaction gate, and change **Hand
height** to scroll from an estimated scalar acoustic range. Select **Hover** for
zone feedback. **Translate**, **Rotate** and **Avatar** explicitly use a synthetic
3D proxy. Move the proxy with mouse/touch or the trajectory control. Noise,
multipath, drift, dropout, hand-presence and measurement-zone controls expose
failures. Stop acquisition releases active interactions.

The **RF laboratory** exposes configurable TX/RX/reflector geometry, CSI amplitude,
phase and Doppler diagnostics, RSSI, carrier/bandwidth/antenna and nuisance
controls. CSI scalar motion may gate a user-chosen scrolling direction; unsigned
RF Doppler does not infer hand direction. RSSI provides coarse diagnostics with
no directional scrolling. **Evidence & protocol** displays executed synthetic
results and authenticated relay pairing.

**Optical** offers opt-in, locally processed MediaPipe image-plane hand landmarks.
No camera media is uploaded or retained. Live camera availability and physical
accuracy require a real camera/consenting user. Fake-camera browser tests verify
software startup and cleanup only.

Install the produced [debug APK](artifacts/golden-motion-debug.apk), or build it:

```sh
npm run build --workspace @golden-motion/android
.tools/android/platform-tools/adb install -r artifacts/golden-motion-debug.apk
```

The APK embeds its JavaScript bundle and hand model. Native capability inventory,
audio/Wi-Fi/BLE/hotspot probes, synthetic semantics, calibration, replay and
permissions are documented in [apps/android/README.md](apps/android/README.md).
Requested sample rates, declared ultrasound properties and successful compilation
do not establish usable hand sensing or measured audio bandwidth.

## Native-to-web synchronization

```sh
npm run relay
.tools/android/platform-tools/adb reverse tcp:8787 tcp:8787
.tools/android/platform-tools/adb reverse tcp:3000 tcp:3000
```

The relay prints a fresh pairing token once. Enter it in the native publisher and
browser subscriber; keep it in memory. The server binds only `127.0.0.1`, rejects
unauthenticated/malformed/stale/out-of-order streams and bounds connections,
messages and queues. The browser's opt-in preview additionally requires intent,
appropriate measurement frames and clocks aligned within one second. Without a
phone, use the explicitly synthetic publisher described in
[services/relay/README.md](services/relay/README.md). There is no public sensor
endpoint or retained relay history.

## Research and continuation

- [Scientific models and experiments](science/README.md): matched filtering,
  phase/Doppler, observability, Kalman comparison, fusion failures and BLE model.
- [Wi-Fi/RF pillar](science/rf/README.md): A–H acquisition pathways, prior art,
  CSI/RSSI separation, classifiers, uncertainty, ESP-CSI acquisition and parity.
- [ISI contract](packages/isi/README.md): events, units, zones, temporal safety,
  filters, replay, adapter lifecycle and calibration.
- [Architecture](docs/ARCHITECTURE.md) and
  [coordinate/physics contract](docs/SCIENCE_AND_COORDINATES.md).
- `PROJECT_STATE.json`, `EXPERIMENT_REGISTRY.json`, `CAPABILITY_MATRIX.json`,
  `RESEARCH_LEDGER.md`, `DECISION_LOG.md`, `BLOCKERS.md`, `VALIDATION_REPORT.md`
  and `NEXT_ACTIONS.md` are the durable checkpoint.

```sh
npm run harness:status
npm run harness -- --budget 600 --max-tasks 20
npm run package:demo
```

The harness executes a finite, dependency-aware graph with hashes, resource/time
limits, checkpoints, bounded retries and ranked corrective actions. It does not
run after the session stops, generate scientific success from failures, or change
source without an engineering agent. On resumption, inspect state and ledgers,
then run the highest-value unblocked task; do not restart completed experiments.
