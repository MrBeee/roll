# roll_main_window.py
# coding=utf-8

"""Main window for the Roll plugin."""

try:    # need to TRY importing numba, only to see if it is available
    haveNumba = True
    import numba  # pylint: disable=W0611
except ImportError:
    haveNumba = False

try:    # need to TRY importing debugpy, only to see if it is available
    haveDebugpy = True
    import debugpy  # pylint: disable=W0611
except ImportError as ie:
    haveDebugpy = False

import contextlib
import gc
import os
import os.path
import platform
import sys
import traceback
import webbrowser
import winsound  # make a sound when an exception ocurs
from math import atan2, ceil, degrees

# PyQtGraph related imports
import numpy as np  # Numpy functions needed for plot creation
import pyqtgraph as pg
from numpy.lib import recfunctions as rfn
from qgis.core import QgsApplication
from qgis.PyQt import uic
from qgis.PyQt.QtCore import (QDateTime, QEvent, QFile, QFileInfo, QIODevice,
                              QPoint, QRectF, QSettings, QSize, Qt,
                              QTextStream)
from qgis.PyQt.QtGui import (QBrush, QColor, QFont, QIcon, QImage, QPainter,
                             QTextCursor, QTransform)
from qgis.PyQt.QtPrintSupport import QPrinter, QPrintPreviewDialog
from qgis.PyQt.QtWidgets import (QAction, QApplication, QFileDialog,
                                 QGraphicsEllipseItem, QGraphicsRectItem,
                                 QLabel, QMainWindow, QMessageBox,
                                 QProgressBar, QTabWidget, QWidget)
from qgis.PyQt.QtXml import QDomDocument

from . import config  # used to pass initial settings
from .aux_classes import LineROI
from .aux_functions import (aboutText, convexHull, exampleSurveyXmlText,
                            highDpiText, licenseText, myPrint,
                            qgisCheatSheetText)
from .binning_worker_mixin import BinningWorkerMixin
from .chunked_data import ChunkedData
from .display_dock import create_display_dock
from .enums_and_int_flags import (Direction, MsgType, PaintDetails, PaintMode,
                                  SurveyType2)
# from .find import Find.
# Superseded by FindNotepad, which is more user friendly and has a better implementation.
# The old Find class is still available in find.py, but not imported here.
from .find import FindNotepad
from .functions_numba import (numbaAziInline, numbaAziX_line,
                              numbaFilterSlice2D, numbaNdft_1D, numbaNdft_2D,
                              numbaOffInline, numbaOffsetBin, numbaOffX_line,
                              numbaSlice3D, numbaSliceStats)
from .land_wizard import LandSurveyWizard
from .logging_dock import create_logging_dock
from .marine_wizard import MarineSurveyWizard
from .my_parameters import registerAllParameterTypes
from .property_dock import create_property_dock
from .qgis_interface import (CreateQgisRasterLayer, ExportRasterLayerToQgis,
                             exportPointLayerToQgis, exportSpsOutlinesToQgis,
                             exportSurveyOutlinesToQgis,
                             identifyQgisPointLayer, readQgisPointLayer)
from .roll_binning import BinningType
from .roll_main_window_create_geom_tab import createGeomTab
from .roll_main_window_create_layout_tab import createLayoutTab
from .roll_main_window_create_pattern_tab import createPatternTab
from .roll_main_window_create_sps_tab import createSpsTab
from .roll_main_window_create_stack_response_tab import createStackResponseTab
from .roll_main_window_create_trace_table_tab import createTraceTableTab
from .roll_output import RollOutput
from .roll_survey import RollSurvey
from .settings import SettingsDialog, readSettings, writeSettings
from .spider_navigation_mixin import SpiderNavigationMixin
from .sps_import_dialog import SpsImportDialog
from .sps_io_and_qc import (calcMaxXPStraces, calculateLineStakeTransform,
                            convertCrs, deletePntDuplicates, deletePntOrphans,
                            deleteRelDuplicates, deleteRelOrphans,
                            exportDataAsTxt, fileExportAsR01, fileExportAsS01,
                            fileExportAsX01, findRecOrphans, findSrcOrphans,
                            getAliveAndDead, markUniqueRPSrecords,
                            markUniqueSPSrecords, markUniqueXPSrecords,
                            pntType1, readRpsLine, readSpsLine, readXpsLine,
                            relType2)
from .survey_paint_mixin import SurveyPaintMixin
from .xml_code_editor import QCodeEditor, XMLHighlighter


# code to run Roll standalone, without QGIS, for testing and development purposes
def runStandalone(argv=None):
    argv = argv or sys.argv

    # Ensure one Qt app exists
    qtApp = QApplication.instance()
    if qtApp is None:
        qtApp = QApplication(argv)

    # Init QGIS app (no GUI flag here because Roll uses widgets)
    qgsApp = QgsApplication.instance()
    ownsQgsApp = False
    if qgsApp is None:
        # Optional: set prefix if needed in your environment
        # QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", r"C:\OSGeo4W\apps\qgis"), True)
        qgsApp = QgsApplication(argv, True)
        qgsApp.initQgis()
        ownsQgsApp = True

    window = RollMainWindow(iface=None, parent=None, standaloneMode=True)
    window.show()

    exitCode = qtApp.exec()

    if ownsQgsApp:
        qgsApp.exitQgis()

    return exitCode

if __name__ == '__main__':
    raise SystemExit(runStandalone())

# Determine path to resources
current_dir = os.path.dirname(os.path.abspath(__file__))
resource_dir = os.path.join(current_dir, 'resources')

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'roll_main_window_base.ui'))

