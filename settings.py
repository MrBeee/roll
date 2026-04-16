import importlib
import json
import sys
from ast import literal_eval

import pyqtgraph as pg
from qgis.PyQt.QtCore import QStandardPaths, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QHeaderView,
                                 QVBoxLayout)

try:
    from console import console
except ImportError:
    console = None

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


from . import config  # used to pass initial settings
from .app_settings import AppSettings
from .aux_functions import makeParmsFromPen, makePenFromParms
from .my_range import MyRangeParameter as rng


def _getAppSettings(self):
    appSettings = getattr(self, 'appSettings', None)
    if appSettings is None:
        appSettings = AppSettings()
        self.appSettings = appSettings
        appSettings.activate()
    return appSettings


def _applyNumbaSetting(useNumba):
    if not haveNumba:
        return

    numba.config.DISABLE_JIT = not useNumba                                    # disable/enable numba pre-compilation in @jit decorator. See 'decorators.py' in numba/core folder
    moduleName = f'{__package__}.functions_numba'
    module = sys.modules.get(moduleName)
    if module is not None:
        importlib.reload(module)                                                # reloading will ensure proper value of numba.config.DISABLE_JIT is being used
    else:
        importlib.import_module(moduleName)                                     # load it for the first time, which will ensure proper value of numba.config.DISABLE_JIT is being used


