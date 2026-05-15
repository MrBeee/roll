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
| wellpathpy | 0.5.2           | For sensors  & sources in a well trajectory (VSPs etc.)      |



### 2	Introduction

**Roll** is a plugin aimed at designing 3D seismic survey geometries, using a template based approach.

- Each survey consists of one or more (rectangular) *blocks*

- Each block contains one or more templates 

- Each template contains at least ***two*** seeds
  - One seed is required for *receiver* layout
  - One seed is required for *source* layout

    *Within a template **all** available sources shoot into **all** available receivers in that template.*
  
    *Additional source- and/or receiver seeds my be defined in each template.* 
  
- A seed defines the starting location of a single *source / receiver*

- Each seed can be **grown** up to *three* times
  - The 1st grow step changes a seed position into a line segment (sequence) of positions
  - The 2nd grow step changes a line segment into a multitude (grid) of lines 
  - The 3rd grow step changes the grid into a sequence of (intertwined) grids

- The seeds, combined with their grow steps, define the active sources and receivers in a template

- Each template can be **rolled**  in up to *three* directions, for instance:
  - Firstly in the inline direction, at source line intervals
  - Secondly in the crossline direction, at receiver line intervals
  - Optionally at a skew angle for fancy designs (e.g. using a slanted design, or a brick design)

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

When using '**Full Binning**' the following figures are also created when binning has completed:
- A **RMS offset increment map** is created that shows regularity of offset increments
- A **Max offset gap map** is created that shows the largest offset gap for each bin
- A **spider diagram**, that is overlaid on the layout map, showing start- and end-points of all traces for a particular bin

As the survey project-file always contains a (projected) coordinate reference system (CRS) the analysis maps can be exported to the current QGIS project as a georeferenced Tiff (GeoTiff) file. These files can also be exported as a standalone GeoTiff file from the  File -> Export menu.

To use '**Full binning**' from the Processing menu, the project first needs to be saved, because a named memory-mapped **analysis file** needs to be created, that contains the complete binning information for each bin. Think of: 

- line & stake numbers, 
- src (x, y, z), 
- rec(x, y, z), 
- cmp(x, y, z), 
- TWT [ms], 
- offset, 
- azimuth, and 
- uniqueness (for unique fold)

Using  the **Analysis** tab, the following information then becomes available:

- A **trace table**, showing the information from the analysis file
- **Offsets** shown for a line in the **inline** direction (radial, inline, x-line or TWT)
- **Offsets** shown for a line in the **x-line** direction (radial, inline, x-line or TWT)
- **Source -> receiver azimuths** shown for a line in the **inline** direction
- **Source -> receiver azimuths** shown for a line in the **x-line** direction
- **Kr stack response** shown for a line in the **inline** direction
- **Kr stack response** shown for a line in the **x-line** direction
- **Kxy stack response** shown for a **single bin**
- **|Offset| histogram** for all traces in the selected binning area
- **Offset/azimuth histogram** for all traces in the selected binning area, in steps of 5 degrees

The templates can be converted into **geometry files**, consisting of (a) a source file, (b) a receiver file and (c) a relation file, similar how this is managed in the SPS format. The source- and receiver points from the source and receiver files can be exported to the current QGIS project as an ArcGIS Shape file, where these points can be inspected, moved around or deleted. Edited points can be re-imported into Roll to assess the impact on fold, etc.

The geometry files themselves can also be exported as SPS-files.

* As of version 3.34.6, QGIS upgraded Python from V3.9 to to V3.12 This change speeds up calculations and solves some security issues.  But when <i>**upgrading**</i> from an earlier QGIS version, it requires installing all the dependencies ***again***. See chapter 4 below for a list of external dependencies.

* As of version 0.3.3 Roll has a 'working' interface with QGIS, and is able to read back points that have been changed in QGIS. This involves either moving points around, or setting a flag whether the point is in use. The integer Field Code that is used to decide whether a point is active or not can be selected in the Layer Selection Dialog. Points that are 'inactive' are shown in grey in the geometry tables and in the Layout view. They do not contribute is the fold (etc.) analysis. As of version 0.3.3 Roll is no longer considered an experimental plugin.

