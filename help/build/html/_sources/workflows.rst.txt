Workflows
=========

Template-Based Survey Design
----------------------------

This is the core Roll workflow.

1. Create a new project or load an existing ``.roll`` file.
2. Define one or more blocks and templates.
3. Add source and receiver seeds, then configure grow and roll lists.
4. Review the survey layout in the main plotting views.
5. Save the project before running full binning, because Roll needs a named
   analysis file for memory-mapped output.
6. Run basic or full binning from the Processing menu.
7. Inspect the generated maps, plots, and trace information.
8. Export outputs to QGIS or GeoTIFF where needed.

This path starts from the compact survey definition and is generally the best
choice when you are still designing the geometry rather than reviewing an
existing acquisition.

Land and Marine Wizards
-----------------------

Roll includes separate wizards for land and marine survey creation.

The land wizard supports several survey families, including orthogonal,
parallel, slanted, brick, and zigzag layouts.

The marine wizard is specialized for towed-streamer acquisition and considers
turning-radius constraints when building race-track style acquisition plans.

SPS-Driven Workflow
-------------------

Roll can also work from SPS data instead of from a template-first project.

1. Import SPS, RPS, and XPS style data through the file menu.
2. Select or configure the correct fixed-width SPS dialect.
3. Set the CRS and local survey grid.
4. Export the resulting source and receiver layers to QGIS if needed.
5. Run geometry-based analysis inside Roll.

This path is useful when the survey already exists in legacy acquisition files
and the main goal is QC, visualization, or re-analysis rather than design.

Because Roll treats imported SPS data much like internally generated geometry,
you can still export points to QGIS, perform edits there, and bring the changes
back into Roll for analysis.

QGIS Round-Trip Editing
-----------------------

Generated geometry and imported SPS data can be exported to QGIS. In QGIS,
points can be moved, deleted, or marked inactive and then imported back into
Roll for renewed analysis.

This workflow is documented in more detail in the ``Roll and QGIS Interface
Guide`` page in this Sphinx site.

3D and Well-Oriented Work
-------------------------

Roll also supports a 3D view for a subset of the survey layout, including
non-rolling seeds, grids, circles, spirals, and well-related geometry. This is
particularly relevant for dipping-plane, well, and VSP-style use cases.

Packaging the Documentation
---------------------------

When you want the Sphinx documentation included in the plugin zip, run these
steps from the plugin root:

1. ``run_sphinx_documentation.bat``
2. ``run_package_plugin.bat``

The packaging script copies the built ``help/build/html`` output into the zip
when it is present.