class SettingsDialog(QDialog):

    appliedSignal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent
        self.setWindowTitle('Roll Settings')
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        # self.setMaximumHeight(1200)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)

        # We create the ParameterTree for the settings dialog
        # See: https://www.programcreek.com/python/example/114819/pyqtgraph.parametertree.ParameterTree
        # See: https://www.programcreek.com/python/?code=CadQuery%2FCQ-editor%2FCQ-editor-master%2Fcq_editor%2Fpreferences.py

        # We need to find the right sps entry in a list of dictionaries
        # See: https://stackoverflow.com/questions/8653516/search-a-list-of-dictionaries-in-python
        # See: https://stackoverflow.com/questions/4391697/find-the-index-of-a-dict-within-a-list-by-matching-the-dicts-value

        # See: https://www.geeksforgeeks.org/pyqtgraph-setting-color-map-to-image-view/
        # See: https://www.programcreek.com/python/example/114819/pyqtgraph.parametertree.ParameterTree
        # See: https://python.hotexamples.com/examples/pyqtgraph.parametertree/ParameterTree/-/python-parametertree-class-examples.html?utm_content=cmp-true
        # See: https://github.com/DerThorsten/ivigraph/blob/master/layerviewer/viewer.py
        # See: https://programtalk.com/python-examples/pyqtgraph.parametertree.Parameter.create/?utm_content=cmp-true
        # See: http://radjkarl.github.io/fancyWidgets/_modules/fancywidgets/pyqtgraphBased/parametertree/parameterTypes.html
        # See: https://stackoverflow.com/questions/50795993/data-entered-by-the-user-are-not-taken-into-account-by-the-parameter-tree
        # See: http://pymodaq.cnrs.fr/en/latest/_modules/pymodaq/utils/parameter/ioxml.html
        # See: https://www.reddit.com/r/Python/comments/8qqznc/python_gui_and_parameter_tree_data_entered_by_the/
        # See: https://gist.github.com/blink1073/1b2f7ae3214742574d51

        appSettings = _getAppSettings(parent)

        # See: https://github.com/cbrunet/fibermodes/blob/master/fibermodesgui/fieldvisualizer/colormapwidget.py

        # Try this nice example
        # See: https://searchcode.com/file/50487139/gui/pyqtgraph/examples/parametertree.py/
        # See: https://github.com/campagnola/relativipy/blob/master/relativity.py how to register three paramater types (Clock, Grid and AccelerationGroup)

        # See: https://doc.qt.io/qtforpython-5/PySide2/QtGui/QColorConstants.html for color constants

        spsNames = []                                                           # create list of sps names to choose from
        for n in appSettings.spsFormatList:
            spsNames.append(n['name'])

        binAreaPenParam = makeParmsFromPen(appSettings.binAreaPen)              # create parameter tuples from current pens
        cmpAreaPenParam = makeParmsFromPen(appSettings.cmpAreaPen)
        recAreaPenParam = makeParmsFromPen(appSettings.recAreaPen)
        srcAreaPenParam = makeParmsFromPen(appSettings.srcAreaPen)

        # Note: QColor uses 'argb' in hex format, whereas pyqtgraph uses 'rgba' so first need to convert #hex value to a QColor()
        colorParams = [
            dict(
                name='Color Settings',
                type='myGroup',
                brush='#add8e6',
                children=[  # Qt light blue background
                    dict(name='Bin area color', type='color', value=QColor(appSettings.binAreaColor), default=QColor(appSettings.binAreaColor)),
                    dict(name='Cmp area color', type='color', value=QColor(appSettings.cmpAreaColor), default=QColor(appSettings.cmpAreaColor)),
                    dict(name='Rec area color', type='color', value=QColor(appSettings.recAreaColor), default=QColor(appSettings.recAreaColor)),
                    dict(name='Src area color', type='color', value=QColor(appSettings.srcAreaColor), default=QColor(appSettings.srcAreaColor)),
                    dict(name='Bin area pen', type='myPen', flat=True, expanded=False, value=binAreaPenParam, default=binAreaPenParam),
                    dict(name='Cmp area pen', type='myPen', flat=True, expanded=False, value=cmpAreaPenParam, default=cmpAreaPenParam),
                    dict(name='Rec area pen', type='myPen', flat=True, expanded=False, value=recAreaPenParam, default=recAreaPenParam),
                    dict(name='Src area pen', type='myPen', flat=True, expanded=False, value=srcAreaPenParam, default=srcAreaPenParam),
                    dict(name='Fold/offset color map', type='myCmap', value=appSettings.foldDispCmap, default=appSettings.foldDispCmap),
                    dict(name='Analysis color map', type='myCmap', value=appSettings.analysisCmap, default=appSettings.analysisCmap),
                ],
            ),
        ]

        lodParams = [
            dict(
                name='Level of Detail Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='LOD 0 [survey]   ', type='mySlider', value=appSettings.lod0, default=appSettings.lod0, precision=4, limits=config.lod0Range, step=0.02 * appSettings.lod0),
                    dict(name='LOD 1 [templates]', type='mySlider', value=appSettings.lod1, default=appSettings.lod1, precision=4, limits=config.lod1Range, step=0.02 * appSettings.lod1),
                    dict(name='LOD 2 [points]   ', type='mySlider', value=appSettings.lod2, default=appSettings.lod2, precision=4, limits=config.lod2Range, step=0.02 * appSettings.lod2),
                    dict(name='LOD 3 [patterns] ', type='mySlider', value=appSettings.lod3, default=appSettings.lod3, precision=4, limits=config.lod3Range, step=0.02 * appSettings.lod3),
                ],
            )
        ]

        # Note: QColor uses 'argb' in hex format, whereas pyqtgraph uses 'rgba' so first need to convert #hex value to a QColor()
        tip0 = (
            'In parallel/NAZ geometries, the source lines run parallel to the receiver lines.\n'
            'In other geometries, the source lines run perpendicular to the receiver lines.\n'
            'This setting only determines how source line- and point-numbers are displayed in QGIS.\n'
            '(Line, Point) or (Point, Line). It has no effect on the actual processing of the data.'
        )
        spsParams = [
            dict(
                name='SPS Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='SPS implementation', type='list', limits=spsNames, value=appSettings.spsDialect, default=appSettings.spsDialect),
                    dict(name='Parallel/NAZ geometry', type='bool', value=appSettings.spsParallel, default=appSettings.spsParallel, tip=tip0),
                    dict(name='Rps point marker', type='myMarker', flat=True, expanded=False, symbol=appSettings.rpsPointSymbol, color=QColor(appSettings.rpsBrushColor), size=appSettings.rpsSymbolSize),
                    dict(name='Sps point marker', type='myMarker', flat=True, expanded=False, symbol=appSettings.spsPointSymbol, color=QColor(appSettings.spsBrushColor), size=appSettings.spsSymbolSize),
                ],
            ),
        ]

        geoParams = [
            dict(
                name='Geometry Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Rec point marker', type='myMarker', flat=True, expanded=False, symbol=appSettings.recPointSymbol, color=QColor(appSettings.recBrushColor), size=appSettings.recSymbolSize),
                    dict(name='Src point marker', type='myMarker', flat=True, expanded=False, symbol=appSettings.srcPointSymbol, color=QColor(appSettings.srcBrushColor), size=appSettings.srcSymbolSize),
                ],
            ),
        ]

        kkkParams = [
            dict(
                name='K-response Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Kr  stack response', type='myRange', flat=True, expanded=False, value=appSettings.kraStack, default=appSettings.kraStack, suffix=' [1/km]'),
                    dict(name='Kxy stack response', type='myRange', flat=True, expanded=False, value=appSettings.kxyStack, default=appSettings.kxyStack, suffix=' [1/km]', twoDim=True),
                    dict(name='Kxy array response', type='myRange', flat=True, expanded=False, value=appSettings.kxyArray, default=appSettings.kxyArray, suffix=' [1/km]', twoDim=True),
                ],
            ),
        ]

        useDebugpy = appSettings.debugpy if haveDebugpy else False

        dbgParams = [
            dict(
                name='Debug Settings',
                type='myGroup',
                brush='#add8e6',
                children=[  # Qt light blue background
                    dict(name='Debug logging', type='bool', value=appSettings.debug, default=appSettings.debug, enabled=True, tip='show debug messages in Logging pane'),
                    dict(name='Debug plugin threads', type='bool', value=useDebugpy, default=useDebugpy, enabled=haveDebugpy, tip='run plugin threads in debug mode using debugpy'),
                ],
            ),
        ]

        useNumba = appSettings.useNumba if haveNumba else False
        tip1 = 'Experimental option to speed up processing significantly.\nIt requires the Numba package to be installed'
        tip2 = 'Save well file names relative to .roll project file.\nThis makes moving the project folder easier.'
        tip3 = 'Show summary information of underlying parameters in the property pane'
        tip4 = "Show functionality that hasn't been completed yet.\nWork in progress for the developer to finish !"

        misParams = [
            dict(
                name='Miscellaneous Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Use Numba', type='bool', value=useNumba, default=useNumba, enabled=haveNumba, tip=tip1),
                    dict(name='Use relative paths', type='bool', value=appSettings.useRelativePaths, default=appSettings.useRelativePaths, enabled=True, tip=tip2),
                    dict(name='Show summary properties', type='bool', value=appSettings.showSummaries, default=appSettings.showSummaries, enabled=True, tip=tip3),
                    dict(name='Show unfinished code', type='bool', value=appSettings.showUnfinished, default=appSettings.showUnfinished, enabled=True, tip=tip4),
                ],
            ),
        ]

        self.parameters = pg.parametertree.Parameter.create(name='Analysis Settings', type='group', children=colorParams)
        self.parameters.addChildren(lodParams)
        self.parameters.addChildren(spsParams)
        self.parameters.addChildren(geoParams)
        self.parameters.addChildren(kkkParams)
        self.parameters.addChildren(dbgParams)
        self.parameters.addChildren(misParams)

        self.parameters.sigTreeStateChanged.connect(self.updateSettings)

        self.paramTree = pg.parametertree.ParameterTree(showHeader=True)
        self.paramTree.setParameters(self.parameters, showTop=False)
        self.paramTree.header().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.paramTree.header().resizeSection(0, 275)

        for item in self.paramTree.listAllItems():                              # Bug. See: https://github.com/pyqtgraph/pyqtgraph/issues/2744
            p = item.param                                                      # get parameter belonging to parameterItem
            p.setToDefault()                                                    # set all parameters to their default value
            if hasattr(item, 'updateDefaultBtn'):                               # note: not all parameterItems have this method
                item.updateDefaultBtn()                                         # reset the default-buttons to their grey value
            if 'tip' in p.opts:                                                 # this solves the above mentioned bug
                item.setToolTip(0, p.opts['tip'])                               # the widgets now get their tooltips

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.paramTree)
        self.layout.addWidget(self.buttonBox)

        self.setLayout(self.layout)

    def updateSettings(self):
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)

    def apply(self):
        self.accepted()
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        self.appliedSignal.emit()

    def accept(self):
        self.accepted()
        QDialog.accept(self)

    def accepted(self):
        appSettings = _getAppSettings(self.parent)

        # categories
        COL = self.parameters.child('Color Settings')
        LOD = self.parameters.child('Level of Detail Settings')
        SPS = self.parameters.child('SPS Settings')
        GEO = self.parameters.child('Geometry Settings')
        KKK = self.parameters.child('K-response Settings')
        DBG = self.parameters.child('Debug Settings')
        MIS = self.parameters.child('Miscellaneous Settings')

        # sps settings
        appSettings.spsDialect = SPS.child('SPS implementation').value()
        appSettings.spsParallel = SPS.child('Parallel/NAZ geometry').value()

        rpsMarker = SPS.child('Rps point marker')
        appSettings.rpsPointSymbol = rpsMarker.marker.symbol()
        appSettings.rpsBrushColor = rpsMarker.marker.color().name(QColor.NameFormat.HexArgb)
        appSettings.rpsSymbolSize = rpsMarker.marker.size()

        spsMarker = SPS.child('Sps point marker')
        appSettings.spsPointSymbol = spsMarker.marker.symbol()
        appSettings.spsBrushColor = spsMarker.marker.color().name(QColor.NameFormat.HexArgb)
        appSettings.spsSymbolSize = spsMarker.marker.size()

        # color (map) settings
        appSettings.analysisCmap = COL.child('Analysis color map').value()
        appSettings.foldDispCmap = COL.child('Fold/offset color map').value()

        appSettings.binAreaColor = COL.child('Bin area color').value().name(QColor.NameFormat.HexArgb)
        appSettings.cmpAreaColor = COL.child('Cmp area color').value().name(QColor.NameFormat.HexArgb)
        appSettings.recAreaColor = COL.child('Rec area color').value().name(QColor.NameFormat.HexArgb)
        appSettings.srcAreaColor = COL.child('Src area color').value().name(QColor.NameFormat.HexArgb)

        # config.binAreaPen = COL.child('Bin area pen').value()                 # the pen value isn't properly updated
        # config.cmpAreaPen = COL.child('Cmp area pen').value()                 # use saveState()['value'] instead
        # config.recAreaPen = COL.child('Rec area pen').value()
        # config.srcAreaPen = COL.child('Src area pen').value()

        binAreaPenParam = COL.child('Bin area pen').saveState()['value']        # intermediate values
        cmpAreaPenParam = COL.child('Cmp area pen').saveState()['value']
        recAreaPenParam = COL.child('Rec area pen').saveState()['value']
        srcAreaPenParam = COL.child('Src area pen').saveState()['value']

        appSettings.binAreaPen = makePenFromParms(binAreaPenParam)             # final values
        appSettings.cmpAreaPen = makePenFromParms(cmpAreaPenParam)
        appSettings.recAreaPen = makePenFromParms(recAreaPenParam)
        appSettings.srcAreaPen = makePenFromParms(srcAreaPenParam)

        appSettings.lod0 = LOD.child('LOD 0 [survey]   ').value()
        appSettings.lod1 = LOD.child('LOD 1 [templates]').value()
        appSettings.lod2 = LOD.child('LOD 2 [points]   ').value()
        appSettings.lod3 = LOD.child('LOD 3 [patterns] ').value()

        # geometry settings
        recValue = GEO.child('Rec point marker').value()
        appSettings.recPointSymbol = recValue.symbol()
        appSettings.recBrushColor = recValue.color().name(QColor.NameFormat.HexArgb)
        appSettings.recSymbolSize = recValue.size()

        srcValue = GEO.child('Src point marker').value()
        appSettings.srcPointSymbol = srcValue.symbol()
        appSettings.srcBrushColor = srcValue.color().name(QColor.NameFormat.HexArgb)
        appSettings.srcSymbolSize = srcValue.size()

        # k-plot settings
        appSettings.kraStack = KKK.child('Kr  stack response').value()
        appSettings.kxyStack = KKK.child('Kxy stack response').value()
        appSettings.kxyArray = KKK.child('Kxy array response').value()

        # debug settings
        # See: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
        appSettings.debug = DBG.child('Debug logging').value()
        appSettings.debugpy = DBG.child('Debug plugin threads').value()

        # miscellaneous settings
        appSettings.useNumba = MIS.child('Use Numba').value()
        appSettings.useRelativePaths = MIS.child('Use relative paths').value()  # save well file names relative to .roll project file
        appSettings.showUnfinished = MIS.child('Show unfinished code').value()  # show/hide "work in progress"
        appSettings.showSummaries = MIS.child('Show summary properties').value()

        appSettings.activate()
        _applyNumbaSetting(appSettings.useNumba)

