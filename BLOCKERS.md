# Blockers

- Actual Galaxy A16 not connected. Model, variant, hardware capability inventory, physical audio bandwidth, camera accuracy, power and latency measurements remain pending.
- Initial Julia/Octave/Android tooling absence was resolved through pinned local installs. Python, Julia, Octave, SDK/Gradle, web and APK builds now execute.
- No physical experiment datasets provided. Simulated and acquired evidence remain distinct.
- API35 Google and API30 AOSP software-emulator first boots exceeded bounded deadlines; no installed-app runtime test completed. KVM is absent. Both emulators were stopped and failure evidence preserved.
- Active headless software-rendered 3D measured ~8 FPS, below the 30–60 FPS target. Demand/low-power rendering and responsive semantic controls are implemented; actual Galaxy A16 rendering/power remains unmeasured.
- Public Android APIs do not establish raw CSI access. ESP32/CSI-capable NIC/radar/participating RTT hardware is absent; licensed physical RF datasets were investigated but not acquired or evaluated.
