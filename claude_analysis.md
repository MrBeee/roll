# Claude Analysis — Roll QGIS Plugin Codebase Review

**Analyst:** Claude Sonnet 4.6  
**Date:** 2026-04-27 (revised 2026-05-19, revised 2026-04-27 again, fourth revision 2026-04-27, fifth revision 2026-04-28)  
**Context:** This project is being refactored by GPT5.4. The observations below are based on a review of the full codebase (~102 Python files) together with `Refactoring_roadmap.txt` (now 108 completed items). The fifth revision reflects four further landings since the last review: (104) `SessionService` MRU duplicates already removed, (105) `ProjectLoadApplier` now reuses `prepareLayoutImageAndColorBar()` for the layout-image restore path, (106) the legacy `BinningThread(QThread)` and `Worker(QObject)` scaffolding moved out of `worker_threads.py` into `__archive__/worker_threads_old_methods.py`, (107) `RuntimeState` now persists `wellDirectory` as part of the runtime document context, and (108) `PropertyPanelController` now owns the Well-file directory propagation seam previously inlined in `RollMainWindow.propertyTreeStateChanged()`.

---

## 1. Overall Architecture

The plugin is a QGIS-integrated seismic survey design tool. Its purpose is to model land and marine acquisition geometries, import SPS/RPS/XPS field-data files, run fold/offset/azimuth binning analyses, and display results in a PyQtGraph-based viewer inside a QGIS dock.

The main structural layers are:

| Layer | Key classes / modules |
|---|---|
| **Entry point** | `roll.py` → `RollMainWindow` |
| **Main window** | `roll_main_window.py` (3 574 lines); multiple-inheritance with `SpiderNavigationMixin`, `SurveyPaintMixin`, `BinningWorkerMixin` |
| **Domain model** | `RollSurvey`, `RollBlock`, `RollTemplate`, `RollSeed`, `RollPattern`, `RollPatternSeed`, `RollGrid`, `RollWell`, etc. |
| **Output model** | `RollOutput` (holds numpy arrays: `binOutput`, `minOffset`, `maxOffset`, `rmsOffset`, `anaOutput`, …) |
| **Session / state** | `SessionState`, `SessionService`, `RuntimeState`, `AppSettings` |
| **Services** | `ProjectService`, `ProjectLoadApplier`, `ImportService`, `FilterService`, `DocumentContextService` |
| **Controllers** | `StackResponseController`, `PlotNavigationController`, `PlotViewStateController`, `ActionStateController`, `PrintPresentationController`, `PropertyPanelController`, `WorkerOperationController`, `BinningResultApplier`, `GeometryResultApplier` |
| **Workers** | `BinningWorker`, `BinFromGeometryWorker`, `GeometryWorker` in `worker_threads.py`; lifecycle via `BinningWorkerMixin` and `WorkerOperationController` |
| **Parameter tree** | `my_parameters.py` (2 832 lines) — PyQtGraph `ParameterTree` classes for the property panel |
| **Tab builders** | `roll_main_window_create_geom_tab.py`, `_layout_tab.py`, `_pattern_tab.py`, `_sps_tab.py`, `_trace_table_tab.py`, `_stack_response_tab.py`, `_offset_tabs.py`, `_off_azi_tab.py` |
| **Helpers** | `parameter_aggregate_helpers.py`, `parameter_list_helpers.py`, `parameter_seed_well_helpers.py`, `parameter_creation_helpers.py`, `plot_redraw_helper.py`, `aux_functions.py` |
| **Shared config** | `config.py` (read-only constants; no longer mutated by settings) |
| **Numerics** | `functions_numba.py` (Numba-accelerated; with `nonumba.py` fallback path implied) |
| **Wizards** | `LandSurveyWizard`, `MarineSurveyWizard` — defaults now live in their own classes |
| **QGIS integration** | `qgis_interface.py` (1 871 lines), `qgis_layer_dialog.py` |

---

## 2. State of the Refactoring

### 2.1 Completed work (per roadmap)

The roadmap documents 103 numbered completed items. The following groupings summarise the live state:

#### Project / Persistence (Phase 1 — complete)
- `ProjectService` is the sole owner of XML read/write, sidecar naming, existence checks, validation, legacy normalization, and memmap opening.
- `ProjectLoadApplier` owns the loaded-sidecar apply path; `fileLoad()` in `RollMainWindow` is now a thin orchestrating shell.
- All sidecar writes go through `ProjectService`; no raw `np.save` calls remain in the worker completion path.