# Helper functions to read/clear format groups
def _readFormatGroup(self, group):
    self.settings.beginGroup(group)
    entries = []
    for key in self.settings.childKeys():
        raw = self.settings.value(key)
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(entry, dict):
            entry.setdefault('name', key)
            entries.append(entry)
    self.settings.endGroup()
    return entries

def _clearFormatGroup(self, group):
    self.settings.beginGroup(group)
    self.settings.remove('')
    self.settings.endGroup()

def _writeFormatGroup(self, group, entries):
    self.settings.beginGroup(group)
    self.settings.remove('')  # clear existing entries
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name', 'Unnamed')
        self.settings.setValue(name, json.dumps(entry))
    self.settings.endGroup()

def readSettings(self):
    appSettings = _getAppSettings(self)
    documentContext = self.runtimeState

    # main window information
    geom = self.settings.value('mainWindow/geometry', bytes('', 'utf-8'))       # , bytes('', 'utf-8') prevents receiving a 'None' object
    self.restoreGeometry(geom)                                                  # https://gist.github.com/dgovil/d83e7ddc8f3fb4a28832ccc6f9c7f07b

    state = self.settings.value('mainWindow/state', bytes('', 'utf-8'))         # , bytes('', 'utf-8') prevents receiving a 'None' object
    self.restoreState(state)                                                    # No longer needed to test: if geometry != None:

    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)    # 'My Documents' on windows; default if settings don't exist yet
    projectDirectory = self.settings.value('settings/projectDirectory', path)   # start folder for SaveAs
    importDirectory = self.settings.value('settings/importDirectory', path)     # start folder for reading SPS files
    recentFileList = self.settings.value('settings/recentFileList', [])
    if recentFileList is None:
        recentFileList = []
    elif isinstance(recentFileList, str):
        recentFileList = [recentFileList] if recentFileList else []
    else:
        recentFileList = list(recentFileList)

    self.documentContextService.loadStoredValues(
        documentContext,
        projectDirectory=projectDirectory,
        importDirectory=importDirectory,
        recentFileList=recentFileList,
    )

    # color & pen information
    appSettings.binAreaColor = self.settings.value('settings/colors/binAreaColor', '#20000000')
    appSettings.cmpAreaColor = self.settings.value('settings/colors/cmpAreaColor', '#0800ff00')
    appSettings.recAreaColor = self.settings.value('settings/colors/recAreaColor', '#080000ff')
    appSettings.srcAreaColor = self.settings.value('settings/colors/srcAreaColor', '#08ff0000')

    binAreaPenParams = self.settings.value('settings/colors/binAreaPen', str(makeParmsFromPen(appSettings.binAreaPen)))
    cmpAreaPenParams = self.settings.value('settings/colors/cmpAreaPen', str(makeParmsFromPen(appSettings.cmpAreaPen)))
    recAreaPenParams = self.settings.value('settings/colors/recAreaPen', str(makeParmsFromPen(appSettings.recAreaPen)))
    srcAreaPenParams = self.settings.value('settings/colors/srcAreaPen', str(makeParmsFromPen(appSettings.srcAreaPen)))

    appSettings.binAreaPen = makePenFromParms(literal_eval(binAreaPenParams))
    appSettings.cmpAreaPen = makePenFromParms(literal_eval(cmpAreaPenParams))
    appSettings.recAreaPen = makePenFromParms(literal_eval(recAreaPenParams))
    appSettings.srcAreaPen = makePenFromParms(literal_eval(srcAreaPenParams))

    appSettings.analysisCmap = self.settings.value('settings/colors/analysisCmap', 'CET-R4')
    appSettings.foldDispCmap = self.settings.value('settings/colors/foldDispCmap', 'CET-L4')

    # sps information
    appSettings.rpsBrushColor = self.settings.value('settings/sps/rpsBrushColor', '#772929FF')
    appSettings.rpsPointSymbol = self.settings.value('settings/sps/rpsPointSymbol', 'o')
    appSettings.rpsSymbolSize = self.settings.value('settings/sps/rpsSymbolSize', 25)

    appSettings.spsBrushColor = self.settings.value('settings/sps/spsBrushColor', '#77FF2929')
    appSettings.spsPointSymbol = self.settings.value('settings/sps/spsPointSymbol', 'o')
    appSettings.spsSymbolSize = self.settings.value('settings/sps/spsSymbolSize', 25)

    appSettings.spsParallel = self.settings.value('settings/sps/spsParallel', config.DEFAULT_SPS_PARALLEL, type=bool)
    appSettings.spsDialect = self.settings.value('settings/sps/spsDialect', config.DEFAULT_SPS_DIALECT)

    # read custom SPS formats
    customSpsFormats = _readFormatGroup(self, 'settings/sps/spsFormatList')
    customXpsFormats = _readFormatGroup(self, 'settings/sps/xpsFormatList')
    customRpsFormats = _readFormatGroup(self, 'settings/sps/rpsFormatList')

    counts = [len(customSpsFormats), len(customXpsFormats), len(customRpsFormats)]
    if any(counts):
        if not all(counts) or len(set(counts)) != 1:
            print('Stored SPS/XPS/RPS formats are inconsistent; reverting to built-in defaults.')
            for group in (
                'settings/sps/spsFormatList',
                'settings/sps/xpsFormatList',
                'settings/sps/rpsFormatList',
            ):
                _clearFormatGroup(self, group)
            appSettings.resetSpsDatabase(preferredDialect=appSettings.spsDialect)
        else:
            appSettings.spsFormatList = customSpsFormats
            appSettings.xpsFormatList = customXpsFormats
            appSettings.rpsFormatList = customRpsFormats

    # geometry information
    appSettings.recBrushColor = self.settings.value('settings/geo/recBrushColor', '#772929FF')
    appSettings.recPointSymbol = self.settings.value('settings/geo/recPointSymbol', 'o')
    appSettings.recSymbolSize = self.settings.value('settings/geo/recSymbolSize', 25)
    appSettings.srcBrushColor = self.settings.value('settings/geo/srcBrushColor', '#77FF2929')
    appSettings.srcPointSymbol = self.settings.value('settings/geo/srcPointSymbol', 'o')
    appSettings.srcSymbolSize = self.settings.value('settings/geo/srcSymbolSize', 25)

    # k-plot information
    appSettings.kraStack = rng.read(self.settings.value('settings/k-plots/kraStack', '0;20;0.1'))
    appSettings.kxyStack = rng.read(self.settings.value('settings/k-plots/kxyStack', '-5;5;0.05'))
    appSettings.kxyArray = rng.read(self.settings.value('settings/k-plots/kxyArray', '-50;50;0.5'))

    # debug information
    # See: https://forum.qt.io/topic/108622/how-to-get-a-boolean-value-from-qsettings-correctly/8
    appSettings.debug = self.settings.value('settings/debug/logging', config.DEFAULT_DEBUG, type=bool)
    appSettings.debugpy = self.settings.value('settings/debug/debugpy', False, type=bool)

    # miscellaneous information
    appSettings.useNumba = self.settings.value('settings/misc/useNumba', False, type=bool)
    appSettings.useRelativePaths = self.settings.value('settings/misc/useRelativePaths', True, type=bool)
    appSettings.showUnfinished = self.settings.value('settings/misc/showUnfinished', config.DEFAULT_SHOW_UNFINISHED, type=bool)
    appSettings.showSummaries = self.settings.value('settings/misc/showSummaries', config.DEFAULT_SHOW_SUMMARIES, type=bool)

    appSettings.activate()
    _applyNumbaSetting(appSettings.useNumba)

    if appSettings.debug and console is not None:
        if console._console is None:                                            # pylint: disable=W0212 # unfortunately need access to protected member
            console.show_console()                                              # opens the console for the first time
        else:
            console._console.setUserVisible(True)                               # pylint: disable=W0212 # unfortunately need access to protected member
        print('print() to Python console has been enabled; Python console is opened')   # this message should always be printed
    elif appSettings.debug:
        print('print() to Python console has been enabled, but the QGIS console module is not available')
    else:
        print('print() to Python console has been disabled from now on')        # this message is the last one to be printed

