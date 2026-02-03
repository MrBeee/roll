# Copilot instructions for Roll (QGIS plugin)

## Big picture architecture
- Plugin entrypoint is `Roll` in [roll.py](roll.py); it wires QGIS menu/toolbar actions and launches `RollMainWindow`.
- Main UI lives in `RollMainWindow` in [roll_main_window.py](roll_main_window.py), created from the Qt Designer file [roll_main_window_base.ui](roll_main_window_base.ui) with tab setup split into [roll_main_window_create_*_tab.py](roll_main_window_create_geom_tab.py) and similar modules.
- The core data model is `RollSurvey` in [roll_survey.py](roll_survey.py): it owns survey geometry (blocks/templates/seeds/patterns), CRS, transforms, and paints via PyQtGraph (`RollSurvey` subclasses `pg.GraphicsObject`).
- Analysis outputs are stored in `RollOutput` in [roll_output.py](roll_output.py); `RollMainWindow.fileLoad()` loads/saves sidecar numpy arrays (e.g., .min.npy/.max.npy) linked to the .roll XML project file.

## Data formats and flows
- Project files are XML “.roll” documents; they serialize the survey hierarchy (blocks/templates/seeds) and output extents. See the example in [Readme.md](Readme.md).
- SPS/RPS/XPS import uses fixed-width formats and numpy structured dtypes defined in [sps_io_and_qc.py](sps_io_and_qc.py) (`pntType1`, `relType2`, etc.). Dialects are configured in [config.py](config.py) (`spsFormatList`, `rpsFormatList`, `xpsFormatList`).
- QGIS integration for point I/O happens via `importSpsFromQgis`/`exportSpsToQgis` and similar methods in [roll_main_window.py](roll_main_window.py); those call helper functions in [qgis_interface.py](qgis_interface.py) and [qgis_layer_dialog.py](qgis_layer_dialog.py).

## Worker threads and performance
- Long-running binning/geometry work runs in `QThread` via `BinningWorkerMixin` in [binning_worker_mixin.py](binning_worker_mixin.py) and worker classes in [worker_threads.py](worker_threads.py). Follow the `binFromTemplates`/`binFromSps` pattern: create worker, move to thread, connect `progress`/`message` signals, and finish with `binningThreadFinished`.
- Heavy math and optional JIT live in [functions_numba.py](functions_numba.py); keep `nonumba.py` in mind when adding fallback paths.

## Project-specific conventions
- UI uses PyQtGraph for plotting and progressive painting (see `RollSurvey`’s framebuffer fields and `paint()` logic in [roll_survey.py](roll_survey.py)). Avoid direct painting in the UI thread for large datasets.
- Globals in [config.py](config.py) are used as shared settings (QSettings keys, SPS dialects, LOD thresholds). Prefer updating config lists rather than hardcoding formats.
- Formatting: line length 210 and no string normalization (see [pyproject.toml](pyproject.toml)).
- Formatting: use camelCase for method/variable names (e.g., `loadSpsFile`), PascalCase for class names (e.g., `RollSurvey`), and UPPER_SNAKE_CASE for constants (e.g., `DEFAULT_CRS_EPSG`).  

## Workflows (from repo docs)
- Dependencies must be installed in the OSGeo4W/QGIS Python environment: debugpy, numba, numpy, pyqtgraph, rasterio, wellpathpy (see [Readme.md](Readme.md) and [metadata.txt](metadata.txt)).
- Tests run via `make test` (uses nosetests and expects a QGIS Python env); translation tasks use `make transup`/`make transcompile` (see [Makefile](Makefile)).
- Plugin packaging/deploy uses `make deploy`/`make zip` (see [Makefile](Makefile)).
