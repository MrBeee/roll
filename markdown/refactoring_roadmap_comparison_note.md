# Refactoring Roadmap Comparison Note

Date: 2026-05-16

## Purpose

This note compares the analysis documents in the `markdown` folder against `Refactoring_roadmap.txt` and classifies which notes are still current, which are partially superseded, and which should be treated as historical or generic background.

The roadmap remains the primary source of truth because it is the most current document and explicitly tracks which refactoring items have landed versus which seams remain active.

## Overall Assessment

The current codebase is past the early service-extraction phase. The roadmap describes a codebase where the main persistence, import/QC, runtime state, worker lifecycle, plot-navigation, redraw-policy, property-panel, and print/export seams already have named owners outside `roll_main_window.py`.

The best-aligned notes in `markdown/` agree with that state and mostly differ only in emphasis:

1. `claude_analysis.md` is the closest broad comparison document to the roadmap.
2. `CODEBASE_SUMMARY.md` is a concise, current summary that mostly agrees with the roadmap.
3. `Layout_3D_refactor_proposal.md` is the most useful next-step document because it sharpens the roadmap's recommended next seam.

The weaker notes are weaker for different reasons:

1. `gpt55_analysis.md` contains useful architectural commentary, but several of its cleanup concerns have already been resolved in later work.
2. `Gemma4_Analysis.md` is too generic and recommends a larger package reshaping that does not match the incremental strategy now reflected in the roadmap.
3. The recovered chat notes are useful context, but they are topical discussions rather than current structural guidance.

## Comparison By Document

### `Refactoring_roadmap.txt`

Status: authoritative current source.

Why:

1. It reflects the live codebase after the more recent controller, settings/runtime, property-panel, worker-boundary, layout-helper, and `3D Subset` work.
2. It already records that earlier cleanup concerns such as MRU ownership, project-load layout-helper reuse, and worker scaffolding archival have landed.
3. It gives a clear current priority order: prefer the layout-analysis seam next, especially the growing `3D Subset` bridge, then treat `my_parameters.py` and `marine_wizard.py` as follow-up hotspots.

Key active recommendations from the roadmap:

1. Keep performance work behind structural cleanup.
2. Prefer the layout-analysis seam over a broad new `roll_survey.py` refactor.
3. Add direct tests around the `3D Subset` helper seam if that feature keeps evolving.

### `claude_analysis.md`

Status: current and strongly aligned.

Agreement with the roadmap:

1. It recognizes that persistence, session/runtime state, filter extraction, import/QC, plot/redraw refactors, and most parameter-helper work have already landed.
2. It explicitly marks several previously open cleanup concerns as resolved, including the `SessionService` MRU duplication, `ProjectLoadApplier` layout-helper reuse, `SurveyTypeOld` removal, and `Find` archival.
3. It identifies the same meaningful remaining risks: `RollSurvey` model-render coupling, `roll_main_window.py` as a broad orchestration hotspot, higher-level behavioral coupling in `my_parameters.py`, weak direct coverage for wizard flows, and missing direct record-level coverage for `sps_io_and_qc.py`.
4. It also aligns with the roadmap that the layout/3D seam is a practical next target and that `binFromGeometry9()` remains an explicit experimental/open track question rather than an already-adopted default.

Where it differs:

1. It is slightly more conservative about `marine_wizard.py`; the roadmap now treats it as a peer hotspot with `my_parameters.py`, while Claude still describes it more as a large but not actively scoped file.
2. It emphasizes direct SPS parser tests more strongly than the roadmap, although that does not conflict with the roadmap.

Judgment:

Use this as a high-quality narrative companion to the roadmap.

### `CODEBASE_SUMMARY.md`

Status: current summary, high-level only.

Agreement with the roadmap:

1. It correctly describes the project as having reached an advanced refactoring milestone.
2. It identifies the same dominant hotspots: `roll_survey.py`, `roll_main_window.py`, and `my_parameters.py`.
3. It notes the same unresolved architectural tensions: `RollSurvey` still mixes domain and rendering concerns, and `my_parameters.py` still has behavioral complexity after most mechanical duplication was removed.
4. Its testing recommendation for direct SPS parser coverage matches a real gap still acknowledged elsewhere.

Limitations:

1. It is a summary, not a planning document, so it does not capture the roadmap's more precise ordering that places the layout-analysis seam ahead of further parameter-tree work.
2. It does not surface `marine_wizard.py` as prominently as the roadmap now does.
3. It does not spell out which older cleanup concerns are already closed.

Judgment:

Keep this as a concise snapshot, but not as a substitute for the roadmap.

### `Layout_3D_refactor_proposal.md`

Status: current focused next-step proposal.

Agreement with the roadmap:

1. It directly matches the roadmap's current recommendation to refactor the layout-analysis seam next.
2. It correctly treats `roll_main_window_create_layout_tab.py` as a real controller/presentation seam rather than a pure tab-builder.
3. It follows the roadmap's preferred refactoring style: one narrow seam, minimal churn, move code before rewriting code, and add direct tests around the new seam.
4. It explicitly avoids widening into `roll_survey.py`, worker redesign, or general performance work in the first slice, which is fully consistent with the roadmap.

Judgment:

This is the most actionable note in `markdown/` if the next work item is meant to follow the roadmap closely.

### `gpt55_analysis.md`

Status: partially superseded historical review.

What still holds up:

1. Its overall architectural assessment is directionally correct.
2. Its hotspot list remains broadly accurate.
3. Its warnings about `RollSurvey` coupling, strong back-references in controller extractions, and behavioral complexity in `my_parameters.py` are still valid.

What is stale:

1. Several items under `Verified Concerns` were true when written but have since been resolved and recorded as landed in the roadmap.
2. The recommended cleanup tickets around stale MRU ownership in `SessionService`, duplicated layout image/colorbar setup in `ProjectLoadApplier`, and legacy worker scaffolding archival are no longer current roadmap priorities because those cleanups have already landed.
3. Some legacy-artifact concerns are now better handled by the archive structure and later cleanup work than this note implies.

Judgment:

Useful as a historical checkpoint, but it should not drive current priority decisions without checking the roadmap first.

### `Gemma4_Analysis.md`

Status: generic background only.

Why it is weak relative to the roadmap:

1. It recommends a broad package restructure into `src/core`, `src/io`, `src/ui`, and `src/utils`, which does not reflect the current repository layout or the roadmap's incremental strategy.
2. It refers to modules such as `sps_io.py` and `layout_editor.py`, which are not the live seams in this repo.
3. Its model-view separation advice is generic rather than anchored to the actual refactoring surfaces already present in the codebase.

Judgment:

The ideas are not wrong in the abstract, but this note is not specific enough to be used for present refactoring decisions in this repository.

### Recovered chat notes

Files:

1. `chat_2026_03_12.md`
2. `chat_2026_05_01.md`
3. `chat_2026_05_01_binning_speedup_recovered.md`

Status: background discussion and decision history.

Usefulness:

1. They preserve reasoning behind earlier changes and performance discussions.
2. The May 1 binning-speedup discussion is consistent with the roadmap in one important way: it argues against rushing into GPU/CuPy work and favors profiling and structural clarity first.

Limitation:

1. These are not maintained planning documents and should not override the roadmap.

## Classification Summary

### Current and should be treated as active guidance

1. `Refactoring_roadmap.txt`
2. `claude_analysis.md`
3. `CODEBASE_SUMMARY.md`
4. `Layout_3D_refactor_proposal.md`

### Useful but partly historical or superseded

1. `gpt55_analysis.md`
2. recovered chat notes

### Generic or low-value for present planning

1. `Gemma4_Analysis.md`

## Practical Recommendation

If there is a single working hierarchy for planning, it should be:

1. `Refactoring_roadmap.txt` as the source of truth.
2. `Layout_3D_refactor_proposal.md` as the best concrete note for the next refactor slice.
3. `claude_analysis.md` as the best broad narrative review of the current codebase.
4. `CODEBASE_SUMMARY.md` as a short orientation document.
5. `gpt55_analysis.md` and the recovered chat notes as historical context only.
6. `Gemma4_Analysis.md` as generic background rather than repo-specific guidance.

## Suggested Maintenance Step

If you want the folder to stay easy to trust, the next documentation cleanup should be lightweight rather than editorially heavy:

1. Keep this note as the comparison index.
2. Optionally add a one-line status banner to the top of `gpt55_analysis.md` noting that parts of it are superseded.
3. Optionally add a one-line status banner to `Gemma4_Analysis.md` noting that it is generic background, not a current roadmap document.