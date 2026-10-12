# GOLDEN MOTION research ledger

## 2026-10-12 — Session initialization

Workspace was empty. Created a fresh repository on branch `gm-foundation`. Observed Python 3.12.14, Node 24.19.0, Java 21.0.12.1; NumPy/SciPy available; Julia, Octave, Android SDK, ADB and Gradle absent on PATH. HTTP network policy unrestricted and enforced; no configured credentials, no VPN. No physical sensor data or hardware connection discovered.

Design choice: local monorepo with explicit source provenance and measurement-space semantics. User's autonomous execution directive supersedes skill approval pauses and sequential implementation suggestions. Subsystems have disjoint ownership to permit parallel implementation. Builds and synthetic results are separate from hardware validation.

Plan: `docs/superpowers/plans/2026-10-12-golden-motion.md`. Contract: `docs/ARCHITECTURE.md`. Implementation begins from an empty baseline; no prior experiment is rerun.

## Priority amendment GM-RF-001

Preserved the five original tracks and added a sixth dedicated RF track in `science/rf` and `packages/rf`. RF becomes a primary UI and scientific pillar. CSI, RSSI, hotspot capability, participating-device RTT and ESP32 acquisition are separate pathways. Coarse RSSI does not become hand coordinates. Numerical work includes moving-reflector channel simulation, RSSI negative controls, observability/ambiguity and fusion failures. Android receives documented Wi-Fi/hotspot probes; web receives configurable geometry and CSI/RSSI displays. No authorized physical radio hardware is connected.

Harness implementation evidence: `python3 -m unittest discover -s tests -p 'test_*.py' -v` passed 10 tests covering dependency order, checkpoint/unchanged-task reuse, bounded retries, timeout termination, missing artifacts/dependencies, hardware blocking, output bounds and input fingerprints. Environment inventory saved in `artifacts/environment.json`.