#### Session and Runtime State (Phase 3 — substantially complete)
- `SessionState` is a plain dataclass owning all imported and geometry arrays plus derived live/dead/convex-hull state.
- `SessionService.setArray()` and `refreshArrayState()` are the canonical paths for updating session arrays.
- `RuntimeState` is a plain dataclass owning `fileName`, `projectDirectory`, `importDirectory`, `wellDirectory`, and `recentFileList`.
- `DocumentContextService` owns document-path commit, MRU management, and file-resolution.
- `AppSettings` owns all persisted settings; the old mutable `config.py` write-back bridge has been removed.
- Land and marine wizard defaults live in `LandSurveyWizard` and `MarineSurveyWizard`.

#### Filter Service (Phase 2 — complete)
- `FilterService` is descriptor-driven; all 14 filter keys (point/relation duplicates and orphans) are centralized.
- `RollMainWindow` retains only thin dispatch wrappers.

#### Import Service (Phase 4 — substantially complete)
- `ImportService` owns SPS/RPS/XPS text parsing, QC passes, duplicate/orphan checks, CRS conversion, progress callbacks, and cancellation.
- `fileImportSpsData()` in the main window now acts as a controller for file selection and final session-commit.

#### Plot / Redraw (Phase 5 — substantially complete)
- `PlotRedrawHelper` owns invalidation policy, cache-key state, and reused-axis reconstruction for pattern, inline, xline, and stack-cell surfaces.
- `StackResponseController`, `PlotNavigationController`, `PlotViewStateController`, `ActionStateController`, `PrintPresentationController`, and `PropertyPanelController` each own a previously-inlined controller cluster; `RollMainWindow` keeps only thin delegating wrappers.
- `AnalysisRedrawReason` enum drives real invalidation behavior (not just metadata).
- O/A has explicit rectangular vs. polar render paths; offset has a dedicated preparation/render/dispatch structure matching O/A.
- Pattern-response and stack-response reuse cached results when selection or navigation context is unchanged.
- Plot mouse tracking is wired centrally from `createPlotWidget()`.

#### Worker Contracts (Phase 6 — substantially in progress)
- `WorkerOperationController` owns job specifications, launch/cancel/shutdown rules.
- `BinningResultApplier` and `GeometryResultApplier` own the success/failure apply paths.
- Workers emit typed `resultReady` payloads plus a no-argument `finished()` signal.
- Large arrays are not copied a second time across the worker boundary; geometry profiling travels as one explicit optional sub-payload.

#### Parameter Tree (`my_parameters.py` — substantially refactored)
- A large number of repeated `changed()` method bodies have been extracted into narrow local helpers: `applyBinAnglesParameters`, `applySphereParameters`, `applyPlaneParameters`, `applyLocalGridParameters`, `applyGlobalGridParameters`, `applyBinOffsetParameters`, `applyUniqueOffsetParameters`, `applyBinMethodParameters`, `applyPatternSeedParameterValues`, `applyConfigurationParameterValues`, `applyAnalysisParameters`, `applyBlockParameters`, `applyTemplateParameters`, `applyRollListParameters`, `applyRollParameterIncrement`, `applyRollParameterStepCount`, `applyWellHeaderParameterChange`, `applyWellSamplingFromParameters`, `applyCircleParameters`, `applySpiralParameters`, etc.
- Shared constructor child-binding patterns use `bindChildParameters`, `connectValueChangedSignals`, and `connectTreeStateChangedSignals`.
- Shared preview helpers: `formatPreviewPointSummary`, `previewGridStepPointCount`, `previewSeedShotCount`, `previewTemplateSourceSummary`, `previewBlockSourceSummary`, `previewSeedListCompositionSummary`, `previewWellSummary`, and `formatPreviewCountLabel`.
- Seed/pattern coordination: `SeedParameterStateHelper`, `SeedPatternRefreshState`, `findParameterTreeRoot`, `iterTemplateSeedParameters`, `applySeedTypeChange`, `applyGridSeedPatternRefresh`, `resolveGridSeedPatternRefreshState`, `applyNonGridSeedTypeState`.
- Pattern list side effects: `applyPatternListSideEffects`, `applyPatternRemovalSideEffects`, `applyPatternMoveSideEffects`.
- The shared `addSeedColorOriginGridChildren` / `bindSeedColorOriginGridChildren` / `connectSeedColorOriginGridChangedSignals` cluster eliminates duplication between `MySeedParameter` and `MyPatternSeedParameter`.
- The shared `addPreviewAngleIntervalPointChildren` / `bindPreviewAngleIntervalPointChildren` cluster eliminates duplication between `MyCircleParameter` and `MySpiralParameter`.
- Preview-item setup is owned by `MyGroupParameterItem.initializePreviewItem()` and `updatePreviewLabelText()` shared from `my_group.py`; this pattern has been applied to `my_crs2.py`, `my_point2D.py`, `my_point3D.py`, `my_rectf.py`, `my_range.py`, `my_vector.py`, and `my_n_vector.py`.
- `parameter_aggregate_helpers.py` owns the value-snapshot / write-back dataclasses for `AnalysisParameterValues`, `ConfigurationParameterValues`, `ReflectorParameterValues`, `BlockParameterValues`, and `TemplateParameterValues`.
- `parameter_list_helpers.py` owns `removeManagedParameterItem`, `moveManagedParameterItem`, `nextManagedChildName`, `appendManagedParameterItem`, and `swapManagedParameterItems` (the last for name-preserving roll-list reordering).
- `parameter_creation_helpers.py` owns survey-bound default block, template, and appended-seed construction.

