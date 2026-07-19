# Roll Refactoring Assessment And Way Forward

**Assessment date:** 2026-07-18  
**Scope:** Current working tree, all Python sources, and every document in `markdown/`  
**Mode:** Read-only review. No application, test, configuration, UI, or generated-document files were changed for this assessment.

## Executive Assessment

Roll has passed the most valuable early refactoring milestone: persistence, import/QC, runtime state, worker orchestration, action state, plot navigation, and major property-panel ownership are no longer concentrated solely in `RollMainWindow`. The code is materially better structured than the historical notes suggest.

The project is not yet lean in the sense of having a small number of compact modules. That is expected for a QGIS/PyQt application with numerical survey algorithms, but several real concentration points remain:

1. `roll_survey.py` still combines domain state, XML serialization, geometry generation, binning, numerical-path routing, and PyQtGraph painting.
2. `roll_main_window.py` remains the application composition root plus a broad plot/layout coordinator.
3. `roll_main_window_create_layout_tab.py` has become a presentation bridge rather than only a tab builder.
4. `PropertyPanelController` holds five near-parallel propagation workflows.
5. `my_parameters.py`, the two survey wizards, `table_model_view.py`, and `qgis_interface.py` are still large, behavior-rich modules.

The right response is **not** a package reorganization or a broad rewrite. The codebase has made progress by carving out bounded, testable seams. Continue that method: fix the two verified correctness defects first, establish the CFP documentation baseline, extract the layout-to-3D bridge, and then reduce one property-panel propagation flow at a time.

## Review Scope And Evidence

### Python inventory

The review consulted every current Python source file in the workspace, including production code, tests, archive/reference files, QGIS tooling, numerical modules, tab builders, custom parameter classes, and standalone helpers.

| Category | Files | Lines | Interpretation |
| --- | ---: | ---: | --- |
| Production | 111 | 36,679 | Main refactoring surface; includes QGIS integration and numerical code. |
| Tests | 32 | 10,072 | Strong test volume, but too much high-level coverage is concentrated in one file. |
| Archive/reference | 7 | 2,504 | Intentional comparison/history code; retain it as a clearly separate reference surface. |
| Total Python | 150 | 49,255 | A mature, non-trivial desktop/GIS application rather than a small plugin. |

The biggest current production modules are:

| Module | Lines | Primary responsibility | Assessment |
| --- | ---: | --- | --- |
| [`roll_survey.py`](../roll_survey.py) | 3,791 | Survey aggregate, geometry/binning, XML, painting | Highest architectural coupling; do not broadly rewrite. |
| [`roll_main_window.py`](../roll_main_window.py) | 3,387 | UI composition and orchestration | Improved, but still broad. |
| [`marine_wizard.py`](../marine_wizard.py) | 2,213 | Marine survey wizard | UI and calculation logic are interleaved. |
| [`my_parameters.py`](../my_parameters.py) | 2,185 | PyQtGraph parameter-tree schema/binding | Mechanical duplication is reduced; behavioral coupling remains. |
| [`land_wizard.py`](../land_wizard.py) | 1,969 | Land survey wizard | Similar UI/domain coupling, lower urgency. |
| [`qgis_interface.py`](../qgis_interface.py) | 1,687 | QGIS import/export and layer integration | Large, but mostly independent adapter functions. |
| [`worker_threads.py`](../worker_threads.py) | 1,627 | Long-running numerical workers | Reasonably bounded by typed request/result paths. |
| [`layout_3D.py`](../layout_3D.py) | 1,445 | Matplotlib 3D renderer | Rendering is cohesive; input translation belongs elsewhere. |
| [`table_model_view.py`](../table_model_view.py) | 1,162 | Qt table models/views | SPS/RPS models contain real duplication. |

### Static style indicators

These counts are indicators, not automatic defects:

| Signal | Count | Assessment |
| --- | ---: | --- |
| Calls to `processEvents()` | 61 | Legitimate responsiveness motivation in a large parameter-tree UI, but this is a material re-entrancy risk and should not grow. |
| Bare `except:` handlers | 0 | Good. The code avoids the least diagnosable exception form. |
| `except Exception` handlers | 34 | Often defensible at Qt/QGIS lifecycle boundaries, but each should either log, constrain scope, or remain clearly best-effort. |
| `TypeError` fallback branches in the layout 3D bridge | 6 | Too many. They can turn a real renderer-contract error into a silent downgrade. |

The assessment was performed against the current dirty working tree, not a clean historical commit. Existing uncommitted changes are intentionally not reverted, reformatted, or otherwise modified.

## Current Architecture Status

### Healthy boundaries that should be preserved

These are completed or credible refactoring boundaries. They need normal maintenance, not another general extraction campaign.

| Area | Current owner(s) | Assessment |
| --- | --- | --- |
| Project persistence and sidecars | `ProjectService`, `ProjectLoadApplier` | Clear ownership of XML, sidecar validation/loading, compatibility normalization, and application. |
| Runtime and document state | `AppSettings`, `RuntimeState`, `SessionState`, `SessionService`, `DocumentContextService` | Much clearer than historic main-window/config ownership. |
| SPS/RPS/XPS import and filtering | `ImportService`, `FilterService`, `sps_io_and_qc.py` | Import workflow and filters have useful separations; fixed-width mechanics still duplicate locally. |
| Worker lifecycle | `WorkerOperationController`, request/result dataclasses, result appliers | A substantial improvement over implicit worker completion state. |
| Plot navigation and invalidation | `PlotNavigationController`, `PlotViewStateController`, `PlotRedrawHelper`, `StackResponseController` | Appropriate controller extraction without premature abstraction. |
| UI action state and presentation | `ActionStateController`, `PrintPresentationController` | Reasonable composition-root delegation. |
| Parameter mechanics | `parameter_*_helpers.py` modules | Good helper extraction. Further work must target behavior, not mechanically split files. |
| Numerical strategy/reference paths | stable/experimental routes plus `__archive__/` | Intentional parity and performance comparison surface; preserve and document it. |

### Remaining architectural seams

#### 1. Layout 2D-to-3D translation

[`roll_main_window_create_layout_tab.py`](../roll_main_window_create_layout_tab.py) currently builds widgets and also decides what the 3D renderer receives: projected/local state, visibility, point sets, bin/block areas, analysis image, reflector styling, and spider overlays. Its `refreshLayout3DFromSurvey()` retries several increasingly older `updateFromSurvey()` signatures after a `TypeError`.

This is the best next refactoring seam because it is cohesive, user-visible, and testable without changing survey algorithms. The renderer in [`layout_3D.py`](../layout_3D.py) should continue to render an already-built payload, not discover UI state.

#### 2. Property propagation transactions

[`property_panel_controller.py`](../property_panel_controller.py) carefully tracks and applies five similar propagation workflows: rename, color, origin shift, grid-grow list, and pattern. Each has pending state, matching-seed selection, confirmation, survey mutation, and parameter-tree synchronization.

This is not bad code; it is a complex business rule written several times. The risk is behavioral drift when a sixth propagation rule is added. Extract one generic transaction decision/application seam only after direct characterization tests describe current confirmation and matching behavior.

#### 3. Survey aggregate coupling

[`roll_survey.py`](../roll_survey.py) is both a PyQtGraph `GraphicsObject` and the central survey/domain aggregate. It owns rendering state, geometry, binning, XML, transforms, output references, and legacy/experimental strategy routing. This is the most substantial architectural tension, but it is also the highest-risk refactor.

Keep the current stable/experimental routing and parity tests intact. A future renderer split should be a dedicated phase with a concrete target such as a `SurveyGraphicsItem`/renderer adapter. It is not the next task.

#### 4. Wizard calculation versus UI mutation

[`marine_wizard.py`](../marine_wizard.py) and [`land_wizard.py`](../land_wizard.py) mix page wiring, field reads, default selection, survey construction, and mathematical calculation. Qt form construction itself is not a smell. The extractable future seam is pure configuration calculation and survey application, each protected by small default-flow tests.

#### 5. Structured-table duplication

