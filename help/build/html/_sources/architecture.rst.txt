Architecture
============

Entry Points
------------

The plugin entry point is the ``Roll`` class in ``roll.py``. It integrates with
QGIS, creates plugin actions, and launches the main application window.

The main UI lives in ``RollMainWindow`` in ``roll_main_window.py``. It loads the
Qt Designer UI, wires menu and toolbar actions, and coordinates project,
plotting, property editing, and processing services.

Core Data Model
---------------

The survey model is centered on ``RollSurvey`` in ``roll_survey.py``.

``RollSurvey`` owns:

* survey geometry such as blocks, templates, seeds, and patterns;
* coordinate transforms and CRS handling;
* binning-related state; and
* rendering support for the plotting views.

Project files are stored as XML ``.roll`` documents. The XML keeps the survey
hierarchy together with metadata such as the CRS WKT string.

Processing Model
----------------

Long-running geometry and binning work is pushed onto ``QThread`` workers.
This keeps the GUI responsive while heavy processing runs in the background.

Numeric hot paths live in ``aux_functions_numba.py`` with fallback behavior kept in
mind for environments where Numba is unavailable.

Output and Analysis Storage
---------------------------

Analysis outputs are represented by ``RollOutput`` in ``roll_output.py``.
Full binning writes detailed per-trace information to memory-mapped analysis
files so large datasets can be processed and inspected without forcing a full
in-memory load.

UI Composition
--------------

The main window delegates substantial UI setup to focused modules such as the
``roll_main_window_create_*`` files. Additional controllers and services handle
stateful concerns like:

* property-panel behavior;
* action enablement;
* plotting navigation and redraw reuse;
* project loading and saving; and
* import and export workflows.

QGIS Integration
----------------

QGIS integration includes:

* importing and exporting source and receiver geometry;
* exporting rasters and outlines into the active QGIS project; and
* supporting point-layer round-trips for editing outside Roll.

The plugin therefore sits between a compact internal survey definition and the
more explicit geometry and raster products consumed in QGIS.

Documentation Boundary
----------------------

The Sphinx documentation in ``help/source`` is intended to provide maintainable
project documentation. The QGIS round-trip guide is maintained directly in the
reStructuredText sources so it can be updated alongside the rest of the help.