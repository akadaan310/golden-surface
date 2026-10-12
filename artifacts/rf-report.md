# GOLDEN MOTION RF foundation — GM-RF-001 amendment

The RF track is executable in Python and shared TypeScript, with independently executed Julia/Octave kernels and an ESP-CSI acquisition adapter. **All sensing results are synthetic; real-world validation is false for every path below.** No Galaxy A16, ESP32, NIC or SDR was accessed, and no Wi-Fi network was captured or probed. Official documentation/publications were read through the inherited HTTPS proxy. Physical acquisition, phone feature checks, RF gesture training and participant evaluation remain pending.

## Model, observations and application contract

For each receive antenna and subcarrier, the forward model computes

\[
H_{a, k}(t)=\sum_\ell A_\ell e^{-j 2\pi f_k L_{a,\ell}(t)/c}+n_{a, k}(t),\qquad
L(t)=\|p(t)-TX\|+\|p(t)-RX_a\|.
\]

Direct/static paths and moving reflectors are explicit. Configurable nuisances include complex noise, common CFO, SFO subcarrier slope, packet phase noise, loss, clock drift and, in the scientific failure controls, independent antenna phase drift. Antenna positions are spaced by half a carrier wavelength. Scattering coefficients are supplied constants: no material scattering, polarization, diffraction, near-field hand deformation, AGC, transceiver transfer function or Maxwell solution is claimed. The default synthetic scene uses 5.2 GHz, 100 packets/s and 30 contiguous 312.5 kHz-spaced subcarriers (~9.06 MHz frequency span); it is not a captured ESP32 configuration.

CSI inference normalizes a coherent inter-antenna conjugate product and estimates its temporal spectrum. This cancels *common* CFO/SFO/phase disturbances, while independent antenna drift remains a demonstrated confound. Multiple reflectors produce sidebands. The result is **unsigned bistatic path-rate**: \(|\dot L|=|f_D|c/f_c\). Only explicitly colocated TX/RX reports unsigned radial speed \(|\dot L|/2\). Direction, absolute target range and XYZ are not inferred. A single bistatic delay constrains an ellipsoid; one-link Fisher position rank is 1. Three diverse synthetic calibrated range links have rank 3 and condition 10.19, but this is local differential observability, not an implemented global localization algorithm or a hardware result. Mirrored/global ambiguities remain.

At 100 Hz/5.2 GHz, the ideal unsigned path-rate Nyquist bound is ~2.88 m/s; a 4 s Fourier window has ~0.0144 m/s bin width. Missing packets, changing velocity and sidebands alter those limits. For context, 20 MHz bandwidth gives ~7.49 m equivalent half-path range resolution; carrier phase wraps every ~5.77 cm of path and cannot create absolute range without additional calibration/information. The default synthetic frequency span is narrower than that 20 MHz example.

RSSI has a separate log-distance/shadowing forward model and inverse:

\[
P(d)=P_0-10\eta\log_{10}(d/d_0)+S(t),\quad
\hat d=d_0\, 10^{(P_0-P)/(10\eta)}.
\]

Its inverse estimates **calibrated TX–RX link distance**, not a moving hand's range. The coarse 1 Hz cadence, correlated shadowing and motion-induced power modulation are explicit. Changing orientation, power, gain or unrelated traffic can mimic motion. No CSI phase/Doppler estimator is applied to RSSI.

`@golden-motion/rf` exports `defaultRfConfig`, `generateCsiFrame`, `simulateRf`, `analyzeCsi`, `extractRssiSamples`, `analyzeRssi`, `csiDiagnostics`, and `rfMeasurement`. Browser and React Native use the same dependency-free TS kernel. Spectrum power and corrected inter-antenna phase diagnostics reuse the actual estimator calculation. Estimates include presence/score/quality, source, warnings, optional scalar path-rate, ambiguity and a Fourier-bin width. `confidence` is an **uncalibrated signal-quality heuristic**. `rfMeasurement` passes shared SDK validation, uses `measurement-space` with `rf-motion-score`/`unitless`, emits no position or velocity vector, omits absent optional values, and defaults `intent=false`. RF channel variation alone identifies neither a hand nor deliberate action. A simulator's displayed reflector position is truth, never RF-reconstructed position.

## Executed statistical evidence

