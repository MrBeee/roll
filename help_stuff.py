# adding a MatPlotLib plot in PyQt
# See: https://stackoverflow.com/questions/12459811/how-to-embed-matplotlib-in-pyqt-for-dummies
#
# Create a figure instance to plot on, and give it a title
# See: https://matplotlib.org/stable/api/figure_api.html?highlight=figure
# self.fig = Figure()
# self.fig.suptitle('Survey geometry', fontsize=12)
# self.ax = self.fig.add_subplot(111)
#
# # this is the Canvas Widget that displays the `figure`
# # it takes the `figure` instance as a parameter to __init__
# self.canvas = FigureCanvas(self.fig)
#
# # we give it a minimum size, and define the widget as expandable
# self.canvas.setMinimumSize(200, 200)
# self.canvas.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
# self.toolbar = MatplotlibToolbar(self.canvas, self)
#
# vbl.addWidget(self.canvas)
# vbl.addWidget(self.toolbar)
#
# to plot RP & SP dependent on zoom level
# See: https://stackoverflow.com/questions/29821177/python-matplotlib-replot-on-zoom
# See: https://www.oreilly.com/library/view/python-data-science/9781491912126/ch04.html for nice plots
# See: https://matplotlib.org/stable/users/explain/performance.html?highlight=fast+plot for faster plotting
# See: https://matplotlib.org/stable/users/explain/interactive.html for interactive mode
# See: https://stackoverflow.com/questions/62900078/how-to-make-a-matplotlib-plot-interactive-in-pyqt5
# See: https://stackoverflow.com/questions/11551049/matplotlib-plot-zooming-with-scroll-wheel to zoom with a scrollwheel
# See: https://sukhbinder.wordpress.com/2013/12/16/simple-pyqt-and-matplotlib-example-with-zoompan/
# See; https://stackoverflow.com/questions/31490436/matplotlib-finding-out-xlim-and-ylim-after-zoom
# See: https://www.geeksforgeeks.org/how-to-update-a-plot-on-same-figure-during-the-loop/
#
# nrl  = self.field("nrl")
# nsl  = self.field("nsl")
# rli  = self.field("rli")
# sli  = self.field("sli")
# offImin = self.field("offImin")
# offImax = self.field("offImax")
# offXmin = self.field("offXmin")
# offXmax = self.field("offXmax")
# # First declare inner function
# # See: https://realpython.com/inner-functions-what-are-they-good-for
# # inner function to plot the source and receiver lines
# def plotLines():
#     # plot the source lines
#     nS = 0
#     y = np.array([offXmin, offXmax])
#     for n in range(nsl):
#         xval = n * sli
#         x = np.array([xval, xval])
#         # self.ax.plot(x, y, 'r')
#         nS += 1
#     # plot the receiver lines
#     nR = 0
#     x = np.array([offImin, offImax])
#     for n in range(nrl):
#         yval = n * rli
#         y = np.array([yval, yval])
#         # self.ax.plot(x, y, 'b')
#         nR += 1
# Note: ax.cla() + plotLines() + canvas.draw() are the core of plotting 'dynamic' data
# See: https://matplotlib.org/2.0.2/examples/user_interfaces/embedding_in_qt4.html
# self.ax.cla()
# plotLines()
# self.ax.grid(True, linestyle='-.', lw=0.75, alpha=0.5)
# self.ax.set_xlabel('inline (m)', fontsize=10)
# self.ax.set_ylabel('X-line (m)', fontsize=10)
# self.canvas.draw()
# https://matplotlib.org/stable/users/explain/interactive_guide.html
# self.fig.canvas.draw()
# self.fig.canvas.draw_idle()
# self.fig.canvas.flush_events()

# pyqt5:
# See: https://github.com/baoboa/pyqt5 for a mirror of the pyqt5 project