---

### 2.2 What still remains

The roadmap is explicit that the following are not yet complete:

1. **Worker cleanup tail. ✓ resolved.** `worker_threads.py` now contains only the live typed workers (`BinFromGeometryWorker`, `BinningWorker`, `GeometryWorker`) and their request/result dataclasses. `BinningThread(QThread)` and `Worker(QObject)` have been moved to `__archive__/worker_threads_old_methods.py`. The compatibility wrapper `binningResultThreadFinished()` is also gone (per roadmap item 106).

2. **`binFromGeometry9()` dispatch.** This new experimental Numba-parallel-batch method (line 1321 in `roll_survey.py`) exists and is correct, but is not yet wired into `setupBinFromGeometry()` (still routes through `binFromGeometry8`/`binFromGeometryNoRel`). It should either be hooked in or clearly marked as experimental pending benchmarking. **This is the only Phase 6 follow-up still open.**

3. **`my_parameters.py` higher-level coupling.** The 103-item extract-helper track plus the `swapManagedParameterItems` follow-up landed in this session is at a natural stopping point for low-level duplication. What remains is higher-level coupling between larger parameter-schema clusters, complex UI mutation, and domain-specific side effects spread across many parameter classes. The roadmap's guidance is: attempt another extraction only if a comparably small, testable seam is identified from live code; otherwise switch to selective worker cleanup.

4. **`config.py` further splitting.** Currently a read-only constants module. The roadmap considers further splitting by concern optional, not a structural blocker.

5. **Performance work.** Explicitly deferred until structure stabilizes. Candidates: repeated `np.unique` during geometry generation, large array copies on worker completion, broad redraw invalidation after small changes, XML as internal worker transport. `binFromGeometry9()`'s Numba parallel kernel is the most concrete forward-facing candidate.

6. **Small document-tab flow.** The `onMainTabChange()` / `find()` tab-focus tail is not considered a worthwhile extraction target on its own.

---

## 3. Module-by-Module Observations

### `roll_main_window.py` (3 574 lines)
The largest file in the project and still the main concentration of complexity, but it is materially shorter than it would have been without the extraction work. The current content is:
- Property definitions (proxy setters/getters delegating to `SessionState` and `RuntimeState`) — these are idiomatic but voluminous; 35+ properties each with a getter/setter pair account for roughly 200 lines.
- `__init__` wiring: instantiates all services, controllers, and tab builders; connects signals.
- `fileLoad()` / `fileSave()` / `fileNew()` — orchestration shells delegating into `ProjectService`, `ProjectLoadApplier`, `DocumentContextService`.
- `fileImportSpsData()` — thin controller: file-pick, progress, commit.
- Plot methods: `plotLayout()`, `plotPatterns()`, `plotStkTrk()`, `plotStkBin()`, `plotStkCel()`, `plotOffset()`, `plotOffAzi()`, and `dispatchAnalysisRedraw()` — these are the remaining concentration of plotting computation and widget mutation that Phase 5 left in the main window after controller extractions. This is still the largest structural concern.
- Action/menu wiring: delegated to `ActionStateController` but `RollMainWindow` still keeps thin wrappers that must stay in sync with the controller.

**Observation:** The proxy-property block (lines ~300–600) is mechanical but necessary to preserve backward compatibility across the codebase. It is unlikely to be meaningfully shortened without either eliminating the properties entirely (risky) or consolidating the delegation boilerplate into a metaclass or descriptor, which would be over-engineering.

