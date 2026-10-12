# Independent foundational review — 2026-10-12

Scope: `science/golden_motion/**`, scientific RF sources (excluding downloaded sources/tools), `packages/isi/**`, `packages/rf/**`, `services/relay/**`, `harness/**`, and bootstrap/verification integration. Android and web implementations were excluded because their tracks were still in progress. Reviewed against `docs/ARCHITECTURE.md` and the global constraints/review focus in `docs/superpowers/plans/2026-10-12-golden-motion.md`.

## Verdict

**Changes required: seven Important findings; no Critical finding established.** The specification has useful, testable scientific boundaries: scalar acoustic/RF observations remain scalar, optical image coordinates do not establish depth, explicit intent gates actions, and synthetic/physical provenance is separate. The implementation broadly follows those scientific boundaries. Its acceptance evidence is not yet reliable enough for a reproducible handoff because the verification graph can validate old results, skip changed kernels, or fail before running.

I found no demonstrated ground-truth leakage into the reviewed inverse or classifier feature paths. RF phase models use geometric path length and explicitly expose unsigned-rate ambiguity and confounds. Synthetic fusion uses a declared calibrated bearing proxy plus acoustic range. The acoustic anchored-bearing comparator uses a truth-derived initial bearing, but its result is explicitly named a bearing-prior comparator; it is not presented as independent acoustic localization. Reports acknowledge absent physical hardware and uncalibrated confidence. Those acknowledged limitations are not implementation findings.

Existing scientific/SDK/relay reports and tests were inspected. Full suites and physical acquisition were not rerun. Reproductions below used short in-process checks, isolated temporary directories, or a mocked TCP stream. No production source was edited. This report describes the reviewed snapshot; the root agent owns fixes and final covering verification.

## F1 — Important: future observations can authorize actions and suppress dropout

**Locations:** `packages/isi/src/engine.ts:118`, `:95`, and `:11`.

The freshness condition only checks `now() - timestamp > maxAgeMs`. A future timestamp has negative age and passes even when a finite freshness limit is configured. Once stored, the same timestamp prevents `tick()` dropout and makes subsequent correctly timestamped observations fail the ordering check. Separately, the default `maxAgeMs: Infinity` allows arbitrarily old live input to authorize actions, contrary to the stated stale-input policy.

**Executed reproduction:** instantiate with `now: () => 1791800000000`, `maxAgeMs: 500`, and a metric zone centered at `[0,0,0]`, radius 1. Ingest confident, intentional `source: 'live'` measurements at `[0,0,0]` with timestamps `now + 86400000` and `now + 86400400`. The second ingest returns `hover, hold, select`. `tick(now + 1000)` returns no release. Repeating with default freshness and timestamps `now - 86400000` and `now - 86399600` also returns `hover, hold, select`.

**Needed behavior:** reject excessive future skew before advancing ordering/state, expire using a suitable host-arrival clock, and make live freshness bounded by default. Preserve deterministic replay by an explicit replay/simulation clock or opt-in historical policy rather than weakening live safety.

## F2 — Important: task timeout leaves child processes alive

**Locations:** `harness/process.py:25`, `:57`, and `:69`.

`_stop()` sends SIGTERM to the process group but decides whether to escalate solely by waiting for the group leader. If the leader exits and a child ignores SIGTERM, the wait succeeds, SIGKILL is never sent, and the child continues outside RSS/time monitoring. A child retaining stdout also leaves the drain thread blocked; the result can lose output after the two-second join timeout. Monitoring similarly ends as soon as the leader exits normally even if descendants remain.

**Executed reproduction:** run `execute()` with a Python parent that forks, both processes sleep, and the child installs `SIG_IGN` for SIGTERM and writes its PID into a temporary file. Use a 0.2-second timeout. Observed result: `returncode: -15`, `error: 'resource_budget'`, duration approximately 2.216 seconds. `os.kill(child_pid, 0)` succeeds afterwards: the child is still alive. The reproduction explicitly SIGKILLed its child afterwards.

**Needed behavior:** enforce termination of the owned process group/descendants independently of the leader's exit and finish output draining after cleanup. Cover a resistant descendant as well as the current single-process timeout test.

## F3 — Important: numerical parity can pass without testing current kernels

**Locations:** `harness/tasks.json:14`, `:15`; `science/golden_motion/parity.py:53`; `science/rf/parity.py:11` and `:22`.

The acoustic parity task fingerprints `science/julia/**/*` and `science/octave/**/*`, but it actually executes `science/kernels/acoustic.jl` and `.m`. Editing a real independent kernel therefore does not invalidate a cached successful task. The RF graph runs `parity.py`, which only compares already-written CSV/JSON outputs; it does not invoke the current independent kernels or TypeScript source. Its existing `parity_runner.py` execution path is bypassed. A rerun after a Julia/Octave edit can still report all languages passed using old files.