# PyQtGraph stuff:
# See: https://www.pythonguis.com/tutorials/plotting-pyqtgraph/ for plotting with pyqtgraph
# See: https://github.com/rookiepeng/antenna-array-analysis for pattern responses
# See: https://github.com/pyplotter/pyplotter for a plotter example
# See: https://enmap-box.readthedocs.io/en/latest/ for integration with QGis
# See: https://www.geeksforgeeks.org/pyqtgraph-extensive-examples/
# See: https://github.com/PacktPublishing/Game-Programming-Using-Qt-5-Beginners-Guide-Second-Edition for graphics
# See: https://github.com/PacktPublishing/Game-Programming-Using-Qt-5-Beginners-Guide-Second-Edition/blob/4c95eecd43024e385344ec13f19842fd8b3855ed/Chapter04/Graphics%20View/9.%20Sine%20graph/sineitem.cpp
# See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
# See: https://stackoverflow.com/questions/54368118/modify-graphic-grid for grid updates
# See: https://www.qtcentre.org/threads/55520-Multithreading-in-QGraphicsItem-painting for plotting 1000000 objects
# See: https://www.youtube.com/watch?v=RHmTgapLu4s on youtube
# See: https://github.com/titusjan/pgcolorbar
#
# styles = {"color": "#646464", "font-size": "10pt"}
# self.plotWidget = pg.PlotWidget(background='w', setMouseEnabled=True)
# self.plotWidget = pg.PlotWidget(background='w', viewBox = pg.ViewBox(border = pg.mkPen(color='k', width=1))) # this closes the graph using the viewbox
# Note:From Qt 4.6, QStyleOptionGraphicsItem.levelOfDetail() has been deprecated in favour of QStyleOptionGraphicsItem.levelOfDetailFromTransform()
# In view of this it is recommended to replace code like this: option.levelOfDetail > 0.5 with code like this: option.levelOfDetailFromTransform(painter.transform()) > 0.5
# See: https://github.com/search?l=Python&q=levelOfDetailFromTransform&type=Code
# See: https://github.com/alexssssalex/Rapid-GUI-Programming-with-Python-and-Qt/blob/d4fc9399358908e018feff6544c5081cc38199dd/chap12/multipedes3.py
#
# See: https://github.com/gtaylor/python-colormath/blob/master/colormath/color_conversions.py for color conversion
# See: https://github.com/pyqtgraph/pyqtgraph/pull/2781
# Rather than using a heavy-weight ImageItem, a colorbar can be rendered by drawing a rectangle using a gradient brush.
# (both GradientLegend and GLGradientLegendItem already do that)
# See: https://python.hotexamples.com/examples/pyqtgraph/GradientEditorItem/-/python-gradienteditoritem-class-examples.html
# See: https://github.com/campagnola/relativipy/blob/master/relativity.py to register a new parameter type
# See: https://github.com/Emerica/tsmate/blob/master/tsmate.py for well structured parameter input

# See: https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QHeaderView.html to change with of colon 0 in a tree widget
# self.paramTree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

# See: https://wiki.qt.io/Qt_for_Python/Porting_guide to port code from C++ to Python

# See: https://groups.google.com/g/pyqtgraph/c/OKY-Y_rSlL4 for grabbing mouse
# See: https://stackoverflow.com/questions/63407588/pyqtgraph-disable-mouse-wheel-but-leave-other-functions-of-the-mouse-untouched for python example
# See: D:\Source\Python\pyqtgraph\pyqtgraph\GraphicsScene\GraphicsScene.py to handle drag events; check also main window where the mouse position is shown in the statusbar !
#
# See: https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/widgets/GraphicsView.html#GraphicsView.__init__ how to grab the mouse for sigSceneMouseMoved
# See: https://stackoverflow.com/questions/22448229/pyqtgraph-how-to-drag-a-a-plot-item
# def mouseDragEvent(self, event):
#     print("I'm dragging the mouse !")
#     self.mouseGrabbed = True
#     return super().mouseDragEvent(event)
# def event(self, event: QEvent) -> bool:                                   # using this routine shows all events that pass by
#     print(event_lookup[str(event.type())])
#     return super().event(event)
#
# See: https://doc.qt.io/qt-5/eventsandfilters.html#event-filters for event filters
# def eventFilter(self, watched, event):                                    # event filter that can alter mouse behavior
#     if event.type() == QEvent.GrabMouse or event.type() == QEvent.GraphicsSceneMousePress:
#         self.mouseGrabbed = True
#         print("Mouse grabbed !")
#     # elif event.type() == QEvent.UngrabMouse:
#     #     self.mouseGrabbed = False
#     return super().eventFilter(watched, event)
#
# Note: mouseEnabled=True is needed to receive mouse events
# See: D:\Source\Python\pyqtgraph\pyqtgraph\widgets\GraphicsView.py  @ line 111
# you can also use: enableMouse(self, b=True)                        @ line 189
# you should then receive re-emitted events for:
#   self.sigMouseReleased.emit(ev) for a mouseReleaseEvent
#   self.sigSceneMouseMoved.emit(self.mapToScene(lpos)) for a mouseMoveEvent event

