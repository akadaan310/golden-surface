# Application / integration review

Review date: 2026-10-12. Scope: `apps/android` and `apps/web` source, their SDK/relay boundaries, README and architecture truth requirements. Generated output, dependencies and tool installations excluded. No ADB operations, hardware claims, deployment or source edits. Existing suite/build results were supplied by the integrator; this review ran only focused reproductions.

**Disposition: five Important findings; no Critical finding. Approval pending correction of the findings below.** Pending physical-device validation is not itself a defect.

## APP-1 — Important: pending native starts can restart acquisition after Stop or lifecycle pause

- Location: `apps/android/src/App.tsx:31`, `:40`, `:42`, `:43`, and the asynchronous hotspot/BLE handlers at `:61` / `:63`.
- Root cause: `stop()` clears current resources, but does not invalidate outstanding asynchronous start operations. `start()` resumes after permission and capability promises without checking that the request is still current, the selected mode is unchanged, or AppState remains active. Its eventual `setRunning(true)` also disregards intervening stop requests. Rapid repeated starts can similarly race.
- Reproduction: execute actual transpiled `App.tsx` with a deferred `PermissionsAndroid.requestMultiple` and counted native methods. Select Wi-Fi, invoke Start session, invoke Stop all before resolving permission, then resolve permission as granted. Observed `{stopCalls:2,startWifiCallsAfterStop:1}`. The same continuation pattern exists for audio and camera. Lifecycle change invokes the same unguarded `stop()`.
- Impact: an explicit stop/backgrounding can be followed by audio/camera/Wi-Fi acquisition starting, contrary to the promised release behavior.
- Required correction: invalidate pending operations using a session generation/token and verify it plus current lifecycle after asynchronous boundaries; handle native starts that settle after cancellation with cleanup. Apply the same cancellation discipline to independent permission-dependent probes. Add a deferred-permission stop/mode-change/lifecycle regression.

## APP-2 — Important: native semantic recordings discard the values needed to replay actions

- Location: `apps/android/src/safety.cjs:3`; consumers `apps/android/src/App.tsx:26`, `:27`, `:50`.
- Root cause: `recordEvent()` whitelists metadata provenance but omits `scrollDelta`, `angleRad` and `delta`. Native replay feeds these reduced semantic events directly into `applyEvent()`, which reads `scrollDelta` and `angleRad` from metadata. A recorded scroll therefore becomes a zero scroll; a recorded rotation becomes a zero rotation. Forwarded replay drag events also lose the delta consumed by the web preview.
- Reproduction: pass `{type:'scroll',metadata:{scrollDelta:25,unit:'px',intentional:true,evidence:'synthetic'}}` to the actual `recordEvent`. Returned metadata is only `{"evidence":"synthetic"}`. The action consumer then defaults the missing value to zero.
- Impact: the advertised semantic replay cannot reproduce core recorded actions, locally or across the native-to-web path.
- Required correction: retain a bounded, validated set of action metadata, or record and replay validated measurements through the inference engine. Preserve the existing raw-media exclusion. Test action-value round trips, not only buffer size/privacy.

## APP-3 — Important: native replay bypasses the intent gate and leaves selection active at completion

- Location: `apps/android/src/App.tsx:24`, `:25`, `:27`, `:50`.
- Root cause: replay sends recorded events directly to `applyEvent()`. That consumer applies selection/drag/rotation without consulting current intent. The end-of-recording branch only calls `setRunning(false)`; replay state was never ingested by the engine, so its heartbeat cannot release the selected target afterward.
- Reproduction: execute actual transpiled App with initial `intent=false`, one recorded valid synthetic `select` event, and controlled timers. Invoke Replay, then its EOF timer. Observed `intentRef:false`, selection transitions `[false,true]`, and running transitions `[false,true,false]`. Thus disarmed replay selects, and the target remains selected after running ends. A bounded recording ending on select/drag makes this an ordinary user path.
- Impact: the UI statement “Intent gate · enable to issue actions” is false during replay, and replay completion fails interaction cleanup.
- Required correction: gate replay effects with current intent, release them immediately on disarm, and explicitly cancel/reset replay-owned selection at EOF and stop. Maintain provenance and permit event monitoring while disarmed.

## APP-4 — Important: a stalled live browser camera observation is continuously restamped as fresh

- Location: `apps/web/components/Laboratory.tsx:45`, `:47`, `:48`; camera emission `apps/web/lib/useCamera.ts:17`.
- Root cause: the camera callback provides an observation timestamp, but the 80 ms sampling loop discards it and creates fresh `Date.now()` measurements from the last `observed` object. If video frames cease changing, `useCamera` emits nothing and remains live; the engine repeatedly receives apparently fresh high-confidence hand data. The web host also has no independent engine heartbeat for missing observations.
- Reproduction: apply the actual adapter expression to one hand observation at time 1000 and repeatedly ingest it with sampling timestamps 1000–3000. At 3000 the SDK still emits `hover`, despite the camera observation being two seconds old and the configured dropout bound being 350 ms. A stalled camera stream produces this exact adapter behavior.
- Impact: a lost live camera feed can retain an active hover/selection instead of releasing on dropout; recorded observations also misstate acquisition time.
- Required correction: retain the acquisition timestamp, ingest each new observation once, and tick/release the engine when observations age beyond the selected freshness bound. Handle stream ended/muted/error transitions as appropriate. Test a detected hand followed by a frozen feed.

## APP-5 — Important: native audio measurements violate the shared measurement-unit contract

