# Decisions

- D001: Preserve an isolated new local repository in `/workspace/golden-motion`, branch `gm-foundation`; existing workspace files untouched.
- D002: Scalar acoustic observations support scalar interactions; image measurements support image-plane interactions. 3D synthetic proxy is labelled synthetic.
- D003: Opt-in loopback transport uses a runtime token and bounded messages. No public hosting or credentials operations are needed for local delivery.
- D004: Use React Native 0.76.9 with legacy Kotlin bridge for build compatibility, React 18.3.1 and Next.js 15. Pin resolved package versions and record limitations.
- D005: GM-005 uses a tagged BLE RSSI scalar alternative; magnetic dipole rendering is a separate synthetic model. A bare hand is not assumed to generate a magnetic tag field.
- D006: Actual browser testing found React18/Fiber8 incompatible with Next15 App Router's bundled React19. Use the supported Pages Router; preserve Next.js/TypeScript/Three.js requirements.
- D007: RF classifier and fusion failures remain published in local evidence. Synthetic thresholds and uncalibrated quality do not authorize precise hand positions or physical RF gesture claims.
- D008: Software-emulator API35 then lighter API30 attempts received fixed budgets and were stopped when boot readiness failed. Native app runtime is pending a usable emulator or actual phone.
- D009: Implement demand/low-power rendering after measured software-renderer performance. Keep below-target active FPS in the report; semantic same-host latency is a separate measurement.
- D010: Resolve Python tasks through the pinned local virtual environment; execute current language kernels and validate fresh RF statistics through explicit graph dependencies.
