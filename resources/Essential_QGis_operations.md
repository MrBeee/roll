# Essential QGIS operations with 'Roll'

This brief document describes the various steps required for the Roll-plugin to work together with the main QGIS application in transferring data across, calculating attributes in Roll, and rendering the results in QGIS. 

*The document has been created as a mark-down file (.md) using Typora and is subsequently exported as an html file that preserves the various chapter styles*

## 1. Add a Point Layer

Adding a point layer may be needed to show the requested survey outline from a client (Area of interest), or a prospect outline from the geologist

1. In QGIS: Layer → Add layer → Add delimited text layer

2. Select filename
3. Optionally, give it a layer name that is different from the file name
4. Check File Format
5. Check Record and Field Options (For header lines etc.)
6. Define columns that represent X, Y and optionally Z values
7. Finally, select `Add`
8. Using Full Zoom <img src="mActionZoomFullExtent.svg" alt="mActionZoomFullExtent" style="zoom:100%;" /> (Ctrl+Shift+F) in QGIS, you can now zoom to these points on the map

## 2. Create a Line layer from Points (Vertices)

Once a point layer has been created, you can find them as a series of “small dots” in QGIS. But these “dots” are hard to spot once you zoom out. It is therefore useful to turn these points into connected lines. It is also a step that is required to create (filled) polygons from (*the next step*).

1. In QGIS: Processing → Toolbox will show (or hide) the Processing Toolbox

2. Processing Toolbox **→** Vector creation → Points to path

3. Select Input layer
4. Create closed path (optionally)
5. Then, select `Run` to create a multi-line layer in the order the points have been listed

## 3. Create a (filled) Polygon Layer from Lines

The lines are much better visible than individual points, but you cannot *fill* a line layer, and more importantly you cannot *clip* against a line layer; for this we need ***polygons***. Therefore we need to convert the lines to a polygon.

1. In QGIS: Processing → Toolbox will show (or hide) the Processing Toolbox

2. Processing Toolbox → Vector geometry → Lines to polygons

3. Select Input layer
4. Then, select `Run` to create a filled polygon
5. Double-click the polygon to show the Layer Properties
6. Under `Symbology` adjust the Color to a meaningful color
7. Reduce Opacity to less than 100% to see features in underlying layers
8. You can also add an outline to the polygon. To do so:

​	a.   Add a Symbol Layer by pressing the green `Plus` Icon

​	b.   For symbol layer type select: `Outline: Simple Line` (Sits at the bottom of the list)

​	c.   Select appropriate color and Stroke width

​	d.   Select **`OK`**

9. Finally, in Layers Panel → context menu of the created layer → Make permanent
10. When an outline has been added to the polygon; you may delete the line layer. The line layer served its purpose (creating a polygon) and is no longer needed for the following steps, where we edit the exported src/rec and sps/rps data in QGIS.

## 4. Export src/rec and sps/rps data from Roll to QGIS

1.   In Roll: File → Export to QGIS→ Export Geometry → Export xxx Records to QGIS

2. Alternatively: SPS import tab → Export to QGIS buttons for SPS and RPS records

3. Alternatively: Geometry tab → Export to QGIS buttons for SRC and REC records

4. This will create in-memory (“scratch”) layers in QGIS with the exported data

## 5. Make scratch src/rec and sps/rps layers permanent

To make the exported source and receiver data permanent, and available when you open the QGISproject the next time, follow the steps below

1. in Layers Panel → context menu of the scratch layer → Rename layer
2. Use Ctrl+C to copy the layer name. Hit escape, and do not rename
3. in Layers Panel → context menu of the scratch layer → Make Permanent
4. Alternatively → push the ‘scratch’ button on the right side of the layer’s name
5. Select ESRI Shapefile as file format
6. Select ellipses ( … ) next to filename → navigate to desired file location in the dialog
7. Paste the “filename” from clipboard in the dialog’s `File name` field
8. Select ok. The layer is now permanent, and will be restored if the project is opened again.

## 6. Truncate src/rec and sps/rps point areas in QGIS

In Roll, survey geometry created is created using one or more rectangular blocks. In reality, a survey rarely consists of one or more rectangular shapes, but its outline is truncated according to the concession boundary, or impacted by features such as cities, lakes, etcetera. So, it will be necessary to cut (completely remove) or to switch off (mute) points in certain areas. In QGISthis can be done by checking if points fall inside a polygon. There are two obvious solutions:

#### 6.a. Clipping: the easy way out

Clipping will remove all points outside a selected polygonal area. It is quick and easy, but won’t allow for points to be reinstated at a later stage; gone-is-gone. This can be cumbersome when the survey area is being finetuned over several iterations. Steps are straightforward:

1. Vector → Geoprocessing Tools → Clip …
2. Select Input layer: the layer containing SRC/REC or SPS/RPS points
3. Select Overlay layer: the layer with the boundary polygon
4. Select Run
5. The clipped point layer is now created as a scratch layer.

#### 6.b. Clipping: future proofing your edits

