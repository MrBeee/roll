# Layout / 3D Refactoring Proposal

Date: 2026-05-13

## Purpose

Capture a practical next-step refactoring proposal that follows the current roadmap without opening a broad or risky rewrite.

The recommendation is to refactor the layout-analysis seam next, centered on `roll_main_window_create_layout_tab.py` and `layout_3D.py`.

## Why This Seam Next

The current codebase is already past the obvious service/controller extraction stage. The remaining structural issue is not basic tab construction anymore; it is the concentration of layout-specific presentation logic around the 2D/3D bridge.

This seam is now the best next target because:

1. `roll_main_window_create_layout_tab.py` is no longer only a tab builder. It now owns real presentation/controller logic.
2. The recent `3D Subset` work showed that visibility, depth, local/global mapping, and style mirroring bugs tend to cluster in this bridge layer.
3. This surface can be improved without opening a high-risk refactor in `roll_survey.py`.
4. It is testable with narrow helper-level regressions.

## Current Problem Statement

Today, `roll_main_window_create_layout_tab.py` mixes several different responsibilities:

1. Qt widget construction for the Layout tab.
2. Layout-tab action wiring.
3. Building 3D payloads from 2D/session/survey state.
4. Translating 2D visibility and style choices into 3D equivalents.
5. Refresh orchestration for the `3D Subset` widget.

At the same time, `layout_3D.py` owns the actual matplotlib rendering and helper math.

That leaves the boundary blurry:

1. The builder module is too behavior-heavy.
2. The renderer module must implicitly know too much about how payloads were assembled.
3. Tests mostly protect this via higher-level layout paths instead of a direct seam.

## Proposal Summary

Create one new focused module for the Layout tab's 2D-to-3D presentation bridge.

Recommended name:

`layout_3d_bridge.py`

Keep it simple and function-oriented first. Do not introduce a large new class hierarchy unless the seam later proves that one is necessary.

## Target Ownership After Refactor

### `roll_main_window_create_layout_tab.py`

Keep this module focused on:

1. Building the Layout tab widgets.
2. Creating and wiring actions/buttons.
3. Delegating 3D refresh requests to the bridge module.

It should stop owning detailed payload construction for the 3D scene.

### `layout_3d_bridge.py`

This new module should own:

1. Building the `Layout3DWidget.updateFromSurvey()` payload from window state.
2. Translating 2D layer visibility into 3D layer visibility.
3. Translating 2D marker/pen/color choices into 3D-friendly style payloads.
4. Collecting point-layer arrays and z values for the 3D subset.
5. Packaging bin area, block areas, reflector style, and spider overlay payloads.
6. The main `refreshLayout3DFromSurvey(window)` bridge entry point.

This is the main new ownership slice.

### `layout_3D.py`

Keep this module focused on:

1. Rendering.
2. View state.
3. Coordinate helper math used by the renderer.
4. Applying an already-built scene payload.

Avoid moving more UI-state translation logic into this file.

## Proposed First-Cut API

Start with a small, explicit, function-based boundary:

```python
def refreshLayout3DFromSurvey(window):
    ...

def buildLayout3DUpdatePayload(window):
    ...

def buildVisiblePointSets(window):
    ...

def buildBinAreaConfig(window):
    ...

def buildBlockAreasConfig(window):
    ...

def buildReflectorStyleConfig(window):
    ...
```

The payload can remain a plain dict in the first slice.

If the payload shape later stabilizes and grows further, introduce a small dataclass then, not before.

## Why A Function-Based Bridge First

This keeps the first step small and reversible:

1. It preserves the existing `Layout3DWidget.updateFromSurvey()` contract.
2. It avoids creating a new stateful controller object before there is evidence that one is needed.
3. It matches the current code style better than introducing a larger presentation abstraction immediately.
4. It should be easy to land with minimal churn.

## Suggested Extraction Order

### Slice 1: Move Pure Payload Builders

Move the current helper-style functions out of `roll_main_window_create_layout_tab.py` into `layout_3d_bridge.py`.

Initial candidates:

1. `_buildBinAreaConfig()`
2. `_buildBlockAreasConfig()`
3. `_buildReflectorStyleConfig()`
4. `_buildVisiblePointSets()`

Goal: no behavior change, only ownership change.

### Slice 2: Move Refresh Orchestration

Move `refreshLayout3DFromSurvey()` into the bridge module and make the Layout tab builder call through that module.

Goal: one canonical place owns the 2D-to-3D update assembly.

### Slice 3: Add Direct Bridge Tests

Add narrow tests around the new bridge seam so changes no longer depend mainly on manual 3D verification.

Best initial cases:

1. visible point-layer mirroring
2. source/receiver depth forwarding
3. template visibility gating
4. local/global mapping inputs
5. block/bin area style packaging

### Slice 4: Decide Whether More Layout Presentation Logic Belongs There

Only after the bridge is stable, decide whether adjacent layout responsibilities should also move, such as:

1. image-selection payload packaging
2. layout-specific status-text derivation
3. export-routing helpers tied specifically to layout presentation state

This should be a follow-up decision, not part of the first slice.

## Explicit Non-Goals For The First Slice

Do not mix the following into the initial refactor:

1. `roll_survey.py` algorithm changes
2. worker payload redesign
3. `roll_main_window.py` broad plot refactor
4. new performance work
5. larger API changes inside `Layout3DWidget.updateFromSurvey()`

The first cut should be structural only.

## Test Strategy

The roadmap already points to a missing direct seam around the `3D Subset` helpers. This proposal should close that gap.

Recommended tests:

1. Keep one higher-level integration test proving the bridge still forwards payloads into `Layout3DWidget.updateFromSurvey()`.
2. Add direct helper-level tests for `layout_3d_bridge.py` payload assembly.
3. Keep the current `layout_3D.py` helper tests for bbox, transform, spider-depth, and point-z behavior.

The important shift is this: future 3D behavior changes should mostly be testable without going through the full Layout tab wiring path.

## Expected Benefits

If this refactor lands cleanly, it should produce:

1. A smaller and clearer `roll_main_window_create_layout_tab.py`.
2. A direct, testable ownership seam for 3D payload assembly.
3. Fewer regressions in visibility/style/depth/local-global translation logic.
4. A clearer distinction between presentation-bridge code and renderer code.
5. A safer starting point for any later cleanup in the broader Layout tab.

## Risks And Guardrails

Main risk:

The bridge touches user-visible behavior in a feature that is easy to verify manually but still only lightly protected by tests.

Guardrails:

1. Preserve the existing payload shape in the first slice.
2. Move code before rewriting code.
3. Add tests as soon as the seam exists.
4. Validate with focused 3D tests after each slice.
5. Stop before pulling in unrelated Layout-tab cleanup.

## Proposed Tomorrow Starting Point

Tomorrow's implementation can start with this exact small scope:

1. Add `layout_3d_bridge.py`.
2. Move the current 3D payload-builder helpers there unchanged.
3. Move `refreshLayout3DFromSurvey()` there and keep the current call sites.
4. Add direct tests for the new bridge module.
5. Stop after behavior is unchanged and tests pass.

That is the smallest useful slice that follows the roadmap and improves the structure without widening risk.

## Follow-Up Priority After This

After the layout/3D seam is in better shape, the next follow-up hotspots should remain:

1. `my_parameters.py`
2. `marine_wizard.py`

Do not take on `roll_survey.py` next unless there is a specific correctness issue or a deliberate longer algorithm refactor planned.