def writeSettings(self):
    appSettings = _getAppSettings(self)
    documentContext = self.runtimeState

    # main window information
    self.settings.setValue('mainWindow/geometry', self.saveGeometry())          # save the main window geometry
    self.settings.setValue('mainWindow/state', self.saveState())                # and the window state too
    self.settings.setValue('settings/projectDirectory', documentContext.projectDirectory)
    self.settings.setValue('settings/importDirectory', documentContext.importDirectory)
    self.settings.setValue('settings/recentFileList', documentContext.recentFileList)      # store list in settings

    # color and pen information
    self.settings.setValue('settings/colors/binAreaColor', appSettings.binAreaColor)
    self.settings.setValue('settings/colors/cmpAreaColor', appSettings.cmpAreaColor)
    self.settings.setValue('settings/colors/recAreaColor', appSettings.recAreaColor)
    self.settings.setValue('settings/colors/srcAreaColor', appSettings.srcAreaColor)
    self.settings.setValue('settings/colors/binAreaPen', str(makeParmsFromPen(appSettings.binAreaPen)))
    self.settings.setValue('settings/colors/cmpAreaPen', str(makeParmsFromPen(appSettings.cmpAreaPen)))
    self.settings.setValue('settings/colors/recAreaPen', str(makeParmsFromPen(appSettings.recAreaPen)))
    self.settings.setValue('settings/colors/srcAreaPen', str(makeParmsFromPen(appSettings.srcAreaPen)))
    self.settings.setValue('settings/colors/analysisCmap', appSettings.analysisCmap)
    self.settings.setValue('settings/colors/foldDispCmap', appSettings.foldDispCmap)

    # sps information
    self.settings.setValue('settings/sps/rpsBrushColor', appSettings.rpsBrushColor)
    self.settings.setValue('settings/sps/rpsPointSymbol', appSettings.rpsPointSymbol)
    self.settings.setValue('settings/sps/rpsSymbolSize', appSettings.rpsSymbolSize)

    self.settings.setValue('settings/sps/spsBrushColor', appSettings.spsBrushColor)
    self.settings.setValue('settings/sps/spsPointSymbol', appSettings.spsPointSymbol)
    self.settings.setValue('settings/sps/spsSymbolSize', appSettings.spsSymbolSize)

    self.settings.setValue('settings/sps/spsParallel', appSettings.spsParallel)
    self.settings.setValue('settings/sps/spsDialect', appSettings.spsDialect)

    _writeFormatGroup(self, 'settings/sps/spsFormatList', appSettings.spsFormatList)
    _writeFormatGroup(self, 'settings/sps/xpsFormatList', appSettings.xpsFormatList)
    _writeFormatGroup(self, 'settings/sps/rpsFormatList', appSettings.rpsFormatList)

    # geometry information
    self.settings.setValue('settings/geo/recBrushColor', appSettings.recBrushColor)
    self.settings.setValue('settings/geo/recPointSymbol', appSettings.recPointSymbol)
    self.settings.setValue('settings/geo/recSymbolSize', appSettings.recSymbolSize)
    self.settings.setValue('settings/geo/srcBrushColor', appSettings.srcBrushColor)
    self.settings.setValue('settings/geo/srcPointSymbol', appSettings.srcPointSymbol)
    self.settings.setValue('settings/geo/srcSymbolSize', appSettings.srcSymbolSize)

    # k-plot information
    self.settings.setValue('settings/k-plots/kraStack', rng.write(appSettings.kraStack))
    self.settings.setValue('settings/k-plots/kxyStack', rng.write(appSettings.kxyStack))
    self.settings.setValue('settings/k-plots/kxyArray', rng.write(appSettings.kxyArray))

    # debug information
    self.settings.setValue('settings/debug/logging', appSettings.debug)
    self.settings.setValue('settings/debug/debugpy', appSettings.debugpy)

    # miscellaneous information
    self.settings.setValue('settings/misc/useNumba', appSettings.useNumba)
    self.settings.setValue('settings/misc/useRelativePaths', appSettings.useRelativePaths)
    self.settings.setValue('settings/misc/showUnfinished', appSettings.showUnfinished)
    self.settings.setValue('settings/misc/showSummaries', appSettings.showSummaries)

    self.settings.sync()