[`table_model_view.py`](../table_model_view.py) has closely related SPS and RPS table models. [`sps_io_and_qc.py`](../sps_io_and_qc.py) similarly has parallel RPS/SPS parsing and uniqueness code. This is a valid later cleanup target, but only if a shared implementation can preserve field names, Qt roles, colors, sorting, keyboard navigation, and structured-array ordering.

## Verified Correctness Defects

These are deliberately separate from refactoring priorities. They should be handled as small test-first bug fixes before any structural movement in the same files.

### P0. XPS column preview updates the SPS preview state

In `SpsImportDialog.onXpsSpinboxValueChanged()`, the selected XPS column bounds are written to `self.spsTab.line1` and `self.spsTab.line2`, then the XPS tab is selected and `self.xpsTab.update()` is called. The XPS preview therefore redraws with stale selection bounds.

**Required test:** edit one XPS bound, then assert that `xpsTab.line1` and `xpsTab.line2` are updated and that the XPS tab is selected/refreshed.

**Exit criterion:** the XPS preview highlights the edited XPS range, while SPS and RPS handlers continue to update their own previews.

### P0. Marine natural crossline bin size can index beyond two CMP positions

`MarineTemplatePage.xlineBinSize()` builds and de-duplicates CMP crossline positions, then uses `cmpActX[cmp + 1] - cmpActX[cmp]` where `cmp = size // 2`. With two unique positions, `cmp` is `1` and `cmp + 1` is outside the array.

**Required test:** use the smallest valid two-position configuration, including `nSrc=1` and `nCab=2`, and assert a finite non-negative natural bin size.

**Exit criterion:** two, three, and larger unique-CMP configurations all return a valid spacing; no wizard page or default workflow regresses.

## Leanness, Compactness, And Python Style

### Leanness: good boundary progress, still too many broad owners

The codebase is leaner than its line count suggests because major behavior now has named owners. The strongest evidence is the dedicated state/services/controllers/worker contracts and the intentional archive directory. Splitting source only to reduce file length would make the code worse.

The remaining non-lean areas are functions/classes that mix framework wiring with application policy:

1. `RollMainWindow` retains top-level orchestration and broad plot/layout work.
2. `RollSurvey` mixes five ownership categories that cannot be independently reasoned about.
3. The layout tab module has accumulated an entire presentation adapter.
4. The property controller repeats a complex propagation transaction shape.
5. The wizards and parameter tree include mutation-heavy UI logic that requires disciplined boundaries.

**Judgment:** the project is structurally lean in its new service/controller seams, but not yet lean in its core UI/domain aggregates. Continue carving only seams with a stable, testable contract.

### Compactness: avoid compression; reduce duplication and stale narration

The configured 210-character line limit is appropriate for this domain because NumPy structured types, Qt signal wiring, and UI definitions are naturally wide. Compactness should mean less duplicated behavior and fewer stale cognitive branches, not shorter individual lines.

The clearest compactness opportunities are:

1. Replace the layout bridge's six compatibility retries with one stable contract after a bridge extraction.
2. Consolidate property-propagation mechanics only after behavior characterization.
3. Parameterize shared SPS/RPS table-model behavior, not the domain-specific colors/labels themselves.
4. Extract fixed-width parser mechanics while retaining explicit SPS/RPS/XPS field mappings.
5. Relocate long historical/tutorial comment blocks from active modules to targeted developer documentation when they no longer explain a current non-obvious decision.

The code should retain explanatory comments for QGIS object lifetime, NumPy axis orientation, sidecar compatibility, and stable-versus-experimental numerical semantics. Those comments are part of the safety model.

### Pythonic style: strong modern core, legacy imperative edges

The modern core is appropriately Pythonic:

1. Request/result objects use dataclasses and targeted type annotations.
2. Domain and service names generally describe actual behavior.
3. NumPy is used as array computation rather than Python-level per-sample loops where performance matters.
4. `with` blocks, small helpers, properties, enum-like types, and explicit `None` guards are used consistently in newer code.
5. No bare `except:` handlers were found.

The legacy/Qt edges are understandably more imperative, but should not become the default style:

1. Do not add further `QApplication.processEvents()` calls. Prefer a deferred Qt update or worker progress mechanism where feasible, and document any unavoidable re-entrancy guard.
2. Catch `TypeError` only around a single operation when it denotes an expected compatibility case. It must not be used to select an API version at runtime once both sides are owned by this repository.
3. Replace large commented-out implementations and generic tutorial links when they no longer clarify the active code. Preserve intentional historical implementations under `__archive__/` instead.
4. Keep explicit field mappings in SPS/RPS/XPS code; “DRY” must not conceal differences that are part of the file format.
5. Continue using small, behavior-named helpers rather than meta-programming the main window or parameter tree.

**Overall judgment:** new/refactored code is generally Pythonic and pragmatic. The primary issue is historical accretion and framework-heavy mutation flows, not an absence of Python language discipline.

## Test Posture

The 32 test modules are a substantial strength, particularly for geometry parity, sidecar compatibility, settings/runtime state, parameter helpers, QGIS table models, workers, and recent CFP behavior. The testing strategy should now become more deliberately distributed.

### Main issue: integration-test concentration

[`test/test_project_sidecars.py`](../test/test_project_sidecars.py) is 5,152 lines and carries tests for much more than project sidecars: worker completion, CFP modes, layout state, redraws, settings, controller behavior, property propagation, and main-window application paths. It is valuable regression coverage, but it is difficult to navigate and expensive to use as the default characterization location.

Move tests by ownership, preserving fixtures and assertions before simplifying anything:

1. Layout bridge tests into a dedicated bridge test module.
2. Property propagation tests into a controller-focused module.
3. CFP worker/request/result regressions into focused CFP worker test modules.
4. Keep genuine project-sidecar compatibility tests in the existing file.

### Test execution policy

Use the repository's QGIS-aware launcher on Windows:

```bat
.\run_unittest_suite.bat test.test_module.Class.test_case
```

Run targeted tests for the edited seam first. Use the broader suite after a sequence of related changes or before merging. Do not use a full suite run as a substitute for an absent narrow regression.

## Markdown Documentation Assessment

### Authority hierarchy

Planning documents need a clear hierarchy:

1. [`Refactoring_roadmap.txt`](../Refactoring_roadmap.txt) is the source of truth for active structural work.
2. This assessment records the July 18 audit and supersedes no behavioral specification.
3. [`Layout_3D_refactor_proposal.md`](Layout_3D_refactor_proposal.md) is the actionable implementation companion for the next structural slice.
4. All chat/session/third-party-model documents are historical evidence or technical references, not active instructions.

### Complete markdown inventory

| Document | Current status | Recommended use |
| --- | --- | --- |
| `2026-05-30-cfp-beam-debugging.md` | Historical debugging checkpoint | Preserve as evidence only. |
| `cfp_demo_bart_4_roll_mismatch_2026_05_29.md` | MATLAB-parity reference | Use only for strict scientific compatibility work. |
| `cfp_single_template_parity_matrix_2026_05_29.md` | Technical compatibility gap register | Preserve; do not treat as current product roadmap. |
| `chat-on-cfp-plane-analysis.md` | Detailed implementation ledger | Mine for provenance, not planning. |
| `chat_2026_03_12.md` | Historical chat recovery | Background decision context. |
| `chat_2026_05_01.md` | Historical discussion | Background decision context. |
| `chat_2026_05_01_binning_speedup_recovered.md` | Durable performance principle | Keep: measure before GPU/optimization work. |
| `chat_2026_05_18.md` | Geometry stabilization handoff | Completed baseline evidence. |
| `chat_2026_05_21.md` | Sphinx/package workflow record | Current operational reference. |
| `chat_2026_05_26.md` | CFP Radon robustness handoff | Deferred technical reference. |
| `chat_2026_05_27_cfp_workflow_decisions.md` | CFP job-model decision | Serialized-worker decision remains valid. |
| `claude_analysis.md` | Broad prior architecture review | Useful narrative, but some chronology is stale. |
| `CODEBASE_SUMMARY.md` | Short architecture orientation | Keep concise; not sufficient as a roadmap. |
| `GeminiChat.md` | Raw generated chat capture | Historical background only; verify claims in live code. |
| `Gemini_cfp_discussion.md` | CFP theory/source discussion | Reference only, not an implementation authority. |
| `Gemma4_Analysis.md` | Generic refactoring advice | Do not use its package-reorganization proposal. |
| `gpt55_analysis.md` | Historical review | Useful for provenance; marked partly superseded. |
| `Layout_3D_refactor_proposal.md` | Focused active proposal | Use with the roadmap for the next refactor. |
| `refactoring_roadmap_comparison_note.md` | Historic classification index | Useful, but predates the current assessment. |
| `session_2026_05_27_cfp_numba_hardening.md` | Numba robustness handoff | Revisit only with a reproducible issue. |
| `session_2026_05_28_cfp_worker_fixes.md` | Historical CFP worker fixes | Preserve; later decisions supersede partial-update advice. |
| `session_2026_05_29_cfp_beam_debugging.md` | Historical debugging note | Preserve as evidence only. |
| `session_2026_06_01_cfp_performance_and_imprint_handoff.md` | CFP performance baseline | Benchmarks remain useful; implementation status is partly superseded. |
| `session_notes_template.md` | Session record template | Keep and update workflow commands when they change. |

