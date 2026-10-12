# GOLDEN MOTION scientific laboratory

All supplied signals and results are synthetic. No microphone, camera, BLE tag, RF instrument, or Galaxy A16 is connected to this laboratory. Model or APK execution does not establish hardware feasibility.

From repository root:

```bash
python -m pip install -r science/requirements.txt
python -m unittest discover -s science/tests -v
python -m science.golden_motion.experiments
bash science/bootstrap-tools.sh
python -m science.golden_motion.parity
```

Python 3.12 is the orchestration authority. NumPy/SciPy dependencies are pinned. Julia 1.11.5 and Octave 9.4.0 independently implement selected deterministic noiseless kernels without calling Python. The bootstrap downloads local Linux x86_64 runtimes into ignored `science/.tools`; Julia archive SHA256 and the complete conda Octave dependency graph are pinned. The first unavailable Octave version pin and the conda `OCTAVE_HOME` diagnosis are retained in `results`. `JULIA_BIN` and `OCTAVE_BIN` may override discovery. Python parity supplies `OCTAVE_HOME` for a locally installed conda prefix.

`results/results.json` contains comparative metrics, perturbation controls, observability Jacobians/ranks, environment and forward configuration. `results/browser-fixture.json` contains 121 common frames and plotting traces; its schema is documented below. `results/parity.json` records commands, versions, exit status, timings, outputs and tolerances for actual independent execution. RF experiments belong to the independent `rf/` track.

## Model and interpretation

For position `p`, speaker `s`, microphone `m`, speed `c`, and velocity `v`, bistatic path length is `L = ||p-s|| + ||p-m||`. Complex receive samples use the analytic emitted chirp at `t - L(p+vt)/c - clockOffset`, with inverse product-distance amplitude, explicitly configured excess-path reflections, static direct leakage, clock offset/rate error and seeded complex Gaussian noise. This approximation neglects target motion during propagation, transducer response, diffraction, directivity, AGC, deformation, physical noise coloration. The synthetic sample rate 96 kHz and 15–21 kHz sweep are model parameters, **not measured Android capabilities**.

The matched filter finds the strongest correlation envelope peak and interpolates fractional sample delay. In monostatic geometry `r = c tau/2`; generally this quantity is equivalent half-path and cannot be presented as a radial distance from a distinct speaker/microphone origin. Pure-tone phase displacement is `-c deltaPhase/(4 pi carrier)`, ambiguous modulo 9.528 mm at 18 kHz. An inter-frame displacement must remain below 4.764 mm to choose the correct wrapped phase branch. Doppler uses the fitted unwrapped baseband phase slope; receding motion is negative frequency shift, with half-path rate `-c fD/(2 carrier)`.

Matched-filter correlation confidence is a quality heuristic. The bandwidth resolution scale `c/(2 bandwidth)` is explicitly **not** a calibrated standard deviation. Range uncertainty needs independent calibration. Static no-hand background subtraction is supported by `estimate_delay(signal, cfg, background=recorded_background)`; its successful synthetic control assumes unchanged direct leakage and environmental paths. Strong multipath and changing clutter still invalidate strongest-peak interpretation. The raw failed direct-leakage hypothesis is preserved in results. A 200 ppm clock rate error creates 3.6 Hz apparent Doppler, or -34.3 mm/s apparent motion for a static target; independent timing/reference calibration is required.

The constant-velocity Kalman estimator operates only on scalar range/rate. Its tuned range/rate noise and acceleration process model are simulation assumptions. It is not guaranteed to beat the matched filter; the common trajectory reports that it does not.

A single monostatic path observes one position and one velocity direction (state rank 2 of 6), and never produces a 3D acoustic position. A noncoplanar synthetic array has local rank 6 under known timing/geometry; collinear target geometry remains rank 2. These are local ranks, not proof of global uniqueness. The optical adapter returns normalized pinhole image coordinates and bearing without depth; uniformly scaled targets produce identical images. Fusion uses a calibrated synthetic camera ray colocated with the monostatic origin. Under this explicit assumption `position = ray * range`, and combined local rank is 3. Phone camera intrinsics, extrinsics and sensor synchronization remain unmeasured. Biased optical fusion is included and performs worse.

## Browser fixture schema v1

Top-level fields: `schemaVersion`, `source`, `modelVersion`, `seed`, `units`, `assumptions`, `frames`, `traces`, `experiments`. `source` is always `synthetic` here. Timestamps are epoch milliseconds with relative `elapsedS`; frame interval is 1/30 s.

Each frame contains:

- `truth`: `positionM`, `velocityMps`, `rangeM`, `radialVelocityMps`; synthetic ground truth only.
- `acoustic`: scalar `rangeM`, anchored `phaseRangeM`, `dopplerIntegratedRangeM`, `filteredRangeM`, `radialVelocityMps`, `dopplerHz`, `confidence`, `valid`, and `coordinateFrame: measurement-space`. It has no spatial position.
- `optical`: normalized `image`, calibrated synthetic `bearing`, `depthObserved: false`, quality heuristic confidence, and `coordinateFrame: camera-image-normalized`.
- `fused`: `positionM`, `coordinateFrame: phone-local-m`, `source: synthetic`, `calibrationId: synthetic-colocated-pinhole-v1`. Render only with the accompanying calibration assumptions.
- `ble`: scalar RSSI measurement with `relative` in dBm, quality heuristic confidence and assumed RSSI standard deviation. Any inverse distance is explicitly optional scalar metadata.

`traces` includes sample times, transmitted/received real analytic traces, original rate and plot decimation. The traces are decimated for plotting and unsuitable for frequency estimation. `experiments` repeats summary metrics for display. Scientific values repeat exactly with seed/version; wall-clock cost fields intentionally vary between executions.

## BLE hardware adapter

GM-005 uses the log-distance model `RSSI = P1m - 10 n log10(r) + GaussianNoise`; inversion needs measured transmitter power, exponent and RSSI noise. It is a tagged-object alternative and cannot locate an uninstrumented hand. A 6 dB body attenuation control tests sensitivity to unmodeled propagation.

`golden_motion.adapters.BLEAdapter` accepts Android `ScanResult.getRssi()` callbacks or timestamped scan exports. Native integration should request Android version-appropriate Bluetooth scan/connect permissions, make acquisition opt-in, filter to a user-selected advertised service/device, stop scans on lifecycle pause and never retain raw hardware identifiers by default. The Python boundary rejects invalid, nonfinite, duplicate and out-of-order samples. It emits scalar measurement-space data without spatial coordinates. Example for an actual scan export containing `timestamp_ms,rssi_dbm`:

```python
import csv, json
from science.golden_motion.adapters import BLEAdapter
adapter = BLEAdapter('user-selected-tag', source='recorded')
with open('scan.csv', newline='') as stream:
    for row in csv.DictReader(stream):
        print(json.dumps(adapter.ingest(float(row['timestamp_ms']), float(row['rssi_dbm']))))
```

No calibration object means RSSI only. Pass `RSSICalibration(...)` only with a documented measured calibration; the supplied default object is labeled synthetic. A camera/acoustic recording requires microphone/camera opt-in and actual acquired rates/timestamps, device impulse response, loopback baseline and synchronization measurements before assigning live accuracy.
