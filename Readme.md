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

* In version 0.6.4, a polar diagram was added for the offset/azimuth histogram and refactoring of code continued. The code for the polar diagram was completed using ['agentic coding'](https://cloud.google.com/discover/what-is-agentic-coding). This agent-driven approach was also used to develop a series of unit tests in the test subdirectory. As of version 5.4 GPT has become stable and trustworthy enough to work in agent mode, optimizing the source code and implementing new features. This LLM was also used consistently during code refactoring

  >You may remember, when Plug-and-Play (PnP) was introduced in the early 1990s to manage hardware updates, it did not always work out-of-the-box (understatement) and people often called it "Plug-and-Pray". With AI coding at the moment, we are at the stage where software development has turned into "Prompt-and-Pray".

  May first, and working on Roll, I heard a good quote about AI on a BBC radio programme:

  >You can outsource your thinking, but you cannot outsource your understanding

* In version 0.6.8 a 3D view has been added to the Layout tab, for a subset of survey geometry data. This is in particular useful for working with well-based seeds, think of VSPs

### 3	3D View

As Roll supports binning against a dipping plane, well trajectories and VSP geometries, it seemed logical to include showing a 3D view of the survey area. The implemented 3D view shows a subset of the survey's layout, as rolling templates would take way too much time to render in 3D. But all non-rolling seeds (grids, circles, spirals and well locations can be shown in a 3D setting) See the figure below, that also shows the contribution of different rays paths to a single bin

![3D_vsp_image](images/3D_vsp_image.png)

*3D representation of a survey area*



### 4	Survey wizards

**Land** and **marine** surveys can be created using two separate wizards, that takes you through the different steps of defining the block(s), template(s) and grow factors. 

#### 4.1 Land surveys

The land survey wizard supports various types of survey geometries. Some designs are no longer in use (e.g. brick and zigzag) but these are included for completeness.  The different types that are supported are:

1. Orthogonal
2. Parallel
3. Slanted
4. Brick
5. Zigzag

#### 4.2.	Marine surveys

The marine survey wizard honours minimal turning radius for the inner streamers (*using a minimal towing speed to keep the spread stable*) and a maximal turning radius for the outer streamer(s) (*based on maximum allowed towing forces the streamers can handle*).  Theory for this was developed in the thesis `Simplified Modeling of Seimic Survey Vessels to Determine Optimaal Maneuver Patterns` by Caio de Araujo Ferraz de Carvalho. Where formulas were not explicitly given, they have been reversed engineered, and checked against the numerous figures present in the thesis.

In a towed marine survey, there is only one shot per template as the vessel moves, waiting for the next shot to be taken with a different source at a different location. Furthermore, data is acquired in 'racetracks' whereby east EW sail line is followed by a WE sail line acquired at a distance. The optimal number of sail lines in a racetrack is determined by the optimal turning radius, avoiding turns that are too tight ('tear drops') or turns that are too wide ('crossline sailing'). The wizard takes all of this into account when selecting optimal number of lines per race track.



### 5	Import of SPS data

If (legacy) SPS data is available, this can be imported from the file menu, and is treated in the same way as the internally generated geometry files. This makes it handy to analize survey performance based solely on SPS-data. This SPS data can also be exported as shapefiles to the current QGIS project.

As there are many flavors of SPS files, a number varieties have been predefined, which can be selected in the SPS Import Dialog. The SPS import dialog also allows for creating additional SPS 'dialects', based on the one that is currently selected. Names of these 'dialects' can be altered and their columns for lines, points, northing, easting, etc. can easily be modified. Results are permanently stored in the registry. In case of a mishap, the database can be restored to the original content

**Initially**, the plugin was intended to work from a ***survey template*** (*preferably generated by the land- or marine survey wizard*), followed by analysis of the performance of such a template. Subsequently, the generation of geometry files also allowed for export of the source and receiver points to QGIS, where these points could be edited, for re-import into Roll for further analysis.

**Currently**, it is also possible to start a new (blank) project by ***importing SPS data***, thereby selecting the correct CRS, and defining the local survey grid, before source and receiver points are exported to QGIS, in the same way as is done with the geometry files. This means you can work from ***standalone SPS data***, import this into Roll for analysis, and visualize the point locations and the corresponding fold map in QGIS. Hopefully this makes the plugin more versatile.



### 6	Editing a survey file

As it is cumbersome to manipulate xml-data directly, the user is helped at two levels:

1. Creating a new project can be done using a **survey wizard** for either **marine** (towed streamer) of **land/OBC** templates. 
2. Parameters can be modified added or deleted from the **property pane**. Behind the scenes, this updates the xml-structure, which is always visible from the Xml-tab in the main window. 

But in case you get very familiar with the xml-structure, you can also inspect and edit the xml data directly and apply any changes using the '**Refresh Document**' toolbar button.



### 7	Interaction with QGIS

The generated Geometry points, the imported SPS data, as well as the analysis plots can all be exported to QGIS. In QGIS, source- and receiver points can be moved, deleted, or marked as 'inactive'. These modifications can be loaded back into Roll, for a renewed analysis.   This process is described in much more detail in an html file, accessible from the Help menu in Roll.

The result is a realistic coverage map, created by the edited sources and receivers located on their true position in space.

![foldmap](images/foldmap.png)

*Fold map of 'Noordoostpolder' example project*

### 8	Status

On 8 Feb 2024, the first release of Roll has been published on [GitHub](https://github.com/MrBeee/roll). Initial release on the QGIS plugin website occurred on 13 March 2024.

As of version 0.3.3 Roll is no longer considered an experimental plugin. But there is still some functionality left to be added. See 'To Do' section.

As of version 0.4.6 Roll is compatible with Qt6.0 and therefore ready to work with QGIS 4.0.

As of version 0.7.0 improvements in `binning from templates` and `binning from geometry` have been implemented using `Numba`. Due to inherent dispersed writing of trace data in the binning analysis file, the approach of multiprocessing has been shelved. Use of a relational database was dropped as well, as a relational database would replace the memory mapped approach with row encoding, update statements, index maintenance, and transaction overhead on a workload that is fundamentally numeric-array-heavy.

Finally, see the 'Changelog' for already implemented functionality. Any [Issues](https://github.com/MrBeee/roll/issues) or [pull requests](https://github.com/MrBeee/roll/pulls) can be raised through the GitHub repository.

**Note**: the Model/View approach used by Qt (that takes care of all the widgets in QGIS) allows for fairly large tables. Nevertheless, for each row in a table view, circa 12 bytes are allocated. For very large tables, QGIS will simply crash without any warning. As a result the GUI will 'hang' and you may lose all your work. For large files, the trace table is therefore implemented in a chunked manner, showing chunks of 1 milion traces at the time. Buttons have been added to navigate through these chunks. You may also use the <i>**spider navigation**</i> based on ALT+Arrow keys to move to the next line and stake numbers (or make larger jumps using Ctrl and/or Shift keys in combination with ALT). 

The plugin works best using one or two QHD Screens (2560 x 1440 pixels) or larger. As of QGIS V3.32 High DPI UI scaling issues have arisen. See the following discussion on GitHub <a href="https://github.com/qgis/QGIS/issues/53898">here</a>. The Help menu in Roll shows how you can mitigate against these issues. 

#### 8.1	Project size

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

#### 8.2	Agentic coding - `use experimental code` flag

Using GPT5.4 or Gemini 3 to optimize the code using 'agents' that analyse binning and geometry generation routines, helps to find bottlenecks and speeds up the code, at the risk that bugs are introduced that are difficult to spot due to the large permutation in survey designs caused by varying number of blocks, templates, seeds and seed types. For that reason, for **binning** and **geometry generation** alternative routines are implemented: 

1.  legacy code
2. experimental code

By extensive testing the experimental routines, they will be replacing the legacy routines over time. The selection is controlled by a flag in the settings dialog: `use experimental code` 



### 9	To Do

- Improve Roll's analysis capabilities; think of multiple suppression and DMO smear, CFP analysis
- Expand the 3D Layout View, introduced in version 0.6.8
- Expand Sphinx documentation

