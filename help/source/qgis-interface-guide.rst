Roll and QGIS Interface Guide
=============================

This guide describes the round-trip workflow between Roll and QGIS: exporting
geometry or SPS data to QGIS, editing or filtering it there, and then importing
the updated result back into Roll for renewed analysis.

1. Add a Point Layer
--------------------

Adding a point layer may be needed to show a requested survey outline from a
client or a prospect outline from the geologist.
A convenient way of doing this, is to import a layer from a delimeted text file.
Such a text file may look as follows:

.. csv-table::
   :header: "X", "Y"
   :align: left

   "647285,", "5556357"
   "652514,", "5560823"
   "669808,", "5552982"
   "666808,", "5547061"
   "647285,", "5556357"

The approach is as follows:

#. In QGIS, choose ``Layer -> Add layer -> Add delimited text layer``.
#. Select the file name.
#. Optionally, give the layer a name that is different from the file name.
#. Check the file format.
#. Check the record and field options, including header lines when needed.
#. Define the columns that represent X, Y, and optionally Z values.
#. Select ``Add``.
#. Use Full Zoom (``Ctrl+Shift+F``) in QGIS, zoom to the imported points.

2. Create a Line Layer from Points
----------------------------------

Once a point layer has been created, the points can be hard to spot after you
zoom out. Turning them into connected lines improves visibility and also
prepares them for polygon creation.

#. In QGIS, open ``Processing -> Toolbox``.
#. In the Processing Toolbox, choose ``Vector creation -> Points to path``.
#. Select the input layer.
#. Enable closed path creation if needed.
#. Select ``Run`` to create a multi-line layer in the order the points were
   listed.

3. Create a Filled Polygon Layer from Lines
-------------------------------------------

Lines are easier to see than individual points, but line layers cannot be
filled and cannot be used as clip boundaries. For that, you need polygons.

#. In QGIS, open ``Processing -> Toolbox``.
#. In the Processing Toolbox, choose
   ``Vector geometry -> Lines to polygons``.
#. Select the input layer.
#. Select ``Run`` to create a filled polygon.
#. Double-click the polygon to open Layer Properties.
#. Under ``Symbology``, choose a meaningful color.
#. Reduce opacity below 100 percent so underlying layers remain visible.
#. To add an outline:

   * Add a symbol layer with the green plus icon.
   * For the symbol layer type, choose ``Outline: Simple Line``.
   * Select an appropriate color and stroke width.
   * Select ``OK``.

#. In the Layers panel, open the layer context menu and choose
   ``Make permanent``.
#. After the polygon outline has been added, you can delete the temporary line
   layer because it is no longer needed for the later src/rec and sps/rps
   editing steps.

4. Export src/rec and sps/rps Data from Roll to QGIS
----------------------------------------------------

#. In Roll, choose
   ``File -> Export to QGIS -> Export Geometry -> Export xxx Records to QGIS``.
#. Alternatively, use the export buttons for SPS and RPS records from the ``SPS import`` tab .
#. Alternatively, use the export buttons for SRC and REC records from the ``Geometry`` tab .
#. Roll creates in-memory scratch layers in QGIS with the exported data.

5. Make Scratch src/rec and sps/rps Layers Permanent
----------------------------------------------------

To make the exported source and receiver data permanent and available the next
time the QGIS project is opened:

#. In the Layers panel, open the scratch layer context menu and choose
   ``Rename layer``.
#. Use ``Ctrl+C`` to copy the layer name, then press Escape without renaming.
#. In the layer context menu, choose ``Make Permanent``.
#. Alternatively, use the scratch button on the right side of the layer name.
#. Select ``ESRI Shapefile`` as the file format.
#. Select the ellipsis button next to the file name and navigate to the desired
   file location.
#. Paste the copied layer name into the dialog's ``File name`` field.
#. Select ``OK``. The layer is now permanent and will be restored when the
   project is opened again.

6. Truncate src/rec and sps/rps Point Areas in QGIS
---------------------------------------------------

Survey geometry in Roll is created from rectangular blocks, while the
real survey outline is usually constrained by concession boundaries, cities,
lakes, or similar features. In QGIS you can either clip the points away or mark
them inactive by testing whether they fall inside a polygon.

6.a. Clipping: the Easy Way Out
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Clipping removes all points outside a selected polygonal area. It is quick, but
the removed points are not easy to reinstate later.

#. Choose ``Vector -> Geoprocessing Tools -> Clip``.
#. Select the point layer containing SRC/REC or SPS/RPS points as the input
   layer.
#. Select the boundary polygon as the overlay layer.
#. Select ``Run``.
#. The clipped point layer is created as a scratch layer.

