Bundled hand reference model

Official MediaPipe Hand Landmarker task, float16, revision 1:
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

Downloaded 2026-10-12. Integrity is recorded in hand_landmarker.sha256.
Adapter uses com.google.mediapipe:tasks-vision:0.10.20 in IMAGE mode, one hand.
Only index fingertip x/y and landmark count leave the frame processor. Image depth,
world landmarks and handedness score are not treated as measured position or
tracking confidence. JPEG, bitmap, MPImage and raw preview buffers are transient.
Task instructions: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/android