# the viewbox is normally generated as part of the PlotWidget creation.
# by doing this separately, we have more control, and we can easily step through the code
# self.viewbox = pg.ViewBox()
# self.plotWidget = pg.PlotWidget(viewbox=self.viewbox, background="w")
# self.plotWidget = pg.PlotWidget(background='w', setMouseEnabled=True)
# self.plotWidget = pg.PlotWidget(background='w', viewBox = pg.ViewBox(border = pg.mkPen(color='k', width=1))) # this closes the graph using the viewbox
#
# self.plotWidget.installEventFilter(self)                              # captures events
# See: https://stackoverflow.com/questions/58526980/how-to-connect-mouse-clicked-signal-to-pyqtgraph-plot-widget
# on how to connect to a mouse clicked signal
#
# See: https://stackoverflow.com/questions/10591635/can-i-get-mouse-events-in-a-qgraphicsitem
# See: https://forum.qt.io/topic/82085/qgraphicsview-mousereleaseevent-ensures-that-i-can-t-select-qgraphicsitems-anymore/2
# See: https://forum.qt.io/topic/51629/how-can-i-get-a-mouse-event-clicked-pressed-released-etc-in-my-custom-graphicsitem-contained-by-a-qgraphics-view/2
# See: https://www.qtcentre.org/threads/24949-mouse-events-handling-with-QGraphicsItem
# Note setFlags(QGraphicsItem::ItemIsFocusable  | QGraphicsItem::ItemIsSelectable)
# See: https://doc.qt.io/qt-5/qgraphicsitem.html#setEnabled
# See: https://doc.qt.io/qt-5/qgraphicsitem.html#isEnabled
# See: https://stackoverflow.com/questions/28375598/how-to-accept-both-qgraphicsscene-and-qgraphicsitem-drop-event
# See: https://www.programcreek.com/python/?code=epolestar%2Fequant%2Fequant-master%2Fsrc%2Fqtui%2Freportview%2Ffundtab.py
# See: https://www.programcreek.com/python/?code=MouseLand%2Fsuite2p%2Fsuite2p-master%2Fsuite2p%2Fgui%2Fgraphics.py
# See: https://github.com/MouseLand/suite2p for interesting python libraries

# We need to get a class for efficient 3D points in Python.
# See: https://splunktool.com/implementing-3d-vectors-in-python-numpy-vs-xyz-fields
# See: https://stackoverflow.com/questions/19458291/efficient-vector-point-class-in-python
# See: http://ilan.schnell-web.net/prog/vec3/
# See: https://codereview.stackexchange.com/questions/114409/a-3-d-vector-class-built-on-top-of-numpy-array
# See: https://github.com/SplinterFM/Point3d
# See: https://github.com/joshbmair/python-3d-point-cloud/blob/master/PointCloud/__init__.py

# numpy file viewers and other stuff...
# See: https://github.com/ArendJanKramer/Numpyviewer
# See: https://colab.research.google.com/github/timeseriesAI/tsai/blob/master/tutorial_nbs/00_How_to_efficiently_work_with_very_large_numpy_arrays.ipynb
# See: https://www.statology.org/numpy-remove-element-from-array/ how to remove elements from numpy array
# See: https://www.statology.org/numpy-remove-duplicates/ how to remove duplicates from numpy array
# See: n = np.iinfo(np.int32).max ## largest int32 numpy can manage on this system
# See: https://stackoverflow.com/questions/49322017/merging-1d-arrays-into-a-2d-array
# print([(i[0], i[1]) for i in data])                               # use list comprehension to turn numpy array back into a list

