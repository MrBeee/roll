# Session Notes

## Session

- Date: 2026-06-01
- Topic: CFP performance, Geometry Tables parity, Trace Table retirement, and acquisition-imprint planning
- Goal: Make CFP analysis fast and robust for Templates and Geometry Tables, then define the MVP path for a target-depth acquisition-imprint map
- Model / thread: GitHub Copilot
- Related workspace / project: QGis/MyPlugins/roll

## Key Outcome

CFP single-point analysis is now fast enough from both supported production paths. Geometry Tables remains the best flat-array path and completed the Noordoostpolder test case in about 46 seconds. Templates now use weighted station accumulation and compact duplicate station weights instead of expanding source/receiver trace pairs, reducing runtime from about 7 minutes to about 54 seconds on the same test while preserving the same SNR values. CFP from Trace Table is no longer needed and code solely supporting that mode was removed, while general Trace Table UI/data support was kept.

The recommended next feature is a separate `CFP Illumination from Geometry Tables` job. It should compute a normalized 2D target-depth illumination map over the binning area using Geometry/SPS tables, not the template traversal path.

## Decisions

- Keep two single-point CFP production paths: Templates and Geometry/SPS Tables.
- Retire `CFP Analysis from Trace Table`; it was slower/less complete than Geometry Tables and no longer adds value.
- Preserve general Trace Table loading/display/full-analysis code; only the CFP-from-Trace-Table action path should be removed.
- Preserve the WIP `CfpAmplitudeMapWorker`, but treat it as incomplete. It needs correction before production use.
- Use Geometry/SPS tables as the preferred input for illumination because relation/source/receiver arrays are flat and Numba-friendly.
- Start with a 2D target-depth imprint map across `output.rctOutput`; do not start with a full 3D volume.
- Keep the worker model serialized through the existing `WorkerOperationController`; do not run CFP imprint concurrently with other CFP jobs.

## Evidence

- Template CFP before the final weighted-buffer compaction:
  - Runtime: `0:07:05`
  - Contributing rolled template positions: `459 / 10,248`
  - SNR: Source `47.0 dB`, Receiver `38.2 dB`, AVP `80.3 dB`
- Template CFP after weighted-buffer compaction:
  - Runtime: `0:00:54`
  - Contributing rolled template positions: `459 / 10,248`
  - SNR: Source `47.0 dB`, Receiver `38.2 dB`, AVP `80.3 dB`
- Geometry Tables CFP on the same target:
  - Runtime: `0:00:46`
  - Contributing relation records: `59,886 / 1,795,499`
  - Contributing receiver traces: `12,989,527 / 29,694,648` resolved traces
  - Inactive source records ignored: `14,499`
  - Inactive receiver records ignored: `44,496`
  - Relation records ignored because source is inactive: `465,472`
  - SNR: Source `47.0 dB`, Receiver `38.2 dB`, AVP `80.3 dB`
- Validation performed during the session:
  - QGIS Python `py_compile` passed for touched CFP modules after key changes.
  - Small weighted-equivalence checks confirmed weighted template accumulation matches the old expanded trace-pair multiplicity.
  - Small weighted-compaction checks confirmed duplicate station weights are summed correctly.
  - Geometry Tables Numba scanner first-call compile test passed after restoring `_find_line_key`.

## Work Completed Today

- Optimized CFP from Templates:
  - `RollSurvey.scanCfpTemplates()` now supports a weighted contribution callback.
  - Each contributing template contributes source weights of `nRec` and receiver weights of `nSrc` instead of materializing all trace pairs with `np.repeat` and `np.tile`.
  - `CfpBeamAccumulator` can buffer weighted point arrays.
  - Weighted template buffers compact duplicate station weights at the threshold and defer expensive beam synthesis until `finalizeImages()`.
- Improved CFP from Geometry Tables:
  - Geometry Tables path already uses chunked Numba relation scanning and weighted final beam synthesis.
  - Current benchmark is around `0:00:46` for the Noordoostpolder test target.
- Removed CFP from Trace Table support:
  - Removed code solely required to start, run, apply, and finish CFP analysis from Trace Table.
  - Kept shared CFP accumulator code and general Trace Table analysis/display functionality.
  - User planned to remove the action from the UI file.
- Fixed an accidental Geometry Tables regression:
  - `_find_line_key` in `cfp_aux_functions_numba.py` is required by the Geometry Tables Numba scanner and must remain.
  - The Geometry Tables scanner was validated after restoring it.
- Audited the existing acquisition-imprint skeleton:
  - `CfpAmplitudeMapWorker`, `CfpAmplitudeMapRequest`, `CfpAmplitudeMapResult`, and `CfpAmplitudeMapResultApplier` exist.
  - `output.cfpOutput` and image type `6` labelled `CFP illumination` already exist.
  - The worker is not yet wired as a runnable operation in `WorkerOperationController`/`BinningWorkerMixin`.
  - The current WIP algorithm does not yet reuse the validated Geometry Tables relation scanning semantics.

## Files Touched Or Reviewed

- `worker_threads.py`
- `roll_survey.py`
- `cfp_aux_functions_numba.py`
- `worker_result_appliers.py`
- `worker_operation_controller.py`
- `binning_worker_mixin.py`
- `action_state_controller.py`
- `roll_main_window.py`
- `roll_output.py`
- `3d_cfp_analysis.py`

## Risks / Caveats

- The template path is now close to Geometry Tables runtime, but Geometry Tables remains structurally better for full-area imprint because it starts from flat arrays.
- The existing `CfpAmplitudeMapWorker` is WIP and should not be considered production-correct yet.
- The current WIP amplitude-map relation gather uses trace proxies/range weights and does not fully match the validated Geometry Tables CFP relation handling.
- Full-resolution imprint maps can become expensive because the focal point changes for every map cell.
- Partial-result UI updates should remain throttled; copying and redrawing every row may dominate runtime.
- Any new Numba kernels for CFP should live in `cfp_aux_functions_numba.py`.
- If QGIS keeps a stale imported module after edits, reload the plugin/process before rerunning Numba workers.