GM-RF-001/002 controls use 40 fixed independent noise/loss seeds per CSI scenario and 40 per RSSI scenario. Wilson 95% intervals describe fixed-model detection counts; 0/40 has upper bound 8.76% and 40/40 has lower bound 91.24%. Error intervals use 2,000 bootstrap means. These intervals do not establish across-room/participant generalization. Full trials, configurations and rejected hypotheses remain in `science/rf/results`.

| CSI scenario | Detections / 40 | Detected scalar path-rate MAE | Finding |
|---|---:|---:|---|
| Nominal moving reflector |40|0.00389 m/s|Small error under supplied geometry/scattering assumptions|
| No-hand static / no reflector |0 /0|—|Negative controls remain inactive|
| No-hand strong common CFO/SFO/phase noise |0|—|Common-phase cancellation works; naive raw-phase baseline activates 40/40|
| Clock drift 2000 ppm |40|0.00337 m/s|Rate bias retained|
| Noise 0.20 |40|0.00389 m/s|Confidence/calibration deteriorates; not robustness to arbitrary hardware noise|
| Packet loss 50% |40|0.00527 m/s|Degraded quality and reduced confidence|
| Weak reflection amplitude 0.08 |0|—|Physical motion can be missed|
| Iso-delay circular motion around baseline |0|—|Real motion unobservable in this geometry|
| No-hand independent antenna drift 3 Hz |40|0.173 m/s apparent motion|False-positive control has confidence 1; confidence is not probability|
| Multiple opposed movers |40|0.0826 m/s|A strongest peak does not identify one target's velocity|
| One coherent receive antenna |0|—|Estimator declares unobservable|

Coarse RSSI detects 0/40 nominal small hand motions and 0/40 no-hand low-shadow controls. With 6 dB correlated shadowing it falsely activates 40/40 no-hand trials. Slower 0.2 Hz cadence also detects 0/40 motions. This demonstrates a synthetic failure of the simple RSSI baseline, not a claim that RSSI can never support learned coarse gestures.

GM-RF-006 compares a validation-tuned classical variance threshold with regularized logistic classifiers. Each of 56 generated environment sessions has 8 condition windows; train/validation/test sessions are 32/8/16, with entire sessions held out and no overlapping windows. **There are zero physical participants.** Models learn synthetic environmental channel-motion labels, not a trained human gesture vocabulary. No deep network is warranted by 256 synthetic training windows. Session-cluster bootstrap intervals preserve within-session dependence; per-window Wilson intervals in JSON are secondary IID approximations.

| Held-out 128 windows / 16 synthetic sessions | Accuracy | Session-bootstrap 95% accuracy | False activation | Recall |
|---|---:|---|---:|---:|
| Classical variance threshold |57.81%|54.69–60.94%|68.75%|84.38%|
| Logistic, CSI features only |82.03%|78.91–85.16%|9.38%|73.44%|
| Logistic, CSI + coarse RSSI |78.91%|75.78–82.81%|10.94%|68.75%|

RSSI addition harms this held-out comparison; it is preserved. CSI-only false-activation session-bootstrap interval is 3.13–15.63%. Probability calibration bins/Brier scores are published; scores remain imperfect. Measured container median feature-plus-CSI processing is ~0.5 ms/window and classifier processing ~0.001 ms/window; acquisition requires a 4 s window. These are not phone latency measurements. The shared TS implementation uses a bounded direct spectral scan and is separately tested/built.

GM-RF-007 uses the **actual independent acoustic signal generator/matched-filter estimator**, the scientific track's calibrated optical-bearing proxy, and generated complex RF on a common moving trajectory. Optical input is a geometric pinhole proxy, not actual images/detection. Under explicitly known colocated camera/acoustic origins and camera calibration, optical bearing + acoustic scalar provides position; RF adds only unsigned motion corroboration. RF-only and acoustic-only remain scalar; optical-only has no measured depth.

| Common 40-seed scene | RF / acoustic / optical activation | Quality-gated acoustic+optical activation | Fused position MAE |
|---|---|---:|---:|
| Nominal |100% /100% /100%|100%|0.00246 m|
| No hand; RF independent phase drift |100% /0% /0%|0%|unavailable|
| Optical unavailable |100% /100% /0%|0%|unavailable|
| Acoustic clock bias 1 ms |100% /100% /100%|100%|0.1724 m|
| Strong excess-path acoustic multipath |100% /100% /100%|100%|0.1008 m|
| Weak RF reflector |0% /100% /100%|100%|0.00246 m|
| Unrelated moving reflecting object labelled as non-hand |100% /100% /100%|100% false hand activation|~0.00246 m object-location error|