# With:
# test = np.array([[1, 2], [3, 4], [5, 6]])
# To access column 0:
# >>> test[:, 0]
# array([1, 3, 5])
# To access row 0:
# >>> test[0, :]
# array([1, 2])
# This is covered in Section 1.4 (Indexing) of the NumPy reference. This is quick, at least in my experience. It's certainly much quicker than accessing each element in a loop.

# See: https://stackoverflow.com/questions/10591635/can-i-get-mouse-events-in-a-qgraphicsitem
# See: https://forum.qt.io/topic/82085/qgraphicsview-mousereleaseevent-ensures-that-i-can-t-select-qgraphicsitems-anymore/2
# See: https://forum.qt.io/topic/51629/how-can-i-get-a-mouse-event-clicked-pressed-released-etc-in-my-custom-graphicsitem-contained-by-a-qgraphics-view/2
# See: https://www.qtcentre.org/threads/24949-mouse-events-handling-with-QGraphicsItem
# Note setFlags(QGraphicsItem::ItemIsFocusable  | QGraphicsItem::ItemIsSelectable)
# See: https://doc.qt.io/qt-5/qgraphicsitem.html#setEnabled
# See: https://doc.qt.io/qt-5/qgraphicsitem.html#isEnabled
# See: https://stackoverflow.com/questions/28375598/how-to-accept-both-qgraphicsscene-and-qgraphicsitem-drop-event
# See: https://www.programcreek.com/python/?code=epolestar%2Fequant%2Fequant-master%2Fsrc%2Fqtui%2Freportview%2Ffundtab.py
# See: https://www.programcreek.com/python/?code=MouseLand%2Fsuite2p%2Fsuite2p-master%2Fsuite2p%2Fgui%2Fgraphics.py
# See: https://github.com/MouseLand/suite2p for interesting python libraries
# See: https://www.qtcentre.org/threads/55520-Multithreading-in-QGraphicsItem-painting for plotting large number of points
# See: https://stackoverflow.com/questions/73282663/pyqtgraph-roi-mirrors-the-displayed-text for ROI and crosshair stuff

# Copy numpy array to excel
# See: https://numpy.org/doc/stable/reference/generated/numpy.searchsorted.html to scroll to the right position
# See: https://stackoverflow.com/questions/32160576/how-to-select-a-portion-of-a-numpy-array-efficiently
# See: https://stackoverflow.com/questions/22488566/how-to-paste-a-numpy-array-to-excel
# See: https://stackoverflow.com/questions/44672524/how-to-create-in-memory-file-object
# See: https://stackoverflow.com/questions/11914472/how-to-use-stringio-in-python3
# See: https://www.geeksforgeeks.org/stringio-module-in-python/
# See: https://www.pythonpool.com/python-stringio/
# See: https://python.readthedocs.io/en/v2.7.2/library/stringio.html
# See: https://stackoverflow.com/questions/22355026/numpy-savetxt-to-a-string
# See: https://numpy.org/doc/stable/reference/generated/numpy.array2string.html MUCH EASIER THAN THROUGH MEMORY BASED FILE
# See: https://www.programcreek.com/python/example/102172/numpy.array2string
# See: https://forum.qt.io/topic/144109/performance-problem-about-qitemselectionmodel/5
# See: https://github.com/NextSaturday/myQT/blob/main/tSelection/tSelection/tSelection.cpp

# structured arrays
# See: https://blog.finxter.com/numpy-structured-arrays-and-record-arrays/
# See: https://jakevdp.github.io/PythonDataScienceHandbook/02.09-structured-data-numpy.html
# See: https://www.datasciencelearner.com/numpy-structured-array-example/
# See: https://prosperocoder.com/posts/science-with-python/numpy-part-11-structured-numpy-arrays/
# See: https://stackoverflow.com/questions/33256823/numpy-resize-array-filling-with-0 to resize an array
# See: https://stackoverflow.com/questions/38191855/zero-pad-numpy-array

