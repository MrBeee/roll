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
except ImportError:
    haveDebugpy = False

import contextlib
import gc
import os
import platform
import sys
import traceback
import webbrowser
import winsound  # make a sound when an exception ocurs
from math import atan2, ceil, degrees

# PyQtGraph related imports
import numpy as np  # Numpy functions needed for plot creation
import pyqtgraph as pg
from qgis.core import QgsApplication
from qgis.PyQt import uic
from qgis.PyQt.QtCore import (QDateTime, QEvent, QFileInfo, QPoint, QRectF,
                              QSettings, QSize, Qt, QTimer)
from qgis.PyQt.QtGui import (QBrush, QColor, QFont, QIcon, QImage, QPainter,
                             QPainterPath, QPen, QTextCursor, QTransform)
from qgis.PyQt.QtPrintSupport import QPrinter, QPrintPreviewDialog
from qgis.PyQt.QtWidgets import (QAction, QApplication, QFileDialog,
                                 QGraphicsEllipseItem, QGraphicsPathItem,
                                 QGraphicsRectItem, QLabel, QMainWindow,
                                 QMessageBox, QProgressBar, QTabWidget,
                                 QWidget)
from qgis.PyQt.QtXml import QDomDocument

# from .functions_numba import (numbaAziInline, numbaAziXline,
#                               numbaFilterSlice2D, numbaNdft1D, numbaNdft2D,
#                               numbaOffInline, numbaOffsetBin, numbaOffXline,
#                               numbaSlice3D, numbaSliceStats)
from . import config  # used to pass initial settings
from . import functions_numba as fnb
from .app_settings import AppSettings
from .aux_classes import LineROI
from .aux_functions import (aboutText, exampleSurveyXmlText, highDpiText,
                            licenseText, myPrint, qgisCheatSheetText)
from .binning_worker_mixin import BinningWorkerMixin
from .chunked_data import ChunkedData
from .display_dock import createDisplayDock
from .document_context_service import DocumentContextService
from .enums_and_int_flags import (AnalysisRedrawReason, Direction, MsgType,
                                  PaintDetails, PaintMode, SurveyType)
from .filter_service import FilterService
# from .find import Find.
# Superseded by FindNotepad, which is more user friendly and has a better implementation.
# The old Find class is still available in find.py, but not imported here.
from .find import FindNotepad
from .import_service import ImportService
from .land_wizard import LandSurveyWizard
from .logging_dock import createLoggingDock
from .marine_wizard import MarineSurveyWizard
from .my_parameters import registerAllParameterTypes
from .plot_redraw_helper import PlotRedrawHelper
from .project_load_applier import ProjectLoadApplier
from .project_service import ProjectService
from .property_dock import createPropertyDock
from .qgis_interface import (CreateQgisRasterLayer, ExportRasterLayerToQgis,
                             exportPointLayerToQgis, exportSpsOutlinesToQgis,
                             exportSurveyOutlinesToQgis,
                             identifyQgisPointLayer, readQgisPointLayer)
from .roll_binning import BinningType
from .roll_main_window_create_geom_tab import createGeomTab
from .roll_main_window_create_layout_tab import createLayoutTab
from .roll_main_window_create_off_azi_tab import createOffAziTab
from .roll_main_window_create_offset_tabs import createOffsetTabs
from .roll_main_window_create_pattern_tab import createPatternTab
from .roll_main_window_create_sps_tab import createSpsTab
from .roll_main_window_create_stack_response_tab import createStackResponseTab
from .roll_main_window_create_trace_table_tab import createTraceTableTab
from .roll_output import RollOutput
from .roll_survey import RollSurvey
from .runtime_state import RuntimeState
from .session_service import SessionService
from .session_state import SessionState
from .settings import SettingsDialog, readSettings, writeSettings
from .spider_navigation_mixin import SpiderNavigationMixin
from .sps_import_dialog import SpsImportDialog
from .sps_io_and_qc import (convertCrs, exportDataAsTxt, fileExportAsR01,
                            fileExportAsS01, fileExportAsX01)
from .survey_paint_mixin import SurveyPaintMixin
from .xml_code_editor import QCodeEditor, XMLHighlighter

# code to run Roll standalone, without QGIS, for testing and development purposes

def _toQgsArgv(argv):
    if argv is None:
        argv = []
    qgsArgv = []
    for arg in argv:
        if isinstance(arg, bytes):
            qgsArgv.append(arg)
        else:
            qgsArgv.append(str(arg).encode('utf-8', errors='ignore'))
    return qgsArgv

def getStandaloneQgisApp(argv=None):
    argv = sys.argv if argv is None else argv
    qgsApp = QgsApplication.instance()
    ownsQgsApp = False

    if qgsApp is None:
        qgsApp = QgsApplication(_toQgsArgv(argv), True)
        qgsApp.initQgis()
        ownsQgsApp = True

    return qgsApp, ownsQgsApp

def runStandalone(argv=None, filePath=None):
    qgsApp, ownsQgsApp = getStandaloneQgisApp(argv)
    qgsApp.setQuitOnLastWindowClosed(True)

    mainWindow = RollMainWindow(iface=None, parent=None, standaloneMode=True)
    mainWindow.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    mainWindow.destroyed.connect(qgsApp.quit)
    qgsApp.aboutToQuit.connect(mainWindow.onAppAboutToQuit)
    mainWindow.show()

    def _safeLoad():
        logPath = os.path.join(os.path.dirname(__file__), 'roll_standalone.err.log')
        try:
            with open(logPath, 'a', encoding='utf-8') as f:
                f.write(f'[INFO] _safeLoad filePath={filePath}\n')
            if not filePath or not os.path.isfile(filePath):
                with open(logPath, 'a', encoding='utf-8') as f:
                    f.write('[ERROR] filePath missing or not a file\n')
                return
            mainWindow.fileLoad(filePath)
        except (OSError, ValueError) as exc:
            with open(logPath, 'a', encoding='utf-8') as f:
                f.write(f'[ERROR] _safeLoad failed: {exc}\n')

    if filePath:
        QTimer.singleShot(0, _safeLoad)

    exitCode = qgsApp.exec()

    if ownsQgsApp:
        qgsApp.exitQgis()

    return exitCode

