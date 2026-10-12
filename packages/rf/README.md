# @golden-motion/rf

Dependency-free TypeScript CSI/RSSI laboratory kernel shared by browser and React Native. All generated streams are synthetic. `defaultRfConfig`, `generateCsiFrame`, `simulateRf`, `analyzeCsi`, `extractRssiSamples`, `analyzeRssi`, `csiDiagnostics`, `rfMeasurement` are public APIs. `npm run build --workspace @golden-motion/rf` emits JS and declarations while package exports use TS for Next/Metro.

```ts
const config = defaultRfConfig();
const frames = simulateRf(config, { durationS: 4, seed: 42 });
const csi = analyzeCsi(frames, config);
const rssi = analyzeRssi(extractRssiSamples(frames), config);
const measurement = rfMeasurement(csi, { timestamp: Date.now() });
```

The complex forward model sums direct, static and moving reflection paths at each antenna/subcarrier and applies CFO, SFO, common packet phase noise, complex thermal noise, packet loss and clock drift. Scattering amplitudes are prescribed; this is not a Maxwell solver or a validated phone channel model. RSSI has a separate calibrated log-distance/shadowing model and is held at a coarse cadence. Never pass scan/RSSI values into the CSI estimator.

CSI estimation requires two *simultaneous coherent* receive channels. The inter-antenna product removes only common phase disturbances. An ordinary single-antenna ESP32 recording cannot satisfy this requirement by stacking packets or duplicating antennas. The Python hardware adapter provides a separate amplitude-anomaly baseline for it. Scalar CSI Doppler yields unsigned bistatic path-rate, not reflector XYZ. Only a colocated TX/RX scene marked `monostatic` reports unsigned radial speed. `uncertaintyMps` is a Fourier-bin width, not a calibrated coverage bound; `confidence` is a quality heuristic. Multiple reflectors or independent antenna phase drift can produce confidently wrong answers.

`rfMeasurement` uses `measurement-space`, `relative.kind='rf-motion-score' with unit='unitless'`, no position/velocity vector, and `intent=false` unless explicitly supplied by an independent interaction policy. A high RF motion score is environmental channel variation, not identified hand presence or deliberate action. Acquisition, calibration, replay, source verification and executable scientific controls are in `science/rf`; actual hardware tests remain pending.
