# Reproducible RF track

All numerical results and ESP-format fixtures are **synthetic**. No Wi-Fi capture, hardware command or private network was used. The official source/license verification is dated 2026-10-12. The standalone report is `artifacts/rf-report.md`.

Run from repository root:

```sh
python science/rf/run.py
npm run test --workspace @golden-motion/rf
npm run build --workspace @golden-motion/rf
```

Python requires NumPy/SciPy; core tests use unittest. The run is bounded to120 seconds per task and currently completes in~15 seconds plus language startup. Independent Julia/Octave executables installed by the main scientific track are detected by `parity_runner.py`; absent tools produce pending status with exit code 3, never a passed parity claim. Source/output hashes reject stale comparisons. Command-specific `OCTAVE_HOME` is required for the relocated conda installation. Seeds are fixed in each script. Window/runtime latency is measured, not a phone benchmark.

`kernel.py` implements complex geometric multipath CSI, common/independent phase disturbances, RSSI forward/inverse, scalar estimates and local Fisher rank. `experiments.py` produces40-seed scenarios and failed hypotheses; `classifiers.py` compares classical processing and regularized statistical classifiers on entirely held-out synthetic sessions; `fusion.py` imports the actual acoustic kernel and calibrated optical-bearing proxy and preserves failures. `parity.py` compares current Python/Julia/Octave/TS complex values. `results/execution.json` and the source hashes provide run evidence; stochastic streams are not claimed identical across languages.

`acquisition.py` decodes ESP32 legacy signed8 imaginary/real CSV. First invalid4 bytes, malformed shapes, timestamp rollover, baseline amplitude calibration, JSONL labels, record/replay and explicit bounded serial/TCP adapters are included. The official current firmware distinguishes ESP32-C5/C6/C61 layouts and12 bit forced-LLTF; unsupported layouts are rejected. CSI subcarrier indices/packet format and gain/phase calibration must be validated before a Doppler algorithm can consume hardware data. Typical ESP32 records supply one coherent antenna, so the adapter deliberately uses an amplitude-only anomaly baseline, not the two-antenna synthetic CSI estimator.

A fixture replay command that does not open hardware:

```sh
python science/rf/acquisition.py --input science/rf/fixtures/esp32-csi-synthetic.csv --fixture --output science/rf/results/fixture-replay.jsonl --label empty-room-synthetic
```

Generated fixtures are marked `source:synthetic` and `physical_acquired:false`. File input without`--fixture` is `recorded` with physical-acquisition status unverified. Only explicitly received serial/TCP hardware packets are `live`; recording/replay never upgrades provenance. Physical adapters require an explicit named source and`--authorized`, packet/time bounds and an existing participant/operator authorization. Optional pyserial is needed only for actual serial collection. No hardware collection command was executed here.

`research_sources.py` optionally rechecks public cited metadata/documentation/publications through the inherited proxy and preserves initial evidence. It retains no publication snapshots, dataset or unlicensed code archives. `bibliography.json` distinguishes verified licenses, unknown licenses and unavailable full text; Widar DataPort metadata identifies CC BY 4.0, while official Widar code ZIP licensing remains unknown.