# next widget not (yet) used; to collapse its content
# self.collapsible_group_box = QgsCollapsibleGroupBox()
# self.collapsible_group_box.setTitle('Source and receiver basic template configuration')

# Check the following on how to show a template in the wizard using MatPlotLib:
# https://github.com/PacktPublishing/Matplotlib-for-Python-Developers-Second-Edition/blob/master/Chapter06/Chapter06.ipynb
# https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_qt_sgskip.html#
# https://www.geeksforgeeks.org/how-to-embed-matplotlib-graph-in-pyqt5/
# https://techbase.kde.org/Development/Tutorials/QtDOM_Tutorial
# https://stackoverflow.com/questions/36744988/c-qt-qdomdocument-iterate-over-all-xml-tags

# To speed up code:
# See: https://medium.com/comparing-microservices-built-on-python-nodejs-and/boosting-python-with-cython-and-numba-31d81e938abd
# See: https://stackoverflow.com/questions/72818680/numba-code-much-faster-than-cython-alternative
# See: https://superfastpython.com/parallel-nested-for-loops-in-python/
# See: https://github.com/S-LABc/Chaos-ru-lang/blob/main/README_ORIG.md for library using NUMBA and PyqtGraph
# See: https://www.theregister.com/2023/03/11/python_codon_compiler/

# rasterIO (rio)
# See: https://medium.com/@mommermiscience/dealing-with-geospatial-raster-data-in-python-with-rasterio-775e5ba0c9f5
# See: https://gis.stackexchange.com/questions/225899/pyqgis-load-an-in-memory-mem-format-raster-as-layer

# 3D seismic data viewer, seismic tomography, sps data
# See: https://seg.org/Portals/0/SEG/News%20and%20Resources/Technical%20Standards/seg_sps_rev2.1.pdf
# See: https://github.com/yunzhishi/seismic-canvas
# See: https://www.pygimli.org/_examples_auto/2_seismics/plot_03_rays_layered_and_gradient_models.html
# See: https://agilescientific.com/blog/2014/12/17/laying-out-a-seismic-survey.html
# See: https://agilescientific.com/blog/2015/1/8/it-goes-in-the-bin
# See: https://nbviewer.org/github/agile-geoscience/notebooks/blob/master/Laying_out_a_seismic_survey.ipynb
# See: https://medium.com/data-analysis-center/making-seismic-interpretation-easy-with-seismiqb-ac62d01a477
# See: https://towardsdatascience.com/visualizing-3d-seismic-volumes-made-easy-with-python-and-mayavi-e0ca3fd61e43
# See: https://stackoverflow.com/questions/33651243/plotting-seismic-wiggle-traces-using-matplotlib
# See: https://github.com/equinor/segyio
# See: https://terranubis.com/datainfo/F3-Demo-2020
# See: https://segysak.readthedocs.io/en/latest/why-segysak.html
# See: https://segysak.readthedocs.io/en/latest/index.html
# See: https://github.com/stuliveshere/PySeis/blob/master/docs/notebooks/1.0%20Introduction%20to%20PySeis.ipynb
# See: https://github.com/stuliveshere/SimplePyRay

# model view architecture
# See: https://www.pythonguis.com/tutorials/modelview-architecture/
# See: https://www.giacomodebidda.com/posts/mvc-pattern-in-python-introduction-and-basicmodel/
# See: https://www.pythontutorial.net/pyqt/pyqt-model-view/
# See: https://www.pythonguis.com/tutorials/qtableview-modelviews-numpy-pandas/
# See: https://doc.qt.io/qt-6/model-view-programming.html
# See: https://www.youtube.com/watch?v=Ub9lg4FWZBA
# See: https://www.youtube.com/watch?v=MkjWena77kU
# See: https://www.pythonguis.com/tutorials/modelview-architecture/

# redirecting signals and slots
# See: https://www.pythonguis.com/examples/python-tabbed-web-browser/
# See: https://www.pythonguis.com/tutorials/transmitting-extra-data-qt-signals/