### `roll_survey.py` (3 713 lines)
The core domain model. Notable characteristics:
- Subclasses `pg.GraphicsObject`; owns the `paint()` / framebuffer fields for progressive LOD rendering — this tight coupling of domain model and rendering is architectural debt acknowledged by the roadmap but not yet addressed.
- `geomTemplate4()`, `binFromGeometryNoRel()`, `binFromGeometry8()`, `binTemplate7()` are the live geometry/binning paths with extracted helper boundaries.
- `binFromGeometry9()` is a **new experimental method** (line 1321) using a Numba parallel batch kernel (`fnb.numbaBinBatchParallel`). It is defined but **not yet wired into `setupBinFromGeometry()` dispatch**, making it a forward-candidate rather than a dead reference. Once validated, it is intended to replace `binFromGeometry8()`.
- `calcOffsetGapValues()` is a **new live analysis method** (line 1706) called from `finalizeLiveBinningOutputs()`, `binFromGeometry8()`, and `binFromGeometry9()`. It computes per-bin minimum offset gap statistics and stores them in `BinningFromGeometryResult`/`BinningFromTemplatesResult`.
- `geomTemplate2/3()`, `binFromGeometry4/5/6/7()`, `binTemplate6()` are **intentionally retained as dead reference implementations** in `__archive__/roll_survey_old_methods.py`; they should not be removed during routine cleanup.
- The active `geomTemplate4()` path uses small helpers for source append, receiver de-dup, `relTemp` construction, and relation expansion.
- `binFromGeometry8()` uses extracted helpers for valid-CMP bin updates, CMP/offArray filtering with radial pruning, and the relation-driven lookup/receiver-selection path.
- `geometryFromTemplates()` uses a small helper to own template-roll dispatch.
- `RollGrid.iterPoints()` is the canonical owner of the fixed three-grow-step traversal used by both pattern painting and pattern-response extraction.
- `RollPattern.readXml()` normalizes legacy implicit-seed grow lists to exactly three entries.
- The coupling of `pg.GraphicsObject` into the domain model means the model cannot be tested without a running PyQtGraph/Qt application. This limits the achievable test coverage for geometry correctness.

### `my_parameters.py` (2 832 lines)
Despite extensive helper extraction, this remains the second-largest single file. Structural observations:
- The file is now approximately 40% module-level helper functions and 60% class definitions.
- The class definitions follow a consistent pattern: `*ParameterItem` (handles rendering/preview) + `*Parameter` (handles domain binding). This is idiomatic for PyQtGraph `ParameterTree` and cannot be easily collapsed.
- The remaining duplication is at the behavior-level (complex signal wiring and mutual-visibility logic between grid/non-grid/well seed types) rather than the mechanical level addressed by the helper extraction. This is correctly identified in the roadmap as the harder remaining problem.
- `MySeedParameter` (the most complex class) orchestrates seed-type routing, pattern synchronization, visibility state, and context-menu operations. The `typeChanged()` → `applySeedTypeChange()` → `applyGridSeedPatternRefresh()` / `applyNonGridSeedTypeState()` chain is now helper-backed but still behaviorally complex.
- **Risk:** `QApplication.processEvents()` is called frequently inside `__init__` methods and `changed()` handlers. This is a known pattern for keeping a PyQtGraph parameter tree responsive during construction, but it introduces re-entrancy risk if signals fire during construction. The existing tests do not cover this scenario.

### `marine_wizard.py` (2 768 lines) and `land_wizard.py` (2 577 lines)
These are the largest files after the top three. They are dense with survey-default presets and UI wiring for wizard flows. No structural concerns are raised in the roadmap about these files, and they appear to be working code that was recently cleaned up (wizard defaults moved here from `config.py`).

### `qgis_interface.py` (1 871 lines)
QGIS integration helpers: raster layer creation, point layer export, SPS outline export, coordinate conversion. This file is large but the functions within it are mostly independent. No refactoring work is currently scoped for it.

### `functions_numba.py` (632 lines)
Numba-accelerated numerical kernels. The roadmap defers all performance work to after structure stabilizes. The file is well-isolated.

### `config.py` (267 lines)
Now a read-only constants module. The `surveyNumber` mutable field remains at the top but the roadmap notes it can optionally be moved to `SessionState` or `RuntimeState` if a clearer naming/session seam appears. No urgent action required.

