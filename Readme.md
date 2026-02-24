# Roll

## Seismic survey design plugin for QGIS


### 1	Preamble, external dependencies

Roll depends on the following Python libraries that need to be installed separately 
In the **OSGeo4W Command Shell**, type: ```pip install --upgrade 'library-name'```,  where --upgrade forces the installation of the latest version

| Library    | Minimum Version | Description (purpose)                                        |
| :--------- | :-------------- | :----------------------------------------------------------- |
| debugpy    | 1.8.17          | Needed if you want to debug code that runs in GUI- and worker threads |
| numba      | 0.62.1          | ***Significantly*** speeds up some numpy calculations        |
| numpy      | 1.26.4          | Array and matrix manipulation                                |
| pyqtgraph  | 0.13.7          | Plotting of vector and raster data                           |
| rasterio   | 1.4.1           | Export of figures as GeoTiff  files                          |
| wellpathpy | 0.5.0           | Position sensors  & sources in a well trajectory (VSPs etc.) |



### 2	Introduction

**Roll** is a plugin aimed at designing 3D seismic survey geometries, using a template based approach.

- Each survey consists of one or more (rectangular) *blocks*
- Each block contains at least two *templates* 
  - One for *receiver* layout
  - One for *source* layout
- Each template contains one or more seeds
- A seed defines the starting location of a single *source / receiver*
- Each seed can be **grown** up to three times
  - The 1st grow step changes a seed position into a line segment (sequence) of positions
  - The 2nd grow step changes a line segment into a multitude (grid) of lines 
  - The 3rd grow step changes the grid into a sequence of (intertwined) grids
- The seeds, combined with their grow steps, define the active sources and receivers in a template
- Each template can be **rolled**  in up to three directions, for instance:
  - Firstly in the inline direction, at source line intervals
  - Secondly in the crossline direction, at receiver line intervals
  - Optionally at a skew angle for fancy designs

The hierarchy in this approach is reflected in the xml-based survey-file structure: 

```xml
<block_list>
    <block>
        <name>Block-1</name>
        <borders>
           <src_border xmin="-20000.0" xmax="20000.0" ymin="-20000.0" ymax="20000.0"/>
           <rec_border xmin="0.0" xmax="0.0" ymin="0.0" ymax="0.0"/>
        </borders>
        <template_list>
            <template>
                <name>Template-1</name>
                <roll_list>
                    <translate n="10" dx="0.0" dy="200.0"/>
                    <translate n="10" dx="250.0" dy="0.0"/>
                </roll_list>
                <seed_list>
                    <seed x0="5975.0" src="True" y0="625.0" argb="#77ff0000" typno="0" azi="False" patno="0">
                        <name>Src-1</name>
                        <grow_list>
                            <translate n="1" dx="250.0" dy="0.0"/>
                            <translate n="4" dx="0.0" dy="50.0"/>
                        </grow_list>
                    </seed>
                    <seed x0="0.0" src="False" y0="0.0" argb="#7700b0f0" typno="0" azi="False" patno="1">
                        <name>Rec-1</name>
                        <grow_list>
                            <translate n="8" dx="0.0" dy="200.0"/>
                            <translate n="240" dx="50.0" dy="0.0"/>
                        </grow_list>
                    </seed>
               </seed_list>
            </template>
        </template_list>
    </block>
</block_list>
```

*Excerpt from a .roll file*

Once the geometry has been defined, a binning analysis can be done directly using the template-based approach. As a result:

- A **fold map** is created that shows (offset dependent) fold
- A **minimum offset map** is created that shows minimum offsets coverage
- A **maximum offset map** is created that show maximum offsets coverage

- A **RMS offset increment map** is created that shows regularity of offset increments

As the survey project-file always contains a (projected) coordinate reference system (CRS) the analysis maps can be exported to the current QGIS project as a georeferenced Tiff (GeoTiff) file. These files can also be exported as a standalone GeoTiff file from the  File -> Export menu.