# reading large text files quickly
# See: https://gist.github.com/zed/0ac760859e614cd03652
# See: https://stackoverflow.com/questions/845058/how-to-get-line-count-of-a-large-file-cheaply-in-python
# See: https://stackoverflow.com/questions/845058/how-to-get-line-count-of-a-large-file-cheaply-in-python/68385697#68385697

# To use QFile and QTextStream to read sps-data, see for more information:
# See: https://srinikom.github.io/pyside-docs/PySide/QtCore/QFile.html
# See: https://python.hotexamples.com/examples/PyQt4.QtCore/QTextStream/-/python-qtextstream-class-examples.html
# See: https://stackoverflow.com/questions/14750997/load-txt-file-from-resources-in-python


# Multithreading and multiprocessing:
# See: https://superfastpython.com/multiprocessing-in-python/

# to get month, day from a Julian date:
# See: https://rafatieppo.github.io/post/2018_12_01_juliandate/

# Original QT examples are available from Riverbank Computing Limited.
# See: https://github.com/baoboa/pyqt5
# See: https://github.com/baoboa/pyqt5/blob/master/examples/itemviews/editabletreemodel/editabletreemodel.py

# pyQt5 csv-file viewer
# See: https://github.com/Axel-Erfurt/TreeView/blob/master/Qt5_CSV.py

# gps-tracker:
# See: https://github.com/gis-support/gps-tracker/blob/master/gpsWidgets.py

# QGIS interface
# See: https://www.qgistutorials.com/en/docs/3/getting_started_with_pyqgis.html
# See: https://gis.stackexchange.com/questions/34082/creating-raster-layer-from-numpy-array-using-pyqgis
# See: https://gis.stackexchange.com/questions/201804/how-to-create-raster-layer-directly-from-numpy-array-in-qgis-without-saving-to
# See: https://webgeodatavore.github.io/pyqgis-samples/gui-group/QgsAttributeForm.html
# See: https://anitagraser.com/pyqgis-101-introduction-to-qgis-python-programming-for-non-programmers/pyqgis101-creating-editing-a-new-vector-layer/
# See: https://gis.stackexchange.com/questions/156096/creating-new-empty-memory-layer-with-fields-scheme-from-other-layer-in-qgis
# See: https://gis.stackexchange.com/questions/155569/copying-attributes-from-point-layer-to-memory-linestring-layer-pyqgis
# See: https://gis.stackexchange.com/questions/173936/creating-memory-layer-and-populate-fields-using-pyqgis
# See: https://www.programcreek.com/python/example/91089/qgis.core.QgsVectorLayer
# See: https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/vector.html#creating-vector-layers
# See: https://courses.spatialthoughts.com/pyqgis-in-a-day.html#:~:text=QGIS%20Comes%20with%20a%20built,print('Hello%20World!
# See: https://gis.stackexchange.com/questions/420268/create-a-point-layer-from-csv-using-python-console-in-qgis
# See: https://gis.stackexchange.com/questions/301825/setting-label-settings-in-pyqgis-3-to-mapunits
# See: https://api.qgis.org/api/classQgsUnitTypes.html
# See: https://qgis.org/pyqgis/3.2/core/Text/QgsTextFormat.html#qgis.core.QgsTextFormat.setSizeUnit
# See: https://api.qgis.org/api/qgis_8h_source.html#l03354
# See: https://qgis.org/pyqgis/master/core/QgsUnitTypes.html#qgis.core.QgsUnitTypes.RenderUnit
# See: https://opensourceoptions.com/blog/loading-and-symbolizing-vector-layers/ to create and edit symbols
# See: https://gis.stackexchange.com/questions/428700/pyqgis-qgspallayersettings-vector-labels-scale-visibility for adding labels
# See: https://www.gislounge.com/scale-and-layer-visibility-qgis-python-programming-cookbook/
# See: https://gis.stackexchange.com/questions/167163/setting-qgsexpression-for-qgspallayersettings-in-qgis
# See: https://python.hotexamples.com/examples/qgis.core/QgsVectorLayerSimpleLabeling/-/python-qgsvectorlayersimplelabeling-class-examples.html
# See: https://qgis.org/pyqgis/3.4/core/QgsRuleBasedLabeling.html
# See: https://stackoverflow.com/questions/57459586/how-to-display-rule-bassed-labeling-in-qgis-using-pyqgis
# See: https://python.hotexamples.com/examples/qgis.core/QgsVectorLayer/setMaximumScale/python-qgsvectorlayer-setmaximumscale-method-examples.html
# See: http://pal.heig-vd.ch/index.php?page=about-pal
# See: https://gis.stackexchange.com/questions/428700/pyqgis-qgspallayersettings-vector-labels-scale-visibility
# See: https://cpp.hotexamples.com/examples/-/QgsPalLayerSettings/-/cpp-qgspallayersettings-class-examples.html
# See: https://gis.stackexchange.com/questions/326166/qgis-set-label-placement-in-python
# See: https://github.com/qgis/QGIS/blob/master/python/utils.py#L291 for accessing version info
# See: D:\qGIS\MyPlugins\roll\test\test_init.py for accessing version information