### Documentation gap to address now

The roadmap's immediate documentation priority remains valid. User-facing CFP documentation should explain:

1. Point versus plane/illumination analysis and supported data paths.
2. Coherent versus incoherent QC output and frequency-list behavior.
3. Normalized display values and the diagnostic normalization factor.
4. The optional 3x3 diagnostic switch and how to interpret its summary.
5. Why template/geometry parity is expected only with identical support.
6. A small reproducible template-versus-geometry parity recipe.

Do not write a broad technical redesign document before this targeted documentation exists.

### End-user documentation gaps and recommended starting order

The current Sphinx documentation has a solid conceptual base:

* `user-guide.rst` explains the survey model, output files, broad workflows, and the existence of the Analysis, 3D, wizard, SPS, and QGIS features.
* `template-design.rst` gives a useful illustrated explanation of seeds, grow lists, roll-along, blocks, nodal layouts, and marine racetracks.
* `qgis-interface-guide.rst` provides the most detailed task-based material, especially for QGIS editing and round trips.

The principal gap is between **knowing what Roll can do** and **completing a first reliable analysis unaided**. The short `workflows.rst` page names the main paths but does not explain the choices, UI actions, expected intermediate results, or recovery when prerequisites are missing. The user documentation should therefore become more task-led before it becomes more exhaustive.

#### Priority 1: First project to first trustworthy fold map

Start with one end-to-end “first successful project” tutorial. This should be the front door for a new user and should link to deeper pages rather than repeat them.

1. Create an orthogonal project with the Land Wizard, or open a bundled/example `.roll` project.
2. Identify the Layout tab, Property pane, and Processing menu.
3. Save the project before selecting Full Binning.
4. Run Basic Binning first and inspect the fold, minimum-offset, and maximum-offset maps.
5. Explain when the result is sufficient and when Full Binning is required.
6. Run Full Binning, then locate the trace table, spider, histogram, offset/azimuth diagram, and extra offset-quality maps.
7. State what a plausible first result looks like and which visible symptoms require adjustment: empty maps, zero fold, clipping, insufficient maximum fold, missing source/receiver seeds, or unsuitable bin size.

This page should include a small decision table:

| User goal | Input path | Processing choice | Main output to inspect |
| --- | --- | --- | --- |
| Compare a proposed layout quickly | Templates | Basic Binning | Fold/minimum/maximum offset maps |
| Inspect trace-level geometry and detailed offset quality | Templates, geometry, or SPS | Full Binning | Trace table, spider, RMS increment, max gap, histograms |
| Assess edited positions from QGIS | Geometry or SPS tables | Basic then Full Binning as needed | Fold maps first, then detailed analysis |

**Why first:** it turns the existing conceptual documentation into an actionable learning path and establishes terms that every later page can use.

#### Priority 2: Analysis and output interpretation guide

The user guide lists the analysis outputs but does not tell users what each plot answers, how to read it, or what action to take when it looks poor. Add one Analysis guide organized by question rather than implementation:

| Question | Output | What to explain |
| --- | --- | --- |
| Is coverage sufficient? | Fold map | Minimum acceptable fold is project-specific; identify holes, edge taper, and clipping. |
| Are near offsets present? | Minimum offset map | Explain the acquisition/design consequence of excessive minimum offset. |
| Is far-offset reach adequate? | Maximum offset map | Explain target-dependent acceptance rather than a universal threshold. |
| Are offsets sampled regularly? | RMS offset increment and maximum offset gap maps | Explain high values, isolated anomalies, and why the two measures differ. |
| Is one bin or line unusual? | Spider, trace table, inline/x-line offsets and azimuths | Show how to navigate to a bin and relate trace rows to the map. |
| Is the full area balanced? | |O| histogram and Offset/Azimuth diagram | Explain offset bins, azimuth coverage, rectangular versus polar display, and empty sectors. |
| Is directional stacking support adequate? | Kr/Kx-Ky stack response | Define the response qualitatively and point to design changes users can make. |

Include a clear Basic-versus-Full Binning section. The current documentation says what Full Binning creates, but users need an operational decision and a warning that full analysis allocates a potentially large `*.ana.npy` memory-mapped file.

**Why second:** analysis is the application’s payoff; users need interpretation guidance before they can make informed design changes.

#### Priority 3: CFP point analysis and illumination guide

CFP is the largest feature/documentation mismatch. The user guide only names the single-point spatial and Radon outputs, whereas the current UI supports:

1. Point CFP from Templates, Geometry Tables, or SPS input tables.
2. Plane/illumination analysis from the same input families.
3. Source beam, receiver beam, resolution, Radon source/receiver beam, and AVP views.
4. Coherent illumination and an incoherent QC mode.
5. Frequency lists, focal depth/location, aperture, velocity, display cut-off, and optional 3x3 source/receiver diagnostics.

Create one self-contained CFP guide with these sections:

1. **When to use CFP:** distinguish local focal-point diagnosis from full-area illumination; state that it is advanced analysis, not the first fold-QC step.
2. **Choose the data path:** Templates for a nominal design; Geometry/SPS when working from explicit or edited points; support must be identical for a parity comparison.
3. **Set the focal target:** bin-area center versus explicit location, focal depth, aperture, velocity, and frequency list.
4. **Run and inspect point CFP:** define every spatial and Radon view in plain survey-design terms.
5. **Run and inspect illumination:** explain normalized display, display cut-off, coherent output, incoherent QC as a diagnostic rather than a competing production result, and 3x3 diagnostic terminology.
6. **Interpret carefully:** a map is relative to its own calculation; do not compare raw display colors across changed settings or unrelated surveys without a common normalization/acceptance rule.
7. **Troubleshoot:** disabled actions, missing input tables, no valid support, long runtimes, and template-versus-geometry differences caused by edited/clipped support.

State prominently that the CFP functions are controlled by the **Use experimental code** setting. Define the effect, prerequisites, and expected maturity in end-user language; do not require users to infer it from a developer-oriented label.

**Why third:** CFP is active, user-visible functionality with enough controls and outputs that an incomplete explanation invites misleading interpretation.

#### Priority 4: Project lifecycle, sidecars, and large-project operations

The user guide lists the `.npy` sidecars but does not explain their practical lifecycle. Add a focused “Project files and large analyses” page covering:

1. What is saved in the `.roll` file versus derived sidecars.
2. Why Full Binning requires the project to be saved first.
3. Which actions invalidate or replace analysis outputs.
4. How to move or copy a project safely, including relative well paths.
5. What to do when sidecars are missing, dimension-mismatched, inaccessible, or from an older layout: preserve the `.roll` file and re-run the relevant analysis.
6. Disk-space and performance expectations for the memory-mapped trace table.
7. Practical trace-table usage: chunks, filtering/navigation, and why very large selections are intentionally constrained.

**Why fourth:** this prevents avoidable data-loss concerns and explains behavior that otherwise feels like a failed processing run.

#### Priority 5: Manual design and property-pane editing

