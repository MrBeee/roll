Installation
============

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   user-guide
   workflows
   template-design
   qgis-interface-guide
   status

.. toctree::
   :maxdepth: 2
   :caption: Developer Documentation

   architecture

Roll is a QGIS plugin for designing and analyzing 3D seismic survey geometries.
The installation details below describe the Python packages that should be available
in the QGIS or OSGeo4W Python environment.

Requirements
------------

* QGIS version 3.34 or later. Note: Roll is compatible with QGIS 4.00 and higher.
* Runs on Windows with the OSGeo4W or QGIS Python environment.

Required Python Packages
------------------------

Please install the following packages before using Roll:

.. csv-table::
   :header: "Package", "Version", "Purpose", "Required ?"
   :align: left

   "``debugpy``", "1.8.17", "Debugging GUI and worker-thread code.", "Optional"
   "``numba``", "0.62.1", "Accelerating numeric kernels.", "Recommended"
   "``numpy``", "1.26.4", "Numeric array processing.", "Required"
   "``pyqtgraph``", "0.13.7", "Plotting and interactive visualization.", "Required"
   "``rasterio``", "1.4.1", "GeoTIFF export.", "Required"
   "``wellpathpy``", "0.5.2", "Well trajectory support.", "Required"

.. warning::

   When upgrading QGIS across Python major versions, these dependencies may need
   to be installed again in the new QGIS Python environment.


Installing Packages
-------------------

Install these packages with ``pip`` from the OSGeo4W command prompt on Windows.
Use ``pip list`` first to detect which packages and versions are already
installed. For example, ``numpy`` should normally already be installed by QGIS.

Start by installing ``rasterio``, because it has quite a few dependencies.
Then install ``numba``, ``pyqtgraph``, and ``wellpathpy`` in that order.

Use the following command pattern:

.. code-block:: bat

   python -m pip install {package_name}=={package_version}

Installing ``rasterio`` also installs or requires packages such as ``affine``,
``attrs``, ``certifi``, ``chardet``, ``charset-normalizer``, ``click``,
``click-plugins``, ``cligj``, and ``colorama``. Installing ``numba`` also
installs the ``llvmlite`` bindings for the LLVM JIT compiler.

Installation notes
------------------

* Packages newer than the versions listed above may contain bug fixes, but may also introduce incompatibilities.
* ``wellpathpy`` 0.5.2 resolved a deprecation warning from 0.5.0 by removing a call to ``import pkg_resources``.
* The plugin has not yet been tested on Linux or macOS.
* The plugin works best on a QHD screen, 2560 x 1440 pixels, or larger.
* As of QGIS 3.32, High-DPI UI scaling issues have arisen. See the `QGIS issue on GitHub <https://github.com/qgis/QGIS/issues/53898>`__.
* As of QGIS 3.34.6, QGIS upgraded Python from version 3.9 to 3.12. This speeds up calculations and solves some security issues. When upgrading from an earlier QGIS version, install the packages listed above again.
* As of Roll 0.4.6, the plugin is compatible with Qt 6. With Qt 6, the High-DPI scaling issues have been resolved.
* As of Roll 0.6.3, the plugin is compatible with QGIS 4.0. Some NumPy attribute names needed to be updated for NumPy 2.0 compatibility.


Changelog
---------

Recent releases are summarized below.

