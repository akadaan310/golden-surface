# GOLDEN MOTION for Android

React Native 0.76.9 / React 18.3.1, Kotlin legacy bridge (`newArchEnabled=false`).
The debug APK embeds its Hermes JavaScript bundle and official MediaPipe model;
Metro is unnecessary for installation. Android 7/API 24 or later is required.
Built ABIs: arm64-v8a, armeabi-v7a, x86_64.

## Build on Linux

From the repository root, with root npm dependencies installed:

```sh
npm run bootstrap --workspace=@golden-motion/android
npm run test --workspace=@golden-motion/android
npm run typecheck --workspace=@golden-motion/android
npm run build --workspace=@golden-motion/android
```

Bootstrap downloads Android command-line tools revision 11076708, platform 35,
build tools 35.0.0, platform-tools and Gradle 8.10.2 into `.tools/`. It uses the
inherited HTTPS proxy when configured. The RN Gradle plugin requests Java 17 and
Gradle can provision that toolchain. This session used Java 21 as the launcher
and Adoptium 17.0.20.1 as the provisioned compiler. `build.sh` runs Kotlin safety
unit tests and packages `artifacts/golden-motion-debug.apk`. AGP is 8.7.2 and
Kotlin is 1.9.25. This is a development build, signed with a local debug key.

## Install and run

```sh
.tools/android/platform-tools/adb devices -l
.tools/android/platform-tools/adb install -r artifacts/golden-motion-debug.apk
.tools/android/platform-tools/adb shell am start -n com.goldenmotion/.MainActivity
```

For a physical Galaxy A16, enable USB debugging, connect the handset and accept
its device debugging prompt. A connected emulator verifies app behavior only;
it does not establish Galaxy A16 sensor, acoustic, RF or tracking feasibility.
A sideloaded APK can also be opened through Android's usual install flow.

Start a synthetic session, enable the explicit intent gate to permit actions,
and inspect the field, semantic scroll, event list and trace. Replay monitors events
while disarmed; scroll/select/drag/rotation effects require current intent. EOF
and disarm release replay-owned selection. Semantic action values are retained
in the bounded metadata whitelist. Increase the zone
radius or capture a local baseline to change the semantic target. The model
confidence is a heuristic. Recording is bounded to 256 semantic events in memory;
replay is labelled `recorded` and preserves original provenance. Stop releases
interaction state, every native resource and the transport connection. Activity
pause/destroy and native module invalidation also stop hardware. Pending permission or native
start acknowledgements are invalidated by Stop, mode changes or backgrounding,
so a late grant cannot restart acquisition.

Live audio, camera, Wi-Fi, BLE and hotspot actions request their relevant runtime
permissions. Permission denial does not start the requested acquisition.

- Audio: mono PCM, requested/configured 48 kHz with 44.1 kHz fallback, a 3 s
  18 kHz tone at <= 0.01 digital full-scale. Keep speaker volume low; the tone
  can be audible. Native bounds are 0.5–5 s and <= 0.01 full-scale regardless of
  JS arguments. Displayed read throughput is not a calibrated hardware rate.
  RMS/peak summaries do not determine distance, Doppler or a 3D position.
  Platform capture/playback frame timestamps are shown when available, without
  a calibrated latency claim. Input rates, near-ultrasound properties and
  microphone frequency-response declarations are inventory evidence, not a
  bandwidth or hardware-clock measurement. Capture uses declared UNPROCESSED
  support or VOICE_RECOGNITION; device/vendor processing remains unknown.
- Camera: 30 s front-camera reference (back-camera fallback) with bundled MediaPipe HandLandmarker 0.10.20.
  Only normalized index-fingertip x/y and landmark count are exposed, without
  model z or world landmarks. The ISI adapter uses scalar image-y; the image axes
  are the raw camera frame and are not phone-local metres. Absent hands have zero
  action confidence. A model failure leaves frame-difference summaries, with no
  hand actions. Raw frames, JPEGs and bitmaps are transient and never saved.
- Wi-Fi: documented connection RSSI, frequency, link rates and state at 1 Hz for
  30 s. RSSI uses the SDK's coarse presence branch, never CSI Doppler, hand range
  or spatial actions. RTT capability means compatible-device ranging support.
  Repeated scans, hidden APIs and rooting are not used. Local-only hotspot is
  opt-in and automatically closes at 30 s; no network credentials are retained.
- BLE: opt-in scan for 10 s; only observation counts and RSSI summaries leave
  the adapter, without addresses or advertisements. Sensors stream at requested
  <=10 Hz for at most 60 s. Unsupported sensors are absent from the inventory.

## Publish to the browser

Start the repository's authenticated loopback relay with a token, then forward
its host endpoint over USB:

```sh
GM_RELAY_TOKEN='use-your-local-random-token-at-least-16-characters' npm run relay
.tools/android/platform-tools/adb reverse tcp:8787 tcp:8787
```

Enter `ws://127.0.0.1:8787` and that token in the app's publisher panel, then
connect. The wire protocol authenticates `{type:'auth',token,role:'publisher'}`
before sending `{type:'event',event:ISIEvent}`. The shared portable RelayClient
handles capped reconnection and output bounds without retaining stale offline
sensor events. Phone and host epoch clocks must agree within the relay's window
(-30/+5 s). Tokens stay in current app memory and never enter recorded events.

Raw CSI is not available through documented Android public APIs. The CSI mode
is an explicitly synthetic coherent-antenna model. External ESP32 or another
CSI-capable adapter is a pending acquisition experiment, not a handset feature.