The visual template-design page is valuable, but it does not yet function as a manual editing guide. Add a property-pane tutorial that shows:

1. Adding, naming, reordering, and deleting blocks, templates, seeds, and patterns.
2. The source/receiver role and the three grow/roll steps.
3. Grid, circle, spiral, and well seed types, including which are stationary under template roll.
4. Pattern assignment and what it changes in the displayed/analysed survey.
5. The propagation prompts for identically named seeds and when to accept or decline them.
6. Safe XML editing as an expert recovery route, with reload behavior and a warning to keep a backup.

**Why fifth:** it supports users who outgrow wizard defaults without forcing them to reverse-engineer the XML or parameter tree.

#### Priority 6: SPS import and data-quality handbook

The documentation explains that configurable dialects exist, but it does not walk a user through a reliable import/QC decision path. Add:

1. SPS/RPS/XPS roles and the minimum files needed for each analysis mode.
2. Selecting, cloning, naming, and resetting a dialect.
3. Setting fixed-width columns and verifying the record preview for each file type.
4. CRS and local-grid setup for an SPS-only project.
5. Meaning of duplicates, source/receiver orphans, and `inuse` values.
6. Binning with no XPS relation file: what Roll can do and what acquisition relationship information is absent.
7. Export/import field expectations for QGIS, with a short cross-reference to the detailed QGIS guide.

**Why sixth:** this is essential for legacy-data users, but is best written after the first project and analysis vocabulary are established.

#### Priority 7: 3D, well, and advanced settings reference

Document specialized features as short focused pages instead of adding them to the first tutorial:

1. **3D Subset:** switch between 2D/3D, local/global view behavior, supported non-rolling content, visible-layer mirroring, and the deliberate exclusion of full rolling-template rendering.
2. **Well/VSP workflow:** well file path handling, depth/elevation conventions, seed types, and which plots help validate the result.
3. **Settings reference:** user-facing Color, Level of Detail, SPS, Geometry, K-response, CFP, and Miscellaneous settings. Exclude developer-only debug detail from the main user path.
4. **Experimental setting:** explain its scope in a standalone warning/reference section, including when users should leave it disabled.

**Why seventh:** these are high-value but specialized. They should be easy to discover once a user needs them, not part of the core onboarding path.

#### Documentation structure to add

Keep the existing conceptual pages. Extend the user toctree with task-oriented pages in this order:

```text
Getting started: first project to first fold map
Analysis: choose a binning mode and interpret outputs
CFP point analysis and illumination
Project files, sidecars, and large analyses
Editing a design in the property pane
SPS import, dialects, and quality control
3D, wells, and VSP workflows
Settings reference and experimental features
```

Each page should begin with **When to use this**, list prerequisites, show an ordered procedure, state the expected result, and end with a short **Common problems** section. Screenshots should be used for stateful dialogs, plot controls, and property-pane locations; text is better for decisions, file-field definitions, and acceptance criteria.

## Prioritized Plan

### P0: Fix verified correctness defects

**Scope:** XPS preview state and two-CMP marine natural-bin calculation.

1. Add targeted regressions that demonstrate the current failures.
2. Make the smallest behavior-preserving fixes.
3. Run just the new/affected test modules through `run_unittest_suite.bat`.

**Exit criteria:** both regressions pass; no unrelated refactoring; SPS/RPS preview behavior and existing wizard defaults remain intact.

### P1: Lock the CFP documentation baseline

**Scope:** Sphinx user documentation and a reproducible parity recipe.

1. Describe the actual current CFP contract, not historical WIP behavior.
2. Build documentation through the established QGIS/Windows workflow.
3. Do not modify numerical behavior in this documentation slice.

**Exit criteria:** a user can select a CFP mode, interpret its map/diagnostics, and understand the template/geometry support caveat from the documentation alone.

### P2: Extract the narrow Layout 2D-to-3D bridge

**Scope:** Move payload/style/visibility translation from the layout tab builder into a focused, function-oriented bridge module.

