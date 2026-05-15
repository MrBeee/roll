# Codebase Structural & Organizational Summary

**Date:** 2026-05-20  
**Project:** Roll QGIS Plugin (Seismic Survey Design & Analysis)  
**Status:** Advanced Refactoring Milestone Complete

## 1. Architectural Overview
The codebase follows a mature **Service-Oriented Architecture (SOA)** with clearly defined layers, significantly reducing the "God Object" dependency on the main window.

| Layer | Component | Responsibility |
| :--- | :--- | :--- |
| **State** | `SessionState`, `RuntimeState` | Single source of truth for arrays and document context. |
| **Services** | `ProjectService`, `ImportService`, `FilterService` | Pure logic, file I/O, and domain validation. |
| **Controllers** | `StackResponseController`, `PropertyPanelController` | Mediates between the Domain and the UI. |
| **Domain** | `RollSurvey`, `RollSeed`, `RollWell` | Core seismic geometry and coordinate logic. |
| **UI Builders** | `roll_main_window_create_*_tab.py` | Modular tab construction and widget layout. |

## 2. Key Organizational Strengths
- **Decoupling Logic:** The move of parsing (SPS/RPS) and persistence (Sidecars) into dedicated services allows for headless testing and cleaner orchestration.
- **State Management:** Utilizing `dataclasses` for state prevents stale data bugs common in complex GIS applications involving coordinate transformations.
- **Refactoring Discipline:** The project maintains an excellent `Refactoring_roadmap.txt`, providing a technical audit trail that preserves architectural intent.
- **Worker Contract Clarity:** Asynchronous operations now use explicit Request/Result payloads, making the threading model predictable and robust.

## 3. High-Level Hotspots
The following files remain points of high complexity due to their inherent responsibilities:

1. **`roll_survey.py` (~4,200 lines):** The primary domain hotspot. It handles geometry generation, binning, and rendering.
2. **`roll_main_window.py` (~3,600 lines):** The central UI orchestrator. While much logic has been moved out, it still manages top-level plotting flow.
3. **`my_parameters.py` (~2,800 lines):** A massive collection of parameter definitions. Most mechanical duplication has been removed via helpers, but behavioral complexity remains high.

## 4. Current Technical Debt & Observations
### Rendering Coupling
`RollSurvey` still inherits from `pg.GraphicsObject`. This forces a dependency on `PyQtGraph` and `Qt` for core domain calculations, making pure unit testing of geometry logic difficult without a GUI environment.

### Re-entrancy Risks
The frequent use of `QApplication.processEvents()` in parameter constructors (`my_parameters.py`) keeps the UI responsive but introduces risks of re-entrant signal firing before object initialization is complete.

### Model-UI Separation
Some domain models (e.g., `RollWell`) still store UI-specific strings like `errorText` rather than raising structured exceptions.

## 5. Testing Posture
The codebase features a robust test suite (28+ files) with high coverage in:
- **Persistence:** Project round-trips and sidecar validation.
- **State:** Session and runtime consistency.
- **Coordinate Math:** Well transformations and local/global conversions.

**Gaps:** Direct unit testing for safety-critical SPS fixed-width parsing is currently indirect and could be strengthened.

## 6. Forward Recommendations
1. **Renderer Abstraction:** Introduce a `SurveyGraphicsItem` delegate to separate the `RollSurvey` model from its `PyQtGraph` rendering logic.
2. **Parameter Modularization:** Further split `my_parameters.py` by grouping related parameters (e.g., Seed, Well, Grid) into separate modules.
3. **SPS Parser Coverage:** Implement explicit record-level tests for `sps_io_and_qc.py` to protect against field-offset regressions.

---
*This document reflects the state of the codebase following roadmap item 111.*