To use **full binning** from the Processing menu, the project needs to be saved first, as a (large, memory mapped) **analysis file** is created that contains the complete binning information. Think of: 

- line & stake numbers, 
- src (x, y), 
- rec(x, y), 
- cmp(x, y), 
- TWT, 
- offset, 
- azimuth, and 
- uniqueness (for unique fold)

Once this step has been completed, additional analysis information becomes available in the **Layout** tab:

- An **rms offset map** that shows the rms offset increments in each bin (lower is better)
- A **spider diagram**, that is overlaid on the layout map, showing start- and end-points of all traces in a single (selected) bin

In the **Analysis** tab, the following information then becomes available:

- A **trace table**, showing the information from the analysis file
- **Radial offsets** shown for a line in the **inline** direction
- **Radial offsets** shown for a line in the **x-line** direction
- **Source -> receiver azimuths** shown for a line in the **inline** direction
- **Source -> receiver azimuths** shown for a line in the **x-line** direction
- **Kr stack response** shown for a line in the **inline** direction
- **Kr stack response** shown for a line in the **x-line** direction
- **Kxy stack response** shown for a **single bin**
- **|Offset| histogram** for all traces in the selected binning area
- **Offset/azimuth histogram** for all traces in the selected binning area, in steps of 5 degrees

The templates can be converted into geometry files, consisting of (a) a source file, (b) a receiver file and (c) a relation file, similar how this is managed in the SPS format. The source- and receiver points from the source and receiver files can be exported to the current QGIS project as an ArcGIS Shape file, where these points can be inspected, moved around or deleted. Edited points can be re-imported into Roll to assess the impact on fold, etc.

The geometry files themselves can also be exported as SPS-files.

Note: the Model/View approach used by Qt (that takes care of all the widgets in QGIS) allows for fairly large tables. Nevertheless, for each row in a table view, circa 12 bytes are allocated per row. For very large tables, QGIS will simply crash without any warning. As a result the GUI will 'hang' and you may lose all your work. For that reason, the trace table is currently limited to 50 million traces.  Larger tables can still be used okay, they are just not shown in the trace table. If you need detailed information on traces that belong to a bin area somewhere in a large survey, the current work around is to select a smaller binning area, such that the total number of traces (Nx x Ny x Fold) is less than 50 million. A 'proper' solution is being worked on.

The plugin works best using one or two QHD Screens (2560 x 1440 pixels) or larger. As of QGIS V3.32 High DPI UI scaling issues have arisen. See the following discussion on GitHub <a href="https://github.com/qgis/QGIS/issues/53898">here</a>. The Help menu in Roll shows how you can mitigate against these issues. 

As of version 3.34.6, QGIS upgraded Python from V3.9 to to V3.12 This change speeds up calculations and solves some security issues.  But when <i>**upgrading**</i> from an earlier QGIS version, it requires installing all the dependencies ***again***. See chapter 4 below for a list of external dependencies.

As of version 0.3.3 Roll has a 'working' interface with QGIS, and is able to read back points that have been changed in QGIS. This involves either moving points around, or setting a flag whether the point is in use. The integer Field Code that is used to decide whether a point is active or not can be selected in the Layer Selection Dialog. Points that are 'inactive' are shown in grey in the geometry tables and in the Layout view. They do not contribute is the fold (etc.) analysis.

The interface still requires a few tweaks, but as of version 3.3.3 Roll is no longer considered an experimental plugin.



### 3	Import of SPS data

If (legacy) SPS data is available, this can be imported from the file menu, and is treated in the same way as the internally generated geometry files. This makes it handy to analize survey performance based solely on SPS-data. This SPS data can also be exported as shapefiles to the current QGIS project.

As there are many flavors of SPS files, a number varieties have been predefined, which can be selected in the SPS Import Dialog. The SPS import dialog also allows for creating additional SPS 'dialects', based on the one that is currently selected. Names of these 'dialects' can be altered and their columns for lines, points, northing, easting, etc. can easily be modified. Results are permanently stored in the registry. In case of a mishap, the database can be restored to the original content