1. Start with pure payload builders for visible points, areas, image, reflector style, and spider overlay.
2. Move refresh orchestration with an unchanged `Layout3DWidget.updateFromSurvey()` contract.
3. Add direct tests for local/global coordinates, visibility, style, depth, block/bin areas, and optional overlays.
4. Remove the cascading `TypeError` compatibility attempts once the single contract is proven.
5. Stop after behavior parity; do not refactor `layout_3D.py` rendering internals in the same change.

**Exit criteria:** `roll_main_window_create_layout_tab.py` owns construction/wiring; the bridge owns translation; `layout_3D.py` owns rendering; focused bridge tests pass.

### P3: Decompose tests by ownership before more controller work

**Scope:** Reduce the catch-all nature of `test_project_sidecars.py` without weakening coverage.

1. First move layout bridge tests after P2.
2. Move property propagation tests to a controller-focused test module.
3. Move CFP worker and display regressions to focused CFP modules when their ownership is unambiguous.
4. Keep true sidecar/load/compatibility assertions together.

**Exit criteria:** a developer can find the relevant test suite from the implementation module, and a focused change does not require navigating a multi-thousand-line catch-all test file.

### P4: Extract one property-propagation transaction seam

**Scope:** One propagation type, preferably the least ambiguous after direct tests exist.

1. Characterize pending-state, matching logic, user confirmation, survey update, and parameter-tree synchronization.
2. Extract shared transaction mechanics only when the resulting API makes those rules clearer.
3. Preserve user-visible confirmation text and matching semantics unless an explicit product decision changes them.

**Exit criteria:** one propagation flow has a narrow testable owner; the other flows remain untouched until individually characterized.

### P5: Targeted compactness improvements

Choose only one item at a time:

1. One behavior cluster from `my_parameters.py` with repeated UI-to-domain write-back.
2. Shared RPS/SPS table-model mechanics after characterization tests protect roles and navigation.
3. Shared fixed-width parser mechanics while leaving field mappings explicit.
4. A pure calculation/application seam in one wizard, accompanied by a wizard smoke test.

**Exit criteria:** each change removes clear duplication or adds a real test seam. No file split merely to reduce a line count.

## Explicit Deferments

The following are worthwhile only when their prerequisite evidence exists:

| Deferred work | Why defer now | Trigger to revisit |
| --- | --- | --- |
| Broad `RollSurvey` model/renderer separation | High coupling and high regression risk | A committed design phase with renderer characterization tests. |
| Package/folder reorganization | Would create wide import churn with little behavior gain | Multiple completed seams require a stable package boundary. |
| Experimental geometry/binning promotion | Reference paths are intentional | Benchmarks plus parity evidence establish a better default. |
| GPU/CuPy or speculative optimization | Structure is not the bottleneck until profiling proves it | Reproducible profile identifies a dominant kernel and CPU path is stable. |
| Broad QGIS interface rewrite | Large but largely functional adapter | Repeated change pain in one cohesive layer-helper family. |
| Strict MATLAB CFP parity | Scientific compatibility is a separate product objective | Explicit reference data, formulas, tolerances, and acceptance examples. |

## Decision Rules For Future Refactoring

1. Name the behavior boundary before creating a new module.
2. Add a narrow regression before moving code whose output is not already characterized.
3. Preserve stable/experimental numerical comparisons until profiling and parity say otherwise.
4. Do not let a generic `except Exception` or `except TypeError` conceal a repository-owned contract failure.
5. Prefer a local function-oriented adapter over a framework-wide abstraction.
6. Measure performance before changing algorithm shape or introducing parallel/GPU paths.
7. Keep this document and `Refactoring_roadmap.txt` current; preserve chats and old analyses as traceable historical material.

## Recommended Immediate Sequence

1. Land the two P0 test-first bug fixes.
2. Document the live CFP contract in the user guide and build the docs.
3. Execute the narrow layout-to-3D bridge extraction with direct tests.
4. Split the bridge/property/CFP tests out of the sidecar mega-suite by ownership.
5. Choose one property propagation flow as the next behavior-focused extraction.

This order fixes known user-facing defects first, completes an existing documentation obligation, improves the clearest structural seam, and only then moves into the more subtle behavior-heavy areas.