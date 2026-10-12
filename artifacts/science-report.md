# Scientific track evidence: GM-001 / GM-004 / GM-005

Status: implemented and executed deterministic synthetic laboratory. **No physical sensor validation was performed.** All acoustic, optical and BLE numerical values below are synthetic results, not Galaxy A16 performance. RF evidence is separately owned in `artifacts/rf-report.md`.

Commands from repository root:

```bash
python -m pip install -r science/requirements.txt
python -m unittest discover -s science/tests -v
python -m science.golden_motion.experiments
bash science/bootstrap-tools.sh
python -m science.golden_motion.parity
```

The latest scientific unittest execution passed **20 tests in 32.375 s**, with no warnings in the passing run. Executed experiments and parity both exited 0. Bootstrap was checked with `bash -n` and executed idempotently. Behavior tests were written before APIs; initial missing-API failures and subsequent incorrect-behavior failures are retained in `science/results/*-red.log`. Tests cover repeatability, fractional delay, reversed Doppler sign, phase ambiguity, nonfinite input rejection, scalar observability, actual optical/fusion Jacobian rank, noise-only/no-hand controls, static-background calibration, clock drift, scalar state smoothing/initial timestamp correctness, optical scale ambiguity, RSSI adapter validation and numerical negative controls.

## Comparable results

Seed **20261012**, model **gm-acoustics-v1**, 121 common synthetic samples over 4 s at 30 Hz. Frames contain identical truth for acoustic chirp/tone, optical pinhole ray and BLE RSSI. The phase and Doppler range tracks use the first matched-filter range as their anchor; they do not use truth. The scalar acoustic estimate has **no 3D position score** because it is unobservable. The two spatial baseline scores below explicitly use fixed initial priors; they do not imply that scalar acoustic or camera image data alone reconstruct 3D position.

| Experiment / estimator | Result | Units |
| --- | ---: | --- |
| GM-001 matched filter range | 0.4433 | mm RMSE |
| GM-001 anchored phase range | 0.3939 | mm RMSE |
| GM-001 Doppler-integrated range | 1.0696 | mm RMSE |
| GM-001 Kalman scalar range | 0.5352 | mm RMSE |
| GM-001 radial velocity | 0.1963 | mm/s RMSE |
| GM-004 calibrated optical+range fusion | 2.1034 | mm position RMSE |
| GM-004 fixed-bearing acoustic prior baseline | 73.6409 | mm position RMSE |
| GM-004 camera with first-range prior baseline | 43.5386 | mm position RMSE |
| GM-004 optical bias, fused | 66.9722 | mm position RMSE |
| GM-005 BLE tag RSSI inverse range | 69.6451 | mm RMSE |
| GM-005 BLE with 6 dB body attenuation | 362.8218 | mm RMSE |

Calibrated synthetic ray+range fusion helps against both fixed-prior baselines. An unmodeled 0.15 normalized-image bias harms fusion. The common trajectory's scalar Kalman estimate is worse than the matched filter; this failed improvement is preserved. A separate constant-velocity/noisy-range regression demonstrates when the same filter reduces jitter. Confidence is normalized correlation or a phase-residual quality heuristic, never a calibrated probability. Chirp bandwidth resolution is labeled separately from standard deviation.

## Forward model and observability

`science/golden_motion/model.py` evaluates explicit speaker/target/microphone bistatic path length, a moving target, analytic complex chirp/carrier phase, inverse product-distance amplitude, excess-path reflections, direct leakage, seeded complex Gaussian noise, clock offset and rate error. Defaults are 96 kHz synthetic sampling, 18 kHz tone and 15–21 kHz chirp with 4 ms pulse. These are model assumptions; Android acquired sample rate and speaker/microphone bandwidth remain unmeasured. The quasi-static approximation neglects target displacement during propagation, diffraction, directivity, AGC, transducer response and colored noise.

The numerical range/range-rate Jacobian has position rank **1** and state rank **2 of 6** for one monostatic pair. A four-anchor noncoplanar synthetic array has position/state ranks **3/6**. A collinear array with target on its axis remains **1/2**. Pinhole image coordinates have scale ambiguity and rank **2**; calibrated colocated ray plus monostatic range has computed local rank **3**. Jacobians and singular values are retained in `results.json`. Local rank does not prove global uniqueness. Actual camera intrinsics/extrinsics and cross-sensor synchronization are not available.

## Negative controls and perturbations

Each range perturbation sweeps 48 distances from 0.120 to 0.402 m with seeded independent noise. All-estimate error and accepted fraction are reported separately; rejected estimates are not silently dropped.

| Perturbation | Range RMSE (mm) | Accepted fraction |
| --- | ---: | ---: |
| baseline | 0.0498 | 1.0000 |
| high_noise | 2.1563 | 0.4375 |
| weak_multipath | 4.9278 | 1.0000 |
| dominant_multipath | 44.7499 | 1.0000 |
| sound_speed_mismatch | 9.9231 | 1.0000 |
| clock_offset_400us | 68.5920 | 1.0000 |
| direct_leakage | 239.9433 | 1.0000 |