### `runtime_state.py`
`RuntimeState` is a small dataclass owning `fileName`, `projectDirectory`, `importDirectory`, `wellDirectory` (newly added), and `recentFileList`. The `wellDirectory` field is now part of the persisted runtime document context, loaded/saved through `settings.py`, and propagated to property-tree items explicitly. Changing a `Well file` field updates the shared directory for the active parameter tree via `PropertyPanelController` (no longer inlined in `RollMainWindow.propertyTreeStateChanged()`).

### `session_service.py`
**Cleaned up.** The duplicate MRU surface (`recordCurrentFile`, `resolveRecentFileName`, `removeRecentFile`, `buildRecentFileMenu`, `resolveRecentSelection`) plus the duplicated `RecentFileMenuEntry`/`RecentFileMenuResult`/`RecentFileResolution` dataclasses have been removed. `SessionService` now owns only array refresh, convex-hull, timer/profiling, and survey-array clearing concerns. MRU ownership lives solely in `DocumentContextService`, with direct test coverage for `buildRecentFileMenu`, `removeRecentFile`, `resolveRecentSelection`, and `resolveRecentFileName` in `test_document_context_service.py`.

### `settings.py` (575 lines)
Loads and saves through `AppSettings` and `RuntimeState`. The `readStoredDebugpySetting()` and similar module-level functions suggest some settings still bypass the dataclass path. These are low-risk but worth tracking.

---

## 4. Test Coverage Assessment

### Scale
- **28 test files**, grown from 25 in the previous review.
- The largest test file (`test_project_sidecars.py`, 2 592 lines) is itself a large and important fixture.

### Coverage highlights
| Area | Coverage status |
|---|---|
| Project XML round-trip | Strong — `test_roll_project_roundtrip.py`, `test_project_service.py` |
| Sidecar load/save | Strong — `test_project_sidecars.py` |
| Filter service | Good — `test_filter_service.py`, `test_sps_filters.py` |
| Session state / service | Good — `test_session_state.py`, `test_session_service.py` |
| Import service | Good — `test_import_service.py` |
| Document context | Good — `test_document_context_service.py` |
| Worker launch / completion | Targeted — `test_project_sidecars.py` includes worker-boundary regressions |
| Geometry generation | Good — `test_roll_survey_geometry.py` covers active `geomTemplate4` and rolled-template paths |
| Binning localization | Covered — relation-driven and no-relation paths |
| Binning completion tail | Covered — `fullAnalysis=True/False` boundary |
| Pattern geometry / array allocation | Covered — `test_roll_survey_geometry.py` |
| Well transform direction | Covered — `test_roll_well_transform.py` |
| `RollSeed` type assignment / `setSurvey` CRS defaulting | **New** — `test_roll_seed.py` (3 cases: int normalization, default CRS, preserved CRS) |
| `np.rec.fromarrays` / searchsorted numpy API | **New** — `test_roll_survey_numpy_api.py` (DeprecationWarning regression for `prepareGeometryRelationBinningLookup`) |
| `SpsTableModel` / `RpsTableModel` / `TableView` | **New** — `test_table_model_view.py` (orphan row foreground, Ctrl-navigation, sound boundary) |
| Parameter aggregate helpers | Good — `test_parameter_aggregate_helpers.py`, `test_my_parameters_aggregate_wrappers.py` |
| Parameter list helpers | Good — `test_parameter_list_helpers.py` (now also covers `swapManagedParameterItems` for the roll-list name-preserving swap path) |
| Parameter seed/well helpers | Good — `test_parameter_seed_well_helpers.py` |
| Parameter creation helpers | Good — `test_parameter_creation_helpers.py` |
| Seed visibility / type routing | Good — `test_my_parameters_seed_visibility.py` (1 265 lines) |
| O/A redraw reuse | Covered — redraw dispatcher regressions in `test_project_sidecars.py` |
| Offset redraw (controller vs. visible) | Covered |
| Numba functions | Targeted — `test_functions_numba.py` |
| RDP algorithm | Covered — `test_rdp.py` |