**Initially**, the plugin was intended to work from a ***survey template*** (*preferably generated by the land- or marine survey wizard*), followed by analysis of the performance of such a template. Subsequently, the generation of geometry files also allowed for export of the source and receiver points to QGIS, where these points could be edited, for re-import into Roll for further analysis.

**Currently**, it is also possible to start a new (blank) project by ***importing SPS data***, thereby selecting the correct CRS, and defining the local survey grid, before source and receiver points are exported to QGIS, in the same way as is done with the geometry files. This means you can work from ***standalone SPS data***, import this into Roll for analysis, and visualize the point locations in QGIS. Hopefully this makes the plugin more versatile.



### 4	Editing a survey file

As it is cumbersome to manipulate xml-data directly, the user is helped at two levels:

1. Creating a new project can be done using a **survey wizard**. At present there is one wizard suitable to generate templates for land seismic and OBN-data. A marine wizard is in the making.
2. Parameters can be modified added or deleted from the **property pane**. Behind the scenes, this updates the xml-structure, which is always visible from the Xml-tab in the main window. 

But in case you get very familiar with the xml-structure, you could also edit the xml data directly and apply these changes using the '**Refresh Document**' toolbar button.



### 5	Interaction with QGIS

The generated Geometry points, the imported SPS data, as well as the analysis plots can all be exported to QGIS. In QGIS, source- and receiver points can be moved, deleted, or marked as 'inactive'. These modifications can be loaded back into Roll, for a renewed analysis.   This process is described in much more detail in an html file, accessible from the Help menu in Roll.



### 6	Status