6.b. Clipping: Future-Proofing Your Edits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This approach first selects points inside a polygon and then writes the
selection state into a permanent attribute, usually ``inuse``.

#. Choose ``Vector -> Research Tools -> Select by Location``.
#. Select the appropriate SPS/RPS or SRC/REC point layer under
   ``Select features from``.
#. For the spatial test, choose ``are within`` and optionally ``touch`` relative
   to the boundary polygon.
#. Select the polygon layer.
#. Create a new selection.
#. Select ``Run`` to create a selection of points inside the polygon.
#. Confirm that the selected points are highlighted in yellow and marked with a
   red cross.
#. From the Attributes toolbar, open ``Field Calculator``.
#. Alternatively, open the Attribute Table (``F6``) and then open the Field
   Calculator (``Ctrl+I``).
#. Uncheck ``Only update xxx selected feature(s)``. The calculation must update
   all features, not only the selected ones.
#. Now either:

   * Create a new 32-bit integer field using the default field length.
   * Update an existing integer field, such as Roll's ``inuse`` field.

#. In the expression widget, enter ``is_selected()``.
#. This function returns true (1) when a point record is selected and false (0)
   otherwise.
#. Select ``OK`` and let the calculation run on all point records in the active
   layer.
#. After completion, verify the result in the Attribute Table.
#. The modified point layer is now ready to be read back into Roll.

7. Move src/rec and sps/rps Points in QGIS
------------------------------------------

To change any of the exported layers you must enable editing first.

#. In the Layers panel, open the point layer context menu and choose
   ``Toggle editing``.
#. A pencil icon appears next to the layer name.
#. The pencil on the digitizing toolbar is also highlighted.
#. In the digitizing toolbar, select the Vertex tool for the current layer.
#. Use one of these vertex selection methods:

   * Right-click to lock on a feature.
   * Click and drag to select vertices by rectangle.
   * ``Alt+click`` to select vertices by polygon.
   * ``Shift+click`` or drag to add vertices to the selection.
   * ``Ctrl+click`` or drag to remove vertices from the selection.
   * ``Shift+R`` to enable range selection.

8. Read src/rec and sps/rps Points from QGIS back into Roll
-----------------------------------------------------------

Once changes have been made to overall source and receiver areas or to
individual point locations in QGIS, including deleted points, you can read the
modified point data back into Roll and rerun the analysis.

#. In Roll, use the ``Geometry`` tab ``Read from QGIS`` buttons for SRC and REC
   data.
#. In Roll, use the ``SPS import`` tab ``Read from QGIS`` buttons for SPS and
   RPS data.
#. In the layer dialog that opens:

   * Select the correct QGIS point layer containing the SPS/RPS or SRC/REC
     data.
   * Confirm that the selected point layer CRS matches the Roll project CRS.
   * Decide whether to use a selection field code. This is normally the
     ``inuse`` field.
   * To inspect the available fields in QGIS:

     * Select the layer in the Layers panel.
     * Open its context menu and choose ``Open Attribute Table``
       (``Shift+F6``).
     * Check the column headers. Roll expects the fields ``line``, ``stake``,
       ``index``, ``code``, ``depth``, ``elev``, and ``inuse``.
     * ``inuse = 0`` deselects a point for analysis in Roll.
     * Integer fields other than ``inuse`` can also be used to select
       active or passive points in Roll.

9. Process Data Edited in QGIS Back in Roll and Show Results in QGIS
--------------------------------------------------------------------

After the edited Geometry or SPS data has been copied back into Roll:

#. In Roll's processing menu, run ``Binning from Geometry`` or
   ``Binning from Imported SPS``.
#. Choose carefully between the two binning modes:

   * **Full binning** creates the RMS offset map, offset plots,
     offset/azimuth diagrams, and trace table content needed for the spider
     plot in the Layout pane. It uses a large memory-mapped
     ``*.roll.ana.npy`` array, so performance can degrade significantly on
     large areas.
   * **Basic binning** creates the fold map and minimum and maximum offsets on
     the fly while processing the source and receiver points. It is faster, but
     it does not create the richer offset products provided by full binning.

#. Once binning is complete, export the fold map and the minimum and maximum
   offsets to QGIS using either the buttons in the Display pane or the export
   options in the File menu.
#. Select the appropriate folder and then choose a file name. Roll suggests a
   name automatically.
#. The georeferenced TIFF file is then imported into the QGIS project.
#. Areas with no data in the fold map or minimum and maximum offset plots are
   fully transparent in QGIS.
#. From within QGIS, verify that the edits or deleted points still produce
   acceptable coverage plots.