### Notable gaps
- **`roll_main_window.py` itself is not directly tested.** Most tests exercise domain/service objects in isolation. The main window's `__init__`, `fileLoad`, `plotLayout`, `plotOffset`, `plotOffAzi`, and `dispatchAnalysisRedraw` methods have no standalone unit tests. Coverage for these paths depends on integration-level tests in `test_project_sidecars.py`, which is a higher-level fixture test.
- **`RollSurvey.paint()` / rendering logic is not tested.** This is expected given the PyQtGraph dependency, but the `pg.GraphicsObject` coupling inside the domain model means that any correctness issue in geometry-to-rendering mapping is invisible to the test suite.
- **Wizard flows** (`land_wizard.py`, `marine_wizard.py`) have no dedicated tests.
- **`qgis_interface.py`** QGIS integration helpers have no dedicated tests. The `test_qgis_environment.py` only verifies the environment bootstraps correctly.
- **`sps_io_and_qc.py`** has no dedicated test file; coverage is indirect through `test_import_service.py` and `test_sps_filters.py`. The new `test_table_model_view.py` tests the table model layer above it, not the format parsing itself.
- **Worker thread error boundaries** on `GeometryWorker` are less covered than the binning paths.
- **`MyRollParameter.contextMenu()`** (move-up/move-down inside `MyRollListParameter`) now routes through `swapManagedParameterItems()` in `parameter_list_helpers.py`, with direct helper-level tests for the swap and out-of-range no-op cases.

---

## 5. Architecture Concerns and Observations

### 5.1 `RollSurvey` subclasses `pg.GraphicsObject`
This is the most significant remaining architectural tension. The domain model and rendering model are tightly coupled in a single class. This makes it impossible to instantiate a `RollSurvey` without a running Qt application, which complicates testing and limits the separation of concerns that the rest of the refactoring aims for. The roadmap does not currently propose addressing this; a future option would be a `RollSurveyRenderer` adapter that takes a read-only view of `RollSurvey` geometry data.

### 5.2 Multiple inheritance in `RollMainWindow`
`RollMainWindow(QMainWindow, FORM_CLASS, SpiderNavigationMixin, SurveyPaintMixin, BinningWorkerMixin)` uses five-way multiple inheritance. The mixins are well-separated (spider navigation, paint-mode bookkeeping, worker lifecycle), but the combination means that any attribute added to a mixin is implicitly accessible from `RollMainWindow` without any formal interface. This is a risk for accidental coupling. The current controller extractions (which receive `window` as a constructor argument and access attributes directly) continue this pattern — they are not isolated objects; they are thin wrappers that maintain a strong back-reference. This is pragmatic but means the controller objects cannot be tested in isolation without a full `RollMainWindow` instance.

### 5.3 `QApplication.processEvents()` in parameter constructors
As noted above, calling `processEvents()` during object construction is a re-entrancy risk. If a signal fires during `__init__` and the handler reads state that has not yet been initialized, the result is an exception or silent incorrect state. The pattern exists throughout `my_parameters.py` and appears to be inherited from PyQtGraph usage conventions, but it would benefit from a safety comment and possibly from replacing the mid-constructor calls with a deferred `QTimer.singleShot(0, ...)` pattern for post-construction initialization.

### 5.4 `config.py` as a singleton-like shared constant store
The module-level mutable fields (`surveyNumber`, and the various color/pen defaults that `AppSettings` copies from at construction time) still create an implicit singleton coupling. `AppSettings.__init__` uses `config.binAreaColor` etc. as defaults, which means that changing `config.py` defaults at runtime (e.g., during testing) would affect subsequently created `AppSettings` instances. This is low risk in production but can cause test-ordering sensitivity.

### 5.5 `SessionService` vs `DocumentContextService` duplication ✓ (resolved)
~~`SessionService` still contains `recordCurrentFile`, `buildRecentFileMenu`, and `resolveRecentFileName` methods that are identical or near-identical to the corresponding methods in `DocumentContextService`.~~

**This has been resolved.** All MRU methods and the duplicated MRU dataclasses were removed from `SessionService`; `DocumentContextService` is the sole MRU owner. The corresponding tests in `test_session_service.py` were dropped, and `test_document_context_service.py` was extended with explicit `resolveRecentSelection` and `resolveRecentFileName` coverage.

### 5.6 `worker_result_appliers.py` — strong back-reference pattern
`BinningResultApplier` and `GeometryResultApplier` both take a `window` argument and access `window.output`, `window.survey`, `window.fileName`, etc. directly. This maintains the same coupling as if the code were inline in `RollMainWindow`. The extraction improves readability and testability of the success/failure paths in isolation, but does not reduce the logical coupling to the main window state. This is appropriate for the current phase (Phase 6 is about explicit contracts, not full decoupling) but should be noted for future evolution.