- Noise-only no-hand control: **0 / 100 false accepts**.
- No-hand with strong direct leakage: naive strongest correlation produces **100 / 100 false accepts**. This disproves the hypothesis that normalized matched-filter correlation alone identifies a hand.
- Static no-hand measured-background subtraction reduces that specific synthetic control to **0 / 100 false accepts** and gives **0.0616 mm** range RMSE with a hand. This assumes unchanged direct leakage/environment; changing clutter still requires new calibration or rejection.
- A 13 mm displacement produces a wrapped phase displacement of **3.4722 mm**. At 18 kHz the range phase period is 9.5278 mm, and the unambiguous inter-frame step is only ±4.7639 mm.
- Clock drift of 200 ppm with a static target creates **3.6000 Hz** apparent Doppler and **-34.3000 mm/s** apparent radial motion. Independent timing/reference calibration is required.
- Dropout has no measurement; scalar interaction expiration is delegated to the ISI SDK.
- BLE requires an instrumented transmitting tag; its synthetic calibrated log-distance inversion is not bare-hand localization. Body attenuation substantially biases inverse distance.

## Independent Julia / Octave execution

Independent source kernels are `science/kernels/acoustic.jl` and `science/kernels/acoustic.m`. They generate complex moving-target echo samples and separately compute bistatic path/gradient, strongest-peak fractional matched-filter range, correlation confidence, tone Doppler/radial rate, phase displacement and local geometry ranks. They do not call Python. Selected parity kernels are noiseless; cross-language RNG equivalence is not claimed.

| Runtime | Actual version | Exit | Scalar max absolute difference | Signal max absolute difference |
| --- | --- | ---: | ---: | ---: |
| julia | julia version 1.11.5 | 0 | 1.013e-13 | 1.110e-16 |
| octave | GNU Octave, version 9.4.0 | 0 | 1.084e-13 | 2.143e-14 |

Tolerance is `1e-9 + 1e-9 * abs(reference)`. Deliberate 0.001 output corruption fails validation. `science/results/parity.json` retains exact commands, versions, values, runtimes and output logs. The first attempted conda Octave 10.1.0 pin did not exist; one retry installed 9.4.0. Direct execution initially found builtin functions but missed standard m-files because conda's compiled prefix remained in the path. Inspecting the conda activation script established `OCTAVE_HOME=<installed-prefix>` as the root cause, and the Python runner now sets it for the command. The first failure report is retained.

Local runtimes occupy about 4.4 GiB in ignored `science/.tools` and must be excluded from source archives. Bootstrap pins Julia 1.11.5 and its SHA256, micromamba 2.9.0 and its SHA256, plus all Octave dependencies through the successful explicit conda URL/hash graph in `science/results/octave-conda-explicit.txt`. Python environment is 3.12.14, NumPy 2.3.5, SciPy 1.17.0.

## Artifacts and integration

- `science/results/browser-fixture.json`: browser-compatible schema v1, common frames/truth/estimates, scalar acoustic measurements, normalized optical coordinates, explicitly calibrated synthetic fused position, BLE scalar metadata and decimated signal plotting traces.
- `science/results/results.json`: GM-001/004/005 metrics, negative controls, configuration, numerical Jacobians and environment.
- `science/results/environment-manifest.json`: seed, model version, dependency versions and output SHA256. Wall-clock cost values intentionally vary; whole-file hashes therefore change after reruns.
- `science/results/repeatability.json`: two actual repeated common experiments produced identical frames, traces and scientific metrics after excluding wall-clock costs.
- `science/results/tools-manifest.json`: actual runtime versions and pinned archive/dependency hashes.
- `science/results/parity.json` and `science/results/parity/*.csv`: actual independent numerical evidence.
- `science/README.md`: equations, limits, complete JSON schema and hardware-ready BLE adapter acquisition guidance.

`BLEAdapter.ingest(timestamp_ms, rssi_dbm)` accepts platform scan callbacks or exported samples, rejects stale/nonfinite/out-of-range input and emits measurement-space RSSI with no position. No calibration means RSSI only; optional range metadata requires explicit calibration. Source provenance is supplied by the acquisition boundary. The supplied calibration is synthetic. Android runtime permissions, opt-in scanning, user-selected tag filtering and lifecycle stop are documented for real acquisition.

Latest synthetic per-frame echo generation+estimation mean/p95: **1.3271/1.2900 ms**; tone generation+estimation: **1.0674/1.2266 ms**. These are host CPU costs and do not establish physical sensing latency.

Pending physical experiments: acquired Galaxy A16 audio rate/bandwidth, opt-in low-amplitude pulse loopback response, device geometry and calibrated static background, timing drift, real moving-hand multipath/no-hand errors, camera intrinsics/extrinsics/time alignment and a measured BLE tag calibration. No physical accuracy or safety outcome is claimed.
