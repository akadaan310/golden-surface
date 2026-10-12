# Native Android evidence

## Implemented

`apps/android` contains the complete React Native native application and Kotlin
legacy hardware bridge. The debug APK embeds its Hermes bundle and MediaPipe
model; it can run without Metro. Synthetic hand interaction consumes the shared
ISI engine, including intent, zone geometry, calibration identifiers, hover,
semantic scroll, select/cancel, object drag/rotation, event subscriptions and
bounded recording/replay. The native publisher uses the shared authenticated
loopback RelayClient and validates the endpoint without React Native's incomplete
URL implementation. Explicit stop publishes SDK release events and closes sensing
and transport; activity pause/destroy and native invalidation close resources.

The inventory queries actual build/model, Android API, available sensors,
sample-rate properties, camera count/permissions, BLE support, battery, power
save and thermal state. Opt-in acquisition includes a bounded low-output
AudioRecord/AudioTrack experiment with RMS/peak, configured rates and read
throughput, optional platform capture/playback frame positions and monotonic
timestamps, available-sensor streaming, a 30-second connection-RSSI timeline,
a 10-second BLE scan and a documented 30-second local-only hotspot adapter.
The bundled official MediaPipe task exposes normalized fingertip image coordinates
and landmark count, without z, world landmarks or saved camera media. Absent hands
have no action confidence; model failures leave only image-motion summaries.

Wi-Fi modes separate synthetic CSI from live or synthetic RSSI. Live RSSI routes
through the SDK's dedicated coarse presence branch and never drives spatial
zones, select, scroll or fabricated coordinates. Synthetic CSI publishes validated
scalar motion-presence/path-rate summaries. Current connection fields include
RSSI, frequency, link rates, supplicant/connection state, scan throttling,
permissions, RTT feature and local-only-hotspot support. Public CSI is explicitly
unavailable; RTT is compatible-device range, never hand range.

## Verification and build

Successful commands:

```sh
npm run test --workspace=@golden-motion/android
npm run typecheck --workspace=@golden-motion/android
bash apps/android/scripts/bootstrap.sh
bash apps/android/scripts/build.sh
```

JS safety tests: 19 passed (low output and finite duration bounds; public or
credential-bearing transport rejection; RN URL portability; bounded recording;
no raw media fields and isolated coordinate arrays). Native JUnit safety tests:
3 passed (duration, amplitude and frequency bounds). TypeScript: passed.
The additional 14 integration regressions execute actual transpiled App.tsx with
controlled React hooks, deferred permission/native promises and the real SDK
engine; they do not represent Android device execution. Thirteen expected
failures were observed before the review fixes, preserved in
`artifacts/android-app-regression-red.log`. The corrected suite verifies Stop,
mode and lifecycle cancellation of pending main acquisitions; independent BLE
and hotspot permission cancellation; cleanup after late native acknowledgements;
action metadata round-trips and isolated vectors; replay current-intent gating,
EOF/disarm release; valid unitless normalized audio RMS; and original camera
acquisition timestamps with silent-feed dropout. The reviewer's original
pending-permission reproduction now reports zero starts after Stop.

Generation and AppState guards surround permission and native-start awaits.
Inactive native callbacks cannot ingest measurements after Stop. Metadata retains
bounded scroll deltas, rotation angles, drag vectors and semantic units/intent,
without raw media. Replay observations remain visible while current intent gates
action effects; EOF and disarm publish cancellation. Audio summaries explicitly
use SDK-supported `unitless` values, normalized by digital full scale, and every
measurement is validated before display/inference.

Initial Gradle build failed because the monorepo default Hermes compiler path
pointed to app-local node_modules. Fixed the explicit compiler path; failure
preserved in `artifacts/android-build-initial-failure.log`. The subsequent build
compiled the Kotlin bridge and MediaPipe adapter and assembled the installable
APK successfully in 2 m 51 s. Build logs preserve compiler/deprecation warnings.
The final incremental rebuild passed in 1 m 44 s after the semantic safety
edits. `artifacts/golden-motion-debug.apk` is 65,978,909 bytes, SHA256
`32eb3c09914a3f3c2fdc6d528c8ac2df4963be26c63e90d57f19f835da8b00c4`.
`aapt dump badging` confirms package `com.goldenmotion`, minimum API 24 and target
API 35. `apksigner verify --verbose` verifies its v2 signature. Final JS tests
and typecheck were rerun successfully after assembly. Root-managed emulator
runtime evidence is being collected separately.

Versions: React Native 0.76.9, React 18.3.1, CLI 15.1.3, Metro 0.81.5, Kotlin
1.9.25, Android Gradle Plugin 8.7.2, Gradle 8.10.2, Android SDK platform 35,
build-tools 35.0.0. Java launcher 21.0.12.1; Gradle provisioned Adoptium
17.0.20.1 for the RN plugin's toolchain. MediaPipe tasks-vision 0.10.20 and the
official float16 Hand Landmarker task revision 1 are bundled. Target API 35,
minimum API 24; arm64-v8a, armeabi-v7a, x86_64. Generated APK is a development
build using a local debug signing key; initial artifact approximately 63 MiB.

Audio inventory also reports input-device sample-rate declarations, PCM minimum
buffer declarations at 16/24/44.1/48/96 kHz, near-ultrasound microphone/speaker
properties, and microphone sensitivity/frequency-response declarations when
permitted. These declarations do not measure actual clock rates or usable
ultrasonic bandwidth. Capture uses UNPROCESSED only when the device declares
support; otherwise VOICE_RECOGNITION, with vendor processing explicitly unknown.
Camera prefers the front camera with a back-camera fallback. BLE emissions are
limited to 10 Hz, 1000 observations and 10 seconds.

## Physical limits

Initial `adb devices -l` found no devices. A root-managed API 35 x86_64 software
emulator later connected. Initial install and launch attempts returned missing
Android `package` / `activity` services; app runtime verification has not yet been
established by those attempts. Its runtime behavior is separate evidence and cannot
verify any Galaxy A16 physical capability. No physical handset is connected.
Camera inference throughput/accuracy, acoustic usable bandwidth, device DSP,
hardware sampling clock, echo delay, physical Doppler and RF response all remain
pending actual device experiments. PCM RMS is not an acoustic range estimate;
no acoustic 3D claim is made. Camera output has no measured depth. Hand model
confidence is a quality heuristic, not calibrated accuracy.

The app uses the legacy Camera API as a bounded camera-to-MediaPipe adapter;
its normalized image axes follow the raw selected-camera frame, not a calibrated
phone pose. No NDK toolchain was required for assembly, so prebuilt native
libraries are packaged without symbol stripping. Source/installation/runtime
instructions are in `apps/android/README.md`. Recording is memory-only and
bounded; no persistence/export of raw audio, images, BLE identifiers or hotspot
credentials is implemented. External raw CSI capture and physical A16/ESP32
integration remain pending hardware.