### 5.7 `functions_numba_before_gemini.py`
This file (553 lines) was a legacy snapshot of `functions_numba.py` before a Gemini-assisted rewrite. **It has been moved to `__archive__/functions_numba_before_gemini.py`**, confirming its status as a pure reference artifact. The `__archive__/` directory now holds: `functions_numba_before_gemini.py`, `simil.py`, `regex_testing.py`, `smooth_circle_item.py`, `find_old_dialog.py`, and `roll_survey_old_methods.py`. The root copies of `regex_testing.py` and `smooth_circle_item.py` have also been **deleted** — only the archive copies remain.

---

## 6. Specific Code Observations

### 6.1 `MyRollParameter.contextMenu()` — move-up/move-down ✓ (resolved)
~~This method implements move-up and move-down by directly manipulating `parent.childs` with remove/reinsert rather than routing through `moveManagedParameterItem`.~~

**This has been resolved.** A new `swapManagedParameterItems()` helper was added to `parameter_list_helpers.py` to model the roll-specific name-preserving swap semantics (slot names like `Planes` / `Lines` / `Points` are preserved while the backing `moveList` values are reordered). `MyRollParameter.contextMenu()` now routes both `moveUp` and `moveDown` through that helper. Direct helper-level tests cover both the successful swap and the out-of-range no-op in `test_parameter_list_helpers.py`.

### 6.2 `ProjectLoadApplier._applyLayoutImageState()` ✓ (resolved)
~~This method reconstructs a `pg.ImageItem` and wires a colorbar inline — the same setup that `prepareLayoutImageAndColorBar()` was extracted to handle.~~

**This has been resolved (roadmap item 105).** `ProjectLoadApplier._applyLayoutImageState()` now calls `mainWindow.prepareLayoutImageAndColorBar(...)` directly (see `project_load_applier.py` line 63) instead of duplicating the image-item and colorbar construction. The loaded-project fold-image restore path and the interactive image-selection path now share the same layout helper.

### 6.3 Property proxies in `RollMainWindow`
The ~35 property getter/setter pairs that proxy `SessionState` and `RuntimeState` attributes are boilerplate-heavy. The `rpsLiveE`, `rpsLiveN`, `rpsDeadE`, `rpsDeadN`, and similar derived-state properties delegate directly to `sessionState` without going through `sessionService`. This is intentional (they are read-only derived state from `sessionService.refreshArrayState()`), but the asymmetry with the writable array properties (which go through `sessionService.setArray()`) is not obvious from reading the code.

### 6.4 `SurveyTypeOld` removed from `enums_and_int_flags.py` ✓ (resolved)
~~`SurveyTypeOld` (a simple `Enum`) exists alongside the current `SurveyType`. The old enum appears to be dead code and should be removed.~~

**This has been resolved.** `SurveyTypeOld` has been removed from `enums_and_int_flags.py`. `enums_and_int_flags.py` now contains only `MsgType`, `Direction`, `AnalysisRedrawReason`, `SeedType`, `SurveyType`, `PaintMode`, and `PaintDetails`. The class is preserved only in `__archive__/roll_survey_old_methods.py` for historical reference.

### 6.5 Commented-out import block in `roll_main_window.py`
Lines near the top contain a large commented-out import of `functions_numba`:
```python
# from .functions_numba import (numbaAziInline, numbaAziXline, ...)
```
This is dead code that could be removed, though it may serve as a navigation aid for future work. Worth confirming intent.

### 6.6 `find.py` — `Find` class archived ✓ (resolved)
~~The module-level comment in `roll_main_window.py` explicitly states that `Find` is superseded by `FindNotepad`. The old `Find` class in `find.py` (292 lines) should be confirmed as dead code and either archived or removed.~~

**This has been resolved.** The old `Find(QDialog)` class has been removed from `find.py` and archived in `__archive__/find_old_dialog.py`. `find.py` now contains only `FindNotepad`, and `roll_main_window.py` imports `from .find import FindNotepad` as expected.

---

## 7. Recommendations for GPT5.4 / Next Refactoring Steps

These are ordered by the current roadmap's recommended priorities.