**Executed reproductions in temporary directories:** changing `science/kernels/acoustic.jl` from one text to another leaves the graph task's fingerprint identical. Copying the RF Python comparator, Python kernel and existing result files, then writing deliberately failing Julia/Octave kernels, still allows the exact graph command `python parity.py` to exit 0 and report `julia`, `octave`, and `typescript` all `passed`. Repository kernels/results were not changed.

**Needed behavior:** fingerprint the actual sources and execution wrapper; regenerate all language outputs before comparison; declare parity outputs and make missing tools/outputs an explicit non-pass or pending result. Include the TypeScript kernel in parity invalidation.

## F4 — Important: RF statistical assertions inspect old results before new experiments run

**Locations:** `harness/tasks.json:10`, `:12`, `:13`; `science/rf/test_statistics.py:7`, `:19`, `:23`.

`rf-science-tests` discovers `test_statistics.py`, which reads `experiments.json`, `classifiers.json`, and `fusion.json`. Both experiment and classifier generators depend on that test task, so the assertions necessarily execute before the new outputs are generated. The graph has no RF fusion generation task at all. On a clean result directory, missing files block the generators; with packaged results present, old metrics pass and current metrics are subsequently written without those statistical assertions being rerun. Acoustic changes can also leave the RF fusion report stale.

**Reproduction from the dependency graph:** remove only the three generated report files in an isolated copy and execute the discovered RF tests: the result-reading tests fail before their producer tasks are eligible. With existing files, the graph orders `rf-science-tests -> rf-experiments/rf-classifiers`, while fusion never runs. `science/rf/run.py:8` already demonstrates the intended generation-before-statistics order, but the root verification path does not use it. This finding is established by the explicit graph and file reads; the expensive experiments were not rerun for review.

**Needed behavior:** separate kernel/unit tests from result assertions, add RF fusion generation with its acoustic/RF inputs, and run statistical validation downstream of all three generators. Fingerprint generated results for the validation task.

## F5 — Important: documented bootstrap and verification use different Python environments

**Locations:** `scripts/bootstrap.py:26`, `:28`; `harness/tasks.json:9` through `:15`; `scripts/verify.py:19`; `science/rf/run.py:8`.

Bootstrap installs pinned NumPy/SciPy into `.venv/bin/python`, then instructs the user to run `npm run verify`. That entry point and every scientific graph command invoke bare `python3`, and the standalone RF runner invokes bare `python`. No code activates `.venv` or selects its interpreter. On an otherwise clean host, successful bootstrap is followed by missing-module failures; on this preprovisioned host the commands can silently use versions different from the pinned environment. This is a command-routing defect independent of the current host's already-installed packages.

**Concrete fresh-host trigger:** run `npm run bootstrap` from a shell whose `python3` has no NumPy/SciPy, then run the printed `npm run verify` command without activating a virtualenv. Scientific tasks import from the shell interpreter, not the environment that bootstrap populated. No new dependency installation was performed for this review.

**Needed behavior:** resolve the project interpreter explicitly for all Python tasks and propagate `sys.executable` through nested runners. Include the selected interpreter/dependency environment in reproducibility evidence.

## F6 — Important: TCP capture timeout is an inactivity timeout, not a capture deadline

**Locations:** `science/rf/acquisition.py:94` through `:96`, and `:75` through `:82`.

The TCP path sets the socket's per-operation timeout and then iterates the stream with no elapsed-time deadline. A peer producing data before each timeout can keep acquisition running arbitrarily long. Non-CSI firmware/status lines never increment the packet budget, so even the maximum packet count does not bound that case. This violates the opt-in, bounded sensing contract and the CLI's advertised capture time budget.

**Executed reproduction:** patch the TCP socket with a stream that yields twelve non-CSI diagnostic lines, 0.02 seconds apart; invoke `main()` with `--timeout-seconds .05`. It exits normally after approximately **0.251 seconds**, five times the requested budget, with zero captured packets. This used a mocked transport and opened no hardware/network capture. An infinite such stream has no stopping condition.

**Needed behavior:** enforce a monotonic deadline across connect/read/parse operations and both accepted and ignored lines, cap line length, and apply remaining deadline to each read. Retain the separate packet limit.

## F7 — Important: quick verification always fails graph validation

**Locations:** `scripts/verify.py:20` through `:22`; `harness/tasks.json:21`.

Quick mode removes `android-build` but retains `galaxy-a16-physical`, which depends on `android-build`. `Runner` validates the graph before marking unavailable hardware blocked, so the missing dependency raises immediately.

**Executed reproduction:** `python3 scripts/verify.py --quick --budget 1` exits 1 with `ValueError: Unknown dependency android-build`, before any task runs or project state is updated.

