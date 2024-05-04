# Roll

### Seismic survey design plugin for QGIS

#### 1	Introduction

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

Once the geometry has been defined, binning analysis can directly be done using the template-based approach.

- A **fold map** can be created to shows (offset dependent) fold
- A **minimum offset map** can be created to show minimum offsets coverage
- A **maximum offset map** can be created to show maximum offsets coverage

As the survey file always contains a (projected) coordinate reference system (CRS) these three maps can be exported to the current QGIS project as a georeferenced Tiff (GeoTiff) file. These files can also be exported as a standalone GeoTiff file from the  File -> Export menu.

The templates can be converted into geometry files, consisting of (a) a source file, (b) a receiver file and (c) a relation file, similar how this is managed in the SPS format. The source- and receiver points from the source and receiver files can be exported to the current QGIS project as an ArcGIS Shape file, where these points can be inspected, moved around or deleted. Edited points can be re-imported into Roll to assess the impact on fold, etc.

The geometry files themselves can also be exported as SPS-files.



#### 2	Import of SPS data

If (legacy) SPS data is available, this can be imported from the file menu, and is treated the same as the internally generated geometry files. This makes it handy to analyze survey performance based solely on SPS-data. This SPS data can also be exported as shapefiles to the current QGIS project.

As there are many flavors of SPS files, a number varieties have been predefined, and can be selected from File -> Settings. The SPS-flavors are kept in a list of available Python dictionaries kept in `config.py`:

```python
spsFormatList = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character is therefore [0, 1], the last one is [79, 80]
    # Note: In SEG rev2.1, Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', line=[11, 15], point=[21, 25], index=[25, 26], code=[26, 28], depth=[33, 37], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', line=[13, 17], point=[17, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='SEG rev2.1',  hdr='H', src='S', rec='R', rel='X', line=[1, 12], point=[11, 21], index=[23, 24], code=[24, 25],depth=[30, 34],east=[46, 55],north=[55, 65],elev=[65, 71],),
]

xpsFormatList = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character is therefore [0, 1], the last one is [79, 80]
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', recNum=[8, 11], srcLin=[23, 27], srcPnt=[33, 37], srcInd=[37, 38], recLin=[57, 61], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', recNum=[8, 15], srcLin=[29, 33], srcPnt=[33, 37], srcInd=[37, 38], recLin=[61, 65], recMin=[65, 69], recMax=[75, 79], recInd=[79, 80]),
    dict(name='SEG rev2.1', hdr='H', src='S', rec='R', rel='X', recNum=[7, 15], srcLin=[17, 27], srcPnt=[27, 37], srcInd=[37, 38], recLin=[49, 59], recMin=[59, 69], recMax=[69, 79], recInd=[79, 80]),
]
```

*Excerpt from the py.config file*

The user can expand this list with new SPS 'flavors', by defining new 'point' and 'relational' record formats



#### 3	Editing a survey file

As it is cumbersome to manipulate xml-data directly, the user is helped on two levels:

1. Creating a new project is done using a **survey wizard**. At present there is one wizard suitable to generate templates for land seismic and OBN-data. A marine wizard is in the making.
2. Parameters can be modified added or deleted from the **property pane**. Behind the scenes, this updates the xml-structure, which is always visible from the Xml-tab in the main window.



#### 4	External dependencies

Roll depends on the following Python libraries that need to be installed separately 
In the **OSGeo4W Command Shell**, type: ```pip install --upgrade 'library-name'```,  where --upgrade forces the installation of the latest version

| Library    | Minimum Version | Description (purpose)                                      |
| :--------- | :-------------- | :--------------------------------------------------------- |
| numba      | 0.59.1          | Significantly speed up numpy calculations                  |
| numpy      | 1.26.24         | Array and matrix manipulation                              |
| pyqtgraph  | 0.13.4          | Plotting of vector and raster data                         |
| rasterio   | 1.3.9           | Export of figures as GeoTiff  files                        |
| wellpathpy | 0.5.0           | Handle sensors  & sources in a well trajectory (VSPs etc.) |



#### 5	Status

On 8 Feb 2024, the first release of Roll has been published on [GitHub](https://github.com/MrBeee/roll)

Currently, there is still some functionality left to be added. See To Do.

See changelog for already implemented functionality

[Issues](https://github.com/MrBeee/roll/issues) or [pull requests](https://github.com/MrBeee/roll/pulls) can be raised through the GitHub repository



#### 6	Changelog

- 2024-05-04 (0.2.8) implemented numba @jit, to speed up calculations. Added Kx-Ky stack analysis and |O| & O/A Histograms. Fixed some bugs.
  Added Kx-Ky stack response as well as |O| & O/A Histograms to the Analysis tab
  
- 2024-04-22 (0.2.7) removed all numba @jit references, as exception handling with numba causes problems. Will revisit later.
  
- 2024-04-21 (0.2.6) added 'Analysis' tab, containing:
  - The Trace table (full binning results)
  - In-/ and X-line offsets
  - In-/ and X-line azimuths
  - In-/ and X-line stack response

- 2024-04-13 (0.2.5) included TWT values in trace table and implemented 'Unique Fold' capability
- 2024-04-08 (0.2.4) improved handling of well-files
- 2024-03-30 (0.2.3) updated metadata.txt (a) about text and (b) dependencies
- 2024-03-30 (0.2.2) improved handling of line- and stake numbers; refactoring of parameter handling
- 2024-03-13 (0.2.1) Initial release on the QGIS plugin website



#### 7	To Do

- Create wizard for Marine towed-streamer geometry
- Improve analysis capabilities
  - Show pattern layout and add Kx-Ky pattern analysis
  - Make k-scales user-adjustable in the settings dialog
  
- Use multiprocessing instead of a worker thread to speed up background tasks
- Consider relational database instead of numpy arrays for geometry tables