> **Changes implemented since original analysis (2026-04-27):**
> - ✅ `Find` class removed from `find.py`; archived to `__archive__/find_old_dialog.py`
> - ✅ `binFromGeometry9()` `StopIteration` exception handling corrected
> - ✅ `functions_numba_before_gemini.py`, `simil.py`, `regex_testing.py`, `smooth_circle_item.py` now in `__archive__/`
> - ✅ Root copies of `regex_testing.py` and `smooth_circle_item.py` deleted
> - ✅ `SurveyTypeOld` removed from `enums_and_int_flags.py`
> - ✅ New test files added: `test_roll_survey_numpy_api.py`, `test_table_model_view.py`, `test_roll_seed.py`
> - ✅ `SessionService` MRU duplicates removed; `DocumentContextService` is the sole MRU owner; tests realigned
> - ✅ `MyRollParameter.contextMenu()` now routes through new `swapManagedParameterItems()` helper in `parameter_list_helpers.py`, with direct helper tests
>
> **Additional changes since fourth revision (landed by 2026-04-28):**
> - ✅ **`ProjectLoadApplier._applyLayoutImageState()`** now reuses `prepareLayoutImageAndColorBar()` (roadmap item 105)
> - ✅ **`worker_threads.py`** legacy `BinningThread(QThread)` and `Worker(QObject)` scaffolding moved to `__archive__/worker_threads_old_methods.py`; the generic `binningResultThreadFinished()` compatibility wrapper removed (roadmap item 106)
> - ✅ **`RuntimeState.wellDirectory`** added; the well-file browse directory is now part of the persisted runtime document context (roadmap item 107)
> - ✅ **`PropertyPanelController`** now owns the Well-file directory propagation guard/update path (previously inlined in `RollMainWindow.propertyTreeStateChanged()`), with direct regression coverage for matching and non-matching tree-change events (roadmap item 108)

### Immediate (next 1–2 steps)

1. **Wire or remove `binFromGeometry9()`.** The new Numba parallel batch method at line 1321 in `roll_survey.py` is ready but not yet dispatched from `setupBinFromGeometry()` (which still routes through `binFromGeometry8`/`binFromGeometryNoRel`). Either hook it in with a feature flag or A/B switch, or move it to `__archive__/roll_survey_old_methods.py` if development has stalled, to avoid ambiguity about the active binning path. **This is now the single most concrete open item on the worker/binning track.**

2. **Add a note to `MyRollParameter.__init__` about the `processEvents()` re-entrancy risk.** Low cost; high value for future maintainers.

### Short-term

### Medium-term

3. **Consider a `RollSurveyRenderer` adapter** to decouple the domain model from `pg.GraphicsObject`. This is the largest architectural debt item not addressed in the current roadmap. Even a thin read-only geometry view interface (a `@dataclass` or `Protocol`) would make the domain model independently testable.

4. **Add a dedicated test file for `sps_io_and_qc.py`.** The fixed-width SPS format parsing is safety-critical (wrong field offsets produce silent data corruption). Even 3–4 round-trip tests for each SPS record type would substantially improve confidence.

5. **Add one integration test for a wizard preset.** `LandSurveyWizard` and `MarineSurveyWizard` are large and recently changed (defaults moved from `config.py`). A single test that constructs a wizard with default settings and verifies the resulting survey XML round-trips cleanly would protect against regressions.

### Longer-term (after structure stabilizes)

6. **Performance measurement pass.** Profile `np.unique` in geometry generation, worker result copy overhead, and redraw invalidation breadth on realistic survey sizes. Then optimize only what is measured. `binFromGeometry9()` with its Numba parallel kernel is the most concrete performance candidate.

7. **`config.py` constants audit.** Confirm which constants are still read by `AppSettings` and which can be inlined or moved to the appropriate owner class.

---

## 8. Summary

The refactoring is mature and well-organized. The milestone-1 definition of done (from the roadmap) is met across all criteria. With roadmap items 104–108 landed since the previous revision, **the worker cleanup tail and the `ProjectLoadApplier` layout-helper duplication are both closed**. The main remaining work is now:

- Decide on `binFromGeometry9()` (wire or archive) — the only concrete open item on the worker/binning track.
- Decide whether one more `my_parameters.py` behavioral extraction is warranted; the 103-item helper-extract track has reached a natural stopping point.
- Not re-opening `RollMainWindow` for another seam until the above are stable.
- Treating performance and `config.py` splitting as optional follow-on work.

The test suite is solid for service/helper/domain objects but has a meaningful gap for the main window and wizard flows. The most impactful single test addition would be a dedicated `sps_io_and_qc.py` round-trip test, as SPS parsing is both safety-critical and currently tested only indirectly.

The codebase is in a good state for continued incremental refinement. The architectural debt around `RollSurvey` subclassing `pg.GraphicsObject` is the largest unaddressed structural concern, but it is correctly deferred given the scale of work that would be required to separate it cleanly.