* 2026-07-07 (0.7.9) Created QGis Processing utility to move points. Improved Sphinx documentation.
* 2026-06-09 (0.7.8) Improved presentation CFP analysis, expanded Sphinx documentation.
* 2026-06-09 (0.7.7) Improved CFP implementation, expanded Sphinx documentation.
* 2026-05-22 (0.7.6) Implemented the first step of Sphinx documentation, accessible from F1.
* 2026-05-20 (0.7.5) Updated ``Readme.md`` and completed final flake8 cleanup for plugin upload.
* 2026-05-19 (0.7.4) Updated metadata project information.
* 2026-05-19 (0.7.3) Fixed an experimental geometry-generation bug affecting fixed grids.
* 2026-05-17 (0.7.2) Fixed template-count progress messaging in geometry generation.
* 2026-05-15 (0.7.1) Added the Shift Survey Location dialog and expanded 3D view support.
* 2026-05-06 (0.7.0) Optimized binning from templates and geometry and completed flake8 cleanup.
* 2026-05-01 (0.6.9) Added TWT support to inline and crossline offset displays.
* 2026-04-30 (0.6.8) Added a 3D view for a subset of survey data and faster worker-thread routines.
* 2026-04-22 (0.6.7) Improved SPS import and handling.
* 2026-04-21 (0.6.6) Added max-offset-gap analysis and fixed an interrupted-worker crash.
* 2026-04-16 (0.6.5) Added inline and crossline offsets to offset plots and improved mouse tracking.
* 2026-04-09 (0.6.4) Added a polar diagram for the offset-azimuth histogram.
* 2026-03-10 (0.6.3) Updated code for NumPy 2.0 compatibility in QGIS 4.0.
* 2026-03-08 (0.6.2) Reformatted attribute and variable names for camelCase compatibility.
* 2026-02-25 (0.6.1) Fixed Boolean reading from XML text input.
* 2026-02-23 (0.6.0) Added standalone app support for testing and debugging.
* 2026-02-13 (0.5.9) Added transparent fold-map rendering where fold equals zero.
* 2026-02-10 (0.5.8) Fixed a chart clipboard bug.
* 2026-02-07 (0.5.7) Updated find-and-replace for direct XML editing and fixed enum issues.
* 2026-02-07 (0.5.6) Added preview and print support for XML and charts.
* 2026-02-06 (0.5.5) Fixed azimuth-range handling in the offset-azimuth diagram.
* 2026-02-03 (0.5.4) Improved SPS import and export.
* 2026-01-29 (0.5.3) Fixed pattern management in the property panel.
* 2026-01-28 (0.5.2) Fixed block-boundary coverage gaps in multi-block marine surveys.
* 2025-12-03 (0.5.1) Added flexible SPS format definition and binning without relation files.
* 2025-09-22 (0.5.0) Added progressive painting, moved debugging to debugpy, and used relative well paths.
* 2025-09-22 (0.4.9) Fixed numba-related bugs.
* 2025-09-19 (0.4.8) Added chunked data access for very large memory-mapped analysis files.
* 2025-09-17 (0.4.7) Fixed a crash with very large memory-mapped analysis files.
* 2025-09-12 (0.4.6) Reformatted the codebase for Qt 6 compatibility while retaining Qt 5 support.
* 2025-06-09 (0.4.5) Accepted projects created from SPS data only.
* 2025-06-01 (0.4.4) Changed QGIS SPS point display behavior for most survey types.
* 2025-05-11 (0.4.3) Improved Roll-QGIS transfer workflows and added the HTML help page.
* 2025-03-05 (0.4.2) Refactored parameter management to speed up large property panes.
* 2025-02-22 (0.4.1) Added marine-wizard feathering and selective survey-detail drawing.
* 2025-02-15 (0.4.0) Updated the marine wizard and simplified no-fanning data structures.
* 2025-02-11 (0.3.9) Added the marine wizard and improved layout-tab LOD rendering.
* 2024-11-02 (0.3.8) Improved pattern editing and pattern-tab display.
* 2024-10-22 (0.3.7) Introduced multiple seeds per pattern with backward compatibility.
* 2024-10-15 (0.3.6) Added a pattern tab and pattern-aware stack-response work.
* 2024-10-09 (0.3.5) Moved statistics calculations to extended binning and updated metadata.
* 2024-07-27 (0.3.4) Added the ``inuse`` field to source and receiver points in QGIS.
* 2024-07-24 (0.3.3) Improved the QGIS interface, rasterio CRS handling, and cleared the experimental flag.
* 2024-07-08 (0.3.2) Significantly sped up geometry creation from templates and fixed land-wizard bugs.
* 2024-06-02 (0.3.1) Added a display menu and fixed related usability issues.
* 2024-05-27 (0.3.0) Reduced minimal table widths for easier work on full-HD displays.
* 2024-05-23 (0.2.9) Expanded Numba usage, added RMS-offset plotting, and implemented profiling.
* 2024-05-04 (0.2.8) Added Numba acceleration, stack-response analysis, and histogram views.
* 2024-04-22 (0.2.7) Temporarily removed Numba JIT references due to exception-handling problems.
* 2024-04-21 (0.2.6) Added the Analysis tab with trace tables, offsets, azimuths, and stack response.
* 2024-04-13 (0.2.5) Included TWT values in the trace table and implemented unique fold.
* 2024-04-08 (0.2.4) Improved well-file handling.
* 2024-03-30 (0.2.3) Updated metadata text and dependency descriptions.
* 2024-03-30 (0.2.2) Improved line and stake handling and refactored parameter handling.
* 2024-03-13 (0.2.1) Initial release on the QGIS plugin website.

