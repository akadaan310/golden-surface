# GOLDEN MOTION validation report

Executed 2026-10-12 in `/workspace/golden-motion`. Directives: GM-ROOT-001 and
GM-RF-001. **Software and synthetic validation completed; physical Galaxy A16
and ESP32 validation remain pending.**

## Verified deliverables

`python3 scripts/verify.py --budget 1800` exited **0**: 21 executable graph tasks
passed, zero failed, zero pending, one actual-device capability task blocked.
The final run reused successful unchanged scientific checks with recorded source
fingerprints and reran changed builds/browser checks. Full evidence is in
`PROJECT_STATE.json`, `artifacts/harness/audit.jsonl` and the bounded per-task logs.

| Component | Executed validation | Status and evidence |
| --- | --- | --- |
| Python acoustic/optical/BLE laboratory | 20 scientific tests, deterministic experiments, repeatability | Simulation-validated; `science/results/results.json` |
| RF laboratory | 16 unit/acquisition/parity tests + 4 fresh statistical tests; experiments/classifiers/fusion | Simulation-validated; `science/rf/results/` |
| ISI SDK | 52 schema/inference/lifecycle/calibration/replay tests and compilation | Unit-tested; `artifacts/isi-report.md` |
| Authenticated relay | 24 protocol/client/CLI tests, actual synthetic publisher/subscriber | Integration-tested; `artifacts/relay-report.md` |
| Shared RF TypeScript model | 8 tests and JS/type declaration build | Simulation-validated; `packages/rf/` |
| Native Android | 19 JS tests including actual transpiled App lifecycle/replay, 3 Kotlin tests, TypeScript, APK assembly/signature | Build/unit-tested; hardware and installed-app runtime unverified |
| Web | 17 model/camera/consumer tests, production build, 14 browser scenarios, 7 browser/relay scenarios | Demonstration-ready in headless Chromium; physical camera performance pending |
| Autonomous harness | 14 scheduling/budget/checkpoint/configuration tests | Unit-tested; `artifacts/harness-final-tests.txt` |

These are **177 unit/integration/scientific tests**, plus 21 browser scenarios and
the recorded performance sample. The numbers do not represent physical trials.
No hosted CI, public deployment or physical-device installation is claimed.

The Android artifact is `artifacts/golden-motion-debug.apk`, 65,978,909 bytes,
SHA256 `32eb3c09914a3f3c2fdc6d528c8ac2df4963be26c63e90d57f19f835da8b00c4`.
Package: `com.goldenmotion`, min API24, target API35. Native MediaPipe, Kotlin
hardware modules and the Hermes JS bundle are included. Debug signing is not
a production release-signing workflow.

The Next.js 15.5.27 production build uses the Pages Router to retain React18/Fiber8
compatibility, discovered through actual WebGL browser testing. First-load JS is
112 kB; the 3D and camera code loads separately. Desktop and 390-pixel mobile
screenshots are in `artifacts/web-{desktop,rf,mobile}.png`.

## Scientific results and rejected hypotheses

All values below are **synthetic evidence under stated models**, not phone accuracy.

| Experiment | Observed result | Practical limitation |
| --- | --- | --- |
| GM-001 | Matched-filter scalar range RMSE 0.443 mm; anchored phase 0.394 mm; Doppler-integrated 1.070 mm; Kalman 0.535 mm | One acoustic path does not recover 3D; Kalman did not improve the matched-filter result |
| GM-001 negative controls | Noise-only false detections 0/100; strong no-hand direct leakage 100/100 with naive detector; measured synthetic background subtraction 0/100 | Physical background stability and calibration untested |
| GM-004 | Calibrated optical-ray + acoustic range position RMSE 2.103 mm; anchored optical prior 43.539 mm; biased optical fusion 66.972 mm | Known colocated geometry and calibration are assumptions; biased fusion can harm |
| GM-RF-001 | Nominal detection 40/40; scalar absolute path-rate MAE 3.89 mm/s; common-CFO no-hand control 0/40 false detections | Weak and iso-delay motion 0/40 detection; one link cannot localize a hand |
| GM-RF-001 confounds | Independent antenna drift without a hand 40/40 false detections despite high heuristic confidence | Quality score is not calibrated gesture probability |
| GM-RF-002 | Coarse simulated RSSI hand motion 0/40 detections; shadow-confounded no-hand 40/40 false detections | RSSI is not CSI, Doppler, target range or precise hand position |
| GM-RF-006 | On 128 windows from 16 held-out synthetic sessions: classical 57.81% accuracy/68.75% false activation; CSI logistic 82.03%/9.38%; CSI+RSSI 78.91%/10.94% | Zero physical participants; generated motion labels are not a validated human gesture vocabulary |
| GM-RF-007 | Nominal calibrated fusion MAE 2.46 mm; 1 ms acoustic clock bias 172 mm; excess-path multipath 101 mm | RF corroboration did not repair biases; unrelated moving objects also passed the synthetic gate |