* As of version 0.6.3 Roll is compatible with QGIS 4.0, and therefore with PyQt6 and numpy 2.0. This was done as part of a refactoring effort aided by the [GitHub Copilot](https://code.visualstudio.com/docs/copilot/overview) in VS Code. A number of LLM models are available in Copilot, some of which tried hard to wreck my code. 

* In version 0.6.4, a polar diagram was added for the offset/azimuth histogram and refactoring of code continued. The code for the polar diagram was completed using '[vibe coding](https://en.wikipedia.org/wiki/Vibe_coding)'. This agent driven approach was also used to develop a series of unit tests in the test subdirectory. As of version 5.4 GPT has become stable and trustworthy enough to work in agent mode, optimizing the source code and implementing new features. This LLM was also used consistently during code refactoring

  >You may remember, when Plug-and-Play (PnP) was introduced in the early 1990s to manage hardware updates, it did not always work out-of-the-box (understatement) and people often called it "Plug-and-Pray". With AI coding at the moment, we are at the stage where software development has turned into "Prompt-and-Pray".

  May first, and working on Roll, I heard a good quote about AI on a BBC radio programme:

  >You can outsource your thinking, but you cannot outsource your understanding

* In version 0.6.8 a 3D view has been added to the Layout tab, for a subset of survey geometry data. This is in particular useful for working with well-based seeds, think of VSPs



### 3	Import of SPS data

If (legacy) SPS data is available, this can be imported from the file menu, and is treated in the same way as the internally generated geometry files. This makes it handy to analize survey performance based solely on SPS-data. This SPS data can also be exported as shapefiles to the current QGIS project.

As there are many flavors of SPS files, a number varieties have been predefined, which can be selected in the SPS Import Dialog. The SPS import dialog also allows for creating additional SPS 'dialects', based on the one that is currently selected. Names of these 'dialects' can be altered and their columns for lines, points, northing, easting, etc. can easily be modified. Results are permanently stored in the registry. In case of a mishap, the database can be restored to the original content

**Initially**, the plugin was intended to work from a ***survey template*** (*preferably generated by the land- or marine survey wizard*), followed by analysis of the performance of such a template. Subsequently, the generation of geometry files also allowed for export of the source and receiver points to QGIS, where these points could be edited, for re-import into Roll for further analysis.

**Currently**, it is also possible to start a new (blank) project by ***importing SPS data***, thereby selecting the correct CRS, and defining the local survey grid, before source and receiver points are exported to QGIS, in the same way as is done with the geometry files. This means you can work from ***standalone SPS data***, import this into Roll for analysis, and visualize the point locations and the corresponding fold map in QGIS. Hopefully this makes the plugin more versatile.



### 4	Editing a survey file

As it is cumbersome to manipulate xml-data directly, the user is helped at two levels:

1. Creating a new project can be done using a **survey wizard** for either **marine** (towed streamer) of **land/OBC** templates. 
2. Parameters can be modified added or deleted from the **property pane**. Behind the scenes, this updates the xml-structure, which is always visible from the Xml-tab in the main window. 

But in case you get very familiar with the xml-structure, you can also inspect and edit the xml data directly and apply any changes using the '**Refresh Document**' toolbar button.



### 5	Interaction with QGIS

The generated Geometry points, the imported SPS data, as well as the analysis plots can all be exported to QGIS. In QGIS, source- and receiver points can be moved, deleted, or marked as 'inactive'. These modifications can be loaded back into Roll, for a renewed analysis.   This process is described in much more detail in an html file, accessible from the Help menu in Roll.



### 6	Status

On 8 Feb 2024, the first release of Roll has been published on [GitHub](https://github.com/MrBeee/roll). Initial release on the QGIS plugin website occurred on 13 March 2024.

As of version 0.3.3 Roll is no longer considered an experimental plugin. But there is still some functionality left to be added. See 'To Do' section.

As of version 0.4.6 Roll is compatible with Qt6.0 and therefore ready to work with QGIS 4.0.

As of version 0.7.0 improvements in `binning from templates` and `binning from geometry` have been implemented using `Numba`. Due to inherent dispersed writing of trace data in the binning analysis file, the approach of multiprocessing has been shelved. Use of a relational database was dropped as well, as a relational database would replace the memory mapped approach with row encoding, update statements, index maintenance, and transaction overhead on a workload that is fundamentally numeric-array-heavy.

Finally, see the 'Changelog' for already implemented functionality. Any [Issues](https://github.com/MrBeee/roll/issues) or [pull requests](https://github.com/MrBeee/roll/pulls) can be raised through the GitHub repository.

**Note**: the Model/View approach used by Qt (that takes care of all the widgets in QGIS) allows for fairly large tables. Nevertheless, for each row in a table view, circa 12 bytes are allocated. For very large tables, QGIS will simply crash without any warning. As a result the GUI will 'hang' and you may lose all your work. For large files, the trace table is therefore implemented in a chunked manner, showing chunks of 1 milion traces at the time. Buttons have been added to navigate through these chunks. You may also use the <i>**spider navigation**</i> based on ALT+Arrow keys to move to the next line and stake numbers (or make larger jumps using Ctrl and/or Shift keys in combination with ALT). 

The plugin works best using one or two QHD Screens (2560 x 1440 pixels) or larger. As of QGIS V3.32 High DPI UI scaling issues have arisen. See the following discussion on GitHub <a href="https://github.com/qgis/QGIS/issues/53898">here</a>. The Help menu in Roll shows how you can mitigate against these issues. 

#### 6.1	Project size

On May 6th 2026, the Addin contained `34,316` Source-Lines-Of-Code (SLOC) across `140` files. 

##### Breakdown:

1. Production Python: `27,482` SLOC across `109` files
2. Test Python: `6,834` SLOC across `31` files
3. All Python: `34,316` SLOC across `140` files

##### For context:

1. Total Python lines including blanks and comments: `50,749`
2. Non-blank Python lines: `40,551`
3. The single `.ui` file adds `1,703` non-blank XML lines, but isn't included in the SLOC

This SLOC count excludes blank lines and lines starting with `#`, but still counts lines that contain code plus an inline comment.



### 7	To Do

- Improve Roll's analysis capabilities; think of multiple suppression and DMO smear
- Expand the 3D Layout View, introduced in version 0.6.8



### 8	Changelog
- 2026-05-15 (0.7.1) Added "Shift Survey Location..." dialog. Expanded 3D view for Subset of survey data. Updated Marine Survey Wizard for optimal x-line bin size.
- 2026-05-06 (0.7.0) Optimization of binning from templates and binning from geometry. Completed Flake8 code clean up.
- 2026-05-01 (0.6.9) Added TWT option to inline and x-line offset displays. Started to fleece code using Flake8.
- 2026-04-30 (0.6.8) Added 3D view for Subset of survey data. Enabled by "Use experimental code" in the Settings dialog. Implemented faster worker thread routines, enabled by the same flag
- 2026-04-22 (0.6.7) Improved import and handling of SPS files.
- 2026-04-21 (0.6.6) Added 'Max Offset Gap' analysis. Fixed bug crashing app when worker thread was interrupted. Improved readability of items in Parameter tree (property pane).
- 2026-04-16 (0.6.5) Added inline and x-line offsets to |offset| plots and mouse tracking in statusbar for all plots. Continued refactoring code.
- 2026-04-09 (0.6.4) Added a polar diagram for the offset/azimuth histogram and continued refactoring of code
- 2026-03-10 (0.6.3) Some numpy attribute names needed to be changed for NumPy 2.0 compatibility in QGIS 4.0
- 2026-03-08 (0.6.2) Reformatting of code to make attribute & variable names compatible with QGIS' use of camelCase, rather than snake_case. Some minor tweaks applied
- 2026-02-25 (0.6.1) Fixed a bug related to reading Boolean values reliably from xml text input
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
- 2025-05-11 (0.4.3) several improvements in transferring data from Roll to QGIS and vice versa. Created html help page in help menu
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