This approach first selects all points that lay inside a polygon, and is followed by turning the selection flag into a permanent attribute value (normally applied to `inuse`)

1. Vector → Research Tools → Select by Location …
2. Select features from: chose appropriate SPS/RPS or SRC/REC point layer
3. For features use: `are within` (and optionally `touch`) relative to the boundary polygon
4. Select the appropriate polygon layer
5. Create a new selection
6. Then, select `Run` to create a selection of points inside a polygon
7. These points will be highlighted in yellow and marked with a red cross
8. Now from the Attributes toolbar → Open Field Calculator
9. Alternatively: First open the Attribute Table ![mActionOpenTable](mActionOpenTable.svg) (F6), and then open the Field Calculator ![mActionCalculateField](mActionCalculateField.svg) (Ctrl+I)
10. Uncheck **`Only update xxx selected feature(s)`**. We need to update **all features**, also those that have not been selected. If you forget to do so, only the already selected records will be altered, and in the unselected fields a NULL value will entered.
11. Now, either:

​	a.   Create a new Field, with a 32-bit integer and use the default field length, or

​	b.   Update an existing integer field, such as the `inuse` field, already created by Roll

12. In the Expression widget type the following:  **`is_selected()`**

This function returns true (=1), when a point record has been selected, and false (=0) otherwise.

13. Press **`OK`** and let the operation run on all point records of the active layer.
14. Upon completion, check that everything went according to plan in the Attribute Table (F6)
15. Now the point layer is ready to be read back into Roll (See par above). 

## 7. Move src/rec and sps/rps points around in QGIS

To make changes to any of the layers you need to enable editing. To do so:

1. in Layers Panel → context menu of the layer with point data from Roll → Toggle editing
2. A pencil icon will appear left of the layer name.
3. The pencil on the digitizing toolbar will also be highlighted.
4. In the digitizing toolbar select the Vertex tool for the current layer. This allows you to manipulate vertices on the active layer using one of the following methods:

​	·    Right click to lock on a feature

​	·    Click and drag to select vertices by rectangle

​	·    Alt+click to select vertices by polygon

​	·    Shift+click/drag to add vertices to selection

​	·    Ctrl+click/drag to remove vertices from selection

​	·    Shift+R to enable range selection

## 8. Read src/rec and sps/rps points from QGIS back into Roll

Once changes have been made to overall source/receiver areas and individual point locations in QGIS(*or when points have been deleted*) it can be useful to read these points back into Roll, to run the analysis `Binning from Geometry`, or alternatively `binning from imported SPS' in the processing menu. To load modified point data back into Roll:

1. In Roll: Geometry tab → `Read from QGIS` buttons (for SRC and REC data separately)
2. In Roll: SPS import tab → `Read from QGIS` buttons (for SPS and RPS data separately)
3. In the layer dialog that pops up:

​	a.   Select the correct point layer from QGIS, containing SPS/RPS and SRC/REC data

​	b.   Check that the CRS of the selected point layer matches that of the Roll project

​	c.   Decide whether (or not) to use a selection field code. Normally this is the `inuse` field.

​	d.   To see what fields are available in a point layer in QGIS, you can:

​                i.   In Layers panel → Select the appropriate layer

​                ii.   In context menu → Open Attribute Table (Shift+F6)

​               iii.   Check column headers. Roll expects the following fields:
​			`line`, `stake`,`index`, `code`, `depth`, `elev` and `inuse`

​               iv.   `inuse` = 0 is used to deselect a point for analysis in Roll

​                v.   Integer fields other than `inuse` may also be used to select active/passive points in Roll. See next paragraph

### 9. Process data - *edited in QGIS* - back in Roll & show results in QGIS

Now that the edited Geometry/SPS data has been copied back to Roll:

1. In Roll’s processing menu → Binning from Geometry or Binning from Imported SPS

2. It is essential to make a well-considered decision whether to use the **Full** or **Basic** binning options

   1. **Full binning** creates the `Rms Offset map`, as well as `|offset|` and `Offset/Azimuth` diagrams and it shows the traces that belong to each bin in the `trace table`, thereby facilitating the `spider plot` in the Layout pane. In order to do full binning, a large array is required that is maintained in a memory mapped file (`*.roll.ana.npy`). If this file becomes too large to keep in random memory, it will result in a lot of swapping to disk, seriously degrading binning performance. So use it wisely, preferably over small areas of interest

   1. **Basic binning** creates the `fold map`, and `min- & max-offsets` 'on the fly' whilst processing source and receiver points. It is relatively fast, but it lacks the above mentioned features.

3. Once binning is completed, you can export the `fold map`, and `min- & max-offsets` to QGIS, using the buttons in the `Display pane`, or using the export options in the `file menu`. 
4. First you need to select the appropriate folder, and then give the file a name (*a name is already suggested*) .
5. Then, automatically, the georeferenced tiff-file will  be imported into the QGIS project
6. Areas where there is no data in the `fold map` or the `min- & max-offset` plots will be fully transparent in QGIS
7. Now you can check ***from within QGIS***, whether the edits, or deleted points, still result in acceptable coverage plots 