A naive OR ensemble accepts the no-hand RF drift. Requiring valid optical hand evidence and valid acoustic scalar is an operational alternative: missing optical input produces no spatial interaction, and RF is accepted as corroboration only when its path-rate agrees with the estimated trajectory. **This gate still fails on acoustic bias, multipath and target identity.** RF agrees with biased trajectories here and does not fix them. The unrelated-object case explicitly supplies a misidentified optical proxy; it is not a measured camera false-positive rate. Acoustic+RF gradients can have velocity rank 2 if signed rate were known, still below full 3D velocity rank; current RF sign ambiguity remains. No fused intentional action is justified by mere multimodal movement agreement.

## Practical paths A–H

Sampling below is documented behavior or a proposed experiment rate, never measured Galaxy A16 capability. Every row has `realWorldValidated:false`.

| Path | Hardware / permission requirements | Available measurement and cadence | Spatial/temporal observability, complexity and limits |
|---|---|---|---|
| A — Galaxy A16 public APIs |Physical phone; runtime feature/permission checks. Scanning normally needs fine location, Wi-Fi state permissions and location enabled. RTT targeting Android 13+ uses nearby Wi-Fi permission; older targets require fine location; hardware/AP FTM support and visible app/service required.|Public RSSI/link/scan fields; cadence/caching vendor dependent. Android 9+ foreground scans:4 per 2 min; all background apps combined:1 per 30 min. RTT measures device-to-FTM AP distance conditionally; foreground RTT not scan-throttled, actual range interval/hardware unknown.|RSSI is coarse channel power, no complex CSI. RTT is cooperating device/AP range, not reflected-hand range. One AP does not localize 3D. Phone model name/OS version does not establish FTM support. Runtime `FEATURE_WIFI_RTT`/availability checks pending.|
| B — Galaxy A16 hotspot |Public local-only hotspot API with applicable runtime permissions; owned phone/clients and consent. Tethering/soft-AP management or client metrics can require privileged permissions.|Public hotspot session/configuration and permitted app socket traffic; no public privileged CSI assumed. Propose bounded 5–20 Hz cooperative app timing, to be measured; RSSI/client diagnostics may not be exposed.|App RTT includes OS/queue/network delay and cannot become RF time-of-flight. AP mode is not a radar upgrade. Hotspot channel/gain/client behavior and handset thermal/power effects untested.|
| C — Authorized existing Wi-Fi |Operator + participant authorization and an authorized app/device. Public API permissions as A; no promiscuous traffic capture or observation of unaware people.|Public app/link/scan fields; documented scan throttling; permitted cooperative own traffic only.|No high-rate CSI inferred from ordinary app metrics. Multipath, people and unrelated traffic confound attribution. No sensing on public/private networks performed.|
| D — Cooperative owned devices |Phone–phone/laptop/ESP32 with consent; explicit transport and clock/calibration setup. Multiple links need known geometry and synchronized acquisition.|App timing/RSSI or device-supported CSI; proposed own-packet generation 10–100 Hz, not verified. Local clock offsets/drift must be estimated.|Multiple receivers can add independent gradients only with calibrated geometry/phase and adequate data. Unsynchronized app clocks do not prove localization. CPU/transport modest; synchronization/calibration is substantial.|
| E — ESP32 official ESP-CSI |Owned supported chip, USB/serial or explicit TCP stream; official ESP-IDF/ESP-CSI firmware and operator/participant permission. Latest README lists ESP32/S2/C3/S3/C5/C6/C61; format varies.|Official per-received-packet CSI/RSSI/timestamp/antenna metadata. Packet rate not guaranteed; set and measure on owned links. Official current parser uses 921600 baud; validate firmware console settings.|Adapter handles legacy signed 8 IQ, first invalid word, rollover clock, calibration and replay. New 12 bit/gain layouts explicitly rejected. Typical one coherent antenna supports amplitude anomaly baseline here, not common-phase-free two-antenna Doppler. Hardware-ready, physically pending.|
| F — Specialized research hardware |CSI-capable research NIC, SDR/USRP, wideband FMCW radar, calibrated arrays and suitable compute. Emissions/capture must comply with local law and operator/participant authorization; no purchases/access here.|Complex CSI or radar IQ/ToF/AoA with hardware-dependent high cadence/bandwidth.|Additional bandwidth/aperture can improve rank/resolution. Cost, driver/firmware compatibility, clock synchronization and reproduction effort exceed phone-only APIs. Historical paper performance is not current feasibility.|
| G — Full synthetic RF lab |Python NumPy/SciPy; shared TS; optional Julia/Octave. No RF hardware/network access.|Complex CSI 100 Hz default; RSSI 1 Hz default; deterministic geometry/loss/noise and truth labels.|Executable perturbation/observability/classifier/fusion controls. Motion truth is available only to evaluation/rendering, not scalar estimator. Cannot validate scattering, gain, firmware or human generalization.|
| H — Properly licensed published RF datasets |Dataset license, attribution, permitted use, storage budget, participant/session labels and provenance review before acquisition.|Widar3.0 official IEEE DataPort metadata verifies CC BY 4.0; paper uses Intel 5300 CSI. Official project links label/gesture data and extraction/model code, but code ZIP licenses remain unknown.|No dataset downloaded or evaluated. Session/participant-separated real evaluation remains pending. Do not import unknown-license code or treat unavailable datasets as reproduced evidence. Dataset sampling/training geometry may differ from phone/ESP32.|

