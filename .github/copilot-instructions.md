# Copilot instructions for Roll (QGIS plugin)

## Big picture architecture
- Plugin entrypoint is `Roll` in [roll.py](roll.py); it wires QGIS menu/toolbar actions and launches `RollMainWindow`.
- Main UI lives in `RollMainWindow` in [roll_main_window.py](roll_main_window.py), created from the Qt Designer file [roll_main_window_base.ui](roll_main_window_base.ui) with tab setup split into [roll_main_window_create_*_tab.py](roll_main_window_create_geom_tab.py) and similar modules.
- The core data model is `RollSurvey` in [roll_survey.py](roll_survey.py): it owns survey geometry (blocks/templates/seeds/patterns), CRS, transforms, and paints via PyQtGraph (`RollSurvey` subclasses `pg.GraphicsObject`).
- Analysis outputs are stored in `RollOutput` in [roll_output.py](roll_output.py); `RollMainWindow.fileLoad()` loads/saves sidecar numpy arrays (e.g., .min.npy/.max.npy) linked to the .roll XML project file.

## Data formats and flows
- Project files are XML “.roll” documents; they serialize the survey hierarchy (blocks/templates/seeds) and output extents. See the example in [Readme.md](Readme.md).

- Roll uses both template-based processing and geometry-based processing. Within a template, one or more shot points are tied to one or more receiver points, and in practice each template usually contains many receiver points. That shared receiver structure can often be exploited when generating geometry or when binning directly from templates.

- Geometry files are the unfolded form of templates. Because templates partly overlap, the same receiver location can appear in multiple templates, but geometry should ultimately store that receiver location only once.

- The many-to-one mapping from shot locations to deduplicated receiver locations is preserved in the relation file. For each shot location, the relation records capture which receiver positions were active for that shot. This template-vs-geometry distinction is central when changing geometry generation, relation handling, or template-binning logic.

- Another reason to use XML is that it allows us to store metadata (e.g., CRS info) as attributes on the root element, which simplifies loading/saving and keeps the project file self-contained. We can also easily extend the format in the future by adding new attributes or elements without breaking backward compatibility.

- Furthermore, the CRS object is stored as a WKT string in the XML, which allows us to preserve all the necessary information about the coordinate reference system without relying on external files or databases. This makes it easier to share project files across different environments and ensures that the survey geometry is always correctly georeferenced when loaded.

- Finally, the CRS object is *unpickable* and not easily represented in a human-readable format, so using WKT in XML is a practical solution for serialization. It strikes a good balance between readability, self-containment, and ease of parsing/loading in Python using libraries like `pyproj` or `osgeo.osr`.

- Seeds and templates use entities called "growList" and "rollList" to define how points are generated. each list contains exactly three entries that define a translation step

- When serializing, we store the seed/grow/roll lists as comma-separated strings in XML attributes; when deserializing, we parse those strings back into lists of tuples. See `seedToXml`/`seedFromXml` and similar methods in [roll_survey.py](roll_survey.py).

- When deserializing, we need to account for the possibility that there are less than three entries in the grow/roll lists (e.g., old project files or user edits). In those cases, we pad the lists with (0,0) entries until they have three items. See `padListToLength` in [roll_survey.py](roll_survey.py). This ensures that the rest of the code can always assume three entries without needing to check lengths.

- This is also the case for RollGrids, which have a "gridList" attribute that follows the same pattern (three entries, padded with (0,0) if needed).

- SPS/RPS/XPS import uses fixed-width formats and numpy structured dtypes defined in [sps_io_and_qc.py](sps_io_and_qc.py) (`pntType1`, `relType2`, etc.). Dialects are configured in [config.py](config.py) (`spsFormatList`, `rpsFormatList`, `xpsFormatList`).

- Elevation and Depth follow the SPS definition:

  - **Elevation**: Located in the receiver (R) or source (S) records, represents the local height relative to a datum (e.g., mean sea level). Normally, we have no information on the datum, so **elevation** can be kept at 0.0, unless actual elevation values are imported from SPS records
  - **Depth**: Represents the vertical distance below the surface. **Depth** values are positive values.

  As a consequence: **real z = `Elev` − `Depth`**.  This means **real z** values are **negative** for anything in the subsurface (below the datum).

- QGIS integration for point I/O happens via `importSpsFromQgis`/`exportSpsToQgis` and similar methods in [roll_main_window.py](roll_main_window.py); those call helper functions in [qgis_interface.py](qgis_interface.py) and [qgis_layer_dialog.py](qgis_layer_dialog.py).

## Worker threads and performance
- Long-running binning/geometry work runs in `QThread` via `BinningWorkerMixin` in [binning_worker_mixin.py](binning_worker_mixin.py) and worker classes in [worker_threads.py](worker_threads.py). Follow the `binFromTemplates`/`binFromSps` pattern: create worker, move to thread, connect `progress`/`message` signals, and finish with `binningThreadFinished`.
- Heavy math and optional JIT live in [functions_numba.py](functions_numba.py); keep `nonumba.py` in mind when adding fallback paths.

## Project-specific conventions
- UI uses PyQtGraph for plotting and progressive painting (see `RollSurvey`’s framebuffer fields and `paint()` logic in [roll_survey.py](roll_survey.py)). Avoid direct painting in the UI thread for large datasets.
- Globals in [config.py](config.py) are used as shared settings (QSettings keys, SPS dialects, LOD thresholds). Prefer updating config lists rather than hardcoding formats.
- Prefer the simplest implementation that preserves behavior. Avoid introducing optimization complexity unless profiling, measured performance, or correctness requirements clearly justify it.
- Formatting: line length 210 and no string normalization (see [pyproject.toml](pyproject.toml)).
- Formatting: use camelCase for method/variable names (e.g., `loadSpsFile`), PascalCase for class names (e.g., `RollSurvey`), and UPPER_SNAKE_CASE for constants (e.g., `DEFAULT_CRS_EPSG`).  

## Workflows (from repo docs)
- Dependencies must be installed in the OSGeo4W/QGIS Python environment: debugpy, numba, numpy, pyqtgraph, rasterio, wellpathpy (see [Readme.md](Readme.md) and [metadata.txt](metadata.txt)).
- Windows helper scripts in the repo root are the active local workflow entry points: `run_tests_qgis.bat`, `run_flake8_qgis.bat`, `run_security_checks_qgis.bat`, `run_sphinx_documentation.bat`, and `run_package_plugin.bat`.
- `run_package_plugin.bat` creates the uploadable plugin zip directly; build Sphinx docs first with `run_sphinx_documentation.bat` when you want the generated HTML included in that zip.

## External documentation
- For PyQGIS and QGIS API questions, prefer the official PyQGIS documentation as the authoritative external reference: https://qgis.org/pyqgis/master/
- `copilot-instructions.md` can point Copilot to that documentation, but it cannot automatically attach a live web page as chat context.
- In current VS Code Copilot Chat, web content is typically referenced by pasting the URL directly into the prompt or by using `#fetch` with the URL.
- If integrated browser sharing or browser tools are available in the current VS Code build, an open documentation page can also be shared with the agent, but that is a separate feature and might be experimental or admin-controlled.
- If the user has already referenced the PyQGIS documentation URL in the prompt or via `#fetch`, prefer that live documentation over weaker secondary sources when answering API-specific questions.