# To get information of the currrent layer, type the following in the python console:
#       layer = iface.activeLayer()
#       print (layer.renderer().symbol().symbolLayers()[0].properties())
#       print (dir(layer)) to get all layer methods
# Then move on to check the symbols
#      symbol = layer.renderer().symbol()
#      print("sym.layers", symbol.symbolLayerCount())                              # normally 1 layer
#      print("properties", symbol.symbolLayers()[0].properties())                  # lists all properties
#      symbol.setSizeUnit(QgsUnitTypes.RenderMetersInMapUnits)                     # can also be done in constructor
#      symbol.setSize(20.0)                                                        # can also be done in constructor

# See: https://pyqtgraph.readthedocs.io/en/pyqtgraph-0.13.2/api_reference/colormap.html#apiref-colormap
# List copied from Directory: D:\Source\Python\pyqtgraph\pyqtgraph\colors\maps
# directoryList = [
#     'CET-C1.csv',   'CET-C1s.csv',  'CET-C2.csv',   'CET-C2s.csv',  'CET-C3.csv',   'CET-C3s.csv',  'CET-C4.csv',   'CET-C4s.csv',
#     'CET-C5.csv',   'CET-C5s.csv',  'CET-C6.csv',   'CET-C6s.csv',  'CET-C7.csv',   'CET-C7s.csv',  'CET-CBC1.csv', 'CET-CBC2.csv',
#     'CET-CBD1.csv', 'CET-CBL1.csv', 'CET-CBL2.csv', 'CET-CBTC1.csv','CET-CBTC2.csv','CET-CBTD1.csv','CET-CBTL1.csv','CET-CBTL2.csv',
#     'CET-D1.csv',   'CET-D10.csv',  'CET-D11.csv',  'CET-D12.csv',  'CET-D13.csv',  'CET-D1A.csv',  'CET-D2.csv',   'CET-D3.csv',
#     'CET-D4.csv',   'CET-D6.csv',   'CET-D7.csv',   'CET-D8.csv',   'CET-D9.csv',   'CET-I1.csv',   'CET-I2.csv',   'CET-I3.csv',
#     'CET-L1.csv',   'CET-L10.csv',  'CET-L11.csv',  'CET-L12.csv',  'CET-L13.csv',  'CET-L14.csv',  'CET-L15.csv',  'CET-L16.csv',
#     'CET-L17.csv',  'CET-L18.csv',  'CET-L19.csv',  'CET-L2.csv',   'CET-L3.csv',   'CET-L4.csv',   'CET-L5.csv',   'CET-L6.csv',
#     'CET-L7.csv',   'CET-L8.csv',   'CET-L9.csv',   'CET-R1.csv',   'CET-R2.csv',   'CET-R3.csv',   'CET-R4.csv',   'cividis.csv',
#     'inferno.csv',  'magma.csv',    'PAL-relaxed.hex','PAL-relaxed_bright.hex',       'plasma.csv',   'viridis.csv']
# these color maps are accessible through ```pg.colormap.listMaps()````
#
# see: https://ai.googleblog.com/2019/08/turbo-improved-rainbow-colormap-for.html for new colormap
# See: https://github.com/pyqtgraph/pyqtgraph/pull/2778 for pull request to add the above colormap
# See: https://github.com/cokelaer/colormap for a  RGB, HEX, HLS, HUV colormap