RF classifier reports include session-cluster bootstrap intervals and calibration
bins. Detection-rate Wilson intervals and numerical uncertainty are retained in
JSON. Cross-modal agreement does not establish hand identity or intentional input.
RF hover/scroll demonstrations are synthetic measurement-threshold policies;
physical RF spatial hovering, signed gesture direction and precise hand localization
are not validated.

Actual Python/Julia1.11.5/Octave9.4.0 acoustic kernels agree within 1.08e-13 for
selected scalar outputs. RF Python/Julia/Octave/TypeScript complex forward values
agree within 4.5e-14 in the deterministic parity fixture. `parity_runner.py` executes
current sources and checks source/output hashes; missing languages or stale output
cannot pass. Mathematical parity establishes implementation agreement, not physical
model correctness. Pinned numerical environments and negative controls are documented
in `science/README.md` and `artifacts/rf-report.md`.

## Demonstrations and performance

Browser tests exercised WebGL phone/hand/zone rendering, estimated scalar scrolling,
intent gating, hover state, dropout/release, replay provenance, modality changes,
RF perturbations/ambiguity/RSSI limitations, local camera start/stop, authenticated
remote effects, stale/low-confidence rejection, reconnection and mobile layout.
Camera startup used **Chromium synthetic test-camera frames**, not a consenting
physical hand accuracy trial. Native-to-web proof used synthetic native-shaped events.

The final same-host publisher-to-browser semantic benchmark measured 10 events:
mean **9.7 ms**, descriptive p95 **32 ms**. This excludes physical acquisition and
RF's four-second analysis window. It assumes synchronized same-host clocks and
is not phone/network latency.

The software-rendered 3D scene produced **8.0 actual frames/s** in a two-second active
sample, below the 30–60 FPS engineering target. The implemented fallback uses
demand rendering, lower resolution/lighting cost and bounded animation scheduling.
Standby produced **zero 3D frames** over 1.988 s while browser RAF cadence was 60 Hz;
RAF cadence is not GPU throughput. An earlier concurrent-emulator run had 207.9 ms
mean event latency/p95 927 ms and 7.09 Hz RAF. The rendering mode and host load both
changed, so no isolated causal performance improvement is claimed. Galaxy A16 FPS,
power, thermal behavior, physical latency and accuracy remain unmeasured. See
`artifacts/browser-performance*.json`.

## Emulator and hardware blockers

Both emulator boot attempts were bounded and unsuccessful:

- API35 Google image: package scanning took 705.768 s; framework services eventually
  registered, but boot completion did not arrive by the fixed deadline.
- API30 AOSP image: probe stopped after 559.16 s within its fixed deadline; package/
  activity readiness and boot completion remained unavailable.

No APK installation or native UI runtime checks ran successfully on either emulator.
Both owned QEMU processes were shut down. No usable API30 screenshot was produced.
The environment lacks KVM; software emulation consumed substantial CPU. Reports and
a reusable emulator-only probe are in `artifacts/emulator-api{30,35}-validation.*`
and `scripts/emulator_smoke.py`. Do not interpret build or isolated JS tests as
installed-device validation.

The Galaxy A16 variant/model, Android version, chipset, microphone geometry, usable
acoustic bandwidth, sensor inventory and RTT/hotspot behavior remain unknown until
connected. `scripts/physical_probe.py` excludes emulators and can inventory/install
the commissioned app on an actual A165/A166 model. It does not declare gesture
sensing validated. ESP32 acquisition, participant/session evaluation on properly
licensed physical datasets and cooperating-radio synchronization remain pending.

## Independent review

Seven foundation findings and five application findings were reproduced and fixed:
temporal guards, descendant termination, fresh parity fingerprints/execution,
fresh statistical ordering, interpreter selection, capture deadlines, quick graph
closure, permission cancellation, replay payload/intent cleanup, stale camera
frames and audio units. Scoped independent re-reviews marked all twelve addressed
with no new material issue. Original findings, regressions and resolution evidence
remain in `artifacts/{foundation,application}-review.md` and each track report.

Continue with `NEXT_ACTIONS.md`. Execution stops at this handoff; no unattended
research, hardware capture or deployment continues after the session.