## MVP: CFP Illumination From Geometry Tables

### MVP Goal

Create a separate worker action that computes a normalized 2D target-depth acquisition-imprint map over the binning area. Each output cell represents the local CFP illumination/resolution strength for a focal point at `(x, y, focalZ)` using the active geometry/SPS source-receiver relation data.

### Recommended Metric

Use a simple first production metric:

`normalized combined CFP focus strength = abs(source focus response * receiver focus response)`

Optionally stack over a small frequency list, but the first MVP can use one frequency, probably `40 Hz`, to match current single-point CFP defaults.

### Preferred Input Path

Use Geometry/SPS tables:

- Prefer `srcGeom`, `relGeom`, `recGeom`.
- Fallback to imported `spsImport`, `xpsImport`, `rpsImport` if geometry tables are unavailable.
- Respect `InUse` for source and receiver records.
- Respect relation orphan flags such as `InSps` and `InRps`.
- Preserve the source-active/inactive diagnostics used by single-point Geometry Tables CFP.

Do not use Templates as the first production input for the full-area imprint map. Template traversal is acceptable for single-point CFP now, but it is the wrong shape for a full grid of focal points.

### Algorithm Shape

1. Build scan arrays once from source/receiver/relation tables, following the validated Geometry Tables CFP path.
2. Allocate `ampMap` over `output.rctOutput` using `survey.grid.binSize`.
3. Run a Python outer loop over rows or tiles to keep progress and cancellation responsive.
4. For each row/tile, call a Numba kernel in `cfp_aux_functions_numba.py`.
5. For each focal cell `(x, y, focalZ)` inside the kernel:
   - find active source relation records;
   - apply source aperture;
   - expand receiver ranges from the relation record;
   - apply receiver aperture;
   - accumulate source and receiver complex focus responses;
   - write `abs(sourceResponse * receiverResponse)` or equivalent energy to the map.
6. Normalize final `ampMap` to `0..1` for display.
7. Emit partial results every N rows/tiles, not every row unless runtime testing shows it is cheap.

### Worker/UI Wiring

Add or complete the following:

1. `CfpAmplitudeMapRequest`
   - Add source name, frequency/frequency-list, grid decimation or preview factor if desired.
2. `CfpAmplitudeMapWorker`
   - Replace WIP trace-proxy gather with validated Geometry Tables scan-array setup.
   - Use row/tile Numba kernel for the imprint map.
   - Keep cancellation checks in the Python outer loop.
3. `WorkerOperationController`
   - Add `startCfpIlluminationFromGeometryTables()`.
   - Add `_buildCfpIlluminationFromGeometryTablesJob()`.
   - Reuse `_resolveCfpGeometryTables()`, `_hasCfpGeometryTables()`, `_resolveCfpMaxDipDegrees()`.
4. `BinningWorkerMixin`
   - Add `cfpIlluminationFromGeometryTables()`.
   - Add result apply/finish methods using `CfpAmplitudeMapResultApplier`.
5. `ActionStateController`
   - Enable/show the new action when experimental mode is enabled and Geometry/SPS inputs exist.
6. Main window/UI
   - Add a processing action named something like `actionCFPIlluminationFromGeometryTables`.
   - Connect it to `cfpIlluminationFromGeometryTables()`.
7. Result applier/display
   - Reuse `output.cfpOutput` and image type `6`.
  - Label as `CFP illumination` consistently.
   - Keep color levels local to the map, preferably normalized `0..1`.

### Validation Plan

1. Smoke test with a tiny synthetic geometry and confirm nonblank `cfpOutput`.
2. Compare a map cell at the current single-point target against the single-point CFP trend.
3. Confirm removing source or receiver lines creates visible imprint stripes/holes.
4. Confirm `InUse = 0` source/receiver records disappear from the map response.
5. Confirm imported SPS fallback produces comparable behavior to generated Geometry Tables.
6. Confirm cancellation and partial display updates work for large grids.
7. Benchmark at full grid and at decimated preview resolution.

## Next Steps

1. Decide action naming and UI placement for `CFP Illumination from Geometry Tables`.
2. Replace the WIP `CfpAmplitudeMapWorker` gather logic with validated Geometry Tables scan arrays.
3. Add a row/tile Numba kernel for map computation in `cfp_aux_functions_numba.py`.
4. Wire the worker through `WorkerOperationController` and `BinningWorkerMixin`.
5. Display results through existing `cfpOutput` / image type `6`.
6. Validate with the same Noordoostpolder target area and with deliberately thinned geometry.

## Recovery Pointers

- Important current CFP modules: `worker_threads.py`, `cfp_aux_functions_numba.py`, `roll_survey.py`, `worker_operation_controller.py`, `binning_worker_mixin.py`, `worker_result_appliers.py`.
- Existing output/display slot for imprint maps: `RollOutput.cfpOutput` and image type `6` in `roll_main_window.py`.
- Existing WIP worker to replace/refine: `CfpAmplitudeMapWorker` in `worker_threads.py`.
- Existing conceptual prototype: `3d_cfp_analysis.py`, useful for ideas but not recommended as the first production implementation.

## End-of-Session Checklist

- Commit or otherwise preserve this handoff note with the CFP code changes.
- Reload the QGIS plugin after Numba helper changes to avoid stale imported modules.
- If another CFP cleanup session starts, first search for remaining Trace Table CFP references and verify Geometry Tables scanner first-call compilation.