class RollMainWindow(QMainWindow, FORM_CLASS, SpiderNavigationMixin, SurveyPaintMixin, BinningWorkerMixin):
    """Main window for the Roll plugin, uses multiple inheritance.
    * It is first of all derived from QMainWindow.
    * FORM_CLASS is generated from the Qt Designer .ui file.
    * SpiderNavigationMixin provides reusable spider-navigation behaviour.
    * SurveyPaintMixin keeps the paint-mode bookkeeping out of RollMainWindow
    * BinningWorkerMixin keeps the binning worker thread code out of RollMainWindow
    """

    def __init__(self, iface=None, parent=None, standaloneMode=False):
        """Constructor."""
        super(RollMainWindow, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing self.<objectname>,
        # and you can use autoconnect slots - see http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # widgets-and-dialogs-with-auto-connect
        # See also: https://doc.qt.io/qt-6/designer-using-a-ui-file-python.html
        # See: https://docs.qgis.org/3.22/en/docs/documentation_guidelines/substitutions.html#toolbar-button-icons for QGIS Icons
        self.setupUi(self)
        create_display_dock(self)
        create_logging_dock(self)

        # reset GUI when the plugin is restarted (not when restarted from minimized state on windows)
        self.killMe = False
        self.findDialog = None                                                  # the find/replace dialog, created when needed

        # GQIS interface
        self.iface = iface                                                      # for access to QGis interface; declared here, and initialized in roll.py
        self.standaloneMode = standaloneMode                                    # True when running outside of QGIS, for testing and development purposes

        # toolbar parameters
        self.XisY = True                                                        # equal x / y scaling
        self.rect = False                                                       # zoom using a rectangle
        self.glob = False                                                       # global coordinates
        self.gridX = True                                                       # use grid lines
        self.gridY = True                                                       # use grid lines
        self.antiA = [False for i in range(12)]                                 # anti-alias painting
        self.ruler = False                                                      # show a ruler to measure distances

        self.fileBar.setIconSize(QSize(24, 24))                                 # set icon size for toolbar
        self.editBar.setIconSize(QSize(24, 24))                                 # set icon size for toolbar
        self.graphBar.setIconSize(QSize(24, 24))                                # set icon size for toolbar
        self.moveBar.setIconSize(QSize(24, 24))                                 # set icon size for toolbar
        self.paintBar.setIconSize(QSize(24, 24))                                # set icon size for toolbar

        # list with most recently used [mru] file actions
        self.recentFileActions = []
        self.recentFileList = []

        # workerTread parameters
        self.worker = None                                                      # 'moveToThread' object
        self.thread = None                                                      # corresponding worker thread
        self.startTime = None                                                   # thread start time
        self.interrupted = False                                                # set to True when the main thread is interrupted

        # statusbar widgets
        self.posWidgetStatusbar = QLabel('(x, y): (0.00, 0.00)')                # mouse' position label, in bottom right corner
        self.progressLabel = QLabel('doing a lot of stuff in the background')   # label next to progressbar indicating background process
        self.progressBar = QProgressBar()                                       # progressbar in statusbar
        self.progressBar.setMaximumWidth(500)                                   # to avoid 'jitter' when the mouse moves and posWidgetStatusbar changes width
        height = self.posWidgetStatusbar.height()                               # needed to avoid statusbar 'growing' vertically by adding the progressbar
        self.progressBar.setMaximumHeight(height)                               # to avoid ugly appearance on statusbar

        # binning analysis
        self.output = RollOutput()                                              # contains result arrays and min/max values
        self.binAreaChanged = False                                             # set when binning area changes in property tree

        # display parameters in Layout tab
        self.imageType = 0                                                      # 1 = fold map
        self.layoutMax = 0.0                                                    # max value for image's colorbar (minimum is always 0)
        self.layoutImg = None                                                   # numpy array to be displayed; binOutput / minOffset / maxOffset / rmsOffset

        # analysis numpy arrays
        self.inlineStk = None                                                   # numpy array with inline Kr stack reponse
        self.x_lineStk = None                                                   # numpy array with x_line Kr stack reponse
        self.xyCellStk = None                                                   # numpy array with cell's KxKy stack response
        self.xyPatResp = None                                                   # numpy array with pattern's KxKy response

        # layout and analysis image-items
        self.layoutImItem = None                                                # pg ImageItems showing analysis result
        self.stkTrkImItem = None
        self.stkBinImItem = None
        self.stkCelImItem = None
        self.offAziImItem = None
        self.kxyPatImItem = None

        # corresponding color bars
        self.layoutColorBar = None                                              # colorBars, added to imageItem
        self.stkTrkColorBar = None
        self.stkBinColorBar = None
        self.stkCelColorBar = None
        self.offAziColorBar = None
        self.kxyPatColorBar = None

        # rps, sps, xps input arrays
        self.rpsImport = None                                                   # numpy array with list of RPS records
        self.spsImport = None                                                   # numpy array with list of SPS records
        self.xpsImport = None                                                   # numpy array with list of XPS records

        self.rpsLiveE = None                                                    # numpy array with list of live RPS coordinates
        self.rpsLiveN = None                                                    # numpy array with list of live RPS coordinates
        self.rpsDeadE = None                                                    # numpy array with list of dead RPS coordinates
        self.rpsDeadN = None                                                    # numpy array with list of dead RPS coordinates

        self.spsLiveE = None                                                    # numpy array with list of live SPS coordinates
        self.spsLiveN = None                                                    # numpy array with list of live SPS coordinates
        self.spsDeadE = None                                                    # numpy array with list of dead SPS coordinates
        self.spsDeadN = None                                                    # numpy array with list of dead SPS coordinates

        self.rpsBound = None                                                    # numpy array with list of RPS convex hull coordinates
        self.spsBound = None                                                    # numpy array with list of SPS convex hull coordinates

        # rel, src, rel input arrays
        self.recGeom = None                                                     # numpy array with list of REC records
        self.srcGeom = None                                                     # numpy array with list of SRC records
        self.relGeom = None                                                     # numpy array with list of REL records

        self.recLiveE = None                                                    # numpy array with list of live REC coordinates
        self.recLiveN = None                                                    # numpy array with list of live REC coordinates
        self.recDeadE = None                                                    # numpy array with list of dead REC coordinates
        self.recDeadN = None                                                    # numpy array with list of dead REC coordinates

        self.srcLiveE = None                                                    # numpy array with list of live SRC coordinates
        self.srcLiveN = None                                                    # numpy array with list of live SRC coordinates
        self.srcDeadE = None                                                    # numpy array with list of dead SRC coordinates
        self.srcDeadN = None                                                    # numpy array with list of dead SRC coordinates

        # spider plot settings
        self.spiderPoint = QPoint(-1, -1)                                       # spider point 'out of scope'
        self.spiderSrcX = None                                                  # numpy array with list of SRC part of spider plot
        self.spiderSrcY = None                                                  # numpy array with list of SRC part of spider plot
        self.spiderRecX = None                                                  # numpy array with list of REC part of spider plot
        self.spiderRecY = None                                                  # numpy array with list of REC part of spider plot
        self.spiderText = None                                                  # text label describing spider bin, stake, fold
        self.actionSpider.setChecked(False)                                     # reset spider plot to 'off'
        self.actionSpider.setEnabled(False)
        self.spiderMode = Direction.NA                                          # current spider navigation mode

        # export layers to QGIS
        self.spsLayer = None                                                    # QGIS layer for sps point I/O
        self.rpsLayer = None                                                    # QGIS layer for rpr point I/O
        self.srcLayer = None                                                    # QGIS layer for src point I/O
        self.recLayer = None                                                    # QGIS layer for rec point I/O
        self.spsField = None                                                    # QGIS field for sps point selection I/O
        self.rpsField = None                                                    # QGIS field for rps point selection I/O
        self.srcField = None                                                    # QGIS field for src point selection I/O
        self.recField = None                                                    # QGIS field for rec point selection I/O

        # ruler settings
        self.lineROI = None                                                     # the ruler's dotted line
        self.roiLabels = None                                                   # the ruler's three labels
        self.rulerState = None                                                  # ruler's state, used to redisplay ruler at last used location

        # warning dialogs that can be hidden
        self.hideSpsCrsWarning = False                                          # warning message: sps crs should be identical to project crs

        # pattern information plotting parameters
        self.patternLayout = True                                               # True shows geometry (layout). False shows kxky response

        # icon_path = ':/plugins/roll/resources/icon.png'
        iconFile = os.path.join(resource_dir, 'icon.png')

        icon = QIcon(iconFile)
        self.setWindowIcon(icon)

        # See: https://gist.github.com/dgovil/d83e7ddc8f3fb4a28832ccc6f9c7f07b dealing with settings
        # See also : https://doc.qt.io/qtforpython-5/PySide2/QtCore/QSettings.html
        # QCoreApplication.setOrganizationName('Duijndam.Dev')
        # QCoreApplication.setApplicationName('Roll')
        # self.settings = QSettings()   ## doesn't work as expected with QCoreApplication.setXXX

        self.settings = QSettings(config.organization, config.application)
        self.fileName = ''
        self.projectDirectory = ''
        self.importDirectory = ''

        self.survey = RollSurvey()                                              # (re)set the survey object; needed in property pane
        readSettings(self)                                                      # read settings from QSettings in an early stage

        self.mainTabWidget = QTabWidget()
        self.mainTabWidget.setTabPosition(QTabWidget.TabPosition.South)
        self.mainTabWidget.setTabShape(QTabWidget.TabShape.Rounded)
        self.mainTabWidget.setDocumentMode(False)                               # has only effect on OSX ?!
        self.mainTabWidget.resize(300, 200)

        self.analysisTabWidget = QTabWidget()
        self.analysisTabWidget.setTabPosition(QTabWidget.TabPosition.South)
        self.analysisTabWidget.setTabShape(QTabWidget.TabShape.Rounded)
        self.analysisTabWidget.setDocumentMode(False)                           # has only effect on OSX ?!
        self.analysisTabWidget.resize(300, 200)

        # See: https://stackoverflow.com/questions/69152935/adding-the-same-object-to-a-qtabwidget
        # See: pyqtgraph/examples/RemoteSpeedTest.py to keep gui responsive when updating a plot (uses multiprocessing)

        self.plotTitles = [
            'New survey',
            'Offsets for inline direction',
            'Offsets for x-line direction',
            'Azimuth for inline direction',
            'Azimuth for x-line direction',
            'Stack response for inline direction',
            'Stack response for x-line direction',
            'Kx-Ky single bin stack response',
            '|Offset| distribution in binning area',
            'Offset/azimuth distribution in binning area',
            'Pattern information',
        ]

        # these plotting widgets have "installEventFilter()" applied to catch the window 'Show' event in "eventFilter()"
        # this makes it possible to reroute commands and status from the plotting toolbar buttons to the active plot
        self.offTrkWidget = self.createPlotWidget(self.plotTitles[1], 'inline', 'offset', 'm', 'm')                         # False -> no fixed aspect ratio
        self.offBinWidget = self.createPlotWidget(self.plotTitles[2], 'x-line', 'offset', 'm', 'm')
        self.aziTrkWidget = self.createPlotWidget(self.plotTitles[3], 'inline', 'angle of incidence', 'm', 'deg', False)
        self.aziBinWidget = self.createPlotWidget(self.plotTitles[4], 'x-line', 'angle of incidence', 'm', 'deg', False)    # no fixed aspect ratio
        self.stkTrkWidget = self.createPlotWidget(self.plotTitles[5], 'inline', '|Kr|', 'm', ' 1/km', False)
        self.stkBinWidget = self.createPlotWidget(self.plotTitles[6], 'x-line', '|Kr|', 'm', ' 1/km', False)
        self.stkCelWidget = self.createPlotWidget(self.plotTitles[7], 'Kx', 'Ky', '1/km', '1/km')
        self.offsetWidget = self.createPlotWidget(self.plotTitles[8], '|offset|', 'frequency', 'm', ' #', False)
        self.offAziWidget = self.createPlotWidget(self.plotTitles[9], 'azimuth', '|offset|', 'deg', 'm', False)
        self.arraysWidget = self.createPlotWidget(self.plotTitles[10], 'inline', 'x-line', 'm', 'm')

        # Create the various views (tabs) on the data
        # Use QCodeEditor with a XmlHighlighter instead of a 'plain' QPlainTextEdit
        # See: https://github.com/luchko/QCodeEditor/blob/master/QCodeEditor.py

        self.textEdit = QCodeEditor(SyntaxHighlighter=XMLHighlighter)           # only one widget on Xml-tab; add directly
        self.textEdit.document().setModified(False)
        self.textEdit.installEventFilter(self)                                  # catch the 'Show' event to connect to toolbar buttons

        # The following tabs have multiple widgets per page, start by giving them a simple QWidget
        self.tabPatterns = QWidget()
        self.tabGeom = QWidget()
        self.tabSps = QWidget()
        self.tabTraces = QWidget()
        self.tabKxKyStack = QWidget()

        self.tabGeom.installEventFilter(self)                                   # catch the 'Show' event to connect to toolbar buttons
        self.tabSps.installEventFilter(self)                                    # catch the 'Show' event to connect to toolbar buttons
        self.tabTraces.installEventFilter(self)                                 # catch the 'Show' event to connect to toolbar buttons

        # The following functions have been removed from this file's class definition, to reduce the size of 'roll_main_window.py'
        # They now reside in separate source files. Therefore self.createLayoutTab() is now called as createLayoutTab(self) instead.
        createLayoutTab(self)
        createPatternTab(self)
        createGeomTab(self)
        createSpsTab(self)
        createTraceTableTab(self)
        createStackResponseTab(self)

        # Add tabs to main tab widget
        self.mainTabWidget.addTab(self.layoutWidget, 'Layout')
        self.mainTabWidget.addTab(self.tabPatterns, 'Patterns')
        self.mainTabWidget.addTab(self.textEdit, 'Xml')
        self.mainTabWidget.addTab(self.tabGeom, 'Geometry')
        self.mainTabWidget.addTab(self.tabSps, 'SPS import')
        self.mainTabWidget.addTab(self.analysisTabWidget, 'Analysis')
        self.mainTabWidget.currentChanged.connect(self.onMainTabChange)         # active tab changed!

        # Add tabs to analysis tab widget
        self.analysisTabWidget.addTab(self.tabTraces, 'Trace table')
        self.analysisTabWidget.addTab(self.offTrkWidget, 'Offset Inline')
        self.analysisTabWidget.addTab(self.offBinWidget, 'Offset X-line')
        self.analysisTabWidget.addTab(self.aziTrkWidget, 'Azi Inline')
        self.analysisTabWidget.addTab(self.aziBinWidget, 'Azi X-line')
        self.analysisTabWidget.addTab(self.stkTrkWidget, 'Stack Inline')
        self.analysisTabWidget.addTab(self.stkBinWidget, 'Stack X-line')
        self.analysisTabWidget.addTab(self.tabKxKyStack, 'Kx-Ky Stack')
        self.analysisTabWidget.addTab(self.offsetWidget, '|O| Histogram')
        self.analysisTabWidget.addTab(self.offAziWidget, 'O/A Histogram')
        # self.arraysWidget is embedded in the layout of the 'pattern' tab
        # self.analysisTabWidget.addTab(self.stkCelWidget, 'Kx-Ky Stack')
        # self.analysisTabWidget.currentChanged.connect(self.onAnalysisTabChange)   # active tab changed!

        self.setCurrentFileName()

        # connect actions
        self.textEdit.document().modificationChanged.connect(self.setWindowModified)    # forward signal to myself, and make some changes
        self.setWindowModified(self.textEdit.document().isModified())                   # update window status based on document status
        self.textEdit.cursorPositionChanged.connect(self.cursorPositionChanged)         # to show cursor position in statusbar

        self.layoutWidget.scene().sigMouseMoved.connect(self.MouseMovedInPlot)
        self.layoutWidget.plotItem.sigRangeChanged.connect(self.layoutRangeChanged)     # to handle changes in tickmarks when zooming

        # the following actions are related to the plotWidget
        self.actionZoomAll.triggered.connect(self.layoutWidget.autoRange)
        self.actionZoomRect.setCheckable(True)
        self.actionZoomRect.setChecked(self.rect)
        self.actionZoomRect.triggered.connect(self.plotZoomRect)

        self.actionAspectRatio.setCheckable(True)
        self.actionAspectRatio.setChecked(self.XisY)
        self.actionAspectRatio.triggered.connect(self.plotAspectRatio)

        self.actionAntiAlias.setCheckable(True)
        self.actionAntiAlias.setChecked(self.antiA[0])
        self.actionAntiAlias.triggered.connect(self.plotAntiAlias)

        self.actionPlotGridX.setCheckable(True)
        self.actionPlotGridX.setChecked(self.gridX)
        self.actionPlotGridX.triggered.connect(self.plotGridX)

        self.actionPlotGridY.setCheckable(True)
        self.actionPlotGridY.setChecked(self.gridY)
        self.actionPlotGridY.triggered.connect(self.plotGridY)

        self.actionProjected.setCheckable(True)
        self.actionProjected.setChecked(self.glob)
        self.actionProjected.triggered.connect(self.plotProjected)

        self.actionRuler.setCheckable(True)
        self.actionRuler.setChecked(self.ruler)
        self.actionRuler.triggered.connect(self.showRuler)

        # actions related to the file menu
        for i in range(config.maxRecentFiles):
            self.recentFileActions.append(QAction(self, visible=False, triggered=self.fileOpenRecent))
            self.menuOpenRecent.addAction(self.recentFileActions[i])

        self.actionNew.triggered.connect(self.newFile)
        self.actionNewLandSurvey.triggered.connect(self.fileNewLandSurvey)
        self.actionNewMarineSurvey.triggered.connect(self.fileNewMarineSurvey)
        self.actionOpen.triggered.connect(self.fileOpen)
        self.actionImportSPS.triggered.connect(self.fileImportSpsData)
        self.actionPrint.triggered.connect(self.filePrint)
        self.actionSave.triggered.connect(self.fileSave)
        self.actionSaveAs.triggered.connect(self.fileSaveAs)
        self.actionSettings.triggered.connect(self.fileSettings)

        self.textEdit.document().modificationChanged.connect(self.actionSave.setEnabled)

        # actions related to file -> export
        self.actionExportFoldMap.triggered.connect(self.fileExportFoldMap)
        self.actionExportMinOffsets.triggered.connect(self.fileExportMinOffsets)
        self.actionExportMaxOffsets.triggered.connect(self.fileExportMaxOffsets)
        self.actionExportRmsOffsets.triggered.connect(self.fileExportRmsOffsets)

        self.actionExportAnaAsCsv.triggered.connect(self.fileExportAnaAsCsv)

        self.actionExportRecAsCsv.triggered.connect(self.fileExportRecAsCsv)
        self.actionExportSrcAsCsv.triggered.connect(self.fileExportSrcAsCsv)
        self.actionExportRelAsCsv.triggered.connect(self.fileExportRelAsCsv)
        self.actionExportRecAsR01.triggered.connect(self.fileExportRecAsR01)
        self.actionExportSrcAsS01.triggered.connect(self.fileExportSrcAsS01)
        self.actionExportRelAsX01.triggered.connect(self.fileExportRelAsX01)

        self.actionExportRpsAsCsv.triggered.connect(self.fileExportRpsAsCsv)
        self.actionExportSpsAsCsv.triggered.connect(self.fileExportSpsAsCsv)
        self.actionExportXpsAsCsv.triggered.connect(self.fileExportXpsAsCsv)
        self.actionExportRpsAsR01.triggered.connect(self.fileExportRpsAsR01)
        self.actionExportSpsAsS01.triggered.connect(self.fileExportSpsAsS01)
        self.actionExportXpsAsX01.triggered.connect(self.fileExportXpsAsX01)

        self.actionExportFoldMapToQGIS.triggered.connect(self.exportBinToQGIS)
        self.actionExportMinOffsetsToQGIS.triggered.connect(self.exportMinToQGIS)
        self.actionExportMaxOffsetsToQGIS.triggered.connect(self.exportMaxToQGIS)
        self.actionExportRmsOffsetsToQGIS.triggered.connect(self.exportRmsToQGIS)

        self.actionQuit.triggered.connect(self.close)                           # closes the window and arrives at CloseEvent()

        # actions related to the edit menu
        # undo and redo are solely associated with the main xml textEdit
        self.actionUndo.triggered.connect(self.textEdit.undo)
        self.actionRedo.triggered.connect(self.textEdit.redo)
        self.textEdit.document().undoAvailable.connect(self.actionUndo.setEnabled)
        self.textEdit.document().redoAvailable.connect(self.actionRedo.setEnabled)

        # copy, cut, paste and select-all must be managed by all active widgets
        # See: https://stackoverflow.com/questions/40041131/pyqt-global-copy-paste-actions-for-custom-widgets
        self.actionCut.triggered.connect(self.cut)
        self.actionCopy.triggered.connect(self.copy)
        self.actionFind.triggered.connect(self.find)
        self.actionPaste.triggered.connect(self.paste)
        self.actionSelectAll.triggered.connect(self.selectAll)

        # the following setEnabled items need to be re-wired, they are still connected to the textEdit
        self.textEdit.copyAvailable.connect(self.actionCut.setEnabled)
        self.textEdit.copyAvailable.connect(self.actionCopy.setEnabled)

        # actions related to the view menu
        self.actionRefreshPlot.triggered.connect(self.replotLayout)             # hooked up with F5
        self.actionReparseDocument.triggered.connect(self.UpdateAllViews)       # hooked up with Ctrl+F5
        self.actionStopPainting.triggered.connect(self.stopPainting)            # hooked up with Esc

        # actions related to the processing menu
        self.actionBasicBinFromTemplates.triggered.connect(self.basicBinFromTemplates)
        self.actionFullBinFromTemplates.triggered.connect(self.fullBinFromTemplates)
        self.actionBasicBinFromGeometry.triggered.connect(self.basicBinFromGeometry)
        self.actionFullBinFromGeometry.triggered.connect(self.fullBinFromGeometry)
        self.actionBasicBinFromSps.triggered.connect(self.basicBinFromSps)
        self.actionFullBinFromSps.triggered.connect(self.fullBinFromSps)
        self.actionGeometryFromTemplates.triggered.connect(self.createGeometryFromTemplates)

        # actions related to the help menu
        self.actionAbout.triggered.connect(self.OnAbout)
        self.actionLicense.triggered.connect(self.OnLicense)
        self.actionHighDpi.triggered.connect(self.OnHighDpi)
        self.actionQGisCheatSheet.triggered.connect(self.OnQGisCheatSheet)
        self.actionQGisRollInterface.triggered.connect(self.OnQGisRollInterface)

        self.actionStopThread.triggered.connect(self.stopWorkerThread)

        # actions related to geometry items to be displayed
        self.actionTemplates.triggered.connect(self.replotLayout)
        self.actionRecPoints.triggered.connect(self.replotLayout)
        self.actionSrcPoints.triggered.connect(self.replotLayout)
        self.actionRpsPoints.triggered.connect(self.replotLayout)
        self.actionSpsPoints.triggered.connect(self.replotLayout)
        self.actionAllPoints.triggered.connect(self.replotLayout)

        # enable/disable various actions
        self.actionClose.setEnabled(False)
        self.actionSave.setEnabled(self.textEdit.document().isModified())
        # self.actionSaveAs.setEnabled((self.textEdit.document().blockCount() > 1))        # need at least one line of text to save the document
        self.actionSaveAs.setEnabled((True))                                    # need at least one line of text to save the document

        self.actionUndo.setEnabled(self.textEdit.document().isUndoAvailable())
        self.actionRedo.setEnabled(self.textEdit.document().isRedoAvailable())
        self.actionCut.setEnabled(False)
        self.actionCopy.setEnabled(self._grabPlotWidgetForPrint() is not None)
        self.actionPaste.setEnabled(self.clipboardHasText())

        self.updateMenuStatus(True)                                             # keep menu status in sync with program's state
        # self.enableProcessingMenuItems(True)                                  # enables processing menu items except 'stop processing thread'; done in resetSurveyProperties()

        # make the main tab widget the central widget
        self.setCentralWidget(self.mainTabWidget)

        self.posWidgetStatusbar = QLabel('(x, y): (0.00, 0.00)')
        self.statusbar.addPermanentWidget(self.posWidgetStatusbar, stretch=0)   # widget in bottomright corner of statusbar

        self.appendLogMessage(f'Plugin : Started on {platform.system()} {platform.release()} v({platform.version()})')  # log program start
        if haveNumba:
            self.appendLogMessage(f'Library: Numba version {numba.__version__} available for JIT acceleration')
            if numba.__version__ < '0.62.1':
                self.appendLogMessage('Library: Numba version is not the latest version, consider upgrading to v0.62.1', MsgType.Warning)
            if config.useNumba:
                self.appendLogMessage('Library: Numba is enabled, running in JIT mode')
        else:
            self.appendLogMessage('Library: Numba not available, running pure Python code only', MsgType.Warning)

        if not haveDebugpy:
            self.appendLogMessage('Library: Debugpy not available, (remote) debugging will not work', MsgType.Warning)

        if pg.__version__ < '0.13.7':
            self.appendLogMessage(f'Library: Pyqtgraph version {pg.__version__} detected, consider upgrading to the latest version', MsgType.Warning)

        self.parseText(exampleSurveyXmlText())                                  # load an example survey in the textEdit
        self.textEdit.setPlainText(exampleSurveyXmlText())
        self.textEdit.moveCursor(QTextCursor.MoveOperation.Start)

        # third docking pane, used to display survey properties
        self.parameters = None
        self.binChild   = None
        self.grdChild   = None
        create_property_dock(self)                                              # defined late, as it needs access the loaded survey object

        # self.dockProperty = QDockWidget('Property pane')
        # self.dockProperty.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        # self.dockProperty.setStyleSheet('QDockWidget::title {background : lightblue;}')

        # # setup the ParameterTree object
        # self.paramTree = pg.parametertree.ParameterTree(showHeader=True)        # define parameter tree widget
        # self.paramTree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # self.paramTree.header().resizeSection(0, 280)
        # self.registerParameters()
        # self.resetSurveyProperties()                                            # get the parameters into the parameter tree

        # self.propertyWidget = QWidget()                                         # placeholder widget to generate a layout
        # self.propertyLayout = QVBoxLayout()                                     # required vertical layout

        # buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply
        # self.propertyButtonBox = QDialogButtonBox(buttons)                      # define 3 buttons to handle property changes

        # # connect 3 buttons (signals) to their event handlers (slots)
        # self.propertyButtonBox.accepted.connect(self.applyPropertyChangesAndHide)
        # self.propertyButtonBox.rejected.connect(self.resetSurveyProperties)
        # self.propertyButtonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.applyPropertyChanges)

        # self.propertyLayout.addWidget(self.paramTree)                           # add parameter tree to layout
        # self.propertyLayout.addStretch()                                        # add some stretch towards 3 buttons
        # self.propertyLayout.addWidget(self.propertyButtonBox)                   # add 3 buttons

        # self.propertyWidget.setLayout(self.propertyLayout)                      # add layout to widget
        # self.dockProperty.setWidget(self.propertyWidget)

        # self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockProperty)           # add docking panel to main window

        # self.dockProperty.toggleViewAction().setShortcut(QKeySequence('Ctrl+Alt+p'))
        # self.menu_View.addAction(self.dockProperty.toggleViewAction())          # show/hide as requested

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

        self.menu_View.addSeparator()
        self.menu_View.addAction(self.fileBar.toggleViewAction())
        self.menu_View.addAction(self.editBar.toggleViewAction())
        self.menu_View.addAction(self.graphBar.toggleViewAction())
        self.menu_View.addAction(self.moveBar.toggleViewAction())
        self.menu_View.addAction(self.paintBar.toggleViewAction())

        self.plotLayout()

        self.updateRecentFileActions()                                          # update the MRU file menu actions, with info from readSettings()

        if self.standaloneMode:                                                 # Optional: disable actions that require a live QGIS iface
            self._configureStandaloneUi()

        self.statusbar.showMessage('Ready', 3000)

    def _configureStandaloneUi(self):
        # Guard or disable iface-dependent actions here
        self.actionImportFromQgis.setEnabled(False)
        self.actionExportToQgis.setEnabled(False)
        self.actionExportFoldMapToQGIS.setEnabled(False)
        self.actionExportMinOffsetsToQGIS.setEnabled(False)
        self.actionExportMaxOffsetsToQGIS.setEnabled(False)
        self.actionExportRmsOffsetsToQGIS.setEnabled(False)

    # deal with pattern selection for display & kxky plotting
    def onPattern1IndexChanged(self):
        self.plotPatterns()

    def onPattern2IndexChanged(self):
        self.plotPatterns()

    def onActionPatternLayoutTriggered(self):
        self.patternLayout = True
        self.plotPatterns()

    def onActionPattern_kx_kyTriggered(self):
        self.patternLayout = False
        self.plotPatterns()

    # deal with pattern selection for bin stack response
    def onStackPatternIndexChanged(self):
        nX = self.spiderPoint.x()                                               # get x, y indices into bin array
        nY = self.spiderPoint.y()

        if self.spiderPoint.x() < 0:
            return

        if self.spiderPoint.y() < 0:
            return

        if self.survey.binTransform is None:
            return

        invBinTransform, _ = self.survey.binTransform.inverted()                # need to go from bin nr's to cmp(x, y)
        cmpX, cmpY = invBinTransform.map(nX, nY)                                # get local coordinates from line and point indices
        stkX, stkY = self.survey.st2Transform.map(cmpX, cmpY)                   # get the corresponding bin and stake numbers

        self.plotStkCel(nX, nY, stkX, stkY)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.Show:                                             # do 'cheap' test first
            if isinstance(source, pg.PlotWidget):                                   # do 'expensive' test next

                with contextlib.suppress(RuntimeError):                             # rewire zoomAll button
                    self.actionZoomAll.triggered.disconnect()
                self.actionZoomAll.triggered.connect(source.autoRange)

                plotIndex = self.getVisiblePlotIndex(source)                        # update toolbar status
                if plotIndex is not None:
                    self.actionZoomAll.setEnabled(True)                             # useful for all plots
                    self.actionZoomRect.setEnabled(True)                            # useful for all plots
                    self.actionAspectRatio.setEnabled(True)                         # useful for all plots
                    self.actionAntiAlias.setEnabled(True)                           # useful for plots only
                    self.actionRuler.setEnabled(plotIndex == 0)                     # useful for 1st plot only
                    self.actionProjected.setEnabled(plotIndex == 0)                 # useful for 1st plot only

                    self.actionAntiAlias.setChecked(self.antiA[plotIndex])          # useful for all plots

                    plotItem = source.getPlotItem()
                    self.gridX = plotItem.saveState()['xGridCheck']                 # update x-gridline status
                    self.actionPlotGridX.setChecked(self.gridX)

                    self.gridY = plotItem.saveState()['yGridCheck']                 # update y-gridline status
                    self.actionPlotGridY.setChecked(self.gridY)

                    self.XisY = plotItem.saveState()['view']['aspectLocked']        # update XisY status
                    self.actionAspectRatio.setChecked(self.XisY)

                    viewBox = plotItem.getViewBox()
                    self.rect = viewBox.getState()['mouseMode'] == pg.ViewBox.RectMode  # update rect status
                    self.actionZoomRect.setChecked(self.rect)
                    self.updateVisiblePlotWidget(plotIndex)
                    return True
            else:                                                                   # QEvent.Show; but for different widgets
                self.actionZoomAll.setEnabled(False)                                # useful for plots only
                self.actionZoomRect.setEnabled(False)                               # useful for plots only
                self.actionAspectRatio.setEnabled(False)                            # useful for plots only
                self.actionAntiAlias.setEnabled(False)                              # useful for plots only
                self.actionRuler.setEnabled(False)                                  # useful for 1st plot only
                self.actionProjected.setEnabled(False)                              # useful for 1st plot only
                return True

        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:  # Check if the ESC key is pressed
            self.interrupted = True
        super().keyPressEvent(event)

    def applyPropertyChangesAndHide(self):
        self.applyPropertyChanges()
        self.dockProperty.hide()

    def registerParameters(self):
        registerAllParameterTypes()

    def resetSurveyProperties(self):

        self.paramTree.clear()

        # set the survey object in the property pane using current survey properties
        copy = self.survey.deepcopy()

        # create valid pattern list, before using it in property panel
        self.updatePatternList(copy)

        # first copy the crs for global access (todo: need to fix this later)
        config.surveyCrs = copy.crs

        # brush color for main parameter categories
        brush = '#add8e6'

        surveyParams = [
            dict(brush=brush, name='Survey configuration', type='myConfiguration', value=copy, default=copy),
            dict(brush=brush, name='Survey analysis', type='myAnalysis', value=copy, default=copy),
            dict(brush=brush, name='Survey reflectors', type='myReflectors', value=copy, default=copy),
            dict(brush=brush, name='Survey grid', type='myGrid', value=copy.grid, default=copy.grid),
            dict(brush=brush, name='Block list', type='myBlockList', value=copy.blockList, default=copy.blockList, directory=self.projectDirectory),
            dict(brush=brush, name='Pattern list', type='myPatternList', value=copy.patternList, default=copy.patternList),
        ]

        self.parameters = pg.parametertree.Parameter.create(name='Survey Properties', type='group', children=surveyParams)
        self.parameters.sigTreeStateChanged.connect(self.propertyTreeStateChanged)

        # Block signals to speed up parameter tree setup
        self.paramTree.blockSignals(True)
        self.paramTree.setParameters(self.parameters, showTop=False)
        self.paramTree.blockSignals(False)

        # Make sure we get a notification, when the binning area or the survey grid has changed, to ditch the analysis files
        self.binChild = self.parameters.child('Survey analysis', 'Binning area')
        self.binChild.sigTreeStateChanged.connect(self.binningSettingsHaveChanged)

        self.grdChild = self.parameters.child('Survey grid')
        self.grdChild.sigTreeStateChanged.connect(self.binningSettingsHaveChanged)

        # deal with a bug, not showing tooltip information in the list of parameterItems
        # make sure the default buttons are greyed out in the parameter tree and count the items
        nItem = 0
        for item in self.paramTree.listAllItems():                              # Bug. See: https://github.com/pyqtgraph/pyqtgraph/issues/2744
            p = item.param                                                      # get parameter belonging to parameterItem
            if 'tip' in p.opts:                                                 # this solves the above mentioned bug
                item.setToolTip(0, p.opts['tip'])                               # the widgets now get their tooltips
            if hasattr(item, 'updateDefaultBtn'):                               # note: not all parameterItems have this method
                p.setToDefault()                                                # set parameters to its default value
                item.updateDefaultBtn()                                         # reset the default-button to its grey value
            nItem += 1
        self.appendLogMessage(f'Params : {self.fileName} survey object read, containing {nItem} parameters')
        self.enableProcessingMenuItems(True)                                    # enable processing menu items; disable 'stop processing thread'

    def updatePatternList(self, survey):

        assert isinstance(survey, RollSurvey), 'make sure we have a RollSurvey object here'

        patterns = survey.patternList                                           # use survey as source of truth (no longer using config.patternList)
        names = [p.name for p in patterns]

        combos = [self.pattern1, self.pattern2, self.pattern3, self.pattern4]

        for combo in combos:
            combo.blockSignals(True)
        try:
            # for pattern response display and kxky response
            self.pattern1.clear()
            self.pattern1.addItem('<no pattern>')
            for name in names:
                self.pattern1.addItem(name)

            self.pattern2.clear()
            self.pattern2.addItem('<no pattern>')                               # setup second pattern list in pattern tab
            for name in names:
                self.pattern2.addItem(name)

            listSize = len(names)                                               # show the first two paterns (if available)
            self.pattern1.setCurrentIndex(min(listSize, 1))                     # select first pattern in list
            self.pattern2.setCurrentIndex(min(listSize, 2))                     # select first pattern in list

            # for convolution of stack response with pattern response
            self.pattern3.clear()
            self.pattern3.addItem('<no pattern>')                               # setup first pattern list in pattern tab
            for name in names:
                self.pattern3.addItem(name)

            self.pattern4.clear()
            self.pattern4.addItem('<no pattern>')                               # setup second pattern list in pattern tab
            for name in names:
                self.pattern4.addItem(name)

            self.pattern3.setCurrentIndex(min(listSize, 1))                     # select first pattern in list
            self.pattern4.setCurrentIndex(min(listSize, 2))                     # select first pattern in list
        finally:
            for combo in combos:
                combo.blockSignals(False)

    def applyPropertyChanges(self):
        # build new survey object from scratch, and start adding to it
        copy = RollSurvey()

        CFG = self.parameters.child('Survey configuration')

        copy.crs, surType, copy.name = CFG.value()                              # get tuple of data from parameter
        copy.type = SurveyType2[surType]                                        # SurveyType2 is an enum
        config.surveyCrs = copy.crs                                             # needed for global access to crs

        ANA = self.parameters.child('Survey analysis')
        copy.output.rctOutput, copy.angles, copy.binning, copy.offset, copy.unique = ANA.value()

        REF = self.parameters.child('Survey reflectors')
        copy.globalPlane, copy.globalSphere = REF.value()

        GRD = self.parameters.child('Survey grid')
        copy.grid = GRD.value()

        BLK = self.parameters.child('Block list')
        copy.blockList = BLK.value()

        PAT = self.parameters.child('Pattern list')
        copy.patternList = PAT.value()

        # first check survey integrity before committing to it.
        if copy.checkIntegrity(self.projectDirectory) is False:
            return

        self.survey = copy.deepcopy()                                           # start using the updated survey object

        # update the survey object with the necessary steps
        self.survey.calcTransforms()                                            # (re)calculate the transforms being used
        self.survey.calcSeedData()                                              # needed for circles, spirals & well-seeds; may affect bounding box
        self.survey.calcBoundingRect()                                          # (re)calculate the boundingBox as part of parsing the data
        self.survey.calcNoShotPoints()                                          # (re)calculate nr of shot points

        # check if it is a marine survey; set seed plotting details accordingly
        self.setPlottingDetails()

        plainText = self.survey.toXmlString()                                   # convert the survey object itself to an Xml string
        self.textEdit.setTextViaCursor(plainText)                               # get text into the textEdit, NOT resetting its doc status
        self.textEdit.document().setModified(True)                              # we edited the document; so it's been modified

        if self.binAreaChanged:                                                 # we need to throw away the analysis results
            self.binAreaChanged = False                                         # reset this flag

            self.inlineStk = None                                               # numpy array with inline Kr stack reponse
            self.x_lineStk = None                                               # numpy array with x_line Kr stack reponse
            self.xyCellStk = None                                               # numpy array with cell's KxKy stack response
            self.xyPatResp = None                                               # numpy array with pattern's KxKy response

            # the following arrays are calculated in a separate binning thread and stored under the 'output' object
            self.output.binOutput = None                                        # numpy array with foldmap
            self.output.minOffset = None                                        # numpy array with minimum offset
            self.output.maxOffset = None                                        # numpy array with maximum offset
            self.output.rmsOffset = None                                        # numpy array with rms delta offset
            self.output.ofAziHist = None                                        # numpy array with offset/azimuth distribution
            self.output.offstHist = None                                        # numpy array with offset distribution

            if self.resetAnaTableModel():
                self.appendLogMessage(f"Edited : Closing memory mapped file {self.fileName + '.ana.npy'}")

            binFileName = self.fileName + '.bin.npy'                            # file names for analysis files
            minFileName = self.fileName + '.min.npy'
            maxFileName = self.fileName + '.max.npy'
            rmsFileName = self.fileName + '.rms.npy'
            anaFileName = self.fileName + '.ana.npy'

            try:
                if os.path.exists(binFileName):
                    os.remove(binFileName)                                      # remove file names, if possible
                if os.path.exists(minFileName):
                    os.remove(minFileName)
                if os.path.exists(maxFileName):
                    os.remove(maxFileName)
                if os.path.exists(rmsFileName):
                    os.remove(rmsFileName)
                if os.path.exists(anaFileName):
                    os.remove(anaFileName)
            except OSError as e:
                self.appendLogMessage(f"Can't delete file, {e}")
            self.updateMenuStatus(True)                                         # keep menu status in sync with program's state; analysis files have been deleted !
        else:
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; analysis files have not been deleted
        self.enableProcessingMenuItems(True)                                    # enable processing menu items; disable 'stop processing thread'

        self.appendLogMessage(f'Edited : {self.fileName} survey object updated')

        self.updatePatternList(self.survey)                                     # pattern list may be altered during parameter editing session
        self.plotLayout()

    def binningSettingsHaveChanged(self, *_):                                   # param, changes unused; replaced by *_
        self.binAreaChanged = True

    ## If anything changes in the tree, print a message
    def propertyTreeStateChanged(self, param, changes):

        # the next line is needed in case we would disable the 'Apply' button in the property pane, when no changes have been made
        # self.propertyButtonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)

        # Nomatter whether debug has been set to True or False
        myPrint('┌── sigTreeStateChanged --> tree changes:')
        for param, change, data in changes:
            path = self.parameters.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()
            myPrint(f'│     parameter: {childName}')
            myPrint(f'│     change:    {change}')
            myPrint(f'│     data:      {str(data)}')
            myPrint('└───────────────────────────────────────')

    def onMainTabChange(self, index):                                           # manage focus when active tab is changed; doesn't work 100% yet !
        if index == 0:                                                          # main plotting widget
            self.handleSpiderPlot()
        else:
            widget = self.mainTabWidget.currentWidget()
            if isinstance(widget, QCodeEditor):
                widget.setFocus()

        plotWidget = self._grabPlotWidgetForPrint()
        if plotWidget is not None:
            self.actionCopy.setEnabled(True)

    def _invokeFocusMethod(self, methodName: str) -> bool:
        obj = QApplication.focusWidget()
        if obj is None:
            obj = QApplication.focusObject()
        if obj is None:
            return False

        method = getattr(obj, methodName, None)
        if callable(method):
            method()
            return True
        return False

    def cut(self):
        self._invokeFocusMethod('cut')
        self.actionPaste.setEnabled(self.clipboardHasText())

    def copy(self):
        if not self._invokeFocusMethod('copy'):
            self._copyPlotWidgetToClipboard()
        self.actionPaste.setEnabled(self.clipboardHasText())

    def paste(self):
        self._invokeFocusMethod('paste')

    def selectAll(self):
        self._invokeFocusMethod('selectAll')

    def find(self):
        # find only operates on the xml-text edit
        self.mainTabWidget.setCurrentIndex(2)
        if getattr(self, 'findDialog', None) is None:
            self.findDialog = FindNotepad(self)
        self.findDialog.show()
        self.findDialog.raise_()
        self.findDialog.activateWindow()

    def createPlotWidget(self, plotTitle='', xAxisTitle='', yAxisTitle='', unitX='', unitY='', aspectLocked=True):
        """Create a plot widget for first usage"""
        w = pg.PlotWidget(background='w')
        w.setAspectLocked(True)                                                 # setting can be changed through a toolbar
        w.showGrid(x=True, y=True, alpha=0.75)                                  # shows the grey grid lines
        w.setMinimumSize(150, 150)                                              # prevent excessive widget shrinking
        # See: https://stackoverflow.com/questions/44402399/how-to-disable-the-default-context-menu-of-pyqtgraph for context menu options
        w.setContextMenuActionVisible('Transforms', False)
        w.setContextMenuActionVisible('Downsample', False)
        w.setContextMenuActionVisible('Average', False)
        w.setContextMenuActionVisible('Alpha', False)
        w.setContextMenuActionVisible('Points', False)

        # w.setMenuEnabled(False, enableViewBoxMenu=None)                       # get rid of context menu but keep ViewBox menu
        # w.ctrlMenu = None                                                     # get rid of 'Plot Options' in context menu
        # w.scene().contextMenu = None                                          # get rid of 'Export' in context menu

        # set up plot title
        w.setTitle(plotTitle, color='b', size='16pt')

        # setup axes
        styles = {'color': '#000', 'font-size': '10pt'}
        w.showAxes(True, showValues=(True, False, False, True))                 # show values at the left and at the bottom
        w.setLabel('bottom', xAxisTitle, units=unitX, **styles)                 # shows axis at the bottom, and shows the units label
        w.setLabel('left', yAxisTitle, units=unitY, **styles)                   # shows axis at the left, and shows the units label
        w.setLabel('top', ' ', **styles)                                        # shows axis at the top, no label, no tickmarks
        w.setLabel('right', ' ', **styles)                                      # shows axis at the right, no label, no tickmarks
        w.setAspectLocked(aspectLocked)

        w.installEventFilter(self)                                              # filter the 'Show' event to connect to toolbar buttons
        return w

    def resetPlotWidget(self, w, plotTitle):
        w.plotItem.clear()
        w.setTitle(plotTitle, color='b', size='16pt')

    # define several sps, rps, xps button functions
    def sortSpsData(self, index):
        if self.spsImport is None:
            return
        self.spsModel.applySort(index)
        self.appendLogMessage(f'Sorting: SPS-data sorted on {self.spsModel.sortColumns()}')

    def sortRpsData(self, index):
        if self.rpsImport is None:
            return
        self.rpsModel.applySort(index)
        self.appendLogMessage(f'Sorting: RPS-data sorted on {self.rpsModel.sortColumns()}')

    def sortXpsData(self, index):
        if self.xpsImport is None:
            return
        self.xpsModel.applySort(index)
        self.appendLogMessage(f'Sorting: XPS-data sorted on {self.xpsModel.sortColumns()}')

    def removeRpsDuplicates(self):
        if self.rpsImport is None:
            return

        self.rpsImport, before, after = deletePntDuplicates(self.rpsImport)
        self.rpsModel.setData(self.rpsImport)                                   # update the model's data
        if after < before:                                                      # need to update the (x, y) points as well
            self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
            self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)            # get the convex hull of the rps points
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rps-duplicates')

    def removeSpsDuplicates(self):
        if self.spsImport is None:
            return

        self.spsImport, before, after = deletePntDuplicates(self.spsImport)
        self.spsModel.setData(self.spsImport)
        if after < before:
            self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
            self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)            # get the convex hull of the rps points
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} sps-duplicates')

    def removeRpsOrphans(self):
        if self.rpsImport is None:
            return

        self.rpsImport, before, after = deletePntOrphans(self.rpsImport)
        self.rpsModel.setData(self.rpsImport)
        if after < before:
            self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
            self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)            # get the convex hull of the rps points
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rps/xps-orphans')

    def removeSpsOrphans(self):
        if self.spsImport is None:
            return

        self.spsImport, before, after = deletePntOrphans(self.spsImport)
        self.spsModel.setData(self.spsImport)
        if after < before:
            self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
            self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)            # get the convex hull of the rps points
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} sps/xps-orphans')

    def removeXpsDuplicates(self):
        if self.xpsImport is None:
            return

        self.xpsImport, before, after = deleteRelDuplicates(self.xpsImport)
        self.xpsModel.setData(self.xpsImport)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} xps-duplicates')

    def removeXpsSpsOrphans(self):
        if self.xpsImport is None:
            return

        self.xpsImport, before, after = deleteRelOrphans(self.xpsImport, True)
        self.xpsModel.setData(self.xpsImport)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} xps/sps-orphans')

    def removeXpsRpsOrphans(self):
        if self.xpsImport is None:
            return

        self.xpsImport, before, after = deleteRelOrphans(self.xpsImport, False)
        self.xpsModel.setData(self.xpsImport)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} xps/rps-orphans')

    # define src, rec, rel button functions
    def sortRecData(self, index):
        if self.recGeom is None:
            return

        self.recModel.applySort(index)
        self.appendLogMessage(f'Sorting: REC-data sorted on {self.recModel.sortColumns()}')

    def sortSrcData(self, index):
        if self.srcGeom is None:
            return

        self.srcModel.applySort(index)
        self.appendLogMessage(f'Sorting: SRC-data sorted on {self.srcModel.sortColumns()}')

    def sortRelData(self, index):
        if self.relGeom is None:
            return

        self.relModel.applySort(index)
        self.appendLogMessage(f'Sorting: REL-data sorted on {self.relModel.sortColumns()}')

    def removeRecDuplicates(self):
        if self.recGeom is None:
            return

        self.recGeom, before, after = deletePntDuplicates(self.recGeom)
        self.recModel.setData(self.recGeom)                                     # update the model's data
        if after < before:                                                      # need to update the (x, y) points as well
            self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rec-duplicates')

    def removeSrcDuplicates(self):
        if self.srcGeom is None:
            return

        self.srcGeom, before, after = deletePntDuplicates(self.srcGeom)
        self.srcModel.setData(self.srcGeom)
        if after < before:
            self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} src-duplicates')

    def removeRecOrphans(self):
        if self.recGeom is None:
            return

        self.recGeom, before, after = deletePntOrphans(self.recGeom)
        self.recModel.setData(self.recGeom)
        if after < before:
            self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rec/rel-orphans')

    def removeSrcOrphans(self):
        if self.srcGeom is None:
            return

        self.srcGeom, before, after = deletePntOrphans(self.srcGeom)
        self.srcModel.setData(self.srcGeom)
        if after < before:
            self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)
            self.updateMenuStatus(False)                                        # keep menu status in sync with program's state; don't reset analysis figure
            self.plotLayout()
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} src/rel-orphans')

    def removeRelDuplicates(self):
        if self.relGeom is None:
            return

        self.relGeom, before, after = deleteRelDuplicates(self.relGeom)
        self.relModel.setData(self.relGeom)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rel-duplicates')

    def removeRelSrcOrphans(self):
        if self.relGeom is None:
            return

        self.relGeom, before, after = deleteRelOrphans(self.relGeom, True)
        self.relModel.setData(self.relGeom)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rel/src-orphans')

    def removeRelRecOrphans(self):
        if self.relGeom is None:
            return

        self.relGeom, before, after = deleteRelOrphans(self.relGeom, False)
        self.relModel.setData(self.relGeom)
        self.appendLogMessage(f'Filter : Filtered {before:,} records. Removed {(before - after):,} rel/rec-orphans')

    # define file export functions
    def fileExportFoldMap(self):
        if self.survey is not None and self.output.binOutput is not None and self.survey.crs is not None:
            fileName = self.fileName + '.bin.tif'
            fileName = CreateQgisRasterLayer(fileName, self.output.binOutput, self.survey)
            if fileName:
                self.appendLogMessage(f'Export : exported fold map to {fileName}')

    def fileExportMinOffsets(self):
        if self.survey is not None and self.output.minOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.min.tif'
            fileName = CreateQgisRasterLayer(fileName, self.output.minOffset, self.survey)
            if fileName:
                self.appendLogMessage(f'Export : exported min-offsets to {fileName}')

    def fileExportMaxOffsets(self):
        if self.survey is not None and self.output.maxOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.max.tif'
            fileName = CreateQgisRasterLayer(fileName, self.output.maxOffset, self.survey)
            if fileName:
                self.appendLogMessage(f'Export : exported max-offsets to {fileName}')

    def fileExportRmsOffsets(self):
        if self.survey is not None and self.output.rmsOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.rms.tif'
            fileName = CreateQgisRasterLayer(fileName, self.output.rmsOffset, self.survey)
            if fileName:
                self.appendLogMessage(f'Export : exported rms-offsets to {fileName}')

    def exportBinToQGIS(self):
        if self.survey is not None and self.output.binOutput is not None and self.survey.crs is not None:
            fileName = self.fileName + '.bin.tif'
            fileName = ExportRasterLayerToQgis(fileName, self.output.binOutput, self.survey)
            if fileName:
                self.appendLogMessage('Export : incorporated fold map in QGIS')

    def exportMinToQGIS(self):
        if self.survey is not None and self.output.minOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.min.tif'
            fileName = ExportRasterLayerToQgis(fileName, self.output.minOffset, self.survey)
            if fileName:
                self.appendLogMessage('Export : incorporated min-offset map in QGIS')

    def exportMaxToQGIS(self):
        if self.survey is not None and self.output.maxOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.max.tif'
            fileName = ExportRasterLayerToQgis(fileName, self.output.maxOffset, self.survey)
            if fileName:
                self.appendLogMessage('Export : incorporated max-offset map in QGIS')

    def exportRmsToQGIS(self):
        if self.survey is not None and self.output.rmsOffset is not None and self.survey.crs is not None:
            fileName = self.fileName + '.rms.tif'
            fileName = ExportRasterLayerToQgis(fileName, self.output.rmsOffset, self.survey)
            if fileName:
                self.appendLogMessage('Export : incorporated rms-offset map in QGIS')

    def exportRpsToQgis(self):
        if self.rpsImport is not None and self.survey is not None and self.survey.crs is not None:
            if not self.fileName:                                               # filename ="" normally indicates working with 'new' file !
                layerName = self.survey.name
            else:
                layerName = QFileInfo(self.fileName).baseName()
            layerName += '-rps-data'
            self.rpsLayer = exportPointLayerToQgis(layerName, self.rpsImport, self.survey.crs, source=False)

    def exportSpsToQgis(self):
        if self.spsImport is not None and self.survey is not None and self.survey.crs is not None:
            if not self.fileName:                                               # filename ="" normally indicates working with 'new' file !
                layerName = self.survey.name
            else:
                layerName = QFileInfo(self.fileName).baseName()
            layerName += '-sps-data'
            self.spsLayer = exportPointLayerToQgis(layerName, self.spsImport, self.survey.crs, source=True)

    def exportRecToQgis(self):
        if self.recGeom is not None and self.survey is not None and self.survey.crs is not None:
            if not self.fileName:                                               # filename ="" normally indicates working with 'new' file !
                layerName = self.survey.name
            else:
                layerName = QFileInfo(self.fileName).baseName()
            layerName += '-rec-data'
            self.recLayer = exportPointLayerToQgis(layerName, self.recGeom, self.survey.crs, source=False)

    def exportSrcToQgis(self):
        if self.srcGeom is not None and self.survey is not None and self.survey.crs is not None:
            if not self.fileName:                                               # filename ="" normally indicates working with 'new' file !
                layerName = self.survey.name
            else:
                layerName = QFileInfo(self.fileName).baseName()
            layerName += '-src-data'
            self.srcLayer = exportPointLayerToQgis(layerName, self.srcGeom, self.survey.crs, source=True)

    def importSpsFromQgis(self):
        self.spsLayer, self.spsField = identifyQgisPointLayer(self.iface, self.spsLayer, self.spsField, self.survey.crs, 'Sps')

        if self.spsLayer is None:
            return

        with pg.BusyCursor():
            self.spsImport = readQgisPointLayer(self.spsLayer.id(), self.spsField)
            if self.spsImport is not None:
                convertCrs(self.spsImport, self.spsLayer.crs(), self.survey.crs)

        if self.spsImport is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
        self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)            # get the convex hull of the sps points

        self.appendLogMessage(f'Import : SPS-records containing {self.spsLiveE.size:,} live records')
        self.appendLogMessage(f'Import : SPS-records containing {self.spsDeadE.size:,} dead records')

        self.spsModel.setData(self.spsImport)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importRpsFromQgis(self):
        self.rpsLayer, self.rpsField = identifyQgisPointLayer(self.iface, self.rpsLayer, self.rpsField, self.survey.crs, 'Rps')

        if self.rpsLayer is None:
            return

        with pg.BusyCursor():
            self.rpsImport = readQgisPointLayer(self.rpsLayer.id(), self.rpsField)
            if self.rpsImport is not None:
                convertCrs(self.rpsImport, self.rpsLayer.crs(), self.survey.crs)

        if self.rpsImport is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
        self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)            # get the convex hull of the rps points

        self.appendLogMessage(f'Import : RPS-records containing {self.rpsLiveE.size:,} live records')
        self.appendLogMessage(f'Import : RPS-records containing {self.rpsDeadE.size:,} dead records')

        self.rpsModel.setData(self.rpsImport)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importSrcFromQgis(self):
        self.srcLayer, self.srcField = identifyQgisPointLayer(self.iface, self.srcLayer, self.srcField, self.survey.crs, 'Src')

        if self.srcLayer is None:
            return

        with pg.BusyCursor():
            self.srcGeom = readQgisPointLayer(self.srcLayer.id(), self.srcField)
            if self.srcGeom is not None:
                convertCrs(self.srcGeom, self.srcLayer.crs(), self.survey.crs)

        if self.srcGeom is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)

        self.appendLogMessage(f'Import : SRC-records containing {self.srcLiveE.size:,} live records')
        self.appendLogMessage(f'Import : SRC-records containing {self.srcDeadE.size:,} dead records')

        self.srcModel.setData(self.srcGeom)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importRecFromQgis(self):
        self.recLayer, self.recField = identifyQgisPointLayer(self.iface, self.recLayer, self.recField, self.survey.crs, 'Rec')

        if self.recLayer is None:
            return

        with pg.BusyCursor():
            self.recGeom = readQgisPointLayer(self.recLayer.id(), self.recField)
            if self.recGeom is not None:
                convertCrs(self.recGeom, self.recLayer.crs(), self.survey.crs)

        if self.recGeom is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)

        self.appendLogMessage(f'Import : REC-records containing {self.recLiveE.size:,} live records')
        self.appendLogMessage(f'Import : REC-records containing {self.recDeadE.size:,} dead records')

        self.recModel.setData(self.recGeom)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save rec data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def exportOutlinesToQgis(self):
        layerName = QFileInfo(self.fileName).baseName()
        exportSurveyOutlinesToQgis(layerName, self.survey)

    def exportSpsBoundariesToQgis(self):
        layerName = QFileInfo(self.fileName).baseName()
        exportSpsOutlinesToQgis(layerName, self.survey, self.rpsBound, self.spsBound)

    def updateMenuStatus(self, resetAnalysis=True):
        if resetAnalysis:
            self.actionArea.setChecked(True)                                    # coupled with tbNone; reset analysis figure
            self.imageType = 0                                                  # reset analysis type to zero
            self.handleImageSelection()                                         # change image (if available) and finally plot survey layout

        self.actionExportFoldMap.setEnabled(self.output.binOutput is not None)
        self.actionExportMinOffsets.setEnabled(self.output.minOffset is not None)
        self.actionExportMaxOffsets.setEnabled(self.output.maxOffset is not None)
        self.actionExportRmsOffsets.setEnabled(self.output.rmsOffset is not None)
        self.actionExportAnaAsCsv.setEnabled(self.output.anaOutput is not None)

        self.actionExportRecAsCsv.setEnabled(self.recGeom is not None)
        self.actionExportSrcAsCsv.setEnabled(self.srcGeom is not None)
        self.actionExportRelAsCsv.setEnabled(self.relGeom is not None)
        self.actionExportRecAsR01.setEnabled(self.recGeom is not None)
        self.actionExportSrcAsS01.setEnabled(self.srcGeom is not None)
        self.actionExportRelAsX01.setEnabled(self.relGeom is not None)
        self.actionExportSrcToQGIS.setEnabled(self.srcGeom is not None)
        self.actionExportRecToQGIS.setEnabled(self.recGeom is not None)

        self.actionExportRpsAsCsv.setEnabled(self.rpsImport is not None)
        self.actionExportSpsAsCsv.setEnabled(self.spsImport is not None)
        self.actionExportXpsAsCsv.setEnabled(self.xpsImport is not None)
        self.actionExportRpsAsR01.setEnabled(self.rpsImport is not None)
        self.actionExportSpsAsS01.setEnabled(self.spsImport is not None)
        self.actionExportXpsAsX01.setEnabled(self.xpsImport is not None)
        self.actionExportSpsToQGIS.setEnabled(self.spsImport is not None)
        self.actionExportRpsToQGIS.setEnabled(self.rpsImport is not None)

        self.btnSrcRemoveDuplicates.setEnabled(self.srcGeom is not None)
        self.btnSrcRemoveOrphans.setEnabled(self.srcGeom is not None)
        self.btnSrcExportToQGIS.setEnabled(self.srcGeom is not None)

        self.btnRecRemoveDuplicates.setEnabled(self.recGeom is not None)
        self.btnRecRemoveOrphans.setEnabled(self.recGeom is not None)
        self.btnRecExportToQGIS.setEnabled(self.recGeom is not None)

        self.btnRelRemoveSrcOrphans.setEnabled(self.relGeom is not None)
        self.btnRelRemoveDuplicates.setEnabled(self.relGeom is not None)
        self.btnRelRemoveRecOrphans.setEnabled(self.relGeom is not None)

        self.actionExportAreasToQGIS.setEnabled(len(self.fileName) > 0)         # test if file name isn't empty
        self.btnRelExportToQGIS.setEnabled(len(self.fileName) > 0)              # test if file name isn't empty

        self.btnSpsExportToQGIS.setEnabled(self.spsImport is not None)
        self.btnRpsExportToQGIS.setEnabled(self.rpsImport is not None)

        self.actionFold.setEnabled(self.output.binOutput is not None)
        self.actionMinO.setEnabled(self.output.minOffset is not None)
        self.actionMaxO.setEnabled(self.output.maxOffset is not None)
        self.actionRmsO.setEnabled(self.output.rmsOffset is not None)

        self.actionSpider.setEnabled(self.output.anaOutput is not None and self.output.binOutput is not None)  # the spider button in the display pane
        self.actionMoveLt.setEnabled(self.output.anaOutput is not None)  # the navigation buttons in the Display pane AND on toolbar (moveBar)
        self.actionMoveRt.setEnabled(self.output.anaOutput is not None)
        self.actionMoveUp.setEnabled(self.output.anaOutput is not None)
        self.actionMoveDn.setEnabled(self.output.anaOutput is not None)

        self.btnBinToQGIS.setEnabled(self.output.binOutput is not None)
        self.btnMinToQGIS.setEnabled(self.output.minOffset is not None)
        self.btnMaxToQGIS.setEnabled(self.output.maxOffset is not None)
        self.btnRmsToQGIS.setEnabled(self.output.rmsOffset is not None)

        self.actionExportFoldMapToQGIS.setEnabled(self.output.binOutput is not None)
        self.actionExportMinOffsetsToQGIS.setEnabled(self.output.minOffset is not None)
        self.actionExportMaxOffsetsToQGIS.setEnabled(self.output.maxOffset is not None)
        self.actionExportRmsOffsetsToQGIS.setEnabled(self.output.rmsOffset is not None)

        self.actionRecPoints.setEnabled(self.recGeom is not None)
        self.actionSrcPoints.setEnabled(self.srcGeom is not None)
        self.actionRpsPoints.setEnabled(self.rpsImport is not None)
        self.actionSpsPoints.setEnabled(self.spsImport is not None)
        self.actionAllPoints.setEnabled(self.recGeom is not None or self.srcGeom is not None or self.rpsImport is not None or self.spsImport is not None)

        if self.survey is None:                                                 # can't do the following
            return

        self.actionShowSrcPatterns.setChecked(self.survey.paintDetails & PaintDetails.srcPat != PaintDetails.none)
        self.actionShowSrcPoints.setChecked(self.survey.paintDetails & PaintDetails.srcPnt != PaintDetails.none)
        self.actionShowSrcLines.setChecked(self.survey.paintDetails & PaintDetails.srcLin != PaintDetails.none)
        self.actionShowRecPatterns.setChecked(self.survey.paintDetails & PaintDetails.recPat != PaintDetails.none)
        self.actionShowRecPoints.setChecked(self.survey.paintDetails & PaintDetails.recPnt != PaintDetails.none)
        self.actionShowRecLines.setChecked(self.survey.paintDetails & PaintDetails.recLin != PaintDetails.none)

    def setColorbarLabel(self, label):                                          # I should really subclass colorbarItem to properly set the text label
        if label is not None:
            if self.layoutColorBar.horizontal:
                self.layoutColorBar.getAxis('bottom').setLabel(label)
            else:
                self.layoutColorBar.getAxis('left').setLabel(label)

    def onActionNoneTriggered(self):
        self.imageType = 0
        self.handleImageSelection()

    def onActionAreaTriggered(self):
        self.imageType = 0
        self.handleImageSelection()

    def onActionFoldTriggered(self):
        self.imageType = 1
        self.handleImageSelection()

    def onActionMinOTriggered(self):
        self.imageType = 2
        self.handleImageSelection()

    def onActionMaxOTriggered(self):
        self.imageType = 3
        self.handleImageSelection()

    def onActionRmsOTriggered(self):
        self.imageType = 4
        self.handleImageSelection()

    def handleImageSelection(self):                                             # change image (if available) and finally plot survey layout

        colorMap = config.fold_OffCmap                                          # default fold & offset color map
        if self.imageType == 0:                                                 # now deal with all image types
            self.layoutImg = None                                               # no image to show
            label = 'N/A'
            self.layoutMax = 10
            colorMap = config.inActiveCmap                                      # grey color map
        elif self.imageType == 1:
            self.layoutImg = self.output.binOutput                              # don't make a copy, create a view
            self.layoutMax = self.output.maximumFold
            label = 'fold'
        elif self.imageType == 2:
            self.layoutImg = self.output.minOffset
            self.layoutMax = self.output.maxMinOffset
            label = 'minimum offset'
        elif self.imageType == 3:
            self.layoutImg = self.output.maxOffset
            self.layoutMax = self.output.maxMaxOffset
            label = 'maximum offset'
        elif self.imageType == 4:
            self.layoutImg = self.output.rmsOffset
            self.layoutMax = self.output.maxRmsOffset
            label = 'rms offset increments'
        else:
            raise NotImplementedError('selected analysis type currently not implemented.')

        # Make no-data bins transparent.
        if self.layoutImg is not None:
            mask = self.output.binOutput == 0
            if np.any(mask):
                img = self.layoutImg.astype(np.float32, copy=True)
                img[mask] = np.nan
                self.layoutImg = img

        self.layoutImItem = pg.ImageItem()                                          # create a PyqtGraph image item
        self.layoutImItem.setImage(self.layoutImg, levels=(0.0, self.layoutMax))    # set image and its range limits

        if self.layoutColorBar is None:                                             # create colorbar with default values
            self.layoutColorBar = self.layoutWidget.plotItem.addColorBar(self.layoutImItem, colorMap=config.inActiveCmap, label='N/A', limits=(0, None), rounding=10.0, values=(0, 10))

        if self.layoutColorBar is not None:
            self.layoutColorBar.setImageItem(self.layoutImItem)                     # couple imageItem to the colorbar
            self.layoutColorBar.setLevels(low=0.0, high=self.layoutMax)
            self.layoutColorBar.setColorMap(colorMap)
            self.setColorbarLabel(label)

        self.plotLayout()

    def exceptionHook(self, eType, eValue, eTraceback):
        """Function handling uncaught exceptions. It is triggered each time an uncaught exception occurs."""
        if issubclass(eType, KeyboardInterrupt):
            # ignore keyboard interrupt to support ctrl+C on console applications
            myPrint('Keyboard interrupt ignored')
            sys.__excepthook__(eType, eValue, eTraceback)
        else:

            # use the next string for a messagebox if "debug is on"
            # See: https://waylonwalker.com/python-sys-excepthook/
            # traceback_details = "\n".join(traceback.extract_tb(eTraceback).format())

            traceback_str = ''
            # for file_name, line_number, func_name, text in traceback.extract_tb(eTraceback, limit=2)[1:]:
            for file_name, line_number, func_name, _ in traceback.extract_tb(eTraceback, limit=2):
                file_name = os.path.basename(file_name)
                traceback_str += f' File "{file_name}", line {line_number}, in function "{func_name}".'

            if traceback_str != '':
                traceback_str = f'Traceback: {traceback_str}'

            exceptionMsg = f'Error&nbsp;&nbsp;:&nbsp;{eType.__name__}: {eValue} {traceback_str}'
            self.appendLogMessage(exceptionMsg, MsgType.Exception)

    def cursorPositionChanged(self):
        line = self.textEdit.textCursor().blockNumber() + 1
        col = self.textEdit.textCursor().columnNumber() + 1
        self.posWidgetStatusbar.setText(f'Line: {line} Col: {col}')

    def MouseMovedInPlot(self, pos):                                            # See: https://stackoverflow.com/questions/46166205/display-coordinates-in-pyqtgraph
        if self.layoutWidget.sceneBoundingRect().contains(pos):                 # is mouse moved within the scene area ?

            if self.survey is None or self.survey.glbTransform is None:
                return

            mousePoint = self.layoutWidget.plotItem.vb.mapSceneToView(pos)      # get scene coordinates

            if self.glob:                                                       # plot is using global coordinates
                toLocTransform, _ = self.survey.glbTransform.inverted()
                globalPoint = mousePoint
                localPoint = toLocTransform.map(globalPoint)
            else:                                                               # plot is using local coordinates
                localPoint = mousePoint
                globalPoint = self.survey.glbTransform.map(localPoint)

            lx = localPoint.x()
            ly = localPoint.y()
            gx = globalPoint.x()
            gy = globalPoint.y()

            if self.survey.binning.method == BinningType.cmp:                   # calculate reflector depth at cursor
                gz = 0.0
                lz = 0.0
            elif self.survey.binning.method == BinningType.plane:
                gz = self.survey.globalPlane.depthAt(globalPoint)               # get global depth from defined plane
                lz = self.survey.localPlane.depthAt(localPoint)                 # get local depth from transformed plane
            elif self.survey.binning.method == BinningType.sphere:
                gz = self.survey.globalSphere.depthAt(globalPoint)              # get global depth from defined sphere
                lz = self.survey.localSphere.depthAt(localPoint)                # get local depth from transformed sphere
            else:
                raise ValueError('wrong binning method selected')

            if self.survey.binTransform is not None:
                binPoint = self.survey.binTransform.map(localPoint)
                bx = int(binPoint.x())
                by = int(binPoint.y())
            else:
                bx = 0
                by = 0

            if self.survey.stkTransform is not None:
                stkPoint = self.survey.stkTransform.map(localPoint)
                sx = int(stkPoint.x())
                sy = int(stkPoint.y())
            else:
                sx = 0
                sy = 0

            if self.layoutImg is not None and bx >= 0 and by >= 0 and bx < self.layoutImg.shape[0] and by < self.layoutImg.shape[1]:
                # provide statusbar information within the analysis area
                if self.imageType == 0:
                    self.posWidgetStatusbar.setText(f'S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')
                elif self.imageType == 1:
                    foldValue = float(self.layoutImg[bx, by])
                    if np.isnan(foldValue):
                        foldValue = 0.0
                    fold = int(foldValue)                                       # fold value is float because of the NaN values for no-data bins. Integers don't understand NaN
                    self.posWidgetStatusbar.setText(f'fold: {fold:,d}, S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')
                elif self.imageType == 2:
                    offset = float(self.layoutImg[bx, by])
                    self.posWidgetStatusbar.setText(f'|min offset|: {offset:.2f}, S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')
                elif self.imageType == 3:
                    offset = float(self.layoutImg[bx, by])
                    self.posWidgetStatusbar.setText(f'|max offset|: {offset:.2f}, S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')
                elif self.imageType == 4:
                    offset = float(self.layoutImg[bx, by])
                    self.posWidgetStatusbar.setText(f'rms offset inc: {offset:.2f}, S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')
            else:
                # provide statusbar information outside the analysis area
                self.posWidgetStatusbar.setText(f'S:({sx:,d}, {sy:,d}), L:({lx:,.2f}, {ly:,.2f}, {lz:,.2f}), W:({gx:,.2f}, {gy:,.2f}, {gz:,.2f}) ')

    def getVisiblePlotIndex(self, plotWidget):
        if plotWidget == self.layoutWidget:
            return 0
        elif plotWidget == self.offTrkWidget:
            return 1
        elif plotWidget == self.offBinWidget:
            return 2
        elif plotWidget == self.aziTrkWidget:
            return 3
        elif plotWidget == self.aziBinWidget:
            return 4
        elif plotWidget == self.stkTrkWidget:
            return 5
        elif plotWidget == self.stkBinWidget:
            return 6
        elif plotWidget == self.stkCelWidget:
            return 7
        elif plotWidget == self.offsetWidget:
            return 8
        elif plotWidget == self.offAziWidget:
            return 9
        elif plotWidget == self.arraysWidget:
            return 10

        return None

    def getVisiblePlotWidget(self):
        if self.layoutWidget.isVisible():
            return (self.layoutWidget, 0)
        if self.offTrkWidget.isVisible():
            return (self.offTrkWidget, 1)
        if self.offBinWidget.isVisible():
            return (self.offBinWidget, 2)
        if self.aziTrkWidget.isVisible():
            return (self.aziTrkWidget, 3)
        if self.aziBinWidget.isVisible():
            return (self.aziBinWidget, 4)
        if self.stkTrkWidget.isVisible():
            return (self.stkTrkWidget, 5)
        if self.stkBinWidget.isVisible():
            return (self.stkBinWidget, 6)
        if self.stkCelWidget.isVisible():
            return (self.stkCelWidget, 7)
        if self.offsetWidget.isVisible():
            return (self.offsetWidget, 8)
        if self.offAziWidget.isVisible():
            return (self.offAziWidget, 9)
        if self.arraysWidget.isVisible():
            return (self.arraysWidget, 10)

        return (None, None)

    def updateVisiblePlotWidget(self, index: int) -> None:
        if index == 0:
            self.plotLayout()                                                   # no conditions to plot main layout plot
            return

        if index == 10:                                                         # no condition to plot patterns either
            self.plotPatterns()
            return

        if self.output.anaOutput is None:                                       # we need self.output.anaOutput to display meaningful ANALYSIS information
            return

        xAnaSize = self.output.anaOutput.shape[0]                               # make sure we have a valid self.spiderPoint, hence valid nx, ny
        yAnaSize = self.output.anaOutput.shape[1]

        if self.spiderPoint == QPoint(-1, -1):                                  # no valid position yet; move to center
            self.spiderPoint = QPoint(xAnaSize // 2, yAnaSize // 2)

        if self.spiderPoint.x() < 0:                                            # build in some safety settings
            self.spiderPoint.setX(0)

        if self.spiderPoint.y() < 0:
            self.spiderPoint.setY(0)

        if self.spiderPoint.x() >= xAnaSize:
            self.spiderPoint.setX(xAnaSize - 1)

        if self.spiderPoint.y() >= yAnaSize:
            self.spiderPoint.setY(yAnaSize - 1)

        nX = self.spiderPoint.x()                                               # get x, y indices into bin array
        nY = self.spiderPoint.y()

        invBinTransform, _ = self.survey.binTransform.inverted()                # need to go from bin nr's to cmp(x, y)
        cmpX, cmpY = invBinTransform.map(nX, nY)                                # get local coordinates from line and point indices
        stkX, stkY = self.survey.st2Transform.map(cmpX, cmpY)                   # get the corresponding bin and stake numbers

        x0 = self.survey.output.rctOutput.left()                                # x origin of binning area
        y0 = self.survey.output.rctOutput.top()                                 # y origin of binning area

        dx = self.survey.grid.binSize.x()                                       # x bin size
        dy = self.survey.grid.binSize.y()                                       # y bin size
        ox = 0.5 * dx                                                           # half the x bin size
        oy = 0.5 * dy                                                           # half the y bin size

        if index == 1:
            self.plotOffTrk(nY, stkY, ox)
        elif index == 2:
            self.plotOffBin(nX, stkX, oy)
        elif index == 3:
            self.plotAziTrk(nY, stkY, ox)
        elif index == 4:
            self.plotAziBin(nX, stkX, oy)
        elif index == 5:
            self.plotStkTrk(nY, stkY, x0, dx)
        elif index == 6:
            self.plotStkBin(nX, stkX, y0, dy)
        elif index == 7:
            self.plotStkCel(nX, nY, stkX, stkY)
        elif index == 8:
            self.plotOffset()
        elif index == 9:
            self.plotOffAzi()

    def plotZoomRect(self):
        visiblePlot = self.getVisiblePlotWidget()[0]
        if visiblePlot is not None:
            viewBox = visiblePlot.getViewBox()
            self.rect = viewBox.getState()['mouseMode'] == pg.ViewBox.RectMode   # get rect status
            if self.rect:
                viewBox.setMouseMode(pg.ViewBox.PanMode)
            else:
                viewBox.setMouseMode(pg.ViewBox.RectMode)

    def plotAspectRatio(self):
        visiblePlot = self.getVisiblePlotWidget()[0]
        if visiblePlot is not None:
            plotItem = visiblePlot.getPlotItem()
            self.XisY = not plotItem.saveState()['view']['aspectLocked']        # get XisY status
            visiblePlot.setAspectLocked(self.XisY)

    def plotAntiAlias(self):
        visiblePlot, index = self.getVisiblePlotWidget()
        if visiblePlot is not None:                                             # there's no internal AA state
            self.antiA[index] = not self.antiA[index]                           # maintain status externally
            visiblePlot.setAntialiasing(self.antiA[index])                      # enable/disable aa plotting

    def plotGridX(self):
        visiblePlot = self.getVisiblePlotWidget()[0]
        if visiblePlot is not None:
            plotItem = visiblePlot.getPlotItem()
            self.gridX = not plotItem.saveState()['xGridCheck']                 # update x-gridline status
            if self.gridX:
                visiblePlot.showGrid(x=True, alpha=0.75)                        # show the grey grid lines
            else:
                visiblePlot.showGrid(x=False)                                   # don't show the grey grid lines

    def plotGridY(self):
        visiblePlot = self.getVisiblePlotWidget()[0]
        if visiblePlot is not None:
            plotItem = visiblePlot.getPlotItem()
            self.gridY = not plotItem.saveState()['yGridCheck']                 # update y-gridline status
            if self.gridY:
                visiblePlot.showGrid(y=True, alpha=0.75)                        # show the grey grid lines
            else:
                visiblePlot.showGrid(y=False)                                   # don't show the grey grid lines

    def plotProjected(self):
        self.glob = self.actionProjected.isChecked()

        if self.ruler:
            self.actionRuler.setChecked(False)
            self.showRuler(False)

        self.rulerState = None

        # if False:                                                          # provide some debugging output on the applied transform; use "if self.debug:" to enable
        #     # Get the transform that maps from local coordinates to the item's ViewBox coordinates
        #     transform = self.survey.glbTransform                                # GraphicsItem method
        #     if transform is not None:
        #         s1 = f'm11 ={transform.m11():12.6f},   m12 ={transform.m12():12.6f},   m13 ={transform.m13():12.6f} » [A1, B1, ...]'
        #         s2 = f'm21 ={transform.m21():12.6f},   m22 ={transform.m22():12.6f},   m23 ={transform.m23():12.6f} » [A2, B2, ...]'
        #         s3 = f'm31 ={transform.m31():12.6f},   m32 ={transform.m32():12.6f},   m33 ={transform.m33():12.6f} » [A0, B0, ...]<br>'

        #         self.appendLogMessage('plotProjected(). Showing transform parameters before changing view', MsgType.Debug)
        #         self.appendLogMessage(s1, MsgType.Debug)
        #         self.appendLogMessage(s2, MsgType.Debug)
        #         self.appendLogMessage(s3, MsgType.Debug)

        #         if not transform.isIdentity():
        #             i_trans, _ = transform.inverted()                           # inverted_transform, invertable = transform.inverted()
        #             s1 = f'm11 ={i_trans.m11():12.6f},   m12 ={i_trans.m12():12.6f},   m13 ={i_trans.m13():12.6f} » [A1, B1, ...]'
        #             s2 = f'm21 ={i_trans.m21():12.6f},   m22 ={i_trans.m22():12.6f},   m23 ={i_trans.m23():12.6f} » [A2, B2, ...]'
        #             s3 = f'm31 ={i_trans.m31():12.6f},   m32 ={i_trans.m32():12.6f},   m33 ={i_trans.m33():12.6f} » [A0, B0, ...]<br>'

        #             self.appendLogMessage('plotProjected(). Showing inverted-transform parameters before changing view', MsgType.Debug)
        #             self.appendLogMessage(s1, MsgType.Debug)
        #             self.appendLogMessage(s2, MsgType.Debug)
        #             self.appendLogMessage(s3, MsgType.Debug)

        self.handleSpiderPlot()                                                 # spider label should move depending on local/global coords
        self.layoutWidget.autoRange()                                           # show the full range of objects when changing local vs global coordinates
        self.plotLayout()

    def showRuler(self, checked):
        self.ruler = checked
        self.plotLayout()

    def UpdateAllViews(self):                                                   # re-parse the text in the textEdit, update the survey object, and replot the layout
        plainText = self.textEdit.getTextViaCursor()                            # read complete file content, not affecting doc status
        success = self.parseText(plainText)                                     # parse the string & check if it went okay...

        if success:
            plainText = self.survey.toXmlString()                               # convert the survey object itself to an xml string
            self.textEdit.setTextViaCursor(plainText)                           # get text into the textEdit, NOT resetting its doc status
            self.textEdit.document().setModified(True)                          # we edited the document; so it's been modified
            self.resetSurveyProperties()                                        # update property pane accordingly

        self.plotLayout()
        # self.layoutWidget.enableAutoRange()                                     # makes the plot 'fit' the survey outline.

    def stopPainting(self):
        if self.survey is not None:
            self.survey._cancelPaint = True                                     # to cancel painting in progress

    def layoutRangeChanged(self):
        """handle resizing of plot in view of bin-aligned gridlines"""
        axLft = self.layoutWidget.plotItem.getAxis('left')                      # get y-axis # 1
        axBot = self.layoutWidget.plotItem.getAxis('bottom')                    # get x-axis # 1
        axTop = self.layoutWidget.plotItem.getAxis('top')                       # get x-axis # 2
        axRht = self.layoutWidget.plotItem.getAxis('right')                     # get y-axis # 2

        vb = self.layoutWidget.getViewBox().viewRect()                          # view area in world coords
        dx = self.survey.grid.binSize.x()                                       # x bin size
        dy = self.survey.grid.binSize.y()                                       # y bin size

        if vb.width() > dx and vb.height() > dy:                                # area must be > a single bin to do something
            if not self.glob and (vb.width() < 30.0 * dx or vb.height() < 30.0 * dy):   # scale grid towards bin size

                # In this case it would be nice to have 3 decimals at the tick marks, not two
                # See: https://stackoverflow.com/questions/47500216/pyqtgraph-force-axis-labels-to-have-decimal-points

                xTicks = [dx, 0.2 * dx]                                         # no tickmarks smaller than bin size
                yTicks = [dy, 0.2 * dy]                                         # no tickmarks smaller than bin size
                axBot.setTickSpacing(xTicks[0], xTicks[1])                      # set x ticks (major and minor)
                axLft.setTickSpacing(yTicks[0], yTicks[1])                      # set x ticks (major and minor)
                axTop.setTickSpacing(xTicks[0], xTicks[1])                      # set x ticks (major and minor)
                axRht.setTickSpacing(yTicks[0], yTicks[1])                      # set x ticks (major and minor)
            else:
                axBot.setTickSpacing()                                          # set to default values
                axLft.setTickSpacing()                                          # set to default values
                axTop.setTickSpacing()                                          # set to default values
                axRht.setTickSpacing()                                          # set to default values

    def replotLayout(self):
        self.survey.invalidatePaintCache()                                      # make sure we repaint everything
        self.survey.update()
        self.plotLayout()

    def plotLayout(self):
        # first we are going to see how large the survey area is, to establish a boundingbox
        # See: https://www.geeksforgeeks.org/pyqtgraph-removing-item-from-plot-window/
        # self.layoutWidget.plotItem.removeItem(self.legend)
        # self.layoutWidget.plotItem.removeItem(self.srcLines)
        # self.layoutWidget.plotItem.removeItem(self.recLines)
        # See also: https://groups.google.com/g/pyqtgraph/c/tlryVLCDmmQ when the view does not refresh

        self.layoutWidget.plotItem.clear()
        self.layoutWidget.setTitle(self.survey.name, color='b', size='16pt')
        self.layoutWidget.showAxes(True, showValues=(True, False, False, True))   # show values at the left and at the bottom

        transform = QTransform()                                                # empty (unit) transform

        # setup axes first
        styles = {'color': '#000', 'font-size': '10pt'}
        if self.glob:                                                           # global -> easting & westing
            self.layoutWidget.setLabel('bottom', 'Easting', units='m', **styles)  # shows axis at the bottom, and shows the units label
            self.layoutWidget.setLabel('left', 'Northing', units='m', **styles)   # shows axis at the left, and shows the units label
            self.layoutWidget.setLabel('top', ' ', **styles)                    # shows axis at the top, no label, no tickmarks
            self.layoutWidget.setLabel('right', ' ', **styles)                  # shows axis at the right, no label, no tickmarks
            transform = self.survey.glbTransform                                # get global coordinate conversion transform
        else:                                                                   # local -> inline & crossline
            self.layoutWidget.setLabel('bottom', 'inline', units='m', **styles)   # shows axis at the bottom, and shows the units label
            self.layoutWidget.setLabel('left', 'crossline', units='m', **styles)  # shows axis at the left, and shows the units label
            self.layoutWidget.setLabel('top', ' ', **styles)                    # shows axis at the top, no label, no tickmarks
            self.layoutWidget.setLabel('right', ' ', **styles)                  # shows axis at the right, no label, no tickmarks

        # add image, if available and required
        if self.layoutImItem is not None and self.imageType > 0:
            self.layoutImItem.setTransform(self.survey.cmpTransform * transform)   # combine two transforms
            self.layoutWidget.plotItem.addItem(self.layoutImItem)

        # Show binning area (if checked and available)
        if self.tbArea.isChecked():
            if self.survey.output.rctOutput.isValid():
                binRect = QGraphicsRectItem(self.survey.output.rctOutput)
                binRect.setOpacity(1.0)
                binRect.setPen(config.binAreaPen)
                binRect.setBrush(QBrush(QColor(config.binAreaColor)))
                binRect.setTransform(transform)  # keeps the bin in the right coordinate space
                self.layoutWidget.plotItem.addItem(binRect)

        # add survey geometry if templates are to be displayed (controlled by checkbox)
        if self.tbTemplat.isChecked():
            surveyItem = self.survey
            surveyItem.setTransform(transform)                                  # always do this; will reset transform for 'local' plot
            self.layoutWidget.plotItem.addItem(surveyItem)                      # this plots the survey geometry

        # to add SPS data, i.e. point lists, please have a look at:
        # https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotitem.html#pyqtgraph.PlotItem.plot and :
        # https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html#pyqtgraph.PlotDataItem.__init__
        # https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/scatterplotitem.html#pyqtgraph.ScatterPlotItem.setSymbol
        # https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html

        # addItem(item, *args, **kargs,)
        # [source] https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/PlotItem/PlotItem.html#PlotItem.addItem
        # Add a graphics item to the view box. If the item has plot data (PlotDataItem , PlotCurveItem , ScatterPlotItem ), it may be included in analysis performed by the PlotItem.

        if self.tbSpsList.isChecked() and self.spsLiveE is not None and self.spsLiveN is not None:
            spsTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                spsTransform, _ = self.survey.glbTransform.inverted()

            spsLive = self.layoutWidget.plot(
                x=self.spsLiveE,
                y=self.spsLiveN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.spsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=config.spsSymbolSize,
                symbolBrush=QColor(config.spsBrushColor),
            )
            spsLive.setTransform(spsTransform)

            spsBound = self.layoutWidget.plot(self.spsBound, pen=pg.mkPen('r'), symbol=None)
            spsBound.setTransform(spsTransform)

        if self.tbSpsList.isChecked() and self.tbAllList.isChecked() and self.spsDeadE is not None and self.spsDeadN is not None:
            spsTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                spsTransform, _ = self.survey.glbTransform.inverted()

            spsDead = self.layoutWidget.plot(
                x=self.spsDeadE,
                y=self.spsDeadN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.spsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=config.spsSymbolSize,
                symbolBrush=QColor(config.spsBrushColor),
            )
            spsDead.setTransform(spsTransform)

        if self.tbRpsList.isChecked() and self.rpsLiveE is not None and self.rpsLiveN is not None:
            rpsTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                rpsTransform, _ = self.survey.glbTransform.inverted()

            rpsLive = self.layoutWidget.plot(
                x=self.rpsLiveE,
                y=self.rpsLiveN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.rpsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=config.rpsSymbolSize,
                symbolBrush=QColor(config.rpsBrushColor),
            )
            rpsLive.setTransform(rpsTransform)

            rpsBound = self.layoutWidget.plot(self.rpsBound, pen=pg.mkPen('b'), symbol=None)
            rpsBound.setTransform(rpsTransform)

        if self.tbRpsList.isChecked() and self.tbAllList.isChecked() and self.rpsDeadE is not None and self.rpsDeadN is not None:
            rpsTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                rpsTransform, _ = self.survey.glbTransform.inverted()

            rpsDead = self.layoutWidget.plot(
                x=self.rpsDeadE,
                y=self.rpsDeadN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.rpsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=config.rpsSymbolSize,
                symbolBrush=QColor(config.rpsBrushColor),
            )
            rpsDead.setTransform(rpsTransform)

        if self.tbSrcList.isChecked() and self.srcLiveE is not None and self.srcLiveN is not None:
            srcTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                srcTransform, _ = self.survey.glbTransform.inverted()

            srcLive = self.layoutWidget.plot(
                x=self.srcLiveE,
                y=self.srcLiveN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.srcPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=config.srcSymbolSize,
                symbolBrush=QColor(config.srcBrushColor),
            )
            srcLive.setTransform(srcTransform)

        if self.tbSrcList.isChecked() and self.tbAllList.isChecked() and self.srcDeadE is not None and self.srcDeadN is not None:
            srcTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                srcTransform, _ = self.survey.glbTransform.inverted()

            srcDead = self.layoutWidget.plot(
                x=self.srcDeadE,
                y=self.srcDeadN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.srcPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=config.srcSymbolSize,
                symbolBrush=QColor(config.srcBrushGrey),
            )
            srcDead.setTransform(srcTransform)

        if self.tbRecList.isChecked() and self.recLiveE is not None and self.recLiveN is not None:
            recTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                recTransform, _ = self.survey.glbTransform.inverted()

            recLive = self.layoutWidget.plot(
                x=self.recLiveE,
                y=self.recLiveN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.recPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=config.recSymbolSize,
                symbolBrush=QColor(config.recBrushColor),
            )
            recLive.setTransform(recTransform)

        if self.tbRecList.isChecked() and self.tbAllList.isChecked() and self.recDeadE is not None and self.recDeadN is not None:
            recTransform = QTransform()                                         # empty (unit) transform
            if not self.glob and self.survey.glbTransform is not None:          # global -> easting & westing
                recTransform, _ = self.survey.glbTransform.inverted()

            recDead = self.layoutWidget.plot(
                x=self.recDeadE,
                y=self.recDeadN,
                connect='all',
                pxMode=False,
                pen=None,
                symbol=config.recPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=config.recSymbolSize,
                symbolBrush=QColor(config.recBrushGrey),
            )
            recDead.setTransform(recTransform)

        if self.tbSpider.isChecked() and self.output.anaOutput is not None and self.output.binOutput is not None:
            if self.spiderSrcX is not None:                                     # if we have data to show, plot it

                src = self.layoutWidget.plot(
                    x=self.spiderSrcX, y=self.spiderSrcY, connect='pairs', symbol='o', pen=pg.mkPen('r', width=2), symbolSize=5, pxMode=False, symbolPen=pg.mkPen('r'), symbolBrush=QColor('#77FF2929')
                )
                src.setTransform(transform)

                rec = self.layoutWidget.plot(
                    x=self.spiderRecX, y=self.spiderRecY, connect='pairs', symbol='o', pen=pg.mkPen('b', width=2), symbolSize=5, pxMode=False, symbolPen=pg.mkPen('b'), symbolBrush=QColor('#772929FF')
                )
                rec.setTransform(transform)

            if self.spiderText is not None:
                self.layoutWidget.plotItem.addItem(self.spiderText)                 # show the spider label anyhow

        if self.tbTemplat.isChecked():
            # Add a marker for the origin
            oriX = [0.0]
            oriY = [0.0]
            orig = self.layoutWidget.plot(x=oriX, y=oriY, symbol='o', symbolSize=16, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))
            orig.setTransform(transform)

        if self.survey.binning.method == BinningType.sphere:
            # Draw sphere as a circle in the plot for guidance when binning against a sphere
            # See: https://stackoverflow.com/questions/33525279/pyqtgraph-how-do-i-plot-an-ellipse-or-a-circle
            # See: https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QGraphicsEllipseItem.html
            r = self.survey.localSphere.radius
            x = self.survey.localSphere.origin.x() - r
            y = self.survey.localSphere.origin.y() - r
            w = r * 2.0
            h = r * 2.0
            sphereArea = QGraphicsEllipseItem(x, y, w, h)
            sphereArea.setPen(pg.mkPen(100, 100, 100))
            sphereArea.setBrush(QBrush(QColor(config.binAreaColor)))            # use same color as binning region
            sphereArea.setTransform(transform)
            self.layoutWidget.plotItem.addItem(sphereArea)

        if self.ruler:
            # add ruler if required
            p1 = pg.mkPen('r', style=Qt.PenStyle.DashLine)
            p2 = pg.mkPen('r', style=Qt.PenStyle.DashLine, width=2)
            p3 = pg.mkPen('b')
            p4 = pg.mkPen('b', width=3)

            # get default location for ruler, dependent on current viewRect
            viewRect = self.layoutWidget.plotItem.vb.viewRect()
            ptCenter = viewRect.center()
            pt1 = (ptCenter + viewRect.topLeft()) / 2.0
            pt2 = (ptCenter + viewRect.bottomRight()) / 2.0

            self.lineROI = LineROI([[pt1.x(), pt1.y()], [pt2.x(), pt2.y()]], pen=p1, hoverPen=p2, handlePen=p3, handleHoverPen=p4)
            if self.rulerState is not None:                                     # restore state, if possible
                self.lineROI.setState(self.rulerState)

            self.layoutWidget.plotItem.addItem(self.lineROI)
            self.lineROI.sigRegionChanged.connect(self.roiChanged)

            length = len(self.lineROI.getHandles()) + 1
            self.roiLabels = [pg.TextItem(anchor=(0.5, 1.3), border='b', color='b', fill=(130, 255, 255, 200), text='label') for _ in range(length)]

            for label in self.roiLabels:
                self.layoutWidget.plotItem.addItem(label)
                label.setZValue(1000)
            self.roiChanged()

    def plotOffTrk(self, nY: int, stkY: int, ox: float):
        with pg.BusyCursor():
            plotTitle = f'{self.plotTitles[1]} [line={stkY}]'

            slice3D = self.output.anaOutput[:, nY, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            self.offTrkWidget.plotItem.clear()
            self.offTrkWidget.setTitle(plotTitle, color='b', size='16pt')
            if slice2D.shape[0] == 0:                                           # empty array
                return

            x, y = numbaOffInline(slice2D, ox)
            self.offTrkWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotOffBin(self, nX: int, stkX: int, oy: float):
        with pg.BusyCursor():
            self.offBinWidget.plotItem.clear()

            slice3D = self.output.anaOutput[nX, :, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[2]} [stake={stkX}]'
            self.offBinWidget.setTitle(plotTitle, color='b', size='16pt')

            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = numbaOffX_line(slice2D, oy)
            self.offBinWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotAziTrk(self, nY: int, stkY: int, ox: float):
        with pg.BusyCursor():
            self.aziTrkWidget.plotItem.clear()

            slice3D = self.output.anaOutput[:, nY, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[3]} [line={stkY}]'
            self.aziTrkWidget.setTitle(plotTitle, color='b', size='16pt')

            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = numbaAziInline(slice2D, ox)
            self.aziTrkWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotAziBin(self, nX: int, stkX: int, oy: float):
        with pg.BusyCursor():
            self.aziBinWidget.plotItem.clear()

            slice3D = self.output.anaOutput[nX, :, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[4]} [stake={stkX}]'
            self.aziBinWidget.setTitle(plotTitle, color='b', size='16pt')
            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = numbaAziX_line(slice2D, oy)
            self.aziBinWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotStkTrk(self, nY: int, stkY: int, x0: float, dx: float):
        with pg.BusyCursor():
            dK = 0.001 * config.kr_Stack.z()
            kMax = 0.001 * config.kr_Stack.y() + dK
            kStart = 1000.0 * (0.0 - 0.5 * dK)                                  # scale by factor 1000 as we want to show [1/km] on scale
            kDelta = 1000.0 * dK                                                # same here

            slice3D, I = numbaSlice3D(self.output.anaOutput[:, nY, :, :], self.survey.unique.apply)
            if slice3D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            self.inlineStk = numbaNdft_1D(kMax, dK, slice3D, I)

            tr = QTransform()                                                   # prepare ImageItem transformation:
            tr.translate(x0, kStart)                                            # move image to correct location
            tr.scale(dx, kDelta)                                                # scale horizontal and vertical axes

            self.stkTrkImItem = pg.ImageItem()                                  # create PyqtGraph image item
            self.stkTrkImItem.setImage(self.inlineStk, levels=(-50.0, 0.0))     # plot with log scale from -50 to 0
            self.stkTrkImItem.setTransform(tr)

            if self.stkTrkColorBar is None:
                self.stkTrkColorBar = self.stkTrkWidget.plotItem.addColorBar(self.stkTrkImItem, colorMap=config.analysisCmap, label='dB attenuation', limits=(-100.0, 0.0), rounding=10.0, values=(-50.0, 0.0))
                self.stkTrkColorBar.setLevels(low=-50.0, high=0.0)
            else:
                self.stkTrkColorBar.setImageItem(self.stkTrkImItem)
                self.stkTrkColorBar.setColorMap(config.analysisCmap)            # in case the colorbar has been changed

            self.stkTrkWidget.plotItem.clear()
            self.stkTrkWidget.plotItem.addItem(self.stkTrkImItem)

            plotTitle = f'{self.plotTitles[5]} [line={stkY}]'
            self.stkTrkWidget.setTitle(plotTitle, color='b', size='16pt')

    def plotStkBin(self, nX: int, stkX: int, y0: float, dy: float):
        with pg.BusyCursor():
            dK = 0.001 * config.kr_Stack.z()
            kMax = 0.001 * config.kr_Stack.y() + dK
            kStart = 1000.0 * (0.0 - 0.5 * dK)                                  # scale by factor 1000 as we want to show [1/km] on scale
            kDelta = 1000.0 * dK                                                # same here

            slice3D, I = numbaSlice3D(self.output.anaOutput[nX, :, :, :], self.survey.unique.apply)
            if slice3D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            self.x_lineStk = numbaNdft_1D(kMax, dK, slice3D, I)

            tr = QTransform()                                                   # prepare ImageItem transformation:
            tr.translate(y0, kStart)                                            # move image to correct location
            tr.scale(dy, kDelta)                                                # scale horizontal and vertical axes

            self.stkBinImItem = pg.ImageItem()                                  # create PyqtGraph image item
            self.stkBinImItem.setImage(self.x_lineStk, levels=(-50.0, 0.0))     # plot with log scale from -50 to 0
            self.stkBinImItem.setTransform(tr)

            if self.stkBinColorBar is None:
                self.stkBinColorBar = self.stkBinWidget.plotItem.addColorBar(self.stkBinImItem, colorMap=config.analysisCmap, label='dB attenuation', limits=(-100.0, 0.0), rounding=10.0, values=(-50.0, 0.0))
                self.stkBinColorBar.setLevels(low=-50.0, high=0.0)
            else:
                self.stkBinColorBar.setImageItem(self.stkBinImItem)
                self.stkBinColorBar.setColorMap(config.analysisCmap)            # in case the colorbar has been changed

            self.stkBinWidget.plotItem.clear()
            self.stkBinWidget.plotItem.addItem(self.stkBinImItem)

            plotTitle = f'{self.plotTitles[6]} [stake={stkX}]'
            self.stkBinWidget.setTitle(plotTitle, color='b', size='16pt')

    def plotStkCel(self, nX: int, nY: int, stkX: int, stkY: int):
        if self.output.anaOutput is None or self.output.anaOutput.shape[0] == 0 or self.output.anaOutput.shape[1] == 0:
            return

        with pg.BusyCursor():
            kMin = 0.001 * config.kxyStack.x()
            kMax = 0.001 * config.kxyStack.y()
            dK = 0.001 * config.kxyStack.z()
            kMax = kMax + dK

            kStart = 1000.0 * (kMin - 0.5 * dK)                                 # scale by factor 1000 as we want to show [1/km] on scale
            kDelta = 1000.0 * dK                                                # same here

            offsetX, offsetY, noData = numbaOffsetBin(self.output.anaOutput[nX, nY, :, :], self.survey.unique.apply)
            if noData:
                fold = 0
            else:
                fold = offsetX.shape[0]

            if offsetX is None:
                kX = np.arange(kMin, kMax, dK)
                nX = kX.shape[0]
                self.xyCellStk = np.ones(shape=(nX, nX), dtype=np.float32) * -50.0           # create -50 dB array of the right size and type
            else:
                self.xyCellStk = numbaNdft_2D(kMin, kMax, dK, offsetX, offsetY)

            i3 = self.pattern3.currentIndex() - 1                               # turn <no pattern> into -1
            i4 = self.pattern4.currentIndex() - 1
            imax = len(self.survey.patternList)

            if self.tbStackPatterns.isChecked() and i3 >= 0 and i3 < imax:
                x3, y3 = self.survey.patternList[i3].calcPatternPointArrays()
                self.xyCellStk = self.xyCellStk + numbaNdft_2D(kMin, kMax, dK, x3, y3)

            if self.tbStackPatterns.isChecked() and i4 >= 0 and i4 < imax:
                x4, y4 = self.survey.patternList[i4].calcPatternPointArrays()
                self.xyCellStk = self.xyCellStk + numbaNdft_2D(kMin, kMax, dK, x4, y4)

            tr = QTransform()                                               # prepare ImageItem transformation:
            tr.translate(kStart, kStart)                                    # move image to correct location
            tr.scale(kDelta, kDelta)                                        # scale horizontal and vertical axes

            self.stkCelImItem = pg.ImageItem()                              # create PyqtGraph image item
            self.stkCelImItem.setImage(self.xyCellStk, levels=(-50.0, 0.0))   # plot with log scale from -50 to 0
            self.stkCelImItem.setTransform(tr)
            if self.stkCelColorBar is None:
                self.stkCelColorBar = self.stkCelWidget.plotItem.addColorBar(self.stkCelImItem, colorMap=config.analysisCmap, label='dB attenuation', limits=(-100.0, 0.0), rounding=10.0, values=(-50.0, 0.0))
                self.stkCelColorBar.setLevels(low=-50.0, high=0.0)
            else:
                self.stkCelColorBar.setImageItem(self.stkCelImItem)
                self.stkCelColorBar.setColorMap(config.analysisCmap)        # in case the colorbar has been changed

            self.stkCelWidget.plotItem.clear()
            self.stkCelWidget.plotItem.addItem(self.stkCelImItem)

            plotTitle = f'{self.plotTitles[7]} [stake={stkX}, line={stkY}, fold={fold}]'
            self.stkCelWidget.setTitle(plotTitle, color='b', size='16pt')

    def plotOffset(self):
        with pg.BusyCursor():

            dO = 50.0                                                           # offsets increments
            oMax = ceil(self.output.maxMaxOffset / dO) * dO + dO                # max y-scale; make sure end value is included
            oR = np.arange(0, oMax, dO)                                         # numpy array with values [0 ... oMax]

            if self.output.offstHist is None:
                offsets, _, noData = numbaSliceStats(self.output.anaOutput, self.survey.unique.apply)
                if noData:
                    return

                y, x = np.histogram(offsets, bins=oR)                           # create a histogram with 100m offset increments

                y1 = np.append(y, 0)                                            # add a dummy value to make x- and y-arrays equal size
                self.output.offstHist = np.stack((x, y1))                       # See: https://numpy.org/doc/stable/reference/generated/numpy.stack.html#numpy.stack

            x2 = self.output.offstHist[0, :]                                    # x in the top row
            y2 = self.output.offstHist[1, :-1]                                  # y in the bottom row, minus the phony last value

            count = np.sum(self.output.binOutput)                               # available traces
            plotTitle = f'{self.plotTitles[8]} [{count:,} traces]'
            self.offsetWidget.setTitle(plotTitle, color='b', size='16pt')
            self.offsetWidget.plotItem.clear()
            self.offsetWidget.plot(x2, y2, stepMode='center', fillLevel=0, fillOutline=True, brush=(0, 0, 255, 150), pen=pg.mkPen('k', width=1))

    def plotOffAzi(self):
        with pg.BusyCursor():
            dA = 5.0                                                            # azimuth increments
            dO = 100.0                                                          # offsets increments

            aMin = 0.0                                                          # min x-scale
            aMax = 360.0                                                        # max x-scale
            aMax += dA                                                          # make sure end value is included

            oMax = ceil(self.output.maxMaxOffset / dO) * dO + dO                # max y-scale; make sure end value is included

            if self.output.ofAziHist is None:                                   # calculate offset/azimuth distribution
                offsets, azimuth, noData = numbaSliceStats(self.output.anaOutput, self.survey.unique.apply)
                if noData:
                    return

                aR = np.arange(aMin, aMax, dA)                                  # numpy array with values [0 ... fMax]
                oR = np.arange(0, oMax, dO)                                     # numpy array with values [0 ... oMax]
                self.output.ofAziHist = np.histogram2d(x=azimuth, y=offsets, bins=[aR, oR], range=None, density=None, weights=None)[0]

            tr = QTransform()                                                   # prepare ImageItem transformation:
            tr.translate(aMin, 0)                                               # move image to correct location
            tr.scale(dA, dO)                                                    # scale horizontal and vertical axes

            self.offAziImItem = pg.ImageItem()                                  # create PyqtGraph image item
            self.offAziImItem.setImage(self.output.ofAziHist)
            self.offAziImItem.setTransform(tr)
            if self.offAziColorBar is None:
                self.offAziColorBar = self.offAziWidget.plotItem.addColorBar(self.offAziImItem, colorMap=config.analysisCmap, label='frequency', rounding=10.0)
                self.offAziColorBar.setLevels(low=0.0)                          # , high=0.0
            else:
                self.offAziColorBar.setImageItem(self.offAziImItem)
                self.offAziColorBar.setColorMap(config.analysisCmap)            # in case the colorbar has been changed

            self.offAziWidget.plotItem.clear()
            self.offAziWidget.plotItem.addItem(self.offAziImItem)

            count = np.sum(self.output.binOutput)                               # available traces
            plotTitle = f'{self.plotTitles[9]} [{count:,} traces]'
            self.offAziWidget.setTitle(plotTitle, color='b', size='16pt')

        # For Polar Coordinates, see:
        # See: https://stackoverflow.com/questions/57174173/polar-coordinate-system-in-pyqtgraph
        # See: https://groups.google.com/g/pyqtgraph/c/9Vv1kJdxE6U/m/FuCsSg182jUJ
        # See: https://doc.qt.io/qtforpython-6/PySide6/QtCharts/QPolarChart.html
        # See: https://www.youtube.com/watch?v=DyPjsj6azY4
        # See: https://stackoverflow.com/questions/50720719/how-to-create-a-color-circle-in-pyqt
        # See: https://stackoverflow.com/questions/70471687/pyqt-creating-color-circle

    def plotPatterns(self):

        self.arraysWidget.plotItem.clear()
        self.arraysWidget.setTitle(self.plotTitles[10], color='b', size='16pt')
        self.arraysWidget.showAxes(True, showValues=(True, False, False, True))   # show values at the left and at the bottom

        styles = {'color': '#000', 'font-size': '10pt'}
        self.arraysWidget.setLabel('top', ' ', **styles)                        # shows axis at the top, no label, no tickmarks
        self.arraysWidget.setLabel('right', ' ', **styles)                      # shows axis at the right, no label, no tickmarks

        i1 = self.pattern1.currentIndex() - 1                                   # turn <no pattern> into -1
        i2 = self.pattern2.currentIndex() - 1
        imax = len(self.survey.patternList)

        if self.patternLayout:                                                  # display the layout
            self.arraysWidget.setLabel('bottom', 'inline', units='m', **styles)   # shows axis at the bottom, and shows the units label
            self.arraysWidget.setLabel('left', 'crossline', units='m', **styles)  # shows axis at the left, and shows the units label

            if i1 >= 0 and i1 < imax:
                self.arraysWidget.plotItem.addItem(self.survey.patternList[i1])

            if i2 >= 0 and i2 < imax:
                self.arraysWidget.plotItem.addItem(self.survey.patternList[i2])

        else:                                                                   # calculate kxky pattern response of selected patterns
            self.arraysWidget.setLabel('bottom', 'Kx', units='1/km', **styles)  # shows axis at the bottom, and shows the units label
            self.arraysWidget.setLabel('left', 'Ky', units='1/km', **styles)    # shows axis at the left, and shows the units label

            with pg.BusyCursor():                                               # now do the real work
                kMin = 0.001 * config.kxyArray.x()
                kMax = 0.001 * config.kxyArray.y()
                dK = 0.001 * config.kxyArray.z()
                kMax = kMax + dK

                kStart = 1000.0 * (kMin - 0.5 * dK)                             # scale by factor 1000 as we want to show [1/km] on scale
                kDelta = 1000.0 * dK                                            # same here

                x1 = y1 = x2 = y2 = None                                        # avoid these variables from being undefined

                if i1 >= 0 and i1 < imax:
                    x1, y1 = self.survey.patternList[i1].calcPatternPointArrays()

                if i2 >= 0 and i2 < imax:
                    x2, y2 = self.survey.patternList[i2].calcPatternPointArrays()

                kX = np.arange(kMin, kMax, dK)                                  # setup k value array
                nX = kX.shape[0]                                                # get array size

                if (x1 is None or len(x1) == 0) and (x2 is None or len(x2) == 0):
                    self.xyPatResp = np.ones(shape=(nX, nX), dtype=np.float32) * -50.0  # create -50 dB array of the right size and type
                else:
                    self.xyPatResp = np.zeros(shape=(nX, nX), dtype=np.float32)   # create zero array of the right size and type

                    if i1 >= 0 and i1 < imax:                                   # multiply with array response (dB -> multiplication becomes summation)
                        self.xyPatResp = self.xyPatResp + numbaNdft_2D(kMin, kMax, dK, x1, y1)

                    if i2 >= 0 and i2 < imax:                                   # multiply with array response (dB -> multiplication becomes summation)
                        self.xyPatResp = self.xyPatResp + numbaNdft_2D(kMin, kMax, dK, x2, y2)

                tr = QTransform()                                               # prepare ImageItem transformation:
                tr.translate(kStart, kStart)                                    # move image to correct location
                tr.scale(kDelta, kDelta)                                        # scale horizontal and vertical axes

                self.kxyPatImItem = pg.ImageItem()                              # create PyqtGraph image item
                self.kxyPatImItem.setImage(self.xyPatResp, levels=(-50.0, 0.0))   # plot with log scale from -50 to 0
                self.kxyPatImItem.setTransform(tr)
                if self.kxyPatColorBar is None:
                    self.kxyPatColorBar = self.arraysWidget.plotItem.addColorBar(
                        self.kxyPatImItem, colorMap=config.analysisCmap, label='dB attenuation', limits=(-100.0, 0.0), rounding=10.0, values=(-50.0, 0.0)
                    )
                    self.kxyPatColorBar.setLevels(low=-50.0, high=0.0)
                else:
                    self.kxyPatColorBar.setImageItem(self.kxyPatImItem)
                    self.kxyPatColorBar.setColorMap(config.analysisCmap)        # in case the colorbar has been changed

                self.arraysWidget.plotItem.clear()
                self.arraysWidget.plotItem.addItem(self.kxyPatImItem)

        plotTitle = f'{self.plotTitles[10]} [{self.pattern1.currentText()} * {self.pattern2.currentText()}]'
        plotTitle = plotTitle.replace('<', '&lt;')                              # bummer; plotTitle is an html string
        plotTitle = plotTitle.replace('>', '&gt;')                              # we need to escape the angle brackets

        self.arraysWidget.setTitle(plotTitle, color='b', size='16pt')

    def roiChanged(self):
        pos = []
        for i, handle in enumerate(self.lineROI.getHandles()):
            handlePos = self.lineROI.pos() + handle.pos()
            self.roiLabels[i].setPos(handlePos)
            pos.append(handlePos)
            self.roiLabels[i].setText(f'({handlePos[0]:.2f}, {handlePos[1]:.2f})')

        # put label in the middle of the line
        pos2 = (pos[0] + pos[1]) / 2.0
        diff = pos[1] - pos[0]
        self.roiLabels[2].setPos(pos2)
        self.roiLabels[2].setText(f'|r|={diff.length():.2f}, Ø={degrees(atan2(diff.y(),diff.x())):.2f}°')
        self.rulerState = self.lineROI.saveState()

    def closeEvent(self, e):  # main window about to be closed event
        # See: https://doc.qt.io/qt-6/qwidget.html#closeEvent
        # See: https://stackoverflow.com/questions/22460003/pyqts-qmainwindow-closeevent-is-never-called

        if self.fileNew():                                                      # file (maybe) saved and cancel NOT used
            self.dockLogging.setFloating(False)                                 # don't keep floating docking widgets hanging araound once closed
            self.dockDisplay.setFloating(False)                                 # don't keep floating docking widgets hanging araound once closed
            self.dockProperty.setFloating(False)                                # don't keep floating docking widgets hanging araound once closed
            # self.writeSettings()                                              # save geometry and state of window(s)
            writeSettings(self)                                                 # save geometry and state of window(s)

            if self.projectDirectory and os.path.isdir(self.projectDirectory):  # append information to log file in working directory
                logFile = os.path.join(self.projectDirectory, '.roll.log')      # join directory & log file name
                with open(logFile, 'a+', encoding='utf-8') as file:             # append (a) information to a logfile, or create a new logfile (a+) if it does not yet exist
                    file.write(self.logEdit.toPlainText())                      # get text from logEdit
                    file.write('+++\n\n')                                       # closing remarks

            e.accept()                                                          # finally accep the event

            self.killMe = True                                                  # to restart the GUI from scratch when the plugin is activated again

        else:
            e.ignore()                                                          # ignore the event and stay active

        # See: https://stackoverflow.com/questions/26114034/defining-a-wx-panel-destructor-in-wxpython/73972953#73972953
        # See: http://enki-editor.org/2014/08/23/Pyqt_mem_mgmt.html

        # The following code is already done in self.fileNew()
        # if self.thread is not None and self.thread.isRunning():
        #     reply = QMessageBox.question(self, 'Please confirm',
        #         "Cancel work in progress and close Roll ?",
        #         QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)

        #     if reply == QMessageBox.Yes:
        #         self.thread.requestInterruption()
        #         self.thread.quit()
        #         self.thread.wait()
        #         # force thread termination
        #         # self.thread.terminate()
        #         self.thread.deleteLater()
        #         e.accept()
        #     else:
        #         e.ignore()                                                      # ignore the event and stay active

    def newFile(self):                                                          # wrapper around fileNew; used to create a log message
        if self.fileNew():
            self.appendLogMessage('Created: new file')
            self.plotLayout()                                                   # update the survey, but not the xml-tab

    def resetNumpyArraysAndModels(self):
        """reset various analysis arrays"""

        # numpy binning arrays
        self.layoutImg = None                                                   # numpy array to be displayed; binOutput / minOffset / maxOffset

        # analysis numpy arrays
        self.inlineStk = None                                                   # numpy array with inline Kr stack reponse
        self.x_lineStk = None                                                   # numpy array with x_line Kr stack reponse
        self.xyCellStk = None                                                   # numpy array with cell's KxKy stack response
        self.xyPatResp = None                                                   # numpy array with pattern's KxKy response

        # layout and analysis image-items
        self.layoutImItem = None                                                # pg ImageItems showing analysis result
        self.stkTrkImItem = None
        self.stkBinImItem = None
        self.stkCelImItem = None
        self.offAziImItem = None
        self.kxyPatImItem = None

        # corresponding color bars
        # self.layoutColorBar = None                                              # DON'T reset these; adjust the existing ones
        # self.stkTrkColorBar = None
        # self.stkBinColorBar = None
        # self.stkCelColorBar = None
        # self.offAziColorBar = None

        # rps, sps, xps input arrays
        self.rpsImport = None                                                   # numpy array with list of RPS records
        self.spsImport = None                                                   # numpy array with list of SPS records
        self.xpsImport = None                                                   # numpy array with list of XPS records

        self.rpsLiveE = None                                                    # numpy array with list of live RPS coordinates
        self.rpsLiveN = None                                                    # numpy array with list of live RPS coordinates
        self.rpsDeadE = None                                                    # numpy array with list of dead RPS coordinates
        self.rpsDeadN = None                                                    # numpy array with list of dead RPS coordinates

        self.spsLiveE = None                                                    # numpy array with list of live SPS coordinates
        self.spsLiveN = None                                                    # numpy array with list of live SPS coordinates
        self.spsDeadE = None                                                    # numpy array with list of dead SPS coordinates
        self.spsDeadN = None                                                    # numpy array with list of dead SPS coordinates

        # rel, src, rel input arrays
        self.recGeom = None                                                     # numpy array with list of REC records
        self.srcGeom = None                                                     # numpy array with list of SRC records
        self.relGeom = None                                                     # numpy array with list of REL records

        self.recLiveE = None                                                    # numpy array with list of live REC coordinates
        self.recLiveN = None                                                    # numpy array with list of live REC coordinates
        self.recDeadE = None                                                    # numpy array with list of dead REC coordinates
        self.recDeadN = None                                                    # numpy array with list of dead REC coordinates

        self.srcLiveE = None                                                    # numpy array with list of live SRC coordinates
        self.srcLiveN = None                                                    # numpy array with list of live SRC coordinates
        self.srcDeadE = None                                                    # numpy array with list of dead SRC coordinates
        self.srcDeadN = None                                                    # numpy array with list of dead SRC coordinates

        # spider plot settings
        self.spiderPoint = QPoint(-1, -1)                                       # spider point 'out of scope'
        self.spiderSrcX = None                                                  # numpy array with list of SRC part of spider plot
        self.spiderSrcY = None                                                  # numpy array with list of SRC part of spider plot
        self.spiderRecX = None                                                  # numpy array with list of REC part of spider plot
        self.spiderRecY = None                                                  # numpy array with list of REC part of spider plot
        self.spiderText = None                                                  # text label describing spider bin, stake, fold
        self.actionSpider.setChecked(False)                                     # reset spider plot to 'off'

        # export layers to QGIS
        self.spsLayer = None                                                    # QGIS layer for sps point I/O
        self.rpsLayer = None                                                    # QGIS layer for rpr point I/O
        self.srcLayer = None                                                    # QGIS layer for src point I/O
        self.recLayer = None                                                    # QGIS layer for rec point I/O
        self.spsField = None                                                    # QGIS field for sps point selection I/O
        self.rpsField = None                                                    # QGIS field for rps point selection I/O
        self.srcField = None                                                    # QGIS field for src point selection I/O
        self.recField = None                                                    # QGIS field for rec point selection I/O

        # ruler settings
        self.lineROI = None                                                     # the ruler's dotted line
        self.roiLabels = None                                                   # the ruler's three labels
        self.rulerState = None                                                  # ruler's state, used to redisplay ruler at last used location

        self.anaModel.setData(None)                                             # update the trace table model

        self.rpsModel.setData(self.rpsImport)                                   # update the three rps/sps/xps models
        self.spsModel.setData(self.spsImport)
        self.xpsModel.setData(self.xpsImport)

        self.recModel.setData(self.recGeom)                                     # update the three rec/rel/src models
        self.relModel.setData(self.relGeom)
        self.srcModel.setData(self.srcGeom)

        self.output.binOutput = None
        self.output.minOffset = None
        self.output.maxOffset = None
        self.output.rmsOffset = None
        self.output.ofAziHist = None
        self.output.offstHist = None

        self.resetAnaTableModel()

        self.resetPlotWidget(self.offTrkWidget, self.plotTitles[1])             # clear all analysis plots
        self.resetPlotWidget(self.offBinWidget, self.plotTitles[2])
        self.resetPlotWidget(self.aziTrkWidget, self.plotTitles[3])
        self.resetPlotWidget(self.aziBinWidget, self.plotTitles[4])
        self.resetPlotWidget(self.stkTrkWidget, self.plotTitles[5])
        self.resetPlotWidget(self.stkBinWidget, self.plotTitles[6])
        self.resetPlotWidget(self.stkCelWidget, self.plotTitles[7])
        self.resetPlotWidget(self.offsetWidget, self.plotTitles[8])
        self.resetPlotWidget(self.offAziWidget, self.plotTitles[9])
        self.resetPlotWidget(self.arraysWidget, self.plotTitles[10])

        self.updateMenuStatus(True)                                             # keep menu status in sync with program's state; and reset analysis figure

    def fileNew(self):                                                          # better create new file created through a wizard
        if self.maybeKillThread() and self.maybeSave():                         # make sure thread is killed AND current file  is saved (all only when needed)
            self.resetNumpyArraysAndModels()                                    # empty all arrays and reset plot titles

            # start defining new survey
            self.parseText(exampleSurveyXmlText())                              # read & parse xml string and create new survey object (that does not contain well-seeds)
            self.textEdit.setPlainText(exampleSurveyXmlText())                  # copy xml content to text edit control
            self.resetSurveyProperties()                                        # get the new parameters into the parameter tree
            self.textEdit.moveCursor(QTextCursor.MoveOperation.Start)           # move cursor to front
            self.survey.calcTransforms()                                        # (re)calculate the transforms being used
            self.survey.calcSeedData()                                          # needed for circles, spirals & well-seeds; may affect bounding box
            self.survey.calcBoundingRect()                                      # (re)calculate the boundingBox as part of parsing the data
            self.survey.calcNoShotPoints()                                      # (re)calculate nr of SPs

            self.setCurrentFileName()                                           # update self.fileName, set textEditModified(False) and setWindowModified(False)

            self.actionProjected.setChecked(False)                              # set to 'local' plotting (not global)
            self.plotProjected()                                                # enforce 'local' plotting and plotLayout()

            return True                                                         # we emptied the document, and reset the survey object
        else:
            return False                                                        # user had 2nd thoughts and did not close the document

    def fileNewLandSurvey(self):
        if not self.fileNew():                                                  # user had 2nd thoughts and did not close the document; return False
            return False

        dlg = LandSurveyWizard(self)

        if dlg.exec():                                                          # Run the dialog event loop, and obtain survey object
            self.survey = dlg.survey                                            # get survey from dialog

            plainText = self.survey.toXmlString()                               # convert the survey object to an Xml string
            self.textEdit.highlighter = XMLHighlighter(self.textEdit.document())  # we want some color highlighteded text
            self.textEdit.setFont(QFont('Ubuntu Mono', 9, QFont.Weight.Normal))        # the font may have been messed up by the initial html text

            self.textEdit.setTextViaCursor(plainText)                           # get text into the textEdit, NOT resetting its doc status
            self.UpdateAllViews()                                               # parse the textEdit; show the corresponding plot

            self.appendLogMessage(f'Wizard : created land survey: {self.survey.name}')
            config.surveyNumber += 1                                            # update global counter

    def fileNewMarineSurvey(self):
        if not self.fileNew():                                                  # user had 2nd thoughts and did not close the document; return False
            return False

        dlg = MarineSurveyWizard(self)

        if dlg.exec():                                                          # Run the dialog event loop, and obtain survey object
            self.survey = dlg.survey                                            # get survey from dialog

            plainText = self.survey.toXmlString()                               # convert the survey object to an Xml string
            self.textEdit.highlighter = XMLHighlighter(self.textEdit.document())  # we want some color highlighteded text
            self.textEdit.setFont(QFont('Ubuntu Mono', 9, QFont.Weight.Normal))        # the font may have been messed up by the initial html text

            self.textEdit.setTextViaCursor(plainText)                           # get text into the textEdit, NOT resetting its doc status

            self.survey.paintDetails &= ~PaintDetails.recLin                    # turn off recLin painting
            self.actionShowBlocks.setChecked(True)                              # show blocks by default
            self.survey.paintMode = PaintMode.justBlocks                        # show blocks by default

            self.UpdateAllViews()                                               # parse the textEdit; show the corresponding plot

            self.appendLogMessage(f'Wizard : created streamer survey: {self.survey.name}')
            config.surveyNumber += 1                                            # update global counter

    def maybeSave(self):
        if not self.textEdit.document().isModified():                           # no need to do anything, as the doc wasn't modified
            return True

        ret = QMessageBox.warning(
            self, 'Roll', 'The document has been modified.\nDo you want to save your changes?', QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )        # want to save changes ?

        if ret == QMessageBox.StandardButton.Save:                                             # yes please; try to save changes
            return self.fileSave()                                              # if not succesfull, return False

        if ret == QMessageBox.StandardButton.Cancel:                                           # user 2nd thoughts ? return False
            return False

        return True                                                             # we're done dealing with the current document

    def maybeKillThread(self) -> bool:
        if self.thread is not None and self.thread.isRunning():
            reply = QMessageBox.question(self, 'Please confirm', 'Cancel work in progress and lose results ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)

            if reply == QMessageBox.StandardButton.Cancel:
                return False
            else:
                self.thread.requestInterruption()
                self.thread.quit()
                self.thread.wait()

        # by now the thread has finished, so clean up and return 'True'
        self.worker = None                                                      # moveToThread object
        self.thread = None                                                      # corresponding worker thread

        self.hideStatusbarWidgets()                                             # remove temporary widgets from statusbar (don't kill 'm)

        self.layoutImg = None                                                   # numpy array to be displayed
        self.layoutImItem = None                                                # pg ImageItem showing analysis result

        self.updateMenuStatus(True)                                             # keep menu status in sync with program's state; and reset analysis figure
        self.handleImageSelection()                                             # update the colorbar accordingly

        return True

    def setCurrentFileName(self, fileName=''):                                  # update self.fileName, set textEditModified(False) and setWindowModified(False)
        self.fileName = fileName
        self.textEdit.document().setModified(False)
        # print(f'called: {whoamI()}() from: {callerName()}(), line {lineNo()}, filename = "{self.fileName}", isWindowModified = {self.isWindowModified()}')

        if not self.fileName:                                                   # filename ="" normally indicates working with 'new' file !
            shownName = self.survey.name
        else:
            shownName = QFileInfo(fileName).fileName()

            try:                                                                # if it is already somewhere in the MRU list, remove it
                self.recentFileList.remove(fileName)
            except ValueError:
                pass

            self.recentFileList.insert(0, fileName)                             # insert it at the top
            del self.recentFileList[config.maxRecentFiles :]                    # make sure the list does not overgrow

            self.updateRecentFileActions()

        self.setWindowTitle(self.tr(f'{shownName}[*] - Roll Survey'))           # update window name, with optional * for modified status
        self.setWindowModified(False)                                           # reset document status

    def updateRecentFileActions(self):                                          # update the MRU file menu actions
        numRecentFiles = min(len(self.recentFileList), config.maxRecentFiles)   # get actual number of recent files

        for i in range(numRecentFiles):
            fileName = self.recentFileList[i]
            showName = QFileInfo(fileName).fileName()
            text = f'&{i + 1} {showName}'
            self.recentFileActions[i].setText(text)
            self.recentFileActions[i].setData(self.recentFileList[i])
            self.recentFileActions[i].setVisible(True)

        for j in range(numRecentFiles, config.maxRecentFiles):
            self.recentFileActions[j].setVisible(False)

    def setDataAnaTableModel(self):
        if self.output.D2_Output is None:
            self.anaModel.setData(None)
            return

        total_rows = self.output.D2_Output.shape[0]
        chunk_size = config.maxRowsPerChunk                                     # Default chunk size from config

        if total_rows <= chunk_size:
            # Dataset is small enough to display directly
            self.anaModel.setData(self.output.D2_Output)
            self.appendLogMessage(f'Loaded : . . . Analysis: {total_rows:,} traces displayed in Trace Table')
        else:
            # Create a ChunkedData view object that will handle paging
            chunked_data = ChunkedData(self.output.D2_Output, chunk_size)
            self.anaModel.setChunkedData(chunked_data)
            self._goToFirstPage()
            self.appendLogMessage(f'Loaded : . . . Analysis: {total_rows:,} traces available (showing {chunk_size:,} at a time)')
        self._updatePageInfo()

    def resetAnaTableModel(self):
        if self.output.anaOutput is not None:                                   # get rid of current memory mapped array first
            self.anaModel.setData(None)                                         # first remove reference to self.output.anaOutput
            self.output.D2_Output = None                                        # flattened reference to self.output.anaOutput

            self.output.anaOutput.flush()                                       # make sure all data is written to disk
            del self.output.anaOutput                                           # try to delete the object
            self.output.anaOutput = None                                        # the object was deleted; reinstate the None version

            gc.collect()                                                        # get the garbage collector going
            return True                                                         # we emptied the document, and reset the survey object
        else:
            return False                                                        # nothing to reset

    def setPlottingDetails(self):
        # actionTemplates is still handy to show the survey's origin, so don't disable it
        # # check if there's at least one block defined
        # if len(self.survey.blockList) == 0:
        #     self.actionTemplates.setChecked(False)

        # check if it is a marine survey; set seed plotting details accordingly
        if self.survey.type == SurveyType2.Streamer:
            self.survey.paintDetails &= ~PaintDetails.recPnt
            self.survey.paintDetails &= ~PaintDetails.recPat

            self.survey.paintDetails &= ~PaintDetails.srcPnt
            self.survey.paintDetails &= ~PaintDetails.srcPat

            self.actionShowBlocks.setChecked(True)
            self.survey.paintMode = PaintMode.justBlocks

    def fileLoad(self, fileName):

        self.projectDirectory = os.path.dirname(fileName)                       # retrieve the directory name

        # make projectDirectory available outside of RollMainWindow
        self.settings.setValue('settings/projectDirectory', self.projectDirectory)

        config.resetTimers()    ###                                             # reset timers for debugging code

        file = QFile(fileName)
        if not file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):   # report status message and return False
            try:                                                                # remove from MRU in case of errors
                self.recentFileList.remove(fileName)
            except ValueError:
                pass

            self.appendLogMessage(f'Open&nbsp;&nbsp;&nbsp;: Cannot open file:{fileName}. Error:{file.errorString()}', MsgType.Error)
            return False

        self.appendLogMessage(f'Opening: {fileName}')                           # send status message

        self.survey = RollSurvey()                                              # reset the survey object; get rid of all blocks in the list !
        self.setCurrentFileName(fileName)                                       # update self.fileName, set textEditModified(False) and setWindowModified(False)

        stream = QTextStream(file)                                              # create a stream to read all the data
        plainText = stream.readAll()                                            # load text in a string
        file.close()                                                            # file object no longer needed

        # Xml tab
        self.appendLogMessage(f'Parsing: {fileName}')                           # send status message
        success = self.parseText(plainText)                                     # parse the string; load the textEdit even if parsing fails !

        self.appendLogMessage(f'Reading: {fileName}, success: {success}', MsgType.Info if success else MsgType.Error)        # send status message

        # in case the xml file was not succesfully parsed, we still load the text into the textEdit, to check its content
        self.textEdit.setPlainText(plainText)                                   # update plainText widget, and reset undo/redo & modified status
        self.resetNumpyArraysAndModels()                                        # empty all arrays and reset plot titles

        if success:                                                             # read the corresponding analysis files
            self.appendLogMessage(f'Loading: {fileName} analysis files')        # send status message
            self.setPlottingDetails()                                           # check if it is a marine survey; set seed plotting details accordingly

            # continue loading the anaysis files that belong to this project
            w = self.survey.output.rctOutput.width()                            # expected dimensions of analysis files
            h = self.survey.output.rctOutput.height()
            dx = self.survey.grid.binSize.x()
            dy = self.survey.grid.binSize.y()
            nx = ceil(w / dx)
            ny = ceil(h / dy)

            if os.path.exists(self.fileName + '.bin.npy'):                      # open the existing foldmap file
                self.output.binOutput = np.load(self.fileName + '.bin.npy')
                nX = self.output.binOutput.shape[0]                             # check against nx
                nY = self.output.binOutput.shape[1]                             # check against ny

                if nx != nX or ny != nY:
                    self.appendLogMessage('Loaded : . . . Fold map&nbsp; : Wrong dimensions, compared to analysis area - file ignored')
                    self.output.binOutput = None
                else:
                    self.output.maximumFold = self.output.binOutput.max()           # calc min/max fold is straightforward
                    self.output.minimumFold = self.output.binOutput.min()

                    self.actionFold.setChecked(True)
                    self.imageType = 1                                              # set analysis type to one (fold map)

                    self.layoutImg = self.survey.output.binOutput                   # use fold map for image data np-array
                    self.layoutMax = self.output.maximumFold                        # use appropriate maximum
                    self.layoutImItem = pg.ImageItem()                              # create PyqtGraph image item
                    self.layoutImItem.setImage(self.layoutImg, levels=(0.0, self.layoutMax))

                    label = 'fold'
                    if self.layoutColorBar is None:
                        self.layoutColorBar = self.layoutWidget.plotItem.addColorBar(self.layoutImItem, colorMap=config.fold_OffCmap, label=label, limits=(0, None), rounding=10.0, values=(0.0, self.layoutMax))
                    else:
                        self.layoutColorBar.setImageItem(self.layoutImItem)
                        self.layoutColorBar.setLevels(low=0.0, high=self.layoutMax)
                        self.layoutColorBar.setColorMap(config.fold_OffCmap)
                        self.setColorbarLabel(label)

                    self.appendLogMessage(f'Loaded : . . . Fold map&nbsp; : Min:{self.output.minimumFold} - Max:{self.output.maximumFold} ')
            else:
                self.output.binOutput = None
                self.actionArea.setChecked(True)
                self.imageType = 0                                              # set analysis type to zero (no analysis)

            if os.path.exists(self.fileName + '.min.npy'):                      # load the existing min-offsets file
                self.output.minOffset = np.load(self.fileName + '.min.npy')
                nX = self.output.minOffset.shape[0]                             # check against nx, ny
                nY = self.output.minOffset.shape[1]                             # check against nx, ny

                if nx != nX or ny != nY:
                    self.appendLogMessage('Loaded : . . . Min-offset: Wrong dimensions, compared to analysis area - file ignored')
                    self.output.minOffset = None
                else:
                    self.output.minOffset[self.output.minOffset == np.NINF] = np.Inf    # replace (-inf) by (inf) for min values
                    self.output.minMinOffset = self.output.minOffset.min()          # calc min offset against max (inf) values

                    self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF  # replace (inf) by (-inf) for max values
                    self.output.maxMinOffset = self.output.minOffset.max()          # calc max values against (-inf) minimum
                    self.output.maxMinOffset = max(self.output.maxMinOffset, 0)     # avoid -inf as maximum

                    self.appendLogMessage(f'Loaded : . . . Min-offset: Min:{self.output.minMinOffset:.2f}m - Max:{self.output.maxMinOffset:.2f}m ')
            else:
                self.output.minOffset = None

            if os.path.exists(self.fileName + '.max.npy'):                      # load the existing max-offsets file
                self.output.maxOffset = np.load(self.fileName + '.max.npy')
                nX = self.output.maxOffset.shape[0]                             # check against nx, ny
                nY = self.output.maxOffset.shape[1]                             # check against nx, ny

                if nx != nX or ny != nY:
                    self.appendLogMessage('Loaded : . . . Max-offset: Wrong dimensions, compared to analysis area - file ignored')
                    self.output.maxOffset = None
                else:
                    self.output.maxMaxOffset = self.output.maxOffset.max()          # calc max offset against max (-inf) values
                    self.output.maxMaxOffset = max(self.output.maxMaxOffset, 0)     # avoid -inf as maximum
                    self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf   # replace (-inf) by (inf) for min values

                    self.output.minMaxOffset = self.output.maxOffset.min()          # calc min offset against min (inf) values
                    self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF   # replace (inf) by (-inf) for max values
                    self.appendLogMessage(f'Loaded : . . . Max-offset: Min:{self.output.minMaxOffset:.2f}m - Max:{self.output.maxMaxOffset:.2f}m ')
            else:
                self.output.maxOffset = None

            if os.path.exists(self.fileName + '.rms.npy'):                      # load the existing max-offsets file
                self.output.rmsOffset = np.load(self.fileName + '.rms.npy')
                nX = self.output.rmsOffset.shape[0]                             # check against nx, ny
                nY = self.output.rmsOffset.shape[1]                             # check against nx, ny

                if nx != nX or ny != nY:
                    self.appendLogMessage('Loaded : . . . Rms-offset: Wrong dimensions, compared to analysis area - file ignored')
                    self.output.rmsOffset = None
                else:
                    self.output.maxRmsOffset = self.output.rmsOffset.max()          # calc max offset against max (-inf) values
                    self.output.minRmsOffset = self.output.rmsOffset.min()          # calc min offset against min (inf) values
                    self.output.minRmsOffset = max(self.output.minRmsOffset, 0)     # avoid -inf as maximum
                    self.appendLogMessage(f'Loaded : . . . Rms-offset: Min:{self.output.minRmsOffset:.2f}m - Max:{self.output.maxRmsOffset:.2f}m ')
            else:
                self.output.rmsOffset = None

            if os.path.exists(self.fileName + '.off.npy'):                      # load the existing azimuth/offset histogram file
                self.output.offstHist = np.load(self.fileName + '.off.npy')
                nX = self.output.offstHist.shape[0]                             # check against nx
                # nY = self.output.offstHist.shape[1]                             # check against ny

                if nX != 2:
                    self.appendLogMessage('Loaded : . . . offset: Wrong dimensions of histogram - file ignored')
                    self.output.offstHist = None
                else:
                    self.appendLogMessage('Loaded : . . . offset histogram')
            else:
                self.output.offstHist = None

            if os.path.exists(self.fileName + '.azi.npy'):                      # load the existing azimuth/offset histogram file
                self.output.ofAziHist = np.load(self.fileName + '.azi.npy')
                nX = self.output.ofAziHist.shape[0]                             # check against nx
                # nY = self.output.ofAziHist.shape[1]                             # check against ny

                if nX != 360 // 5:
                    self.appendLogMessage('Loaded : . . . azi-offset: Wrong dimensions of histogram - file ignored')
                    self.output.ofAziHist = None
                else:
                    self.appendLogMessage('Loaded : . . . azi-offset histogram')
            else:
                self.output.ofAziHist = None

            if self.output.binOutput is not None and os.path.exists(self.fileName + '.ana.npy'):   # only open the analysis file if binning file exists
                try:

                    if self.survey.grid.fold > 0:
                        fold = self.survey.grid.fold                            # fold is defined by the grid's fold (preferred)
                    else:
                        fold = self.output.maximumFold                          # fold is defined by observed maxfold in bin file

                    # if we had a large memmap file open earlier; close it and call the garbage collector
                    self.resetAnaTableModel()

                    # self.output.anaOutput = np.lib.format.open_memmap(self.fileName + '.ana.npy', mode='r+', dtype=np.float32, shape=None)
                    self.output.anaOutput = np.memmap(self.fileName + '.ana.npy', dtype=np.float32, mode='r+', shape=(nx, ny, fold, 13))
                    nT = self.output.anaOutput.size                             # total size of array in Nr of elements

                    # we know the (supposed) size of the binning area, and nr of columns in the file. Therefore
                    delta = nT - (nx * ny * fold * 13)

                    if delta != 0:
                        self.appendLogMessage(f'Loaded : . . . Analysis &nbsp;: mismatch in trace table compared to fold {fold:,} x-size {nx}, and y-size {ny}. Please rerun extended analysis', MsgType.Error)
                        self.output.D2_Output = None                            # remove reference to self.output.anaOutput
                        self.output.anaOutput = None                            # remove self.output.anaOutput itself
                        self.anaModel.setData(None)                             # use this as the model data
                    else:
                        self.output.D2_Output = self.output.anaOutput.reshape(nx * ny * fold, 13)   # create a 2 dim array for table access

                    if self.output.maximumFold > fold:
                        self.appendLogMessage(
                            f'Loaded : . . . Analysis &nbsp;: observed fold in in binning file {self.output.maximumFold:,} larger than allowed in trace table {fold:,} missing traces in spider plot !'
                        )

                    self.appendLogMessage(f'Loaded : . . . Analysis &nbsp;: {self.output.D2_Output.shape[0]:,} traces (reserved space)')
                except (ValueError, PermissionError) as error:
                    self.appendLogMessage(f"Loaded : . . . Analysis &nbsp;: read error {self.fileName + '.ana.npy'}. A {type(error).__name__} has occurred ")
                    self.anaModel.setData(None)
                    self.output.D2_Output = None
                    self.output.anaOutput = None
            else:
                self.anaModel.setData(None)
                self.output.D2_Output = None
                self.output.anaOutput = None

            self.setDataAnaTableModel()                                         # sets model data, in a trunked manner if needed

            if os.path.exists(self.fileName + '.rps.npy'):                      # open the existing rps-file
                self.rpsImport = np.load(self.fileName + '.rps.npy')
                self.rpsImport = rfn.rename_fields(self.rpsImport, {'Record': 'RecNum'})   # rename 'Record' field to 'RecNum' if found
                self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
                self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)        # get the convex hull of the rps points

                nImport = self.rpsImport.shape[0]
                self.actionRpsPoints.setChecked(nImport > 0)
                self.actionRpsPoints.setEnabled(nImport > 0)

                self.appendLogMessage(f'Loaded : . . . read {nImport:,} rps-records')
            else:
                self.rpsImport = None
                self.actionRpsPoints.setChecked(False)
                self.actionRpsPoints.setEnabled(False)

            if os.path.exists(self.fileName + '.sps.npy'):                      # open the existing sps-file
                self.spsImport = np.load(self.fileName + '.sps.npy')
                self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
                self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)        # get the convex hull of the sps points

                nImport = self.spsImport.shape[0]
                self.actionSpsPoints.setChecked(nImport > 0)
                self.actionSpsPoints.setEnabled(nImport > 0)

                self.appendLogMessage(f'Loaded : . . . read {nImport:,} sps-records')
            else:
                self.spsImport = None
                self.actionSpsPoints.setChecked(False)
                self.actionSpsPoints.setEnabled(False)

            if os.path.exists(self.fileName + '.xps.npy'):                      # open the existing xps-file
                self.xpsImport = np.load(self.fileName + '.xps.npy')

                nImport = self.xpsImport.shape[0]
                self.appendLogMessage(f'Loaded : . . . read {nImport:,} xps-records')
            else:
                self.xpsImport = None

            if os.path.exists(self.fileName + '.rec.npy'):                      # open the existing rps-file
                self.recGeom = np.load(self.fileName + '.rec.npy')
                self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)

                nImport = self.recGeom.shape[0]
                self.actionRecPoints.setChecked(nImport > 0)
                self.actionRecPoints.setEnabled(nImport > 0)

                self.appendLogMessage(f'Loaded : . . . read {nImport:,} rec-records')
            else:
                self.recGeom = None
                self.actionRecPoints.setChecked(False)
                self.actionRecPoints.setEnabled(False)

            if os.path.exists(self.fileName + '.src.npy'):                      # open the existing rps-file
                self.srcGeom = np.load(self.fileName + '.src.npy')
                self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)

                nImport = self.srcGeom.shape[0]
                self.actionSrcPoints.setChecked(nImport > 0)
                self.actionSrcPoints.setEnabled(nImport > 0)

                self.appendLogMessage(f'Loaded : . . . read {nImport:,} src-records')
            else:
                self.srcGeom = None
                self.actionSrcPoints.setChecked(False)
                self.actionSrcPoints.setEnabled(False)

            if os.path.exists(self.fileName + '.rel.npy'):                      # open the existing xps-file
                self.relGeom = np.load(self.fileName + '.rel.npy')
                self.relGeom = rfn.rename_fields(self.relGeom, {'Record': 'RecNum'})   # rename 'Record' field to 'RecNum' if found
                nImport = self.relGeom.shape[0]
                self.appendLogMessage(f'Loaded : . . . read {nImport:,} rel-records')
            else:
                self.relGeom = None

            self.rpsModel.setData(self.rpsImport)                               # update the three rps/sps/xps models
            self.spsModel.setData(self.spsImport)
            self.xpsModel.setData(self.xpsImport)

            self.recModel.setData(self.recGeom)                                 # update the three rec/rel/src models
            self.relModel.setData(self.relGeom)
            self.srcModel.setData(self.srcGeom)

            self.handleImageSelection()                                         # change selection and plot survey

        self.spiderPoint = QPoint(-1, -1)                                       # reset the spider location
        index = self.anaView.model().index(0, 0)                                # turn offset into index

        self.anaView.scrollTo(index)                                            # scroll to the first trace in the trace table
        self.anaView.selectRow(0)                                               # for the time being, *only* select first row of traces in a bin

        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.enableProcessingMenuItems(True)                                    # enable processing menu items; disable 'stop processing thread'

        self.layoutWidget.enableAutoRange()                                     # make the layout plot 'fit' the survey outline
        self.mainTabWidget.setCurrentIndex(0)                                   # make sure we display the Layout tab

        # self.plotLayout()                                                     # plot the survey object

        self.resetSurveyProperties()                                            # get the new parameters into the parameter tree. Can be time consuming with many blocks and many seeds
        self.survey.checkIntegrity(self.projectDirectory)                       # check for survey integrity after loading; in particular well file validity

        # self.appendLogMessage('RollMainWindow.parseText() profiling information', MsgType.Debug)
        # for i in range(0, 20):
        #     t = self.survey.timerTmax[i]                             # perf_counter counts in nano seconds, but returns time in [s]
        #     message = f'Time spent in function call #{i:2d}: {t:11.4f}'
        #     self.appendLogMessage(message, MsgType.Debug)

        # self.appendLogMessage('RollMainWindow.resetSurveyProperties() profiling information', MsgType.Debug)
        # i = 0
        # while i < len(config.timerTmin):                        # log some debug messages
        #     tMin = config.timerTmin[i] if config.timerTmin[i] != float('Inf') else 0.0
        #     tMax = config.timerTmax[i]
        #     tTot = config.timerTtot[i]
        #     freq = config.timerFreq[i]
        #     tAvr = tTot / freq if freq > 0 else 0.0
        #     message = f'Index {i:02d}, min {tMin:011.3f}, max {tMax:011.3f}, tot {tTot:011.3f}, avr {tAvr:011.3f}, freq {freq:07d}'
        #     # message = f'{i:02d}: min:{tMin:11.3f}, max:{tMax:11.3f}, tot:{tTot:11.3f}, avr:{tAvr:11.3f}, freq:{freq:7d}'
        #     self.appendLogMessage(message, MsgType.Debug)
        #     i += 1

        return success

    def fileImportSpsData(self) -> bool:
        spsLines = 0
        xpsLines = 0
        rpsLines = 0

        spsRead = 0
        xpsRead = 0
        rpsRead = 0

        # create the dialog to select SPS/RPS/XPS files to import, with dialog parent, current CRS and last used import directory
        dlg = SpsImportDialog(self, self.survey.crs, self.importDirectory)

        if not dlg.exec():                                                      # Run the dialog event loop, and obtain sps information
            return False

        if not dlg.fileNames:                                                   # no files selected; return False
            self.appendLogMessage('Import : no files selected')
            return False

        self.importDirectory = os.path.dirname(dlg.fileNames[0])                # retrieve the directory name from first file found

        spsDialect = dlg.spsFormatList.currentItem().text()                     # selected SPS dialect from dialog

        self.appendLogMessage(f"Import : importing SPS-data using the '{spsDialect}' SPS-dialect")
        self.appendLogMessage(f'Import : importing {len(dlg.rpsFiles)} rps-file(s), {len(dlg.spsFiles)} sps-file(s) and {len(dlg.xpsFiles)} xps-file(s)')

        spsFormat = next((item for item in config.spsFormatList if item['name'] == spsDialect), None)
        assert spsFormat is not None, f'No valid SPS dialect with name {spsDialect}'

        xpsFormat = next((item for item in config.xpsFormatList if item['name'] == spsDialect), None)
        assert xpsFormat is not None, f'No valid XPS dialect with name {spsDialect}'

        rpsFormat = next((item for item in config.rpsFormatList if item['name'] == spsDialect), None)
        assert rpsFormat is not None, f'No valid RPS dialect with name {spsDialect}'

        if dlg.spsFiles:                                                        # import the SPS data
            spsData = dlg.spsTab.toPlainText().splitlines()
            spsLines = len(spsData)
            self.spsImport = np.zeros(shape=spsLines, dtype=pntType1)

            self.progressLabel.setText(f'Importing {spsLines} lines of SPS data...')
            self.showStatusbarWidgets()

            oldProgress = 0
            self.interrupted = False
            for line_number, line in enumerate(spsData):
                QApplication.processEvents()  # Ensure the UI updates in real-time to check if the ESC key is pressed
                if self.interrupted is True:
                    break

                progress = (100 * line_number) // spsLines
                if progress > oldProgress:
                    oldProgress = progress
                    self.progressBar.setValue(progress)
                    QApplication.processEvents()  # Ensure the UI updates in real-time

                spsRead += readSpsLine(spsRead, line, self.spsImport, spsFormat)

            self.progressBar.setValue(100)

            if spsRead < spsLines:
                self.spsImport.resize(spsRead, refcheck=False)                  # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

            if self.interrupted:
                self.appendLogMessage('Import : importing SPS data canceled by user.')
                self.hideStatusbarWidgets()
                return False

        if dlg.xpsFiles:                                                        # import the XPS data
            xpsData = dlg.xpsTab.toPlainText().splitlines()
            xpsLines = len(xpsData)
            self.xpsImport = np.zeros(shape=xpsLines, dtype=relType2)

            self.progressLabel.setText(f'Importing {xpsLines} lines of XPS data...')
            self.showStatusbarWidgets()

            oldProgress = 0
            self.interrupted = False
            for line_number, line in enumerate(xpsData):
                QApplication.processEvents()  # Ensure the UI updates in real-time to check if the ESC key is pressed
                if self.interrupted is True:
                    break

                progress = (100 * line_number) // xpsLines
                if progress > oldProgress:
                    oldProgress = progress
                    self.progressBar.setValue(progress)
                    QApplication.processEvents()  # Ensure the UI updates in real-time

                xpsRead += readXpsLine(xpsRead, line, self.xpsImport, xpsFormat)

            self.progressBar.setValue(100)

            if xpsRead < xpsLines:
                self.xpsImport.resize(xpsRead, refcheck=False)                  # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

            if self.interrupted:
                self.appendLogMessage('Import : importing XPS data canceled by user.')
                self.hideStatusbarWidgets()
                return False

        if dlg.rpsFiles:                                                        # import the RPS data
            rpsData = dlg.rpsTab.toPlainText().splitlines()
            rpsLines = len(rpsData)
            self.rpsImport = np.zeros(shape=rpsLines, dtype=pntType1)

            self.progressLabel.setText(f'Importing {rpsLines} lines of RPS data...')
            self.showStatusbarWidgets()

            oldProgress = 0
            self.interrupted = False
            for line_number, line in enumerate(rpsData):
                QApplication.processEvents()  # Ensure the UI updates in real-time to check if the ESC key is pressed
                if self.interrupted is True:
                    break

                progress = (100 * line_number) // rpsLines
                if progress > oldProgress:
                    oldProgress = progress
                    self.progressBar.setValue(progress)
                    QApplication.processEvents()  # Ensure the UI updates in real-time

                rpsRead += readRpsLine(rpsRead, line, self.rpsImport, rpsFormat)

            self.progressBar.setValue(100)

            if rpsRead < rpsLines:
                self.rpsImport.resize(rpsRead, refcheck=False)        # See: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.resize.html

            if self.interrupted:
                self.appendLogMessage('Import : importing RPS data canceled by user.')
                self.hideStatusbarWidgets()
                return False

            self.appendLogMessage(f'Import : imported {spsLines} sps-records, {xpsLines} xps-records and {rpsLines} rps-records')
            QApplication.processEvents()  # Ensure the UI updates in real-time

        nQcStep = 0
        nQcSteps = 0
        if self.rpsImport is not None:
            nQcSteps += 1
        if self.spsImport is not None:
            nQcSteps += 1
        if self.xpsImport is not None:
            nQcSteps += 1
        if spsRead > 0 and xpsRead > 0:
            nQcSteps += 1
        if rpsRead > 0 and xpsRead > 0:
            nQcSteps += 1
        nQcIncrement = 100 // nQcSteps if nQcSteps > 0 else 0

        if nQcSteps > 0:
            self.progressBar.setValue(0)                                        # first reset to zero

        # sort and analyse imported arrays
        with pg.BusyCursor():
            if self.rpsImport is not None:
                self.progressLabel.setText(f'Import QC step : ({nQcStep + 1} / {nQcSteps}) analysing rps-records')
                self.progressBar.setValue(nQcIncrement * nQcStep)
                nQcStep += 1
                nImport = self.rpsImport.shape[0]
                nUnique = markUniqueRPSrecords(self.rpsImport, sort=True)
                self.appendLogMessage(f'Import : . . . analysed rps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')
                QApplication.processEvents()  # Ensure the UI updates in real-time

                convertCrs(self.rpsImport, dlg.crs, self.survey.crs)  # convert the coordinates to the survey CRS
                origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1 = calculateLineStakeTransform(self.rpsImport)

                self.appendLogMessage(f'Import : . . . . . . Origin: (E{origX:.2f}m, N{origY:.2f}m) @ (pnt{pMin:.1f}, lin{lMin:.1f})')
                self.appendLogMessage(f'Import : . . . . . . Orientation {angle1:,.3f}deg for lines &#8741; x-axis')
                self.appendLogMessage(f'Import : . . . . . . Intervals for (line, point) in design (lin{dLint:,.2f}m, pnt{dPint:,.2f}m)')
                self.appendLogMessage(f'Import : . . . . . . Increments for (line, point) in grid (lin{dLn:,.2f}m, pnt{dPn:,.2f}m)')

                QApplication.processEvents()  # Ensure the UI updates in real-time

                self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
                self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)        # get the convex hull of the rps points
                self.tbRpsList.setChecked(True)                                 # set the RPS list to be visible

            if self.spsImport is not None:
                self.progressLabel.setText(f'Import QC step : ({nQcStep + 1} / {nQcSteps}) analysing sps-records')
                self.progressBar.setValue(nQcIncrement * nQcStep)
                nQcStep += 1
                nImport = self.spsImport.shape[0]
                nUnique = markUniqueSPSrecords(self.spsImport, sort=True)
                self.appendLogMessage(f'Import : . . . analysed sps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')
                QApplication.processEvents()  # Ensure the UI updates in real-time

                convertCrs(self.spsImport, dlg.crs, self.survey.crs)  # convert the coordinates to the survey CRS
                origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1 = calculateLineStakeTransform(self.spsImport)

                self.appendLogMessage(f'Import : . . . . . . Origin: (E{origX:.2f}m, N{origY:.2f}m) @ (pnt{pMin:.1f}, lin{lMin:.1f})')
                self.appendLogMessage(f'Import : . . . . . . Orientation {angle1:,.3f}deg for lines &#8741; x-axis')
                self.appendLogMessage(f'Import : . . . . . . Intervals for (line, point) in design (lin{dLint:,.2f}m, pnt{dPint:,.2f}m)')
                self.appendLogMessage(f'Import : . . . . . . Increments for (line, point) in grid (lin{dLn:,.2f}m, pnt{dPn:,.2f}m)')

                self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
                self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)        # get the convex hull of the rps points
                self.tbSpsList.setChecked(True)

            if self.xpsImport is not None:
                self.progressLabel.setText(f'Import QC step : ({nQcStep + 1} / {nQcSteps}) analysing xps-records')
                self.progressBar.setValue(nQcIncrement * nQcStep)
                nQcStep += 1
                nImport = self.xpsImport.shape[0]
                nUnique = markUniqueXPSrecords(self.xpsImport, sort=True)
                self.appendLogMessage(f'Import : . . . analysed xps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')
                QApplication.processEvents()                                    # Ensure the UI updates in real-time

                traces = calcMaxXPStraces(self.xpsImport)
                self.appendLogMessage(f'Import : . . . the xps-records define a maximum of {traces:,} traces')

            # handle doublets  of RPS / XPS and SPS / XPS-files
            if spsRead > 0 and xpsRead > 0:
                self.progressLabel.setText(f'Import QC step : ({nQcStep + 1} / {nQcSteps}) analysing sps-xps orphans')
                self.progressBar.setValue(nQcIncrement * nQcStep)
                nQcStep += 1

                nSpsOrphans, nXpsOrphans = findSrcOrphans(self.spsImport, self.xpsImport)
                self.appendLogMessage(f'Import : . . . sps-records contain {nXpsOrphans:,} xps-orphans')
                self.appendLogMessage(f'Import : . . . xps-records contain {nSpsOrphans:,} sps-orphans')
                QApplication.processEvents()  # Ensure the UI updates in real-time

            if rpsRead > 0 and xpsRead > 0:
                self.progressLabel.setText(f'Import QC step : ({nQcStep + 1} / {nQcSteps}) analysing xps-rps orphans')
                self.progressBar.setValue(nQcIncrement * nQcStep)
                nQcStep += 1

                nRpsOrphans, nXpsOrphans = findRecOrphans(self.rpsImport, self.xpsImport)
                self.appendLogMessage(f'Import : . . . rps-records contain {nXpsOrphans:,} xps-orphans')
                self.appendLogMessage(f'Import : . . . xps-records contain {nRpsOrphans:,} rps-orphans')
                QApplication.processEvents()  # Ensure the UI updates in real-time

        self.spsModel.setData(self.spsImport)                                   # update the three sps/rps/xps models
        self.xpsModel.setData(self.xpsImport)
        self.rpsModel.setData(self.rpsImport)

        self.mainTabWidget.setCurrentIndex(4)                                   # make sure we display the 'SPS import' tab

        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.enableProcessingMenuItems(True)                                    # enable processing menu items, including binning from SPS data
        # self.actionRpsPoints.setEnabled(rpsRead > 0)
        # self.actionSpsPoints.setEnabled(spsRead > 0)

        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save sps data as numpy arrays upon saving the file
        self.hideStatusbarWidgets()
        return True

    def fileOpen(self):
        if self.maybeKillThread() and self.maybeSave():                         # current file may be modified; save it or discard edits
            fn, _ = QFileDialog.getOpenFileName(
                self,  # self; that's me
                'Open File...',  # caption
                self.projectDirectory,  # start directory + filename
                'Survey files (*.roll);; All files (*.*)'  # file extensions
                # options                                                       # not being used
            )
            if fn:
                self.fileLoad(fn)                                               # load() does all the hard work

    def fileOpenRecent(self):
        action = self.sender()
        if action:
            self.fileLoad(action.data())

    def fileSave(self):
        if not self.fileName:                                                   # need to have a valid filename first, and set the projectDirectory
            return self.fileSaveAs()

        if config.useRelativePaths:
            self.survey.makeWellPathsRelative(self.projectDirectory)            # make well paths relative to working directory

        xml_text = self.survey.toXmlString(4)

        file = QFile(self.fileName)
        success = file.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Truncate)

        if success:
            _ = QTextStream(file) << xml_text                                  # unused stream replaced by _ to make PyLint happy
            self.appendLogMessage(f'Saved&nbsp;&nbsp;: {self.fileName}')
            self.textEdit.document().setModified(False)
            file.close()

            # try to save the analysis files as well
            if self.output.binOutput is not None:
                np.save(self.fileName + '.bin.npy', self.output.binOutput)      # numpy array with fold map

            if self.output.minOffset is not None:
                np.save(self.fileName + '.min.npy', self.output.minOffset)      # numpy array with min-offset map

            if self.output.maxOffset is not None:
                np.save(self.fileName + '.max.npy', self.output.maxOffset)      # numpy array with max-offset map

            if self.output.rmsOffset is not None:
                np.save(self.fileName + '.rms.npy', self.output.rmsOffset)      # numpy array with max-offset map

            if self.output.offstHist is not None:
                np.save(self.fileName + '.off.npy', self.output.offstHist)      # numpy array with offset histogram

            if self.output.ofAziHist is not None:
                np.save(self.fileName + '.azi.npy', self.output.ofAziHist)      # numpy array with offset/azimuth histogram

            if self.rpsImport is not None:
                np.save(self.fileName + '.rps.npy', self.rpsImport)             # numpy array with list of RPS records

            if self.spsImport is not None:
                np.save(self.fileName + '.sps.npy', self.spsImport)             # numpy array with list of SPS records

            if self.xpsImport is not None:
                np.save(self.fileName + '.xps.npy', self.xpsImport)             # numpy array with list of XPS records

            if self.recGeom is not None:
                np.save(self.fileName + '.rec.npy', self.recGeom)               # numpy array with list of REC records

            if self.relGeom is not None:
                np.save(self.fileName + '.rel.npy', self.relGeom)               # numpy array with list of REL records

            if self.srcGeom is not None:
                np.save(self.fileName + '.src.npy', self.srcGeom)               # numpy array with list of SRC records
        else:
            self.appendLogMessage(f'saving : Cannot save file: {self.fileName}', MsgType.Error)
            QMessageBox.information(self, 'Write error', f'Cannot save file:\n{self.fileName}')

        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure

        return success

    def fileSaveAs(self):
        fileName = os.path.join(self.projectDirectory, self.survey.name)        # join dir & survey name, as proposed file path
        fn, _ = QFileDialog.getSaveFileName(
            self,  # that's me
            'Save as...',  # dialog caption
            fileName,  # start directory + filename
            'Survey files (*.roll);; All files (*.*)'  # file extensions
            # options                                                           # options not used
        )
        if not fn:
            return False

        if not fn.lower().endswith('.roll'):                                    # make sure file extension is okay
            fn += '.roll'                                                       # just add the file extension

        self.setCurrentFileName(fn)                                             # update self.fileName, set textEditModified(False) and setWindowModified(False)
        return self.fileSave()

    def fileSettings(self):                                                     # dialog implementation modeled after https://github.com/dglent/meteo-qt/blob/master/meteo_qt/settings.py
        dlg = SettingsDialog(self)
        dlg.appliedSignal.connect(self.updateSettings)

        if dlg.exec():                                                          # Run the dialog event loop, and obtain survey object
            self.updateSettings()

    def updateSettings(self):
        self.handleImageSelection()
        self.plotLayout()

    def fileExportAnaAsCsv(self):
        # export comma separated values
        records, fn = exportDataAsTxt(self, self.fileName, '.ana.csv', self.anaView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRecAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.rec.csv', self.recView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportSrcAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.src.csv', self.srcView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRelAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.rel.csv', self.relView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRpsAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.rps.csv', self.rpsView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportSpsAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.sps.csv', self.spsView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportXpsAsCsv(self):
        records, fn = exportDataAsTxt(self, self.fileName, '.xps.csv', self.xpsView)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRpsAsR01(self):
        # export SPS formatted values
        records, fn = fileExportAsR01(self, self.fileName, '.rps.r01', self.rpsView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRecAsR01(self):
        # export SPS formatted values
        records, fn = fileExportAsR01(self, self.fileName, '.rec.r01', self.recView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportSpsAsS01(self):
        # export SPS formatted values
        records, fn = fileExportAsS01(self, self.fileName, '.sps.s01', self.spsView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportSrcAsS01(self):
        # export SPS formatted values
        records, fn = fileExportAsS01(self, self.fileName, '.src.s01', self.srcView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportXpsAsX01(self):
        # export SPS formatted values
        records, fn = fileExportAsX01(self, self.fileName, '.xps.x01', self.xpsView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def fileExportRelAsX01(self):
        # export SPS formatted values
        records, fn = fileExportAsX01(self, self.fileName, '.rel.x01', self.relView, self.survey.crs)
        self.appendLogMessage(f"Export : exported {records:,} lines to '{fn}'")

    def _grabPlotWidgetForPrint(self):
        currentWidget = self.mainTabWidget.currentWidget()
        if isinstance(currentWidget, pg.PlotWidget):
            return currentWidget

        # If we're on the Analysis tab, drill down to the active analysis widget
        if currentWidget is self.analysisTabWidget:
            currentWidget = self.analysisTabWidget.currentWidget()

        if currentWidget is None:
            return None

        if isinstance(currentWidget, pg.PlotWidget):
            return currentWidget

        return currentWidget.findChild(pg.PlotWidget)

    def _copyPlotWidgetToClipboard(self) -> bool:
        plotWidget = self._grabPlotWidgetForPrint()
        if plotWidget is None:
            return False

        source = plotWidget.rect()
        if source.isEmpty():
            return False

        image = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        try:
            plotWidget.render(painter)
        finally:
            painter.end()

        QApplication.clipboard().setImage(image)
        return True

    def filePrint(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        # printer.setDocName("My Custom Title")
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.printPreview)
        preview.setWindowTitle('Print Preview')
        preview.exec()

    def printPreview(self, printer):
        currentWidget = self.mainTabWidget.currentWidget()

        if currentWidget is self.textEdit:
            self.textEdit.print(printer)
            return

        plotWidget = self._grabPlotWidgetForPrint()
        if plotWidget is not None:

            painter = QPainter(printer)
            try:
                target = printer.pageLayout().paintRectPixels(printer.resolution())
                source = plotWidget.rect()
                if source.isEmpty() or target.isEmpty():
                    return

                margin = int(min(target.width(), target.height()) * 0.10)
                target = target.adjusted(margin, margin, -margin, -margin)
                if target.isEmpty():
                    return

                # provide a header with the file name, if available
                headerText = QFileInfo(self.fileName).fileName() if self.fileName else 'Untitled'
                if headerText:
                    painter.save()
                    headerFont = QFont(painter.font())
                    headerFont.setBold(True)
                    headerFont.setPointSize(max(8, int(headerFont.pointSize() * 1.2)))
                    painter.setFont(headerFont)

                    headerHeight = painter.fontMetrics().height()
                    headerRect = QRectF(target.x(), target.y(), target.width(), headerHeight)
                    painter.drawText(headerRect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, headerText)

                    gap = max(2, int(headerHeight * 0.35))
                    lineY = int(headerRect.bottom() + (gap * 0.5))
                    painter.drawLine(int(target.x()), lineY, int(target.x() + target.width()), lineY)

                    target = target.adjusted(0, headerHeight + gap, 0, 0)
                    painter.restore()

                    if target.isEmpty():
                        return

                image = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.white)
                imagePainter = QPainter(image)
                try:
                    plotWidget.render(imagePainter)
                finally:
                    imagePainter.end()

                scale = min(target.width() / image.width(), target.height() / image.height())
                x = target.x() + (target.width() - image.width() * scale) / 2.0
                y = target.y() + (target.height() - image.height() * scale) / 2.0
                drawRect = QRectF(x, y, image.width() * scale, image.height() * scale)

                painter.drawImage(drawRect, image)
            finally:
                painter.end()
            return

        # fallback: print XML if other tabs are active
        self.textEdit.print(printer)

    def filePrintPdf(self):
        fn, _ = QFileDialog.getSaveFileName(self, 'Export PDF', None, 'PDF files (*.pdf);;All Files (*)')

        if fn:
            if QFileInfo(fn).suffix().isEmpty():
                fn += '.pdf'

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(fn)
            self.textEdit.document().print(printer)

    def appendLogMessage(self, message: str = 'test', index: MsgType = MsgType.Info):
        # dateTime = QDateTime.currentDateTime().toString("dd-MM-yyyy hh:mm:ss")
        dateTime = QDateTime.currentDateTime().toString('yyyy-MM-ddTHH:mm:ss')  # UTC time; same format as is used in QGis

        if index == MsgType.Debug and not config.debug:                         # debug message, which needs to be suppressed
            return

        # use &nbsp; (non-breaking-space) to prevent html eating up subsequent spaces !
        switch = {  # see: https://doc.qt.io/qt-6/qcolor.html
            MsgType.Info:       f'<p>{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;info&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{message}</p>',            # info     = black
            MsgType.Binning:    f'<p style="color:blue" >{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;binning&nbsp;&nbsp;&nbsp;&nbsp;{message}</p>',    # Binning  = blue
            MsgType.Geometry:   f'<p style="color:green">{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;geometry&nbsp;&nbsp;&nbsp;{message}</p>',        # Geometry = green
            MsgType.Debug:      f'<p style="color:darkCyan">{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;debug&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Called : {message}</p>',  # Debug    = darkCyan
            MsgType.Warning:    f'<p style="color:magenta">{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;warning&nbsp;&nbsp;&nbsp;&nbsp;{message}</p>',  # Warning  = magenta
            MsgType.Error:      f'<p style="color:red">{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;error&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{message}</p>',  # Error     = red
            MsgType.Exception:  f'<p style="color:red">{dateTime}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;exception&nbsp;&nbsp;{message}</p>',                  # exception = bold red
        }

        self.logEdit.appendHtml(switch.get(index, 'Unknown Message type'))      # Adds the message to the widget
        self.logEdit.moveCursor(QTextCursor.MoveOperation.End)                                # scroll the edit control

        if index == MsgType.Exception:                                          # play a sound to notify end user of exception
            # SystemAsterisk, SystemExclamation, SystemExit, SystemHand, SystemQuestion are common sounds; use asyync to avoid waiting on sound to finish
            winsound.PlaySound('SystemHand', winsound.SND_ALIAS | winsound.SND_ASYNC)

    def parseText(self, plainText):
        if len(plainText) == 0:                                                 # no text available; return False
            self.appendLogMessage('Parse&nbsp;&nbsp;: error occurred while parsing empty string', MsgType.Error)
            return False
        # print (plainText)
        doc = QDomDocument()                                                    # first get a QDomDocument to work with
        success, errorMsg, errorLine, errorColumn = doc.setContent(plainText)

        if success:                                                             # parsing went ok, start with a new survey object

            with pg.BusyCursor():                                               # this may take some time
                self.survey = RollSurvey()                                      # only reset the survey object upon succesful parse
                self.survey.readXml(doc)                                        # build the RollSurvey object tree; no heavy lifting takes place here
                self.survey.calcTransforms()                                    # (re)calculate the transforms being used; some work to to set up the plane using three points in the global space
                self.survey.makeWellPathsAbsolute(self.projectDirectory)        # make well paths absolute, if they are not already. Used when loading a survey
                self.survey.calcSeedData()                                      # needed for circles, spirals & well-seeds; may affect bounding box
                self.survey.calcBoundingRect()                                  # (re)calculate the boundingBox as part of parsing the data
                self.survey.calcNoShotPoints()                                  # (re)calculate nr of SPs
                self.survey.bindSeedsToSurvey()                                 # bind seeds to survey after parsing
                self.appendLogMessage(f'Parsing: {self.fileName} survey object succesfully parsed')

                return True
        else:  # an error occurred
            self.appendLogMessage(f'Parse&nbsp;&nbsp;: {errorMsg}, at line: {errorLine} col:{errorColumn}; survey object not updated', MsgType.Error)
            return False

    def OnAbout(self):
        QMessageBox.about(self, 'About Roll', aboutText())

    def OnLicense(self):
        QMessageBox.about(self, 'License conditions', licenseText())

    def OnHighDpi(self):
        QMessageBox.about(self, 'High DPI UI scaling issues', highDpiText())

    def OnQGisCheatSheet(self):
        QMessageBox.about(self, 'QGis Cheat Sheet', qgisCheatSheetText())

    def OnQGisRollInterface(self):
        # See: https://stackoverflow.com/questions/4216985/call-to-operating-system-to-open-url

        dirName = os.path.dirname(os.path.abspath(__file__))
        urlName = os.path.join(dirName, 'resources', 'Essential_QGis_operations.html')
        # urlName = 'file:///D:/qGIS/MyPlugins/roll/resources/Essential_QGis_operations.html'
        if os.path.exists(urlName):
            urlName = 'file:///' + urlName.replace('\\', '/')                   # idea from CoPilot: convert to file:///
            webbrowser.open(urlName, new=0, autoraise=True)

    def clipboardHasText(self):
        return len(QApplication.clipboard().text()) != 0

    def enableProcessingMenuItems(self, enable=True):
        """Enable or disable the processing menu items, depending on the state of the survey object."""

        nTemplates = self.survey.calcNoTemplates() if self.survey is not None else 0
        if nTemplates > 0:
            self.actionBasicBinFromTemplates.setEnabled(enable)
            self.actionFullBinFromTemplates.setEnabled(enable)
            self.actionGeometryFromTemplates.setEnabled(enable)
        else:
            self.actionBasicBinFromTemplates.setEnabled(False)
            self.actionFullBinFromTemplates.setEnabled(False)
            self.actionGeometryFromTemplates.setEnabled(False)

        if enable is True and self.srcGeom is not None and self.recGeom is not None:
        # if enable is True and self.srcGeom is not None and self.relGeom is not None and self.recGeom is not None:
            self.actionBasicBinFromGeometry.setEnabled(enable)
            self.actionFullBinFromGeometry.setEnabled(enable)
        else:
            self.actionBasicBinFromGeometry.setEnabled(False)
            self.actionFullBinFromGeometry.setEnabled(False)

        if enable is True and self.spsImport is not None and self.rpsImport is not None:
        # if enable is True and self.spsImport is not None and self.xpsImport is not None and self.rpsImport is not None:
            self.actionBasicBinFromSps.setEnabled(enable)
            self.actionFullBinFromSps.setEnabled(enable)
        else:
            self.actionBasicBinFromSps.setEnabled(False)
            self.actionFullBinFromSps.setEnabled(False)

        self.actionStopThread.setEnabled(not enable)

    def onSpsInUseToggled(self, rows):
        if self.spsImport is None:
            return

        self.spsLiveE, self.spsLiveN, self.spsDeadE, self.spsDeadN = getAliveAndDead(self.spsImport)
        self.spsBound = convexHull(self.spsLiveE, self.spsLiveN)
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} SPS record(s)')

    def onRpsInUseToggled(self, rows):
        if self.rpsImport is None:
            return

        self.rpsLiveE, self.rpsLiveN, self.rpsDeadE, self.rpsDeadN = getAliveAndDead(self.rpsImport)
        self.rpsBound = convexHull(self.rpsLiveE, self.rpsLiveN)
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} RPS record(s)')
    def onSrcInUseToggled(self, rows):
        if self.srcGeom is None:
            return

        self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} SRC record(s)')

    def onRecInUseToggled(self, rows):
        if self.recGeom is None:
            return

        self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} REC record(s)')