# Determine path to resources
currentDir = os.path.dirname(os.path.abspath(__file__))
resourceDir = os.path.join(currentDir, 'resources')

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

    def _setSessionArray(self, arrayAttr, value):
        self.sessionService.setArray(self.sessionState, arrayAttr, value)

    @property
    def rpsImport(self):
        return self.sessionState.rpsImport

    @rpsImport.setter
    def rpsImport(self, value):
        self._setSessionArray('rpsImport', value)

    @property
    def spsImport(self):
        return self.sessionState.spsImport

    @spsImport.setter
    def spsImport(self, value):
        self._setSessionArray('spsImport', value)

    @property
    def xpsImport(self):
        return self.sessionState.xpsImport

    @xpsImport.setter
    def xpsImport(self, value):
        self._setSessionArray('xpsImport', value)

    @property
    def recGeom(self):
        return self.sessionState.recGeom

    @recGeom.setter
    def recGeom(self, value):
        self._setSessionArray('recGeom', value)

    @property
    def srcGeom(self):
        return self.sessionState.srcGeom

    @srcGeom.setter
    def srcGeom(self, value):
        self._setSessionArray('srcGeom', value)

    @property
    def relGeom(self):
        return self.sessionState.relGeom

    @relGeom.setter
    def relGeom(self, value):
        self._setSessionArray('relGeom', value)

    @property
    def rpsLiveE(self):
        return self.sessionState.rpsLiveE

    @rpsLiveE.setter
    def rpsLiveE(self, value):
        self.sessionState.rpsLiveE = value

    @property
    def rpsLiveN(self):
        return self.sessionState.rpsLiveN

    @rpsLiveN.setter
    def rpsLiveN(self, value):
        self.sessionState.rpsLiveN = value

    @property
    def rpsDeadE(self):
        return self.sessionState.rpsDeadE

    @rpsDeadE.setter
    def rpsDeadE(self, value):
        self.sessionState.rpsDeadE = value

    @property
    def rpsDeadN(self):
        return self.sessionState.rpsDeadN

    @rpsDeadN.setter
    def rpsDeadN(self, value):
        self.sessionState.rpsDeadN = value

    @property
    def spsLiveE(self):
        return self.sessionState.spsLiveE

    @spsLiveE.setter
    def spsLiveE(self, value):
        self.sessionState.spsLiveE = value

    @property
    def spsLiveN(self):
        return self.sessionState.spsLiveN

    @spsLiveN.setter
    def spsLiveN(self, value):
        self.sessionState.spsLiveN = value

    @property
    def spsDeadE(self):
        return self.sessionState.spsDeadE

    @spsDeadE.setter
    def spsDeadE(self, value):
        self.sessionState.spsDeadE = value

    @property
    def spsDeadN(self):
        return self.sessionState.spsDeadN

    @spsDeadN.setter
    def spsDeadN(self, value):
        self.sessionState.spsDeadN = value

    @property
    def recLiveE(self):
        return self.sessionState.recLiveE

    @recLiveE.setter
    def recLiveE(self, value):
        self.sessionState.recLiveE = value

    @property
    def recLiveN(self):
        return self.sessionState.recLiveN

    @recLiveN.setter
    def recLiveN(self, value):
        self.sessionState.recLiveN = value

    @property
    def recDeadE(self):
        return self.sessionState.recDeadE

    @recDeadE.setter
    def recDeadE(self, value):
        self.sessionState.recDeadE = value

    @property
    def recDeadN(self):
        return self.sessionState.recDeadN

    @recDeadN.setter
    def recDeadN(self, value):
        self.sessionState.recDeadN = value

    @property
    def srcLiveE(self):
        return self.sessionState.srcLiveE

    @srcLiveE.setter
    def srcLiveE(self, value):
        self.sessionState.srcLiveE = value

    @property
    def srcLiveN(self):
        return self.sessionState.srcLiveN

    @srcLiveN.setter
    def srcLiveN(self, value):
        self.sessionState.srcLiveN = value

    @property
    def srcDeadE(self):
        return self.sessionState.srcDeadE

    @srcDeadE.setter
    def srcDeadE(self, value):
        self.sessionState.srcDeadE = value

    @property
    def srcDeadN(self):
        return self.sessionState.srcDeadN

    @srcDeadN.setter
    def srcDeadN(self, value):
        self.sessionState.srcDeadN = value

    @property
    def rpsBound(self):
        return self.sessionState.rpsBound

    @rpsBound.setter
    def rpsBound(self, value):
        self.sessionState.rpsBound = value

    @property
    def spsBound(self):
        return self.sessionState.spsBound

    @spsBound.setter
    def spsBound(self, value):
        self.sessionState.spsBound = value

    @property
    def projectDirectory(self):
        return self.runtimeState.projectDirectory

    @projectDirectory.setter
    def projectDirectory(self, value):
        self.runtimeState.projectDirectory = value or ''

    @property
    def importDirectory(self):
        return self.runtimeState.importDirectory

    @importDirectory.setter
    def importDirectory(self, value):
        self.runtimeState.importDirectory = value or ''

    @property
    def fileName(self):
        return self.runtimeState.fileName

    @fileName.setter
    def fileName(self, value):
        self.runtimeState.fileName = value or ''

    @property
    def recentFileList(self):
        return self.runtimeState.recentFileList

    @recentFileList.setter
    def recentFileList(self, value):
        self.runtimeState.recentFileList = list(value or [])

    @property
    def surveyNumber(self):
        return self.sessionState.surveyNumber

    @surveyNumber.setter
    def surveyNumber(self, value):
        self.sessionState.surveyNumber = int(value)

    def __init__(self, iface=None, parent=None, standaloneMode=False):
        """Constructor."""
        super().__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing self.<objectname>,
        # and you can use autoconnect slots - see http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # widgets-and-dialogs-with-auto-connect
        # See also: https://doc.qt.io/qt-6/designer-using-a-ui-file-python.html
        # See: https://docs.qgis.org/3.22/en/docs/documentation_guidelines/substitutions.html#toolbar-button-icons for QGIS Icons
        self.setupUi(self)
        createDisplayDock(self)
        createLoggingDock(self)

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
        self.filterService = FilterService()
        self.importService = ImportService()
        self.projectService = ProjectService()
        self.projectLoadApplier = ProjectLoadApplier(self)
        self.documentContextService = DocumentContextService()
        self.sessionService = SessionService()
        self.sessionState = SessionState()
        self.appSettings = AppSettings()
        self.runtimeState = RuntimeState()

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
        self.x0lineStk = None                                                   # numpy array with x_line Kr stack reponse
        self.xyCellStk = None                                                   # numpy array with cell's KxKy stack response
        self.xyPatResp = None                                                   # numpy array with pattern's KxKy response
        self.plotRedrawHelper = PlotRedrawHelper()

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
        self.offAziPolarItems = []
        self._updatingOffAziColorBarLevels = False
        self._resetOffAziDisplayLevels = False
        self.kxyPatColorBar = None

        # Imported and geometry arrays, along with their derived live/dead and
        # convex-hull state, are owned by self.sessionState.

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

        iconFile = os.path.join(resourceDir, 'icon.png')

        icon = QIcon(iconFile)
        self.setWindowIcon(icon)

        # See: https://gist.github.com/dgovil/d83e7ddc8f3fb4a28832ccc6f9c7f07b dealing with settings
        # See also : https://doc.qt.io/qtforpython-5/PySide2/QtCore/QSettings.html
        # QCoreApplication.setOrganizationName('Duijndam.Dev')
        # QCoreApplication.setApplicationName('Roll')
        # self.settings = QSettings()   ## doesn't work as expected with QCoreApplication.setXXX

        self.settings = QSettings(config.organization, config.application)

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
        self.tabOffTrk = QWidget()
        self.tabOffBin = QWidget()
        self.tabOffAzi = QWidget()

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
        createOffsetTabs(self)
        createOffAziTab(self)

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
        self.analysisTabWidget.addTab(self.tabOffTrk, 'Offset Inline')
        self.analysisTabWidget.addTab(self.tabOffBin, 'Offset X-line')
        self.analysisTabWidget.addTab(self.aziTrkWidget, 'Azi Inline')
        self.analysisTabWidget.addTab(self.aziBinWidget, 'Azi X-line')
        self.analysisTabWidget.addTab(self.stkTrkWidget, 'Stack Inline')
        self.analysisTabWidget.addTab(self.stkBinWidget, 'Stack X-line')
        self.analysisTabWidget.addTab(self.tabKxKyStack, 'Kx-Ky Stack')
        self.analysisTabWidget.addTab(self.offsetWidget, '|O| Histogram')
        self.analysisTabWidget.addTab(self.tabOffAzi, 'O/A Histogram')
        # self.arraysWidget is embedded in the layout of the 'pattern' tab
        # self.analysisTabWidget.addTab(self.stkCelWidget, 'Kx-Ky Stack')
        # self.analysisTabWidget.currentChanged.connect(self.onAnalysisTabChange)   # active tab changed!

        self.setCurrentFileName()

        # connect actions
        self.textEdit.document().modificationChanged.connect(self.setWindowModified)    # forward signal to myself, and make some changes
        self.setWindowModified(self.textEdit.document().isModified())                   # update window status based on document status
        self.textEdit.cursorPositionChanged.connect(self.cursorPositionChanged)         # to show cursor position in statusbar

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
        self.actionReparseDocument.triggered.connect(self.updateAllViews)       # hooked up with Ctrl+F5
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
        self.actionAbout.triggered.connect(self.onAbout)
        self.actionLicense.triggered.connect(self.onLicense)
        self.actionHighDpi.triggered.connect(self.onHighDpi)
        self.actionQGisCheatSheet.triggered.connect(self.onQGisCheatSheet)
        self.actionQGisRollInterface.triggered.connect(self.onQGisRollInterface)

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
            if self.appSettings.useNumba:
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
        createPropertyDock(self)                                              # defined late, as it needs access the loaded survey object

        self.menuView.addSeparator()
        self.menuView.addAction(self.fileBar.toggleViewAction())
        self.menuView.addAction(self.editBar.toggleViewAction())
        self.menuView.addAction(self.graphBar.toggleViewAction())
        self.menuView.addAction(self.moveBar.toggleViewAction())
        self.menuView.addAction(self.paintBar.toggleViewAction())

        self.plotLayout()

        self.updateRecentFileActions()                                          # update the MRU file menu actions, with info from readSettings()

        if self.standaloneMode:                                                 # Optional: disable actions that require a live QGIS iface
            self._configureStandaloneUi()

        self.statusbar.showMessage('Ready', 3000)

    def _setActionEnabledSafe(self, actionName, enabled):
        action = getattr(self, actionName, None)
        if action is not None:
            action.setEnabled(enabled)

    def _processImportEvents(self):
        QApplication.processEvents()
        return self.interrupted

    def _updateImportProgress(self, labelText, progress):
        self.progressLabel.setText(labelText)
        self.progressBar.setValue(progress)
        QApplication.processEvents()

    def _configureStandaloneUi(self):
        actionNames = (
            'actionImportFromQgis',
            'actionExportToQgis',
            'actionImportSpsFromQgis',
            'actionExportSpsToQgis',
        )

        for actionName in actionNames:
            self._setActionEnabledSafe(actionName, False)


    # deal with pattern selection for display & kxky plotting
    def onPattern1IndexChanged(self):
        self.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.patternSelectionChanged)

    def onPattern2IndexChanged(self):
        self.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.patternSelectionChanged)

    def onActionPatternLayoutTriggered(self):
        self.patternLayout = True
        self.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.patternDisplayModeChanged)

    def onActionPatternKxKyTriggered(self):
        self.patternLayout = False
        self.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.patternDisplayModeChanged)

    # deal with pattern selection for bin stack response
    def onStackPatternIndexChanged(self):
        self.dispatchAnalysisRedraw('stack-cell', AnalysisRedrawReason.stackPatternChanged)

    def onOffAziDisplayMethodChanged(self):
        if self.output.anaOutput is None and self.output.ofAziHist is None:
            return

        self.dispatchAnalysisRedraw('off-azi', AnalysisRedrawReason.offAziDisplayModeChanged)

    @staticmethod
    def offsetComponentLabel(component: int) -> str:
        if component == 1:
            return 'inline'
        if component == 2:
            return 'x-line'
        return '|offset|'

    def getSelectedOffsetComponent(self, actionGroupName: str) -> int:
        actionGroup = getattr(self, actionGroupName, None)
        if actionGroup is None:
            return 0

        action = actionGroup.checkedAction()
        data = action.data() if action is not None else 0
        return int(data) if data is not None else 0

    def updateOffsetPlotComponentLabel(self, plotWidget, component: int) -> None:
        plotWidget.setLabel('left', self.offsetComponentLabel(component), units='m')

    def onOffTrkComponentChanged(self):
        component = self.getSelectedOffsetComponent('OffTrkComponentActionGroup')
        self.updateOffsetPlotComponentLabel(self.offTrkWidget, component)

        if self.output.anaOutput is None:
            return

        self.updateVisiblePlotWidget(1)

    def onOffBinComponentChanged(self):
        component = self.getSelectedOffsetComponent('OffBinComponentActionGroup')
        self.updateOffsetPlotComponentLabel(self.offBinWidget, component)

        if self.output.anaOutput is None:
            return

        self.updateVisiblePlotWidget(2)

    def onOffAziColorBarLevelsChanged(self, *_):
        if getattr(self, '_updatingOffAziColorBarLevels', False):
            return

        if self.output.ofAziHist is None:
            return

        if self.isOffAziPolarMode():
            self.dispatchAnalysisRedraw('off-azi', AnalysisRedrawReason.offAziColorBarLevelsChanged)

    def isOffAziPolarMode(self):
        action = getattr(self, 'actionOffAziPolar', None)
        return action is not None and action.isChecked()

    def createOffAziSectorPath(self, innerRadius, outerRadius, startAngleDeg, endAngleDeg, samples=8):
        path = QPainterPath()
        outerAngles = np.linspace(startAngleDeg, endAngleDeg, samples)
        innerAngles = np.linspace(endAngleDeg, startAngleDeg, samples)

        startAngleRad = np.deg2rad(outerAngles[0])
        path.moveTo(outerRadius * np.cos(startAngleRad), outerRadius * np.sin(startAngleRad))

        for angleDeg in outerAngles[1:]:
            angleRad = np.deg2rad(angleDeg)
            path.lineTo(outerRadius * np.cos(angleRad), outerRadius * np.sin(angleRad))

        for angleDeg in innerAngles:
            angleRad = np.deg2rad(angleDeg)
            path.lineTo(innerRadius * np.cos(angleRad), innerRadius * np.sin(angleRad))

        path.closeSubpath()
        return path

    def updateOffAziColorBar(self, colorMapObj, lowLevel, highLevel):
        if self.offAziImItem is None:
            return

        label = 'frequency (x 1000)'
        lowLevel = float(lowLevel)
        highLevel = float(highLevel)
        if highLevel <= lowLevel:
            highLevel = lowLevel + 1.0

        if self.offAziColorBar is None:
            try:
                self.offAziColorBar = self.offAziWidget.plotItem.addColorBar(
                    self.offAziImItem,
                    colorMap=colorMapObj,
                    label=label,
                    limits=(0.0, None),
                    rounding=10.0,
                    values=(0.0, highLevel),
                )
                self.offAziColorBar.sigLevelsChanged.connect(self.onOffAziColorBarLevelsChanged)
            except TypeError as exc:
                self.appendLogMessage(f'Colorbar init failed: {exc}', MsgType.Error)
                self.offAziColorBar = None
                return

        try:
            self.offAziColorBar.setImageItem(self.offAziImItem)
            self._updatingOffAziColorBarLevels = True
            self.offAziColorBar.setLevels(low=lowLevel, high=highLevel)
            self.offAziColorBar.setColorMap(colorMapObj)
            if self.offAziColorBar.horizontal:
                self.offAziColorBar.getAxis('bottom').setLabel(label)
            else:
                self.offAziColorBar.getAxis('left').setLabel(label)
        except TypeError as exc:
            self.appendLogMessage(f'Colorbar setColorMap failed: {exc}', MsgType.Error)
        finally:
            self._updatingOffAziColorBarLevels = False

    def clearOffAziGraphics(self):
        if self.offAziImItem is not None:
            with contextlib.suppress(Exception):
                self.offAziWidget.plotItem.removeItem(self.offAziImItem)
            self.offAziImItem = None

        for item in self.offAziPolarItems:
            with contextlib.suppress(Exception):
                self.offAziWidget.plotItem.removeItem(item)

        self.offAziPolarItems = []

    def getOffAziDisplayLevels(self, defaultHigh):
        defaultHigh = max(float(defaultHigh), 1.0)
        if getattr(self, '_resetOffAziDisplayLevels', False):
            self._resetOffAziDisplayLevels = False
            return (0.0, defaultHigh)

        if self.offAziColorBar is None:
            return (0.0, defaultHigh)

        try:
            low, high = self.offAziColorBar.levels()
        except TypeError:
            return (0.0, defaultHigh)

        low = float(low)
        high = float(high)
        if high <= low:
            high = low + 1.0
        return (low, high)

    def renderOffAziRectangular(self, histogram, dA, dO, aMin, colorMapObj):
        levelHigh = float(np.max(histogram)) if histogram.size else 0.0
        lowLevel, highLevel = self.getOffAziDisplayLevels(levelHigh)

        self.clearOffAziGraphics()
        self.offAziDisplayPolar = False
        self.offAziDisplayDA = dA
        self.offAziDisplayDO = dO
        self.offAziDisplayAMin = aMin
        self.offAziDisplayOMax = None

        tr = QTransform()
        tr.translate(aMin, 0)
        tr.scale(dA, dO)

        self.offAziImItem = pg.ImageItem()
        self.offAziImItem.setImage(histogram, levels=(lowLevel, highLevel))
        self.offAziImItem.setTransform(tr)

        self.offAziWidget.plotItem.addItem(self.offAziImItem)
        self.offAziWidget.showGrid(x=True, y=True, alpha=0.75)
        self.offAziWidget.setLabel('bottom', 'azimuth', units='deg')
        self.offAziWidget.setLabel('left', '|offset|', units='m')
        self.offAziWidget.plotItem.getViewBox().setAspectLocked(False)
        self.updateOffAziColorBar(colorMapObj, lowLevel, highLevel)
        self.offAziWidget.autoRange()

    def renderOffAziPolar(self, histogram, dA, dO, oMax, colorMapObj):
        maxCount = float(np.max(histogram)) if histogram.size else 0.0
        lowLevel, highLevel = self.getOffAziDisplayLevels(maxCount)

        self.clearOffAziGraphics()
        self.offAziDisplayPolar = True
        self.offAziDisplayDA = dA
        self.offAziDisplayDO = dO
        self.offAziDisplayAMin = None
        self.offAziDisplayOMax = oMax

        self.offAziImItem = pg.ImageItem()
        self.offAziImItem.setImage(histogram, levels=(lowLevel, highLevel))

        self.offAziWidget.showGrid(x=False, y=False)
        self.offAziWidget.setLabel('bottom', ' ', units='')
        self.offAziWidget.setLabel('left', ' ', units='')
        self.offAziWidget.plotItem.getViewBox().setAspectLocked(True)

        for offsetRadius in np.arange(dO, oMax + 0.5 * dO, dO):
            ring = QGraphicsEllipseItem(-offsetRadius, -offsetRadius, 2.0 * offsetRadius, 2.0 * offsetRadius)
            ring.setPen(pg.mkPen((160, 160, 160), width=1))
            ring.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            self.offAziWidget.plotItem.addItem(ring)
            self.offAziPolarItems.append(ring)

        for angleDeg in range(0, 360, 45):
            angleRad = np.deg2rad(angleDeg)
            x2 = oMax * np.cos(angleRad)
            y2 = oMax * np.sin(angleRad)
            lineItem = self.offAziWidget.plot([0.0, x2], [0.0, y2], pen=pg.mkPen((185, 185, 185), width=1))
            self.offAziPolarItems.append(lineItem)

        for azimuthIndex in range(histogram.shape[0]):
            startAngle = azimuthIndex * dA
            endAngle = startAngle + dA

            for offsetIndex in range(histogram.shape[1]):
                count = float(histogram[azimuthIndex, offsetIndex])
                if count <= 0.0:
                    continue

                innerRadius = offsetIndex * dO
                outerRadius = innerRadius + dO
                if count <= lowLevel:
                    normalized = 0.0
                elif count >= highLevel:
                    normalized = 1.0
                else:
                    normalized = (count - lowLevel) / (highLevel - lowLevel)
                color = colorMapObj.map(normalized, mode='qcolor')

                sector = QGraphicsPathItem(self.createOffAziSectorPath(innerRadius, outerRadius, startAngle, endAngle))
                sector.setBrush(QBrush(color))
                sector.setPen(QPen(color))
                self.offAziWidget.plotItem.addItem(sector)
                self.offAziPolarItems.append(sector)

        pad = 1.05 * oMax
        self.offAziWidget.plotItem.setXRange(-pad, pad, padding=0.0)
        self.offAziWidget.plotItem.setYRange(-pad, pad, padding=0.0)
        self.updateOffAziColorBar(colorMapObj, lowLevel, highLevel)

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
        surveyCopy = self.survey.deepcopy()

        # create valid pattern list, before using it in property panel
        self.updatePatternList(surveyCopy)

        # brush color for main parameter categories
        brush = '#add8e6'

        surveyParams = [
            dict(brush=brush, name='Survey configuration', type='myConfiguration', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey analysis', type='myAnalysis', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey reflectors', type='myReflectors', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey grid', type='myGrid', value=surveyCopy.grid, default=surveyCopy.grid),
            dict(brush=brush, name='Block list', type='myBlockList', value=surveyCopy.blockList, default=surveyCopy.blockList, directory=self.projectDirectory, survey=surveyCopy),
            dict(brush=brush, name='Pattern list', type='myPatternList', value=surveyCopy.patternList, default=surveyCopy.patternList, survey=surveyCopy),
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
        surveyCopy = RollSurvey()

        CFG = self.parameters.child('Survey configuration')

        surveyCopy.crs, surType, surveyCopy.name = CFG.value()                              # get tuple of data from parameter
        surveyCopy.type = SurveyType[surType]                                        # SurveyType is an enum

        ANA = self.parameters.child('Survey analysis')
        surveyCopy.output.rctOutput, surveyCopy.angles, surveyCopy.binning, surveyCopy.offset, surveyCopy.unique = ANA.value()

        REF = self.parameters.child('Survey reflectors')
        surveyCopy.globalPlane, surveyCopy.globalSphere = REF.value()

        GRD = self.parameters.child('Survey grid')
        surveyCopy.grid = GRD.value()

        BLK = self.parameters.child('Block list')
        surveyCopy.blockList = BLK.value()

        PAT = self.parameters.child('Pattern list')
        surveyCopy.patternList = PAT.value()

        surveyCopy.bindSeedsToSurvey()

        # first check survey integrity before committing to it.
        if surveyCopy.checkIntegrity() is False:
            return

        self.survey = surveyCopy.deepcopy()                                           # start using the updated survey object

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
            self.x0lineStk = None                                               # numpy array with x_line Kr stack reponse
            self.xyCellStk = None                                               # numpy array with cell's KxKy stack response
            self.xyPatResp = None                                               # numpy array with pattern's KxKy response
            self.plotRedrawHelper.reset()

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

        w.scene().sigMouseMoved.connect(lambda pos, plotWidget=w: self.mouseMovedInPlot(plotWidget, pos))
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
        self._applyConfiguredPointFilter('rps_duplicates', 'rpsImport', self.rpsModel, ('rpsLiveE', 'rpsLiveN', 'rpsDeadE', 'rpsDeadN'), boundAttr='rpsBound')

    def removeSpsDuplicates(self):
        self._applyConfiguredPointFilter('sps_duplicates', 'spsImport', self.spsModel, ('spsLiveE', 'spsLiveN', 'spsDeadE', 'spsDeadN'), boundAttr='spsBound')

    def removeRpsOrphans(self):
        self._applyConfiguredPointFilter('rps_orphans', 'rpsImport', self.rpsModel, ('rpsLiveE', 'rpsLiveN', 'rpsDeadE', 'rpsDeadN'), boundAttr='rpsBound')

    def removeSpsOrphans(self):
        self._applyConfiguredPointFilter('sps_orphans', 'spsImport', self.spsModel, ('spsLiveE', 'spsLiveN', 'spsDeadE', 'spsDeadN'), boundAttr='spsBound')

    def removeXpsDuplicates(self):
        self._applyConfiguredRelationFilter('xps_duplicates', 'xpsImport', self.xpsModel)

    def removeXpsSpsOrphans(self):
        self._applyConfiguredRelationFilter('xps_sps_orphans', 'xpsImport', self.xpsModel)

    def removeXpsRpsOrphans(self):
        self._applyConfiguredRelationFilter('xps_rps_orphans', 'xpsImport', self.xpsModel)

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
        self._applyConfiguredPointFilter('rec_duplicates', 'recGeom', self.recModel, ('recLiveE', 'recLiveN', 'recDeadE', 'recDeadN'))

    def removeSrcDuplicates(self):
        self._applyConfiguredPointFilter('src_duplicates', 'srcGeom', self.srcModel, ('srcLiveE', 'srcLiveN', 'srcDeadE', 'srcDeadN'))

    def removeRecOrphans(self):
        self._applyConfiguredPointFilter('rec_orphans', 'recGeom', self.recModel, ('recLiveE', 'recLiveN', 'recDeadE', 'recDeadN'))

    def removeSrcOrphans(self):
        self._applyConfiguredPointFilter('src_orphans', 'srcGeom', self.srcModel, ('srcLiveE', 'srcLiveN', 'srcDeadE', 'srcDeadN'))

    def removeRelDuplicates(self):
        self._applyConfiguredRelationFilter('rel_duplicates', 'relGeom', self.relModel)

    def removeRelSrcOrphans(self):
        self._applyConfiguredRelationFilter('rel_src_orphans', 'relGeom', self.relModel)

    def removeRelRecOrphans(self):
        self._applyConfiguredRelationFilter('rel_rec_orphans', 'relGeom', self.relModel)

    def _applyConfiguredPointFilter(self, filterKey, arrayAttr, model, liveDeadAttrs, boundAttr=None):
        del liveDeadAttrs, boundAttr
        array = getattr(self, arrayAttr)
        result = self.filterService.applyFilter(filterKey, array)
        if result is None:
            return

        self.sessionService.setArray(self.sessionState, arrayAttr, result.array)
        model.setData(result.array)

        if result.refreshLayout:
            self.updateMenuStatus(False)
            self.plotLayout()

        self.appendLogMessage(result.message)

    def _applyConfiguredRelationFilter(self, filterKey, arrayAttr, model):
        array = getattr(self, arrayAttr)
        result = self.filterService.applyFilter(filterKey, array)
        if result is None:
            return

        self.sessionService.setArray(self.sessionState, arrayAttr, result.array)
        model.setData(result.array)
        self.appendLogMessage(result.message)

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
            self.spsLayer = exportPointLayerToQgis(layerName, self.spsImport, self.survey.crs, source=True, spsParallel=self.appSettings.spsParallel)

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
            self.srcLayer = exportPointLayerToQgis(layerName, self.srcGeom, self.survey.crs, source=True, spsParallel=self.appSettings.spsParallel)

    def importSpsFromQgis(self):
        self.spsLayer, self.spsField = identifyQgisPointLayer(self.spsLayer, self.spsField, self.survey.crs, 'Sps')

        if self.spsLayer is None:
            return

        with pg.BusyCursor():
            self.spsImport = readQgisPointLayer(self.spsLayer.id(), self.spsField)
            if self.spsImport is not None:
                convertCrs(self.spsImport, self.spsLayer.crs(), self.survey.crs)

        if self.spsImport is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.sessionService.refreshArrayState(self.sessionState, 'spsImport')

        self.appendLogMessage(f'Import : SPS-records containing {self.spsLiveE.size:,} live records')
        self.appendLogMessage(f'Import : SPS-records containing {self.spsDeadE.size:,} dead records')

        self.spsModel.setData(self.spsImport)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importRpsFromQgis(self):
        self.rpsLayer, self.rpsField = identifyQgisPointLayer(self.rpsLayer, self.rpsField, self.survey.crs, 'Rps')

        if self.rpsLayer is None:
            return

        with pg.BusyCursor():
            self.rpsImport = readQgisPointLayer(self.rpsLayer.id(), self.rpsField)
            if self.rpsImport is not None:
                convertCrs(self.rpsImport, self.rpsLayer.crs(), self.survey.crs)

        if self.rpsImport is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.sessionService.refreshArrayState(self.sessionState, 'rpsImport')

        self.appendLogMessage(f'Import : RPS-records containing {self.rpsLiveE.size:,} live records')
        self.appendLogMessage(f'Import : RPS-records containing {self.rpsDeadE.size:,} dead records')

        self.rpsModel.setData(self.rpsImport)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importSrcFromQgis(self):
        self.srcLayer, self.srcField = identifyQgisPointLayer(self.srcLayer, self.srcField, self.survey.crs, 'Src')

        if self.srcLayer is None:
            return

        with pg.BusyCursor():
            self.srcGeom = readQgisPointLayer(self.srcLayer.id(), self.srcField)
            if self.srcGeom is not None:
                convertCrs(self.srcGeom, self.srcLayer.crs(), self.survey.crs)

        if self.srcGeom is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.sessionService.refreshArrayState(self.sessionState, 'srcGeom')

        self.appendLogMessage(f'Import : SRC-records containing {self.srcLiveE.size:,} live records')
        self.appendLogMessage(f'Import : SRC-records containing {self.srcDeadE.size:,} dead records')

        self.srcModel.setData(self.srcGeom)
        self.textEdit.document().setModified(True)                              # set modified flag; so we'll save src data as numpy arrays upon saving the file
        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure
        self.plotLayout()

    def importRecFromQgis(self):
        self.recLayer, self.recField = identifyQgisPointLayer(self.recLayer, self.recField, self.survey.crs, 'Rec')

        if self.recLayer is None:
            return

        with pg.BusyCursor():
            self.recGeom = readQgisPointLayer(self.recLayer.id(), self.recField)
            if self.recGeom is not None:
                convertCrs(self.recGeom, self.recLayer.crs(), self.survey.crs)

        if self.recGeom is None:
            QMessageBox.information(None, 'No features found', 'No valid features found in QGIS point layer', QMessageBox.StandardButton.Cancel)
            return

        self.sessionService.refreshArrayState(self.sessionState, 'recGeom')

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

        colorMap = self.resolveColorMapName(self.appSettings.foldDispCmap, fallback='CET-L4')  # default fold & offset color map
        if self.imageType == 0:                                                 # now deal with all image types
            self.layoutImg = None                                               # no image to show
            label = 'N/A'
            self.layoutMax = 10
            colorMap = self.resolveColorMapName(config.inActiveCmap, fallback='CET-L1')  # grey color map
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

        self.prepareLayoutImageAndColorBar(
            self.layoutImg,
            colorMap,
            label,
            levels=(0.0, self.layoutMax),
            limits=(0, None),
            rounding=10.0,
        )

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
            # tracebackString = "\n".join(traceback.extract_tb(eTraceback).format())

            tracebackString = ''
            # for fileName, line_number, func_name, text in traceback.extract_tb(eTraceback, limit=2)[1:]:
            for fileName, line_number, func_name, _ in traceback.extract_tb(eTraceback, limit=2):
                fileName = os.path.basename(fileName)
                tracebackString += f' File "{fileName}", line {line_number}, in function "{func_name}".'

            if tracebackString != '':
                tracebackString = f'Traceback: {tracebackString}'

            exceptionMsg = f'Error&nbsp;&nbsp;:&nbsp;{eType.__name__}: {eValue} {tracebackString}'
            self.appendLogMessage(exceptionMsg, MsgType.Exception)

    def cursorPositionChanged(self):
        line = self.textEdit.textCursor().blockNumber() + 1
        col = self.textEdit.textCursor().columnNumber() + 1
        self.posWidgetStatusbar.setText(f'Line: {line} Col: {col}')

    def _formatSampledImageValue(self, imageItem, pos, label='value'):
        if imageItem is None or getattr(imageItem, 'image', None) is None or imageItem.scene() is None:
            return None

        if not imageItem.sceneBoundingRect().contains(pos):
            return None

        imagePoint = imageItem.mapFromScene(pos)
        ix = int(imagePoint.x())
        iy = int(imagePoint.y())
        imageData = imageItem.image

        if ix < 0 or iy < 0 or ix >= imageData.shape[0] or iy >= imageData.shape[1]:
            return None

        value = float(imageData[ix, iy])
        if np.isnan(value):
            return f'{label}: no data'

        return f'{label}: {value:,.3f}'

    def _formatOffAziPolarValue(self, mousePoint):
        if self.offAziImItem is None or getattr(self.offAziImItem, 'image', None) is None:
            return None

        dA = getattr(self, 'offAziDisplayDA', None)
        dO = getattr(self, 'offAziDisplayDO', None)
        oMax = getattr(self, 'offAziDisplayOMax', None)
        if dA is None or dO is None or oMax is None:
            return None

        radius = float(np.hypot(mousePoint.x(), mousePoint.y()))
        if radius < 0.0 or radius >= float(oMax):
            return None

        angle = float(np.degrees(np.arctan2(mousePoint.y(), mousePoint.x())))
        if angle < 0.0:
            angle += 360.0

        azimuthIndex = int(angle / dA)
        offsetIndex = int(radius / dO)
        imageData = self.offAziImItem.image

        if azimuthIndex < 0 or offsetIndex < 0 or azimuthIndex >= imageData.shape[0] or offsetIndex >= imageData.shape[1]:
            return None

        value = float(imageData[azimuthIndex, offsetIndex])
        if np.isnan(value):
            return 'value: no data'

        return f'value: {value:,.3f}'

    def _formatPlotImageValue(self, plotWidget, pos, mousePoint):
        if plotWidget == self.stkTrkWidget:
            return self._formatSampledImageValue(self.stkTrkImItem, pos)
        if plotWidget == self.stkBinWidget:
            return self._formatSampledImageValue(self.stkBinImItem, pos)
        if plotWidget == self.stkCelWidget:
            return self._formatSampledImageValue(self.stkCelImItem, pos)
        if plotWidget == self.arraysWidget:
            return self._formatSampledImageValue(self.kxyPatImItem, pos)
        if plotWidget == self.offAziWidget:
            if getattr(self, 'offAziDisplayPolar', False):
                return self._formatOffAziPolarValue(mousePoint)
            return self._formatSampledImageValue(self.offAziImItem, pos)
        return None

    def _setGenericPlotMouseStatus(self, plotWidget, pos, mousePoint):
        valueText = self._formatPlotImageValue(plotWidget, pos, mousePoint)
        coordinateText = f'x={mousePoint.x():,.2f}, y={mousePoint.y():,.2f}'
        if valueText is None:
            self.posWidgetStatusbar.setText(coordinateText)
        else:
            self.posWidgetStatusbar.setText(f'{valueText}, {coordinateText}')

    def _setLayoutMouseStatus(self, mousePoint):
        if self.survey is None or self.survey.glbTransform is None:
            return

        if self.glob:                                                           # plot is using global coordinates
            toLocTransform, _ = self.survey.glbTransform.inverted()
            globalPoint = mousePoint
            localPoint = toLocTransform.map(globalPoint)
        else:                                                                   # plot is using local coordinates
            localPoint = mousePoint
            globalPoint = self.survey.glbTransform.map(localPoint)

        lx = localPoint.x()
        ly = localPoint.y()
        gx = globalPoint.x()
        gy = globalPoint.y()

        if self.survey.binning.method == BinningType.cmp:                       # calculate reflector depth at cursor
            gz = 0.0
            lz = 0.0
        elif self.survey.binning.method == BinningType.plane:
            gz = self.survey.globalPlane.depthAt(globalPoint)                   # get global depth from defined plane
            lz = self.survey.localPlane.depthAt(localPoint)                     # get local depth from transformed plane
        elif self.survey.binning.method == BinningType.sphere:
            gz = self.survey.globalSphere.depthAt(globalPoint)                  # get global depth from defined sphere
            lz = self.survey.localSphere.depthAt(localPoint)                    # get local depth from transformed sphere
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
                fold = int(foldValue)                                           # fold value is float because of the NaN values for no-data bins. Integers don't understand NaN
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

    def mouseMovedInPlot(self, plotWidget, pos):                                # See: https://stackoverflow.com/questions/46166205/display-coordinates-in-pyqtgraph
        viewBox = plotWidget.plotItem.vb
        if not viewBox.sceneBoundingRect().contains(pos):
            return

        mousePoint = viewBox.mapSceneToView(pos)                                # get scene coordinates
        if plotWidget == self.layoutWidget:
            self._setLayoutMouseStatus(mousePoint)
        else:
            self._setGenericPlotMouseStatus(plotWidget, pos, mousePoint)

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

    def getStackResponseRedrawContext(self):
        if self.output.anaOutput is None or self.survey is None or self.survey.binTransform is None:
            return None

        xAnaSize = self.output.anaOutput.shape[0]
        yAnaSize = self.output.anaOutput.shape[1]
        if xAnaSize == 0 or yAnaSize == 0:
            return None

        if self.spiderPoint == QPoint(-1, -1):
            self.spiderPoint = QPoint(xAnaSize // 2, yAnaSize // 2)

        if self.spiderPoint.x() < 0:
            self.spiderPoint.setX(0)

        if self.spiderPoint.y() < 0:
            self.spiderPoint.setY(0)

        if self.spiderPoint.x() >= xAnaSize:
            self.spiderPoint.setX(xAnaSize - 1)

        if self.spiderPoint.y() >= yAnaSize:
            self.spiderPoint.setY(yAnaSize - 1)

        nX = self.spiderPoint.x()
        nY = self.spiderPoint.y()

        invBinTransform, _ = self.survey.binTransform.inverted()
        cmpX, cmpY = invBinTransform.map(nX, nY)
        stkX, stkY = self.survey.st2Transform.map(cmpX, cmpY)

        return {
            'nX': nX,
            'nY': nY,
            'stkX': stkX,
            'stkY': stkY,
            'x0': self.survey.output.rctOutput.left(),
            'y0': self.survey.output.rctOutput.top(),
            'dx': self.survey.grid.binSize.x(),
            'dy': self.survey.grid.binSize.y(),
        }

    def redrawStackResponse(self, surface: str, context) -> None:
        if surface == 'stack-inline':
            self.plotStkTrk(context['nY'], context['stkY'], context['x0'], context['dx'])
            return

        if surface == 'stack-xline':
            self.plotStkBin(context['nX'], context['stkX'], context['y0'], context['dy'])
            return

        if surface == 'stack-cell':
            self.plotStkCel(context['nX'], context['nY'], context['stkX'], context['stkY'])
            return

        raise NotImplementedError(f'unsupported stack-response surface: {surface}')

    @staticmethod
    def shouldRedrawStackResponse(surface: str, direction: Direction) -> bool:
        if direction == Direction.NA:
            return True

        if surface == 'stack-inline':
            return direction in (Direction.Up, Direction.Dn)

        if surface == 'stack-xline':
            return direction in (Direction.Lt, Direction.Rt)

        if surface == 'stack-cell':
            return direction in (Direction.Up, Direction.Dn, Direction.Lt, Direction.Rt)

        raise NotImplementedError(f'unsupported stack-response surface: {surface}')

    def dispatchAnalysisRedraw(
        self,
        surface: str,
        reason: AnalysisRedrawReason = AnalysisRedrawReason.controller,
        direction: Direction = Direction.NA,
    ) -> None:
        self.plotRedrawHelper.applySurfaceInvalidation(self, surface, reason)

        if surface == 'patterns':
            self.plotPatterns()
            return

        if surface == 'off-azi':
            self.redrawOffAzi()
            return

        if surface == 'offset':
            self.redrawOffset()
            return

        if surface not in ('stack-inline', 'stack-xline', 'stack-cell'):
            raise NotImplementedError(f'unsupported analysis redraw surface: {surface}')

        if not self.shouldRedrawStackResponse(surface, direction):
            return

        context = self.getStackResponseRedrawContext()
        if context is None:
            return

        self.redrawStackResponse(surface, context)

    def updateVisiblePlotWidget(self, index: int, direction: Direction = Direction.NA) -> None:
        if index == 0:
            self.plotLayout()                                                   # no conditions to plot main layout plot
            return

        if index == 10:                                                         # no condition to plot patterns either
            self.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.visiblePlotActivated)
            return

        if self.output.anaOutput is None:                                       # we need self.output.anaOutput to display meaningful ANALYSIS information
            return

        if index == 5:
            self.dispatchAnalysisRedraw('stack-inline', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 6:
            self.dispatchAnalysisRedraw('stack-xline', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 7:
            self.dispatchAnalysisRedraw('stack-cell', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 8:
            self.dispatchAnalysisRedraw('offset', AnalysisRedrawReason.visiblePlotActivated)
            return

        if index == 9:
            self.dispatchAnalysisRedraw('off-azi', AnalysisRedrawReason.visiblePlotActivated)
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

        self.handleSpiderPlot()                                                 # spider label should move depending on local/global coords
        self.layoutWidget.autoRange()                                           # show the full range of objects when changing local vs global coordinates
        self.plotLayout()

    def showRuler(self, checked):
        self.ruler = checked
        self.plotLayout()

    def updateAllViews(self):                                                   # re-parse the text in the textEdit, update the survey object, and replot the layout
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
                binRect.setPen(self.appSettings.binAreaPen)
                binRect.setBrush(QBrush(QColor(self.appSettings.binAreaColor)))
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
                symbol=self.appSettings.spsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=self.appSettings.spsSymbolSize,
                symbolBrush=QColor(self.appSettings.spsBrushColor),
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
                symbol=self.appSettings.spsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=self.appSettings.spsSymbolSize,
                symbolBrush=QColor(self.appSettings.spsBrushColor),
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
                symbol=self.appSettings.rpsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=self.appSettings.rpsSymbolSize,
                symbolBrush=QColor(self.appSettings.rpsBrushColor),
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
                symbol=self.appSettings.rpsPointSymbol,
                symbolPen=pg.mkPen('k'),
                symbolSize=self.appSettings.rpsSymbolSize,
                symbolBrush=QColor(self.appSettings.rpsBrushColor),
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
                symbol=self.appSettings.srcPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=self.appSettings.srcSymbolSize,
                symbolBrush=QColor(self.appSettings.srcBrushColor),
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
                symbol=self.appSettings.srcPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=self.appSettings.srcSymbolSize,
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
                symbol=self.appSettings.recPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=self.appSettings.recSymbolSize,
                symbolBrush=QColor(self.appSettings.recBrushColor),
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
                symbol=self.appSettings.recPointSymbol,
                symbolPen=pg.mkPen('#bdbdbd'),
                symbolSize=self.appSettings.recSymbolSize,
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
            sphereArea.setBrush(QBrush(QColor(self.appSettings.binAreaColor)))  # use same color as binning region
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
            component = self.getSelectedOffsetComponent('OffTrkComponentActionGroup')

            slice3D = self.output.anaOutput[:, nY, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = fnb.numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            self.offTrkWidget.plotItem.clear()
            self.offTrkWidget.setTitle(plotTitle, color='b', size='16pt')
            self.updateOffsetPlotComponentLabel(self.offTrkWidget, component)
            if slice2D.shape[0] == 0:                                           # empty array
                return

            x, y = fnb.numbaOffInline(slice2D, ox, component)
            self.offTrkWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotOffBin(self, nX: int, stkX: int, oy: float):
        with pg.BusyCursor():
            self.offBinWidget.plotItem.clear()
            component = self.getSelectedOffsetComponent('OffBinComponentActionGroup')

            slice3D = self.output.anaOutput[nX, :, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = fnb.numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[2]} [stake={stkX}]'
            self.offBinWidget.setTitle(plotTitle, color='b', size='16pt')
            self.updateOffsetPlotComponentLabel(self.offBinWidget, component)

            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = fnb.numbaOffXline(slice2D, oy, component)
            self.offBinWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotAziTrk(self, nY: int, stkY: int, ox: float):
        with pg.BusyCursor():
            self.aziTrkWidget.plotItem.clear()

            slice3D = self.output.anaOutput[:, nY, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = fnb.numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[3]} [line={stkY}]'
            self.aziTrkWidget.setTitle(plotTitle, color='b', size='16pt')

            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = fnb.numbaAziInline(slice2D, ox)
            self.aziTrkWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def plotAziBin(self, nX: int, stkX: int, oy: float):
        with pg.BusyCursor():
            self.aziBinWidget.plotItem.clear()

            slice3D = self.output.anaOutput[nX, :, :, :]
            slice2D = slice3D.reshape(slice3D.shape[0] * slice3D.shape[1], slice3D.shape[2])           # convert to 2D
            slice2D = fnb.numbaFilterSlice2D(slice2D, self.survey.unique.apply)

            plotTitle = f'{self.plotTitles[4]} [stake={stkX}]'
            self.aziBinWidget.setTitle(plotTitle, color='b', size='16pt')
            if slice2D.shape[0] == 0:                                           # empty array; nothing to see here...
                return

            x, y = fnb.numbaAziXline(slice2D, oy)
            self.aziBinWidget.plot(x=x, y=y, connect='pairs', pen=pg.mkPen('k', width=2))

    def createAnalysisImageItem(self, imageData, x0: float, y0: float, dx: float, dy: float, levels=(-50.0, 0.0)):
        tr = QTransform()
        tr.translate(x0, y0)
        tr.scale(dx, dy)

        imageItem = pg.ImageItem()
        imageItem.setImage(imageData, levels=levels)
        imageItem.setTransform(tr)
        return imageItem

    def prepareAnalysisImageAndColorBar(
        self,
        plotWidget,
        imageData,
        x0: float,
        y0: float,
        dx: float,
        dy: float,
        imageAttr: str,
        colorBarAttr: str,
        levels=(-50.0, 0.0),
        label='dB attenuation',
        limits=(-100.0, 0.0),
        rounding=10.0,
    ):
        imageItem = self.createAnalysisImageItem(imageData, x0, y0, dx, dy, levels=levels)

        plotWidget.plotItem.clear()
        plotWidget.plotItem.addItem(imageItem)
        setattr(self, imageAttr, imageItem)

        colorMapObj = self.resolveColorMapObject(self.appSettings.analysisCmap, fallback='viridis')
        colorBar = getattr(self, colorBarAttr, None)

        if colorBar is None:
            try:
                colorBar = plotWidget.plotItem.addColorBar(
                    imageItem,
                    colorMap=colorMapObj,
                    label=label,
                    limits=limits,
                    rounding=rounding,
                    values=levels,
                )
                colorBar.setLevels(low=levels[0], high=levels[1])
            except TypeError as exc:
                self.appendLogMessage(f'Colorbar init failed: {exc}', MsgType.Error)
                colorBar = None
        else:
            try:
                colorBar.setImageItem(imageItem)
                colorBar.setLevels(low=levels[0], high=levels[1])
                colorBar.setColorMap(colorMapObj)
            except TypeError as exc:
                self.appendLogMessage(f'Colorbar setColorMap failed: {exc}', MsgType.Error)

        setattr(self, colorBarAttr, colorBar)
        return imageItem

    def prepareLayoutImageAndColorBar(
        self,
        imageData,
        colorMap,
        label,
        levels=(0.0, 10.0),
        limits=(0, None),
        rounding=10.0,
    ):
        imageItem = pg.ImageItem()
        imageItem.setImage(imageData, levels=levels)
        self.layoutImItem = imageItem

        colorMap = self.coerceColorMap(colorMap, fallback='CET-L1')
        if not isinstance(colorMap, (str, pg.ColorMap)):
            self.appendLogMessage(
                f'Invalid colorMap type {type(colorMap)} value {colorMap!r};',
                MsgType.Debug,
            )
            self.appendLogMessage(f'available maps={len(pg.colormap.listMaps())}', MsgType.Debug)
        elif isinstance(colorMap, str):
            colorMap = str(colorMap)

        colorMapObj = self.resolveColorMapObject(colorMap, fallback='viridis')

        if self.layoutColorBar is None:
            try:
                self.layoutColorBar = self.layoutWidget.plotItem.addColorBar(
                    self.layoutImItem,
                    colorMap=colorMapObj,
                    label='N/A',
                    limits=limits,
                    rounding=rounding,
                    values=levels,
                )
            except TypeError as exc:
                self.appendLogMessage(f'Colorbar init failed: {exc}', MsgType.Error)
                self.layoutColorBar = None

        if self.layoutColorBar is not None:
            self.layoutColorBar.setImageItem(self.layoutImItem)
            self.layoutColorBar.setLevels(low=levels[0], high=levels[1])
            try:
                self.layoutColorBar.setColorMap(colorMapObj)
            except TypeError as exc:
                self.appendLogMessage(f'Colorbar setColorMap failed: {exc}', MsgType.Error)
            self.setColorbarLabel(label)

        return imageItem

    def plotStkTrk(self, nY: int, stkY: int, x0: float, dx: float):
        with pg.BusyCursor():
            kMax, dK, kStart, kDelta = self.plotRedrawHelper.buildInlineStackAxisValues(self)

            responseKey = self.plotRedrawHelper.buildInlineResponseKey(nY)
            if not self.plotRedrawHelper.canReuseInlineResponse(self, responseKey):
                slice3D, I = fnb.numbaSlice3D(self.output.anaOutput[:, nY, :, :], self.survey.unique.apply)
                if slice3D.shape[0] == 0:                                       # empty array; nothing to see here...
                    return

                self.inlineStk = fnb.numbaNdft1D(kMax, dK, slice3D, I)
                self.plotRedrawHelper.storeInlineResponseKey(responseKey)

            self.prepareAnalysisImageAndColorBar(
                self.stkTrkWidget,
                self.inlineStk,
                x0,
                kStart,
                dx,
                kDelta,
                'stkTrkImItem',
                'stkTrkColorBar',
            )

            plotTitle = f'{self.plotTitles[5]} [line={stkY}]'
            self.stkTrkWidget.setTitle(plotTitle, color='b', size='16pt')

    def plotStkBin(self, nX: int, stkX: int, y0: float, dy: float):
        with pg.BusyCursor():
            kMax, dK, kStart, kDelta = self.plotRedrawHelper.buildXlineStackAxisValues(self)

            responseKey = self.plotRedrawHelper.buildXlineResponseKey(nX)
            if not self.plotRedrawHelper.canReuseXlineResponse(self, responseKey):
                slice3D, I = fnb.numbaSlice3D(self.output.anaOutput[nX, :, :, :], self.survey.unique.apply)
                if slice3D.shape[0] == 0:                                       # empty array; nothing to see here...
                    return

                self.x0lineStk = fnb.numbaNdft1D(kMax, dK, slice3D, I)
                self.plotRedrawHelper.storeXlineResponseKey(responseKey)

            self.prepareAnalysisImageAndColorBar(
                self.stkBinWidget,
                self.x0lineStk,
                y0,
                kStart,
                dy,
                kDelta,
                'stkBinImItem',
                'stkBinColorBar',
            )

            plotTitle = f'{self.plotTitles[6]} [stake={stkX}]'
            self.stkBinWidget.setTitle(plotTitle, color='b', size='16pt')

    def getSelectedStackCellPatterns(self):
        if not self.tbStackPatterns.isChecked():
            return (None, None)

        maxPatterns = len(self.survey.patternList)
        patternIndex3 = self.pattern3.currentIndex() - 1
        patternIndex4 = self.pattern4.currentIndex() - 1

        pattern3 = self.survey.patternList[patternIndex3] if 0 <= patternIndex3 < maxPatterns else None
        pattern4 = self.survey.patternList[patternIndex4] if 0 <= patternIndex4 < maxPatterns else None

        return (pattern3, pattern4)

    def computeStackCellResponse(self, nX: int, nY: int, pattern3=None, pattern4=None):
        kMin = 0.001 * self.appSettings.kxyStack.x()
        kMax = 0.001 * self.appSettings.kxyStack.y()
        dK = 0.001 * self.appSettings.kxyStack.z()
        kMax = kMax + dK

        kStart = 1000.0 * (kMin - 0.5 * dK)
        kDelta = 1000.0 * dK

        offsetX, offsetY, noData = fnb.numbaOffsetBin(self.output.anaOutput[nX, nY, :, :], self.survey.unique.apply)
        fold = 0 if noData else offsetX.shape[0]

        if noData or offsetX.size == 0:
            kX = np.arange(kMin, kMax, dK)
            responseSize = kX.shape[0]
            response = np.ones(shape=(responseSize, responseSize), dtype=np.float32) * -50.0
        else:
            response = fnb.numbaNdft2D(kMin, kMax, dK, offsetX, offsetY)

        for pattern in (pattern3, pattern4):
            if pattern is None:
                continue
            xPattern, yPattern = pattern.calcPatternPointArrays()
            response = response + fnb.numbaNdft2D(kMin, kMax, dK, xPattern, yPattern)

        return response, kStart, kDelta, fold

    def plotStkCel(self, nX: int, nY: int, stkX: int, stkY: int):
        if self.output.anaOutput is None or self.output.anaOutput.shape[0] == 0 or self.output.anaOutput.shape[1] == 0:
            return

        with pg.BusyCursor():
            pattern3, pattern4 = self.getSelectedStackCellPatterns()
            responseKey = self.plotRedrawHelper.buildStackCellResponseKey(self, nX, nY)
            if not self.plotRedrawHelper.canReuseStackCellResponse(self, responseKey):
                self.xyCellStk, kStart, kDelta, fold = self.computeStackCellResponse(nX, nY, pattern3, pattern4)
                self.plotRedrawHelper.storeStackCellResponse(responseKey, fold)
            else:
                kStart, kDelta, fold = self.plotRedrawHelper.buildStackCellCachedAxisValues(self)

            self.prepareAnalysisImageAndColorBar(
                self.stkCelWidget,
                self.xyCellStk,
                kStart,
                kStart,
                kDelta,
                kDelta,
                'stkCelImItem',
                'stkCelColorBar',
            )

            plotTitle = f'{self.plotTitles[7]} [stake={stkX}, line={stkY}, fold={fold}]'
            self.stkCelWidget.setTitle(plotTitle, color='b', size='16pt')

    def prepareOffsetHistogramInputs(self):
        dO = 50.0                                                               # offsets increments
        oMax = ceil(self.output.maxMaxOffset / dO) * dO + dO                    # max y-scale; make sure end value is included
        oR = np.arange(0, oMax, dO)                                             # numpy array with values [0 ... oMax]

        if self.output.offstHist is None:
            offsets, _, noData = fnb.numbaSliceStats(self.output.anaOutput, self.survey.unique.apply)
            if noData:
                return None

            y, x = np.histogram(offsets, bins=oR)                               # create a histogram with 100m offset increments

            y1 = np.append(y, 0)                                                # add a dummy value to make x- and y-arrays equal size
            self.output.offstHist = np.stack((x, y1))                           # See: https://numpy.org/doc/stable/reference/generated/numpy.stack.html#numpy.stack

        return {
            'histogram': self.output.offstHist,
            'count': np.sum(self.output.binOutput),
        }

    def prepareOffsetPlotInputs(self, histogramInputs=None):
        if histogramInputs is None:
            histogramInputs = self.prepareOffsetHistogramInputs()

        if histogramInputs is None:
            return None

        histogram = histogramInputs['histogram']
        return {
            'xValues': histogram[0, :],
            'yValues': histogram[1, :-1],
            'plotTitle': f"{self.plotTitles[8]} [{histogramInputs['count']:,} traces]",
        }

    def renderPreparedOffsetPlot(self, plotInputs):
        self.offsetWidget.plotItem.clear()
        self.offsetWidget.plot(
            plotInputs['xValues'],
            plotInputs['yValues'],
            stepMode='center',
            fillLevel=0,
            fillOutline=True,
            brush=(0, 0, 255, 150),
            pen=pg.mkPen('k', width=1),
        )

    def redrawOffset(self):
        with pg.BusyCursor():
            plotInputs = self.prepareOffsetPlotInputs()
            if plotInputs is None:
                return

            self.renderPreparedOffsetPlot(plotInputs)
            self.offsetWidget.setTitle(plotInputs['plotTitle'], color='b', size='16pt')

    def plotOffset(self):
        self.redrawOffset()

    def prepareOffAziHistogramInputs(self):
        dA = 5.0                                                                # azimuth increments
        dO = 100.0                                                              # offsets increments

        aMin = 0.0                                                              # min x-scale
        aMax = 360.0                                                            # max x-scale
        aMax += dA                                                              # make sure end value is included

        oMax = ceil(self.output.maxMaxOffset / dO) * dO + dO                    # max y-scale; make sure end value is included

        if self.output.ofAziHist is None:                                       # calculate offset/azimuth distribution
            offsets, azimuth, noData = fnb.numbaSliceStats(self.output.anaOutput, self.survey.unique.apply)
            if noData:
                return None

            aR = np.arange(aMin, aMax, dA)                                      # numpy array with values [0 ... fMax]
            oR = np.arange(0, oMax, dO)                                         # numpy array with values [0 ... oMax]
            self.output.ofAziHist = np.histogram2d(x=azimuth, y=offsets, bins=[aR, oR], range=None, density=None, weights=None)[0]

        return {
            'histogram': self.output.ofAziHist,
            'dA': dA,
            'dO': dO,
            'aMin': aMin,
            'oMax': oMax,
            'count': np.sum(self.output.binOutput),
        }

    def prepareOffAziPlotInputs(self, histogramInputs=None):
        if histogramInputs is None:
            histogramInputs = self.prepareOffAziHistogramInputs()

        if histogramInputs is None:
            return None

        displayScale = 1000.0
        isPolar = self.isOffAziPolarMode()
        modeText = 'polar' if isPolar else 'rectangular'

        return {
            'displayHistogram': histogramInputs['histogram'].astype(np.float32, copy=False) / displayScale,
            'dA': histogramInputs['dA'],
            'dO': histogramInputs['dO'],
            'aMin': histogramInputs['aMin'],
            'oMax': histogramInputs['oMax'],
            'colorMapObj': self.resolveColorMapObject(self.appSettings.analysisCmap, fallback='viridis'),
            'count': histogramInputs['count'],
            'isPolar': isPolar,
            'modeText': modeText,
            'plotTitle': f"{self.plotTitles[9]} [{histogramInputs['count']:,} traces, {modeText}]",
        }

    def renderPreparedOffAziPlot(self, plotInputs):
        if plotInputs['isPolar']:
            self.renderOffAziPolar(plotInputs['displayHistogram'], plotInputs['dA'], plotInputs['dO'], plotInputs['oMax'], plotInputs['colorMapObj'])
        else:
            self.renderOffAziRectangular(plotInputs['displayHistogram'], plotInputs['dA'], plotInputs['dO'], plotInputs['aMin'], plotInputs['colorMapObj'])

    def redrawOffAzi(self):
        with pg.BusyCursor():
            plotInputs = self.prepareOffAziPlotInputs()
            if plotInputs is None:
                return

            self.renderPreparedOffAziPlot(plotInputs)
            self.offAziWidget.setTitle(plotInputs['plotTitle'], color='b', size='16pt')

    def plotOffAzi(self):
        self.redrawOffAzi()

        # For Polar Coordinates, see:
        # See: https://stackoverflow.com/questions/57174173/polar-coordinate-system-in-pyqtgraph
        # See: https://groups.google.com/g/pyqtgraph/c/9Vv1kJdxE6U/m/FuCsSg182jUJ
        # See: https://doc.qt.io/qtforpython-6/PySide6/QtCharts/QPolarChart.html
        # See: https://www.youtube.com/watch?v=DyPjsj6azY4
        # See: https://stackoverflow.com/questions/50720719/how-to-create-a-color-circle-in-pyqt
        # See: https://stackoverflow.com/questions/70471687/pyqt-creating-color-circle

    def getSelectedPatternInputs(self):
        maxPatterns = len(self.survey.patternList)

        patternIndex1 = self.pattern1.currentIndex() - 1
        patternIndex2 = self.pattern2.currentIndex() - 1

        pattern1 = self.survey.patternList[patternIndex1] if 0 <= patternIndex1 < maxPatterns else None
        pattern2 = self.survey.patternList[patternIndex2] if 0 <= patternIndex2 < maxPatterns else None

        text1 = self.pattern1.currentText()
        text2 = self.pattern2.currentText()

        return pattern1, pattern2, text1, text2

    def computeKxyPatternResponse(self, pattern1, pattern2):
        kMin = 0.001 * self.appSettings.kxyArray.x()
        kMax = 0.001 * self.appSettings.kxyArray.y()
        dK = 0.001 * self.appSettings.kxyArray.z()
        kMax = kMax + dK

        kStart = 1000.0 * (kMin - 0.5 * dK)
        kDelta = 1000.0 * dK

        x1 = y1 = x2 = y2 = None

        if pattern1 is not None:
            x1, y1 = pattern1.calcPatternPointArrays()

        if pattern2 is not None:
            x2, y2 = pattern2.calcPatternPointArrays()

        kX = np.arange(kMin, kMax, dK)
        nX = kX.shape[0]

        if (x1 is None or len(x1) == 0) and (x2 is None or len(x2) == 0):
            response = np.ones(shape=(nX, nX), dtype=np.float32) * -50.0
        else:
            response = np.zeros(shape=(nX, nX), dtype=np.float32)

            if pattern1 is not None:
                response = response + fnb.numbaNdft2D(kMin, kMax, dK, x1, y1)

            if pattern2 is not None:
                response = response + fnb.numbaNdft2D(kMin, kMax, dK, x2, y2)

        return response, kStart, kDelta

    def plotPatterns(self):

        self.arraysWidget.plotItem.clear()
        self.arraysWidget.setTitle(self.plotTitles[10], color='b', size='16pt')
        self.arraysWidget.showAxes(True, showValues=(True, False, False, True))   # show values at the left and at the bottom

        styles = {'color': '#000', 'font-size': '10pt'}
        self.arraysWidget.setLabel('top', ' ', **styles)                        # shows axis at the top, no label, no tickmarks
        self.arraysWidget.setLabel('right', ' ', **styles)                      # shows axis at the right, no label, no tickmarks

        pattern1, pattern2, text1, text2 = self.getSelectedPatternInputs()

        if self.patternLayout:                                                  # display the layout
            self.arraysWidget.setLabel('bottom', 'inline', units='m', **styles)   # shows axis at the bottom, and shows the units label
            self.arraysWidget.setLabel('left', 'crossline', units='m', **styles)  # shows axis at the left, and shows the units label

            if pattern1 is not None:
                self.arraysWidget.plotItem.addItem(pattern1)

            if pattern2 is not None:
                self.arraysWidget.plotItem.addItem(pattern2)

        else:                                                                   # calculate kxky pattern response of selected patterns
            self.arraysWidget.setLabel('bottom', 'Kx', units='1/km', **styles)  # shows axis at the bottom, and shows the units label
            self.arraysWidget.setLabel('left', 'Ky', units='1/km', **styles)    # shows axis at the left, and shows the units label

            with pg.BusyCursor():                                               # now do the real work
                responseKey = self.plotRedrawHelper.buildPatternResponseKey(self)
                if not self.plotRedrawHelper.canReusePatternResponse(self, responseKey):
                    self.xyPatResp, kStart, kDelta = self.computeKxyPatternResponse(pattern1, pattern2)
                    self.plotRedrawHelper.storePatternResponseKey(responseKey)
                else:
                    kStart, kDelta = self.plotRedrawHelper.buildPatternAxisValues(self)

                self.prepareAnalysisImageAndColorBar(
                    self.arraysWidget,
                    self.xyPatResp,
                    kStart,
                    kStart,
                    kDelta,
                    kDelta,
                    'kxyPatImItem',
                    'kxyPatColorBar',
                )

        plotTitle = f'{self.plotTitles[10]} [{text1} * {text2}]'
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
                with open(logFile, 'a+', encoding='utf-8') as qFile:             # append (a) information to a logfile, or create a new logfile (a+) if it does not yet exist
                    qFile.write(self.logEdit.toPlainText())                      # get text from logEdit
                    qFile.write('+++\n\n')                                       # closing remarks

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

    def onAppAboutToQuit(self):
        # See: https://doc.qt.io/qt-6/qcoreapplication.html#aboutToQuit
        # intended to shut down quickly in standaloneme mode,
        # without going through the closeEvent (which is not triggered when the main window is closed in standalone mode)
        if self.thread is not None and self.thread.isRunning():
            self.thread.requestInterruption()
            self.thread.quit()
            self.thread.wait(2000)
        self.resetAnaTableModel()
        gc.collect()

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
        self.x0lineStk = None                                                   # numpy array with x_line Kr stack reponse
        self.xyCellStk = None                                                   # numpy array with cell's KxKy stack response
        self.xyPatResp = None                                                   # numpy array with pattern's KxKy response
        self.plotRedrawHelper.reset()

        # layout and analysis image-items
        self.layoutImItem = None                                                # pg ImageItems showing analysis result
        self.stkTrkImItem = None
        self.stkBinImItem = None
        self.stkCelImItem = None
        self.offAziImItem = None
        self.kxyPatImItem = None

        self.sessionService.clearSurveyArrays(self.sessionState)

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
        self._resetOffAziDisplayLevels = True

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
            self.updateAllViews()                                               # parse the textEdit; show the corresponding plot

            self.appendLogMessage(f'Wizard : created land survey: {self.survey.name}')
            self.surveyNumber += 1                                              # update session counter

            return True

        return False

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

            self.updateAllViews()                                               # parse the textEdit; show the corresponding plot

            self.appendLogMessage(f'Wizard : created streamer survey: {self.survey.name}')
            self.surveyNumber += 1                                              # update session counter

            return True

        return False

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

    def commitOpenedFileContext(self, fileName):
        self.documentContextService.commitOpenedFile(self.runtimeState, fileName, config.maxRecentFiles)
        self.textEdit.document().setModified(False)
        self.updateRecentFileActions()
        writeSettings(self)
        self.updateWindowDocumentTitle()

    def commitSavedFileContext(self, fileName):
        self.documentContextService.commitSavedFile(self.runtimeState, fileName, config.maxRecentFiles)
        self.textEdit.document().setModified(False)
        self.updateRecentFileActions()
        writeSettings(self)
        self.updateWindowDocumentTitle()

    def clearCurrentFileContext(self):
        self.documentContextService.clearCurrentFile(self.runtimeState)
        self.textEdit.document().setModified(False)
        self.updateWindowDocumentTitle()

    def updateWindowDocumentTitle(self):
        shownName = self.survey.name if not self.fileName else QFileInfo(self.fileName).fileName()
        self.setWindowTitle(self.tr(f'{shownName}[*] - Roll Survey'))           # update window name, with optional * for modified status
        self.setWindowModified(False)                                           # reset document status

    def setCurrentFileName(self, fileName=''):                                  # update self.fileName, set textEditModified(False) and setWindowModified(False)
        if fileName:
            self.commitSavedFileContext(fileName)
        else:
            self.clearCurrentFileContext()

    def resolveRecentFileName(self, fileName):
        return self.documentContextService.resolveRecentFileName(fileName, self.projectDirectory)

    def updateRecentFileActions(self):                                          # update the MRU file menu actions
        menuState = self.documentContextService.buildRecentFileMenu(self.runtimeState, config.maxRecentFiles)

        if menuState.changed:
            self.recentFileList = menuState.recentFileList
            writeSettings(self)

        numRecentFiles = len(menuState.visibleEntries)

        for i in range(numRecentFiles):
            entry = menuState.visibleEntries[i]
            text = f'&{i + 1} {entry.displayName}'
            self.recentFileActions[i].setText(text)
            self.recentFileActions[i].setData(entry.storedName)
            self.recentFileActions[i].setVisible(True)

        for j in range(numRecentFiles, config.maxRecentFiles):
            self.recentFileActions[j].setVisible(False)

    def setDataAnaTableModel(self):
        if self.output.an2Output is None:
            self.anaModel.setData(None)
            return

        totalRows = self.output.an2Output.shape[0]
        chunkSize = config.maxRowsPerChunk                                     # Default chunk size from config

        if totalRows <= chunkSize:
            # Dataset is small enough to display directly
            self.anaModel.setData(self.output.an2Output)
            self.appendLogMessage(f'Loaded : . . . Analysis: {totalRows:,} traces displayed in Trace Table')
        else:
            # Create a ChunkedData view object that will handle paging
            chunkedData = ChunkedData(self.output.an2Output, chunkSize)
            self.anaModel.setChunkedData(chunkedData)
            self._goToFirstPage()
            self.appendLogMessage(f'Loaded : . . . Analysis: {totalRows:,} traces available (showing {chunkSize:,} at a time)')
        self._updatePageInfo()

    def resetAnaTableModel(self):
        if self.output.anaOutput is not None:                                   # get rid of current memory mapped array first
            self.anaModel.setData(None)                                         # first remove reference to self.output.anaOutput
            self.output.an2Output = None                                        # flattened reference to self.output.anaOutput

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
        if self.survey.type == SurveyType.Streamer:
            self.survey.paintDetails &= ~PaintDetails.recPnt
            self.survey.paintDetails &= ~PaintDetails.recPat

            self.survey.paintDetails &= ~PaintDetails.srcPnt
            self.survey.paintDetails &= ~PaintDetails.srcPat

            self.actionShowBlocks.setChecked(True)
            self.survey.paintMode = PaintMode.justBlocks

    def saveProjectToPath(self, fileName, projectDirectory, commitCurrentPath=False):
        saveResult = self.projectService.writeProjectXml(fileName, self.survey, projectDirectory, self.appSettings.useRelativePaths, 4)
        success = saveResult.success

        if success:
            self.appendLogMessage(f'Saved&nbsp;&nbsp;: {fileName}')

            self.projectService.saveAnalysisSidecars(fileName, self.output, includeHistograms=True)
            self.projectService.saveSurveyDataSidecars(
                fileName,
                rpsImport=self.rpsImport,
                spsImport=self.spsImport,
                xpsImport=self.xpsImport,
                recGeom=self.recGeom,
                relGeom=self.relGeom,
                srcGeom=self.srcGeom,
            )

            if commitCurrentPath:
                self.commitSavedFileContext(fileName)
            else:
                self.textEdit.document().setModified(False)
        else:
            self.appendLogMessage(f'saving : Cannot save file: {fileName}. Error:{saveResult.errorText}', MsgType.Error)
            QMessageBox.information(self, 'Write error', f'Cannot save file:\n{fileName}')

        self.updateMenuStatus(False)                                            # keep menu status in sync with program's state; don't reset analysis figure

        return success

    def fileLoad(self, fileName):
        projectDirectory = os.path.dirname(fileName)                            # retrieve the directory name

        self.sessionService.resetTimers()    ###                                # reset timers for debugging code

        readResult = self.projectService.readProjectText(fileName)
        if not readResult.success:                                              # report status message and return False
            self.removeRecentFile(fileName)
            self.appendLogMessage(f'Open&nbsp;&nbsp;&nbsp;: Cannot open file:{fileName}. Error:{readResult.errorText}', MsgType.Error)
            return False

        self.appendLogMessage(f'Opening: {fileName}')                           # send status message

        self.survey = RollSurvey()                                              # reset the survey object; get rid of all blocks in the list !
        self.runtimeState.projectDirectory = projectDirectory
        self.commitOpenedFileContext(fileName)
        plainText = readResult.plainText

        # Xml tab
        self.appendLogMessage(f'Parsing: {fileName}')                           # send status message
        success = self.parseText(plainText)                                     # parse the string; load the textEdit even if parsing fails !

        self.appendLogMessage(f'Reading: {fileName}, success: {success}', MsgType.Info if success else MsgType.Error)        # send status message

        # in case the xml file was not succesfully parsed, we still load the text into the textEdit, to check its content
        self.textEdit.setPlainText(plainText)                                   # update plainText widget, and reset undo/redo & modified status
        self.resetNumpyArraysAndModels()                                        # empty all arrays and reset plot titles

        if success:                                                             # read the corresponding analysis files
            self._loadProjectSidecarsIntoWindow(fileName)

        self._finalizeLoadedProject()

        # self.appendLogMessage('RollMainWindow.parseText() profiling information', MsgType.Debug)
        # for i in range(0, 20):
        #     t = self.survey.timerTmax[i]                             # perf_counter counts in nano seconds, but returns time in [s]
        #     message = f'Time spent in function call #{i:2d}: {t:11.4f}'
        #     self.appendLogMessage(message, MsgType.Debug)

        # self.appendLogMessage('RollMainWindow.resetSurveyProperties() profiling information', MsgType.Debug)
        # i = 0
        # while i < len(self.sessionService.timerTmin):          # log some debug messages
        #     tMin = self.sessionService.timerTmin[i] if self.sessionService.timerTmin[i] != float('Inf') else 0.0
        #     tMax = self.sessionService.timerTmax[i]
        #     tTot = self.sessionService.timerTtot[i]
        #     freq = self.sessionService.timerFreq[i]
        #     tAvr = tTot / freq if freq > 0 else 0.0
        #     message = f'Index {i:02d}, min {tMin:011.3f}, max {tMax:011.3f}, tot {tTot:011.3f}, avr {tAvr:011.3f}, freq {freq:07d}'
        #     # message = f'{i:02d}: min:{tMin:11.3f}, max:{tMax:11.3f}, tot:{tTot:11.3f}, avr:{tAvr:11.3f}, freq:{freq:7d}'
        #     self.appendLogMessage(message, MsgType.Debug)
        #     i += 1

        return success

    def _loadProjectSidecarsIntoWindow(self, fileName):
        self.appendLogMessage(f'Loading: {fileName} analysis files')            # send status message
        self.setPlottingDetails()                                               # check if it is a marine survey; set seed plotting details accordingly
        sidecarResult = self.projectService.loadProjectSidecars(self.fileName, self.survey)
        self._appendProjectSidecarMessages(sidecarResult)
        self.projectLoadApplier.apply(sidecarResult)
        self.handleImageSelection()                                             # change selection and plot survey

    def _finalizeLoadedProject(self):
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
        self.survey.checkIntegrity()                                            # check for survey integrity after loading; in particular well file validity

    def _appendProjectSidecarMessages(self, sidecarResult):
        for message in sidecarResult.messages:
            msgType = MsgType.Error if message.level == 'error' else MsgType.Info
            self.appendLogMessage(message.text, msgType)

    def fileImportSpsData(self) -> bool:
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

        spsFormat = next((item for item in self.appSettings.spsFormatList if item['name'] == spsDialect), None)
        assert spsFormat is not None, f'No valid SPS dialect with name {spsDialect}'

        xpsFormat = next((item for item in self.appSettings.xpsFormatList if item['name'] == spsDialect), None)
        assert xpsFormat is not None, f'No valid XPS dialect with name {spsDialect}'

        rpsFormat = next((item for item in self.appSettings.rpsFormatList if item['name'] == spsDialect), None)
        assert rpsFormat is not None, f'No valid RPS dialect with name {spsDialect}'

        spsData = dlg.spsTab.toPlainText().splitlines() if dlg.spsFiles else None
        xpsData = dlg.xpsTab.toPlainText().splitlines() if dlg.xpsFiles else None
        rpsData = dlg.rpsTab.toPlainText().splitlines() if dlg.rpsFiles else None

        self.showStatusbarWidgets()
        self.interrupted = False

        with pg.BusyCursor():
            importResult = self.importService.importTextData(
                spsData=spsData,
                xpsData=xpsData,
                rpsData=rpsData,
                spsFormat=spsFormat,
                xpsFormat=xpsFormat,
                rpsFormat=rpsFormat,
                shouldCancel=self._processImportEvents,
                progressCallback=self._updateImportProgress,
            )

        if importResult.cancelled:
            self.appendLogMessage(importResult.cancelMessage)
            self.hideStatusbarWidgets()
            return False

        spsImport = importResult.spsImport
        xpsImport = importResult.xpsImport
        rpsImport = importResult.rpsImport

        self.appendLogMessage(
            f'Import : imported {importResult.spsRead} sps-records, {importResult.xpsRead} xps-records and {importResult.rpsRead} rps-records'
        )

        if any(array is not None for array in (rpsImport, spsImport, xpsImport)):
            self.progressBar.setValue(0)

        with pg.BusyCursor():
            qcResult = self.importService.runQualityChecks(
                rpsImport=rpsImport,
                spsImport=spsImport,
                xpsImport=xpsImport,
                importCrs=dlg.crs,
                surveyCrs=self.survey.crs,
                progressCallback=self._updateImportProgress,
            )

        self.rpsImport = rpsImport
        self.spsImport = spsImport
        self.xpsImport = xpsImport

        if qcResult.showRpsList:
            self.tbRpsList.setChecked(True)
        if qcResult.showSpsList:
            self.tbSpsList.setChecked(True)

        for message in qcResult.messages:
            self.appendLogMessage(message)

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

    def openFileByPath(self, fileName):
        if not fileName:
            return False

        if not (self.maybeKillThread() and self.maybeSave()):
            return False

        return self.fileLoad(fileName)

    def removeRecentFile(self, fileName):
        removed = self.documentContextService.removeRecentFile(self.runtimeState, fileName)

        if removed:
            self.updateRecentFileActions()
            writeSettings(self)

        return removed

    def fileOpenRecent(self):
        action = self.sender()
        if action:
            data = action.data()
            if data is None:
                return
            toString = getattr(data, 'toString', None)
            recentName = toString() if callable(toString) else str(data)
            resolution = self.documentContextService.resolveRecentSelection(self.runtimeState, recentName)

            if not resolution.exists:
                self.removeRecentFile(recentName)
                self.appendLogMessage(f'Open&nbsp;&nbsp;&nbsp;: Recent file no longer exists and was removed from the list: {resolution.resolvedName}', MsgType.Error)
                return

            self.openFileByPath(resolution.resolvedName)

    def fileSave(self):
        if not self.fileName:                                                   # need to have a valid filename first, and set the projectDirectory
            return self.fileSaveAs()

        return self.saveProjectToPath(self.fileName, self.projectDirectory)

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

        projectDirectory = os.path.dirname(fn)
        return self.saveProjectToPath(fn, projectDirectory, commitCurrentPath=True)

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

        if index == MsgType.Debug and not self.appSettings.debug:               # debug message, which needs to be suppressed
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

    def onAbout(self):
        QMessageBox.about(self, 'About Roll', aboutText())

    def onLicense(self):
        QMessageBox.about(self, 'License conditions', licenseText())

    def onHighDpi(self):
        QMessageBox.about(self, 'High DPI UI scaling issues', highDpiText())

    def onQGisCheatSheet(self):
        QMessageBox.about(self, 'QGis Cheat Sheet', qgisCheatSheetText())

    def onQGisRollInterface(self):
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

        self.sessionService.refreshArrayState(self.sessionState, 'spsImport')
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} SPS record(s)')

    def onRpsInUseToggled(self, rows):
        if self.rpsImport is None:
            return

        self.sessionService.refreshArrayState(self.sessionState, 'rpsImport')
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} RPS record(s)')

    def onSrcInUseToggled(self, rows):
        if self.srcGeom is None:
            return

        self.sessionService.refreshArrayState(self.sessionState, 'srcGeom')
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} SRC record(s)')

    def onRecInUseToggled(self, rows):
        if self.recGeom is None:
            return

        self.sessionService.refreshArrayState(self.sessionState, 'recGeom')
        self.textEdit.document().setModified(True)
        self.updateMenuStatus(False)
        self.replotLayout()
        self.appendLogMessage(f'Edit&nbsp;&nbsp;&nbsp;: Modified in-use flag for {len(rows):,} REC record(s)')
