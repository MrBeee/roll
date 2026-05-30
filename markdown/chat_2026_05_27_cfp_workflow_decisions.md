# Session Handoff - 2026-05-27

## Status

CFP workflow discussions converged on a correctness-first direction, with speed improvements accepted as long as numerical behavior stays within agreed tolerances.

- User priority confirmed: correct results first; Float32 accuracy is acceptable.
- CFP progress/logging and naming consistency work from this session remained aligned.
- We reviewed the current CFP efficiency direction (fused kernels, reduced passes) and framed it against correctness safeguards.
- We discussed adding a separate CFP Amplitude Map task and clarified threading expectations.

## Key Outcomes

- Float32/complex64 remains a valid production path for CFP, provided there is a reference validation path and explicit error tolerances.
- The proposed "separate CFP Amplitude Map task" should be a distinct job type, but still run under the existing single-active-operation controller model.
- Running amplitude concurrently with the 6 CFP plot job is not required and not recommended for this workflow; long-running amplitude computation can stay serialized by design.
- For long amplitude runs, practical reliability features (progress clarity, optional partial update throttling, and checkpoint/restart) are higher value than adding concurrency.

## Decisions

- Keep correctness as the top acceptance criterion; performance is secondary.
- Keep Float32 as the main compute dtype for speed/memory balance, with baseline checks guarding drift.
- Keep one active worker operation at a time in the controller architecture.
- Add CFP Amplitude Map as its own explicit task/job, not as a parallel job competing with CFP 6-plot output generation.

## Evidence

- Benchmarks: No new benchmark run in this final discussion segment.
- Logs checked: Prior session log/category and CFP progress behavior discussions were referenced.
- Transcript / sources reviewed: `worker_operation_controller.py`, `worker_threads.py`, `worker_result_appliers.py`, `binning_worker_mixin.py`.
- Commands/tests run: Workspace file inspection only for architecture mapping.

## Files Touched

- markdown/chat_2026_05_27_cfp_workflow_decisions.md

## Risks / Caveats

- Long runtime remains the dominant UX risk for amplitude map generation.
- Per-row partial UI update copies can dominate runtime if not throttled.
- Any future optimization must preserve numerical acceptance against a stable reference path.

## Next Steps

1. Add a dedicated controller job builder/start path for CFP Amplitude Map while keeping the single-active-operation model.
2. Add long-run UX guardrails: explicit start message, clear phase/progress text, and cancellation behavior identical to other jobs.
3. Consider checkpoint/resume sidecar support for amplitude map to reduce rerun cost after interruptions.
4. Add deterministic numeric regression checks (fast path vs reference path) to lock correctness while future speed work continues.

## Notes

- User confirmed the non-concurrent model is intentional because amplitude map can take a very long time.
- Recommendation was adapted accordingly: separate task identity without parallel execution.