On 8 Feb 2024, the first release of Roll has been published on [GitHub](https://github.com/MrBeee/roll). Initial release on the QGIS plugin website occurred on 13 March 2024.

As of version 3.3.3 Roll is no longer considered an experimental plugin. But there is still some functionality left to be added. See 'To Do' section.

Furthermore, see the 'Changelog' for already implemented functionality. Any [Issues](https://github.com/MrBeee/roll/issues) or [pull requests](https://github.com/MrBeee/roll/pulls) can be raised through the GitHub repository.



### 7	To Do

- Improve Roll's analysis capabilities
- Make processing of Geometry & SPS data more robust
- Use multiprocessing instead of a single worker thread to speed up background tasks
- Consider using a relational database instead of numpy arrays for geometry tables



### 8	Changelog

- 2026-02-23 (0.6.0) Made Roll a 'standalone' app for testing and debugging purposes. Raised minimum QGIS version to 3.34
- 2026-02-13 (0.5.9) Made fold-map transparent for areas where fold = 0. Added context menu in SPS and Geometry tables, to edit 'in-use' status
- 2026-02-10 (0.5.8) Fixed a small bug in copying charts to the clipboard
- 2026-02-07 (0.5.7) Updated 'Find and Replace' dialog for direct Xml editing. Fixed enum bugs to ensure Qt6 compatibility
- 2026-02-07 (0.5.6) Added 'Preview & Print' to the file menu for the xml file and the pyqtgraph charts. Implemented copy & paste for pyqtgraph charts
- 2026-02-06 (0.5.5) Fixed bug in azimuth range in Offset/Azimuth diagram
- 2026-02-03 (0.5.4) Improved import and export of SPS data
- 2026-01-29 (0.5.3) Fixed pattern management (adding/moving/renaming/removing patterns) in the Property panel
- 2026-01-28 (0.5.2) Fixed bug resulting in coverage gaps at block boundaries for multi block (marine) surveys, when working from geometry data
- 2025-12-03 (0.5.1) Updated SPS file import and implemented flexible SPS format definition by the end user. 
  - Binning can now be done in absence of a relation file (*.xps), using offset limits solely
- 2025-09-22 (0.5.0) Some significant changes; 
  - progressive painting, keeps user interface alive while painting large survey objects; 
  - debugging uses Debugpy instead of Debugvs; 
  - well files accessed through relative paths
- 2025-09-22 (0.4.9) Small bug fixes related to using - *or not using* - numba
- 2025-09-19 (0.4.8) Use chunked data-access when using very large memory-mapped analysis files
- 2025-09-17 (0.4.7) Removed a bug that caused QGIS to crash, when using very large memory-mapped analysis files
- 2025-09-12 (0.4.6) The code has been reformatted to be compatible with Qt6. It should still be backwards compatible with Qt5  
- 2025-06-09 (0.4.5) Accept projects that are created from SPS-data only (i.e. projects that are not template-based)
- 2025-06-01 (0.4.4) changed the way SPS source points are shown in QGIS: (point, line) has become (line, point) except for parallel/NAZ surveys
- 2025-05-11 (0.4.3) several improvements in transferring data from Roll to QGis and vice versa. Created html help page in help menu
- 2025-03-05 (0.4.2) refactoring of parameter management code, speeding up display in property pane of surveys with many blocks & seed points
- 2025-02-22 (0.4.1) implemented feathering in Marine Wizard; enabled selective drawing of survey details (lines and/or points and/or patterns)
- 2025-02-15 (0.4.0) updated Marine Wizard; simplifying data structure in case there's no streamer fanning, significantly speeding up property editing
- 2025-02-11 (0.3.9) implemented Marine Wizard for streamer surveys and improved Level of Detail (LOD) rendering in Layout pane
- 2024-11-02 (0.3.8) improved editing patterns in Property pane and displaying hem in the Pattern tab. 
- 2024-10-22 (0.3.7) introduced multiple seeds per pattern, allowing for very complex pattern layout. Ensured backwards compatibility.  
- 2024-10-15 (0.3.6) added 'pattern' tab for pattern display & analysis. Added convolution with patterns to kx-ky stack response. Fixed an assertion bug in Land Wizard.  
- 2024-10-09 (0.3.5) moved statistics calculations to extended binning. Updated metadata.txt to describe installation of plugin
- 2024-07/27 (0.3.4) "inuse" field added to src & rec points in QGIS. Categorized Symbol Renderer implemented to display used/unused points in QGIS.
- 2024-07/24 (0.3.3) Interface with QGIS improved. Display active / inactive points separately. Fixed rasterio CRS bug. Cleared experimental flag.
- 2024-07/08 (0.3.2) Geometry creation from templates now runs significantly faster. Fixed some bugs in Land Survey Wizard.
- 2024-06-02 (0.3.1) Created a 'display' menu. This allows for closing the display pane, when using *smallish* full HD displays. Fixed some bugs.
- 2024-05-27 (0.3.0) reduced minimal width of Geometry & SPS tables, in order to make working with a *smallish* full HD (1920x1080) screen easier.
- 2024-05-23 (0.2.9) expanded numba @jit functions, added rms-offset plot on Layout tab. Fixed some bugs. Implemented function profiling.
- 2024-05-04 (0.2.8) implemented numba @jit, to speed up calculations. Added stack-response analysis and |O| & O/A Histograms. Fixed some bugs.
- 2024-04-22 (0.2.7) removed all numba @jit references, as exception handling with numba causes problems. Will revisit later.
- 2024-04-21 (0.2.6) added 'Analysis' tab, containing:
  - The Trace table (full binning results)
  - In-/ and X-line offsets
  - In-/ and X-line azimuths
  - In-/ and X-line stack response
- 2024-04-13 (0.2.5) included TWT values in trace table and implemented 'Unique Fold' capability.
- 2024-04-08 (0.2.4) improved handling of well-files.
- 2024-03-30 (0.2.3) updated metadata.txt (a) about text and (b) dependencies.
- 2024-03-30 (0.2.2) improved handling of line- and stake numbers; refactoring of parameter handling.
- 2024-03-13 (0.2.1) Initial release on the QGIS plugin website.
