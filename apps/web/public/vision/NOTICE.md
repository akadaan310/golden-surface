# Local MediaPipe assets

MediaPipe Tasks Vision 0.10.22-rc.20250304 and the Google MediaPipe Hand Landmarker model are distributed under Apache-2.0. These assets permit opt-in hand inference entirely within the browser; the application does not send or retain camera frames.

- WASM and loader scripts: `@mediapipe/tasks-vision/wasm` from the pinned npm package.
- Model: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
- Model SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- SIMD WASM SHA-256: `f00ec4731faa23b3e714d00e88d4d10e2df5c0a427d3a2b4ae6e3526fdd14ef7`
- Non-SIMD WASM SHA-256: `3821ea9b1f7fb8c549ef2a064ef5c85750bf375c545a49fd6eea0df44a95f1f4`

See https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE for the Apache-2.0 license and upstream notices.
