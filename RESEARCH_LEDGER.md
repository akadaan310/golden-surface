# GOLDEN MOTION research ledger

## 2026-10-12 — Session initialization

Workspace was empty. Created a fresh repository on branch `gm-foundation`. Observed Python 3.12.14, Node 24.19.0, Java 21.0.12.1; NumPy/SciPy available; Julia, Octave, Android SDK, ADB and Gradle absent on PATH. HTTP network policy unrestricted and enforced; no configured credentials, no VPN. No physical sensor data or hardware connection discovered.

Design choice: local monorepo with explicit source provenance and measurement-space semantics. User's autonomous execution directive supersedes skill approval pauses and sequential implementation suggestions. Subsystems have disjoint ownership to permit parallel implementation. Builds and synthetic results are separate from hardware validation.

Plan: `docs/superpowers/plans/2026-10-12-golden-motion.md`. Contract: `docs/ARCHITECTURE.md`. Implementation begins from an empty baseline; no prior experiment is rerun.

## Priority amendment GM-RF-001

Preserved the five original tracks and added a sixth dedicated RF track in `science/rf` and `packages/rf`. RF becomes a primary UI and scientific pillar. CSI, RSSI, hotspot capability, participating-device RTT and ESP32 acquisition are separate pathways. Coarse RSSI does not become hand coordinates. Numerical work includes moving-reflector channel simulation, RSSI negative controls, observability/ambiguity and fusion failures. Android receives documented Wi-Fi/hotspot probes; web receives configurable geometry and CSI/RSSI displays. No authorized physical radio hardware is connected.

Harness implementation evidence: `python3 -m unittest discover -s tests -p 'test_*.py' -v` passed 10 tests covering dependency order, checkpoint/unchanged-task reuse, bounded retries, timeout termination, missing artifacts/dependencies, hardware blocking, output bounds and input fingerprints. Environment inventory saved in `artifacts/environment.json`.

## Final integration checkpoint — 2026-10-12

All six implementation tracks integrated. Python20 scientific tests, RF20 tests, SDK52, relay24, RF TypeScript8, native JS19/Kotlin3, web17 and harness14 pass (177 tests). Production browser14 scenarios and relay/browser7 scenarios pass. Actual Python/Julia1.11.5/Octave9.4 acoustic/RF parity executed and source/output hashes retained. Native APK assembled and v2 signature verified; production Next15 Pages Router/Fiber8 scene rendered in browser.

Scientific rejected approaches preserved: naive acoustic direct-leakage detector, phase/clock/multipath ambiguity, Kalman not improving this range comparison, biased optical fusion, weak/iso-delay CSI, independent antenna drift, coarse RSSI hand inference, RSSI addition harming classifier accuracy, RF corroboration failing to repair acoustic bias, and unrelated-object multimodal activation. Source/truth/uncertainty distinctions remain explicit.

Independent review found7 foundation and5 application issues. Corrected temporal guards, group-descendant termination, fresh parity/source fingerprints, statistical graph ordering, venv interpreter, TCP elapsed budget, quick graph closure, pending permission cancellation, replay payload/intent/EOF release, stale camera acquisition frames and audio units. Actual regression evidence and scoped re-review resolutions are preserved in the two review reports. Selected-model capacity failures were recovered by resuming/substituting agents without overwriting work.

Two owned software emulators failed boot readiness under fixed budgets (API35 Google, API30 AOSP). Neither installed/launched the app. Both stopped; device runtime remains unverified. Real Galaxy A16/ESP32 access absent. All scientific accuracy numbers remain synthetic.

Measured final same-host semantic event benchmark:10 events, mean9.7ms, p9532ms. Active headless software rendering:8.0 actualfps, below target. Standby rendered0 frames/1.988s; software/mobile fallback reduces cost. Baseline with concurrent emulator had207.9ms mean event latency and7.09Hz RAF; rendering mode and host load both changed, so causality is not isolated.

Final verification command `python3 scripts/verify.py --budget 1800` exited0:21 software/synthetic tasks passed,0 failed,0 pending,1 actual-A16 capability task hardware-blocked. Full source/command evidence is in PROJECT_STATE.json and artifacts/harness. Hardware-dependent next actions are in NEXT_ACTIONS.md. No public deployment, real RF capture, purchases or credential operations occurred. Execution is finite and stops at handoff.

### Delivery checkpoint

Updated all twelve experiment records and project metadata with actual outcomes, negative hypotheses, evidence hashes and pending physical validation. Final independent delivery audit agreed with reported results and identified an ADB path documentation correction, now applied. Local preview stopped; emulators already stopped. Packaging preserves source, models, manifests, test evidence and continuation state without installed toolchains or raw sensor recordings.