## Primary-source taxonomy and licenses

Actual URLs/statuses are in `science/rf/results/source-verification.json`, short evidence in `source-evidence.json`, full citations in `science/rf/bibliography.json`. Source reads do not imply permission to reuse code or data. Full publication PDFs/HTML snapshots were discarded after inspection; no unknown-license datasets/code archives were downloaded.

| Prior art / verified primary source | Actual measurement/hardware distinction | Code/data/license finding |
|---|---|---|
| [WiSee, Pu et al., MobiCom 2013](https://homes.cs.washington.edu/~gshyam/Papers/wisee.pdf) |Doppler/narrowband reconstruction; USRP-N210 prototype and receive-array processing.|Paper grants limited personal/classroom copying, not generic reuse. Code/data availability and licenses unknown.|
| [WiTrack, Adib et al., NSDI 2014](https://witrack.csail.mit.edu/witrack-paper.pdf) |Custom analog FMCW daughterboard + USRP; one TX/three RX, calibrated reflected ToF geometry.|Specialized radar, not commodity hotspot RSSI. Code/data reuse not verified.|
| [WiGest, Abdelnasser et al., 2015](https://arxiv.org/abs/1501.04301) |RSSI temporal gestures; paper reports 50 Hz controlled RSSI collection and Linksys/Netgear AP setups.|arXiv nonexclusive distribution is not a code/dataset license. Android scan 50 Hz support is not established.|
| [WiFinger, Tan/Yang, MobiHoc 2016](https://doi.org/10.1145/2942358.2942393) and [different WiFinger, Li et al., UbiComp 2016](https://doi.org/10.1145/2971648.2971738) |Two distinct systems sharing a name. Crossref primary publisher metadata identifies exact titles/authors/DOIs.|Publisher full text unavailableHTTP 403; attempted author copy 404. Hardware details, code and licenses remain unverified; no phone-support inference.|
| [Widar3.0, Zheng et al., MobiSys 2019](https://tns.thss.tsinghua.edu.cn/widar3.0/data/MobiSys19_Widar3.0_paper.pdf) |Intel 5300 NIC mini-desktops + Linux CSI Tool at 5.825 GHz; body-coordinate velocity-profile recognition.|[Official project](https://tns.thss.tsinghua.edu.cn/widar3.0/) links code/data; code ZIP licenses unknown. [IEEE DataPort metadata](https://ieee-dataport.org/open-access/widar-30-wifi-based-activity-recognition-dataset) explicitly states CC BY 4.0 for the dataset; not downloaded.|
| [RF-Pose, Zhao et al., CVPR 2018](https://openaccess.thecvf.com/content_cvpr_2018/html/Zhao_Through-Wall_Human_Pose_CVPR_2018_paper.html) |Custom FMCW horizontal/vertical antenna arrays;30 heatmap pairs/s; camera cross-modal supervision.|Not ordinary Wi-Fi RSSI. No dedicated source repository identified on the inspected author page; code/data licenses unknown.|
| [DensePose From WiFi, Geng/Huang/De la Torre, 2023](https://arxiv.org/abs/2301.00250) |3TX×3RX paths, 30 subcarriers, 100 Hz CSI and visual pseudo-label supervision for dense image correspondence.|Not uncalibrated one-phone 3D hand recovery. arXiv distribution license is not implementation/data reuse permission; dedicated code/data license unverified.|

Verified official implementation sources: [ESP-CSI](https://github.com/espressif/esp-csi) at commit`8633d67152db2808f141cc1595970aa9cf406045` is Apache-2.0; [current ESP-IDF CSI documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/wifi-driver/wifi-vendor-features.html#wi-fi-channel-state-information) explicitly specifies imaginary-byte then real-byte order and first-four-byte invalidity. Android [scan restrictions](https://developer.android.com/develop/connectivity/wifi/wifi-scan), [RTT](https://developer.android.com/develop/connectivity/wifi/wifi-rtt) and [local-only hotspot](https://developer.android.com/reference/android/net/wifi/WifiManager#startLocalOnlyHotspot(android.net.wifi.WifiManager.LocalOnlyHotspotCallback,%20android.os.Handler)) were read. ESP-IDF's old stable URL is a meta-refresh page; the actual current target above was separately verified. No credential, live network or private API was used.

## Acquisition and remaining physical tests — GM-RF-005

`science/rf/acquisition.py` provides bounded explicit serial input and TCP input with total deadlines, remaining per-receive time and diagnostic-inclusive byte/line/packet budgets plus sidecar audits, official firmware-header CSV parsing, signed IQ extraction, first-word rejection, monotonic 32 bit-microsecond rollover mapping, receipt/local timestamp separation, empty-room amplitude calibration, manual labels and JSONL record/replay. Fixture tests reject wrong/odd lengths and preserve synthetic provenance. Only explicit live received packets can be labelled `live`; reading a file is `recorded` with unverified physical status. Replay retains original acquisition source. No public real capture fixture was found in the inspected official repository: supplied CSV is **official-format-generated synthetic data**, quantized from the RF model, with a separate provenance manifest. It is not evidence of ESP32 acquisition.

The physical plan is reviewable and pending: record firmware/chip/console format and owned-channel configuration; confirm operator/participant consent; acquire empty-room/no-hand baseline and gain/phase stability before hand trials; verify actual cadence, sequence loss, timestamp drift/rollover and channel/LTF layout; annotate rest/approach/retreat/swipe plus unrelated movement, fan/door/phone-motion controls; use independently measured camera/optical or marked motion reference with timestamps; separate complete participant/session trials for calibration/train/test; measure false activations per minute, latency, coverage and calibrated uncertainty; compare amplitude baseline, CSI algorithms valid for actual antenna coherence, RSSI and fusion; retain low-SNR/blind/multiple-target failures. The Galaxy A16 plan first checks public runtime permissions, feature flags, cached field cadence and RTT availability; unavailable CSI/FTM remains unavailable. No hotspot, scan, packet transmission or emissions were initiated.

## Reproduction and verification

From repository root:

```sh
python science/rf/run.py
npm run test --workspace @golden-motion/rf
npm run build --workspace @golden-motion/rf
python science/rf/acquisition.py --input science/rf/fixtures/esp32-csi-synthetic.csv --fixture --output science/rf/results/fixture-replay.jsonl --label empty-room-synthetic
```

Core/adapter/classifier tests first failed on missing implementations before being implemented; SDK integration first failed on unsupported dimensionless units and then passed after using `unitless` and omitting undefined metadata. Current verification is20 Python tests (including4 evidence-preservation/statistical controls),8 TS tests including actual SDK validation, and successful TS declaration/JS build. The bounded numerical run publishes commands/exit codes in `results/execution.json`; fresh language execution manifests hash sources and outputs, reject stale comparisons, replace cached success after execution failure, and return a pending exit code for missing languages; fixed seeds and all trial records are included. Public source rechecks are optional via `research_sources.py` and do not retain full source copies.

Julia 1.11.5 and Octave 9.4.0 were actually executed, not merely installed. Independently written kernels compare18 complex values per language with Python: maximum absolute error4.39×10⁻¹⁴; RSSI inverse2 m and single-link rank1 agree. TS complex forward parity is4.41×10⁻¹⁴. Noise is disabled for mathematical parity; different stochastic PRNGs are not claimed equivalent. Relocated conda Octave requires command-specific `OCTAVE_HOME`; this was diagnosed and incorporated. The implementation is a synthetic scientific/application foundation; practical RF resolution, safety/legality of emissions, hardware support, detection quality and human intent remain unvalidated physical questions.