# To draw a spiral using C++ and Qt:
# See: https://github.com/ZevEisenberg/ZESpiral and:
# See: https://github.com/ZevEisenberg/ZESpiral/issues/1
#
# bool ZELineIntersection(qreal m1, qreal b1, qreal m2, qreal b2, qreal *X, qreal *Y)
# {
#     if (m1 == m2) { // lines are parallel
#         return false;
#     }
#     *X = (b2 - b1) / (m1 - m2);
#     *Y = m1 * *X + b1;
#     return true;
# }
#
# QPainterPath createSpiral(QPointF center, qreal startRadius, qreal spacePerLoop, qreal startTheta, qreal endTheta, qreal thetaStep)
# {
#     QPainterPath path;
#     qreal oldTheta = startTheta;
#     qreal newTheta = startTheta;
#     qreal oldR = startRadius + spacePerLoop * oldTheta;
#     qreal newR = startRadius + spacePerLoop * newTheta;
#     qreal oldSlope = std::numeric_limits<qreal>::max();
#     qreal newSlope = oldSlope;
#     QPointF newPoint(center.x() + oldR * cos(oldTheta), center.y() + oldR * sin(oldTheta));
#     path.moveTo(newPoint);
#     bool firstSlope = true;
#     while (oldTheta < endTheta - thetaStep) {
#         oldTheta = newTheta;
#         newTheta += thetaStep;
#         oldR = newR;
#         newR = startRadius + spacePerLoop * newTheta;
#         newPoint = QPointF(center.x() + newR * cosf(newTheta), center.y() + newR * sinf(newTheta));
#         // Slope calculation with the formula:
#         // (spacePerLoop * sinT + (startRadius + bT) * cosT) / (spacePerLoop * cosT - (startRadius + bT) * sinT)
#         qreal aPlusBTheta = startRadius + spacePerLoop * newTheta;
#         if (firstSlope) {
#             oldSlope = ((spacePerLoop * sin(oldTheta) + aPlusBTheta * cos(oldTheta))
#               /         (spacePerLoop * cos(oldTheta) - aPlusBTheta * sin(oldTheta)));
#             firstSlope = false;
#         } else {
#             oldSlope = newSlope;
#         }
#         newSlope      = (spacePerLoop * sin(newTheta) + aPlusBTheta * cos(newTheta))
#               /         (spacePerLoop * cos(newTheta) - aPlusBTheta * sin(newTheta));
#         qreal oldIntercept = -(oldSlope * oldR * cos(oldTheta) - oldR * sin(oldTheta));
#         qreal newIntercept = -(newSlope * newR * cos(newTheta) - newR * sin(newTheta));
#         qreal outX, outY;
#         if (ZELineIntersection(oldSlope, oldIntercept, newSlope, newIntercept, &outX, &outY)) {
#             QPointF controlPoint = QPointF(outX + center.x(), outY + center.y());
#             path.quadTo(controlPoint, newPoint);
#         } else {
#             qCritical("These lines should never be parallel.");
#         }
#     }
#     return path;
# }

# How can I efficiently transfer data from a NumPy array to a QPolygonF ?
#
# from pylab import *
# from PySide.QtGui import QPolygonF
# from PySide.QtCore import QPointF

# xy = resize(arange(10),(2,10)).T

# qPlg = QPolygonF()
# for p in xy:
#     qPlg.append(QPointF(*p))

# See also: https://github.com/PlotPyStack/PythonQwt/blob/master/qwt/plot_curve.py#L63
# See also: https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/functions.html
# look for: arrayToQPolygonF. It has been commented out, but why ? ? ?

# See: https://pep8.org/ for Python formatting guidelines

# compare adjacent elements in numpy array (e.g. for unique fold)
# See: https://stackoverflow.com/questions/72156653/compare-two-elements-of-the-same-numpy-array-through-broadcasting
# See: https://note.nkmk.me/en/python-numpy-ndarray-compare/
# See: https://scipy-cookbook.readthedocs.io/items/PerformancePython.html