**Needed behavior:** select a dependency-closed quick graph, including removing the dependent physical task when its producer is excluded. Add a graph-construction check for quick mode.

## Review limits and non-findings

No Critical security defect was established in the loopback/authenticated relay. Its documentation correctly distinguishes admission clock tolerance, recent-ID replay protection, and downstream action freshness. Existing temporary failing SDK reports were treated as historical evidence rather than current defects. Replay explicitly documents that its event budget bounds returned storage while per-ingest publication remains bounded by the zone limit, so that documented behavior was not reported as an unbounded timer storm.

An exploratory all-zero acoustic Doppler concern did **not** reproduce as a valid observation with the ordinary generated tone; it is not included as a finding. No additional broad test run is needed merely to repeat the existing evidence. Fix the findings and run their covering regressions plus the final integrated graph.

## Resolution re-review — 2026-10-12, after final integrated verification

**All seven original Important findings are addressed.** This scoped re-review supersedes the initial changes-required verdict for F1–F7. I inspected the fixes, their regression tests and recorded execution evidence; no new Important/Critical regression was identified within those fixes. Application source and unrelated functionality were outside this follow-up scope. No suites or acquisition commands were rerun, and no implementation source was edited.

| Finding | Resolution | Reviewed basis |
|---|---|---|
| F1 — timestamp safety | Addressed | `engine.ts` now enforces finite `liveMaxAgeMs` and `maxFutureMs` (both default 1000 ms), rejects temporal violations before ordering/history updates, and releases existing state using validated history and host time. Historical synthetic/recorded replay remains explicit through the separate age policy. The added tests cover old/future live input, release/order recovery and replay independence. `artifacts/isi-report.md` records 52 passing SDK tests and 76 passing root tests after the change; the final graph also records `isi-tests` passed. |
| F2 — descendant cleanup | Addressed | `_stop()` sends SIGKILL to the owned process group even after its leader exits, and `execute()` also performs group cleanup after normal completion. The resistant-child regression demonstrably failed in `artifacts/harness-descendant-red.txt` and passes in `artifacts/harness-final-tests.txt` (14 tests passed). |
| F3 — current numerical parity | Addressed | Acoustic fingerprints now include `science/kernels/*`. The RF graph invokes `parity_runner.py` and fingerprints the execution wrapper, Python/Julia/Octave kernels and TypeScript source. The runner executes current languages, records source/output hashes, fails language errors and returns a non-success pending status for missing tools. The comparator rejects source/output mismatches. `test_parity_freshness.py` covers changed source, missing tools and failed execution replacing cached success. Final RF execution status is `executed_current_sources`; current Julia, Octave and TypeScript comparisons all passed. |
| F4 — fresh RF statistical evidence | Addressed | RF unit discovery excludes result-dependent statistical assertions. Explicit `rf-fusion` generation depends on acoustic experiments and RF tests; `rf-statistics` depends on experiments, classifiers and fusion, fingerprints those reports, and gates dataset validation. State records the three generators passing before the final statistical validation at 11:12:21 UTC. |
| F5 — Python interpreter routing | Addressed | Both verification and harness entry points use `harness.config.load_tasks()`, selecting the installed project `.venv/bin/python` or the invoking interpreter. The standalone RF runner and parity subprocess use `sys.executable`. Configuration regressions cover virtualenv selection and fallback and pass in the recorded 14-test harness run. |
| F6 — TCP capture deadline | Addressed | `tcp_lines()` enforces one monotonic deadline starting before connection, sets each receive timeout to remaining time, and checks the deadline while parsing buffered lines. Byte, line-count and line-length budgets include diagnostics; a sidecar audit records stopping reason and elapsed time. `test_tcp_budget.py` exercises a continuous diagnostic stream against the total deadline and overlong diagnostics. These regressions are included in the passing RF unit task. |
| F7 — quick graph validity | Addressed | Quick mode now calls `exclude_tasks()`, which removes transitive dependents of excluded tasks. This removes the hardware task when the Android producer is excluded. `test_config.py` verifies the resulting graph and its regression passes in the recorded harness run. |

The inspected `PROJECT_STATE.json` final run records **21 passed, 0 failed, 0 pending and 1 hardware-blocked task**. Current numerical parity records Julia/Octave maximum complex error approximately `4.39e-14` and TypeScript approximately `4.41e-14`. Those are software/synthetic results; this review does not upgrade the explicitly pending physical validation.

## Final delivery audit

Reviewed README, validation report, next actions and final verification evidence. Counts of 177 tests and 21 browser scenarios, APK hash/size, hardware limitations and measured rendering limitation agree with execution evidence. Corrected root README to use the installed ADB path; bootstrap does not alter the caller PATH. No remaining material delivery finding.