- Location: `apps/android/src/App.tsx:37`; schema `packages/isi/src/schema.ts:62`.
- Root cause: the native adapter labels RMS with `relative.unit:'full-scale'` in `measurement-space`, but the shared validator supports only `m`, `dBm`, `rad`, `m/s`, `Hz` and `unitless` there. `InteractionEngine.ingest()` silently rejects this invalid measurement; the adapter's try/catch does not expose that rejection.
- Reproduction: call `validateMeasurement()` with the native audio adapter's emitted shape. Result: `unsupported measurement units`.
- Impact: every native audio summary fails at the Kotlin → JS → shared SDK boundary, despite the app showing it as a current measurement. The chosen low confidence should withhold semantic actions; an invalid unit should not be the mechanism doing so.
- Required correction: represent normalized digital RMS as `unitless`, documenting full-scale normalization in metadata/UI, or compatibly extend/document the SDK contract. Add an adapter-shape validation check while keeping amplitude distinct from range and retaining its conservative action confidence.

## Areas reviewed without a material finding

- RN 0.76 legacy bridge configuration, merged SoLoader mapping, embedded Hermes entry bundle configuration, bundled hand model, manifest permissions/API guards.
- Bounded native audio amplitude/duration, Wi-Fi sampling, BLE observation count/time limits, sensors, hotspot reservation cleanup, camera bitmap/image cleanup, lifecycle hooks and provenance labels. Async operation cancellation remains subject to APP-1.
- RSSI/CSI distinction, scalar audio/range versus spatial position, camera normalized axes/no depth, synthetic proxy labels, RF unsigned rate/user-selected direction.
- Web local intent/zone/stop policy, relay frame and timestamp gates, remote stop suppression, and bounded recording/event displays. No hardware feasibility inferred from compilation or synthetic evidence.

Focused reproductions above used actual source or actual exported validation/recording functions; no full test suite was rerun and no emulator was touched.

## Resolution — scoped final correction review, 2026-10-12

**Final disposition: APP-1 through APP-5 addressed. Application/integration review approved within this scope; no remaining Critical or Important finding identified in these corrections.** This resolution supersedes the initial pending-approval disposition above. Physical sensing and emulator-runtime limitations remain separately documented and are not converted into successful evidence.

The reviewer inspected the frozen corrected source, `artifacts/android-report.md`, `artifacts/web-report.md`, and the new targeted regression code. The integrator's supplied verification covers 19 native JS tests, native typecheck/build/APK signature, 17 web unit tests, production build, 14 browser checks and 7 relay checks. Those full suites were not rerun for this review.

| Finding | Resolution and exact source evidence |
| --- | --- |
| APP-1 | **Addressed.** `apps/android/src/App.tsx:35` increments the session generation and clears active capture on stop; `:36` checks both generation and active AppState; `:47` checks pending permission continuations; `:38` checks before native start and cleans up a late acknowledgement; `:49` captures a new session token, `:50` applies the guarded start to Wi-Fi/audio/camera, and `:55` / `:56` apply it to independent probes/sensors. Native samples now use `activeCapture` at `:42`. Targeted actual-App regressions in `apps/android/tests/app.test.cjs` cover permission-stop, mode/background cancellation, independent probes and late native completion. Independently reran the original `/tmp/application-review-native-harness.cjs` with `EXPECT_STOP_SAFE=1`: **pass**, `startWifiCallsAfterStop:0`; its trace ends at permission grant with no subsequent native start. |
| APP-2 | **Addressed.** `apps/android/src/safety.cjs:4` retains bounded finite `scrollDelta`, `angleRad`, and a copied three-element `delta`, plus allowed semantic units and intent flags; arbitrary raw-media metadata remains excluded and the 256-event bound remains. `apps/android/src/App.tsx:30` / `:31` consume the retained values. The new recording test checks nonzero action round trips and mutation isolation; the armed replay test verifies an actual 25 px scroll. |
| APP-3 | **Addressed.** `apps/android/src/App.tsx:27` gates action effects using the current intent ref while leaving event monitoring available; `:25` synchronously updates that ref and releases replay/engine state on disarm. `:28` tracks replay-owned selection/drag; `:37` emits its cancellation; `:58` releases at EOF and checks session validity on every replay step. `:35` also releases on stop. Actual-App tests cover disarmed replay, armed value application followed by EOF release, and immediate disarm release. |
| APP-4 | **Addressed.** `apps/web/lib/useCamera.ts:18` captures `acquiredAt` before inference and `processedAt` afterward. `apps/web/lib/camera.ts:6` retains acquisition time as the measurement timestamp; `:13` ticks SDK dropout, `:14` deduplicates observations independently of engine history, and `:16` rejects expired/future frames. `apps/web/components/Laboratory.tsx:42` ticks the engine on the host sampling clock, and `:49` uses this consumer for live camera input and records only newly consumed frames. Independently ran `node --import tsx --test apps/web/tests/camera.test.mjs`: **3/3 pass**, including frozen observation through 3000 ms, dropout release, exactly one zone entry, and resumption only with a new frame. |
| APP-5 | **Addressed.** `apps/android/src/App.tsx:44` emits `audio-rms` with SDK-supported `unitless` and explicitly documents PCM16 full-scale normalization. `:34` validates measurements before display/inference, so contract failures are surfaced. Conservative confidence remains 0.4 and no range is fabricated. The actual native audio adapter regression verifies the original timestamp, unit and successful shared-schema validation. |

No app source was changed by this re-review. No ADB or hardware operations were performed. No new material breakage was identified within the five corrections.
