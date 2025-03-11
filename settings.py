from ast import literal_eval

import pyqtgraph as pg
from console import console
from qgis.PyQt.QtCore import QStandardPaths, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QHeaderView, QVBoxLayout

try:    # need to TRY importing numba, only to see if it is available
    haveNumba = True
    import numba  # pylint: disable=W0611
except ImportError:
    haveNumba = False

try:    # need to TRY importing ptvsd, only to see if it is available
    havePtvsd = True
    import ptvsd  # pylint: disable=W0611
except ImportError as ie:
    havePtvsd = False


from . import config  # used to pass initial settings
from .functions import makeParmsFromPen, makePenFromParms
from .my_range import MyRangeParameter as rng


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

        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.apply)

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

        # See: https://github.com/cbrunet/fibermodes/blob/master/fibermodesgui/fieldvisualizer/colormapwidget.py

        # Try this nice example
        # See: https://searchcode.com/file/50487139/gui/pyqtgraph/examples/parametertree.py/
        # See: https://github.com/campagnola/relativipy/blob/master/relativity.py how to register three paramater types (Clock, Grid and AccelerationGroup)

        # See: https://doc.qt.io/qtforpython-5/PySide2/QtGui/QColorConstants.html for color constants

        spsNames = []                                                           # create list of sps names to choose from
        for n in config.spsFormatList:
            spsNames.append(n['name'])

        binAreaPenParam = makeParmsFromPen(config.binAreaPen)                   # create parameter tuples from current pens
        cmpAreaPenParam = makeParmsFromPen(config.cmpAreaPen)
        recAreaPenParam = makeParmsFromPen(config.recAreaPen)
        srcAreaPenParam = makeParmsFromPen(config.srcAreaPen)

        # Note: QColor uses 'argb' in hex format, whereas pyqtgraph uses 'rgba' so first need to convert #hex value to a QColor()
        colorParams = [
            dict(
                name='Color Settings',
                type='myGroup',
                brush='#add8e6',
                children=[  # Qt light blue background
                    dict(name='Bin area color', type='color', value=QColor(config.binAreaColor), default=QColor(config.binAreaColor)),
                    dict(name='Cmp area color', type='color', value=QColor(config.cmpAreaColor), default=QColor(config.cmpAreaColor)),
                    dict(name='Rec area color', type='color', value=QColor(config.recAreaColor), default=QColor(config.recAreaColor)),
                    dict(name='Src area color', type='color', value=QColor(config.srcAreaColor), default=QColor(config.srcAreaColor)),
                    dict(name='Bin area pen', type='myPen', flat=True, expanded=False, value=binAreaPenParam, default=binAreaPenParam),
                    dict(name='Cmp area pen', type='myPen', flat=True, expanded=False, value=cmpAreaPenParam, default=cmpAreaPenParam),
                    dict(name='Rec area pen', type='myPen', flat=True, expanded=False, value=recAreaPenParam, default=recAreaPenParam),
                    dict(name='Src area pen', type='myPen', flat=True, expanded=False, value=srcAreaPenParam, default=srcAreaPenParam),
                    dict(name='Fold/offset color map', type='myCmap', value=config.fold_OffCmap, default=config.fold_OffCmap),
                    dict(name='Analysis color map', type='myCmap', value=config.analysisCmap, default=config.analysisCmap),
                ],
            ),
        ]

        lodParams = [
            dict(
                name='Level of Detail Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='LOD 0 [survey]   ', type='mySlider', value=config.lod0, default=config.lod0, precision=4, limits=config.lod0Range, step=0.02 * config.lod0),  # config.lod0 = 0.005
                    dict(name='LOD 1 [templates]', type='mySlider', value=config.lod1, default=config.lod1, precision=4, limits=config.lod1Range, step=0.02 * config.lod1),  # config.lod1 = 0.050
                    dict(name='LOD 2 [points]   ', type='mySlider', value=config.lod2, default=config.lod2, precision=4, limits=config.lod2Range, step=0.02 * config.lod2),  # config.lod2 = 0.500
                    dict(name='LOD 3 [patterns] ', type='mySlider', value=config.lod3, default=config.lod3, precision=4, limits=config.lod3Range, step=0.02 * config.lod3),  # config.lod3 = 1.250
                ],
            )
        ]

        # Note: QColor uses 'argb' in hex format, whereas pyqtgraph uses 'rgba' so first need to convert #hex value to a QColor()
        spsParams = [
            dict(
                name='SPS Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Local SPS dialect', type='list', limits=spsNames, value=config.spsDialect, default=config.spsDialect),  # SPS 'flavor'
                    dict(name='Rps point marker', type='myMarker', flat=True, expanded=False, symbol=config.rpsPointSymbol, color=QColor(config.rpsBrushColor), size=config.rpsSymbolSize),
                    dict(name='Sps point marker', type='myMarker', flat=True, expanded=False, symbol=config.spsPointSymbol, color=QColor(config.spsBrushColor), size=config.spsSymbolSize),
                ],
            ),
        ]

        geoParams = [
            dict(
                name='Geometry Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Rec point marker', type='myMarker', flat=True, expanded=False, symbol=config.recPointSymbol, color=QColor(config.recBrushColor), size=config.recSymbolSize),
                    dict(name='Src point marker', type='myMarker', flat=True, expanded=False, symbol=config.srcPointSymbol, color=QColor(config.srcBrushColor), size=config.srcSymbolSize),
                ],
            ),
        ]

        kkkParams = [
            dict(
                name='K-response Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Kr  stack response', type='myRange', flat=True, expanded=False, value=config.kr_Stack, default=config.kr_Stack, suffix=' [1/km]'),  # fixedMin=True,
                    dict(name='Kxy stack response', type='myRange', flat=True, expanded=False, value=config.kxyStack, default=config.kxyStack, suffix=' [1/km]', twoDim=True),
                    dict(name='Kxy array response', type='myRange', flat=True, expanded=False, value=config.kxyArray, default=config.kxyArray, suffix=' [1/km]', twoDim=True),
                ],
            ),
        ]

        usePtvsd = config.ptvsd if havePtvsd else False

        dbgParams = [
            dict(
                name='Debug Settings',
                type='myGroup',
                brush='#add8e6',
                children=[  # Qt light blue background
                    dict(name='Debug logging', type='bool', value=config.debug, default=config.debug, enabled=True, tip='show debug messages in Logging pane'),
                    dict(name='Debug worker threads', type='bool', value=usePtvsd, default=usePtvsd, enabled=havePtvsd, tip='run worker threads in debug mode using ptvsd'),
                ],
            ),
        ]

        useNumba = config.useNumba if haveNumba else False
        tip1 = 'This is an experimental option to speed up processing significantly.\nIt requires the Numba package to be installed'
        tip2 = "This shows functionality that hasn't been completed yet.\nWork in progress !"

        misParams = [
            dict(
                name='Miscellaneous Settings',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Use Numba', type='bool', value=useNumba, default=useNumba, enabled=haveNumba, tip=tip1),
                    dict(name='Show summary properties', type='bool', value=config.showSummaries, default=config.showSummaries, enabled=haveNumba, tip=tip1),
                    dict(name='Show unfinished code', type='bool', value=config.showUnfinished, default=config.showUnfinished, enabled=True, tip=tip2),
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
        self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(True)

    def apply(self):
        self.accepted()
        self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)
        self.appliedSignal.emit()

    def accept(self):
        self.accepted()
        QDialog.accept(self)

    def accepted(self):
        # categories
        COL = self.parameters.child('Color Settings')
        LOD = self.parameters.child('Level of Detail Settings')
        SPS = self.parameters.child('SPS Settings')
        GEO = self.parameters.child('Geometry Settings')
        KKK = self.parameters.child('K-response Settings')
        DBG = self.parameters.child('Debug Settings')
        MIS = self.parameters.child('Miscellaneous Settings')

        # sps settings
        config.spsDialect = SPS.child('Local SPS dialect').value()

        rpsMarker = SPS.child('Rps point marker')
        config.rpsPointSymbol = rpsMarker.marker.symbol()
        config.rpsBrushColor = rpsMarker.marker.color().name(QColor.HexArgb)
        config.rpsSymbolSize = rpsMarker.marker.size()

        spsMarker = SPS.child('Sps point marker')
        config.spsPointSymbol = spsMarker.marker.symbol()
        config.spsBrushColor = spsMarker.marker.color().name(QColor.HexArgb)
        config.spsSymbolSize = spsMarker.marker.size()

        # color (map) settings
        config.analysisCmap = COL.child('Analysis color map').value()
        config.fold_OffCmap = COL.child('Fold/offset color map').value()

        config.binAreaColor = COL.child('Bin area color').value().name(QColor.HexArgb)
        config.cmpAreaColor = COL.child('Cmp area color').value().name(QColor.HexArgb)
        config.recAreaColor = COL.child('Rec area color').value().name(QColor.HexArgb)
        config.srcAreaColor = COL.child('Src area color').value().name(QColor.HexArgb)

        # config.binAreaPen = COL.child('Bin area pen').value()                 # the pen value isn't properly updated
        # config.cmpAreaPen = COL.child('Cmp area pen').value()                 # use saveState()['value'] instead
        # config.recAreaPen = COL.child('Rec area pen').value()
        # config.srcAreaPen = COL.child('Src area pen').value()

        binAreaPenParam = COL.child('Bin area pen').saveState()['value']        # intermediate values
        cmpAreaPenParam = COL.child('Cmp area pen').saveState()['value']
        recAreaPenParam = COL.child('Rec area pen').saveState()['value']
        srcAreaPenParam = COL.child('Src area pen').saveState()['value']

        config.binAreaPen = makePenFromParms(binAreaPenParam)                   # final values
        config.cmpAreaPen = makePenFromParms(cmpAreaPenParam)
        config.recAreaPen = makePenFromParms(recAreaPenParam)
        config.srcAreaPen = makePenFromParms(srcAreaPenParam)

        config.lod0 = LOD.child('LOD 0 [survey]   ').value()
        config.lod1 = LOD.child('LOD 1 [templates]').value()
        config.lod2 = LOD.child('LOD 2 [points]   ').value()
        config.lod3 = LOD.child('LOD 3 [patterns] ').value()

        # geometry settings
        recValue = GEO.child('Rec point marker').value()
        config.recPointSymbol = recValue.symbol()
        config.recBrushColor = recValue.color().name(QColor.HexArgb)
        config.recSymbolSize = recValue.size()

        srcValue = GEO.child('Src point marker').value()
        config.srcPointSymbol = srcValue.symbol()
        config.srcBrushColor = srcValue.color().name(QColor.HexArgb)
        config.srcSymbolSize = srcValue.size()

        # k-plot settings
        config.kr_Stack = KKK.child('Kr  stack response').value()
        config.kxyStack = KKK.child('Kxy stack response').value()
        config.kxyArray = KKK.child('Kxy array response').value()

        # debug settings
        # See: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
        config.debug = DBG.child('Debug logging').value()
        config.ptvsd = DBG.child('Debug worker threads').value()

        # miscellaneous settings
        config.useNumba = MIS.child('Use Numba').value()
        if haveNumba:                                                           # can only do this when numba has been installed
            numba.config.DISABLE_JIT = not config.useNumba                      # disable/enable numba pre-compilation in @jit decorator. See 'decorators.py' in numba/core folder
        config.showUnfinished = MIS.child('Show unfinished code').value()       # show/hide "work in progress"
        config.showSummaries = MIS.child('Show summary properties').value()         # show/hide summary information in property pane


def readSettings(self):
    # main window information
    geom = self.settings.value('mainWindow/geometry', bytes('', 'utf-8'))       # , bytes('', 'utf-8') prevents receiving a 'None' object
    self.restoreGeometry(geom)                                                  # https://gist.github.com/dgovil/d83e7ddc8f3fb4a28832ccc6f9c7f07b

    state = self.settings.value('mainWindow/state', bytes('', 'utf-8'))         # , bytes('', 'utf-8') prevents receiving a 'None' object
    self.restoreGeometry(state)                                                 # No longer needed to test: if geometry != None:

    path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)    # 'My Documents' on windows; default if settings don't exist yet
    self.workingDirectory = self.settings.value('settings/workingDirectory', path)   # start folder for SaveAs
    self.importDirectory = self.settings.value('settings/importDirectory', path)   # start folder for reading SPS files
    self.recentFileList = self.settings.value('settings/recentFileList', [])

    # color & pen information
    config.binAreaColor = self.settings.value('settings/colors/binAreaColor', '#20000000')  # argb - light grey
    config.cmpAreaColor = self.settings.value('settings/colors/cmpAreaColor', '#0800ff00')  # argb - light green
    config.recAreaColor = self.settings.value('settings/colors/recAreaColor', '#080000ff')  # argb - light blue
    config.srcAreaColor = self.settings.value('settings/colors/srcAreaColor', '#08ff0000')  # argb - light red

    binAreaPenParams = self.settings.value('settings/colors/binAreaPen', str(makeParmsFromPen(config.binAreaPen)))  # black
    cmpAreaPenParams = self.settings.value('settings/colors/cmpAreaPen', str(makeParmsFromPen(config.cmpAreaPen)))  # green
    recAreaPenParams = self.settings.value('settings/colors/recAreaPen', str(makeParmsFromPen(config.recAreaPen)))  # blue
    srcAreaPenParams = self.settings.value('settings/colors/srcAreaPen', str(makeParmsFromPen(config.srcAreaPen)))  # red

    config.binAreaPen = makePenFromParms(literal_eval(binAreaPenParams))
    config.cmpAreaPen = makePenFromParms(literal_eval(cmpAreaPenParams))
    config.recAreaPen = makePenFromParms(literal_eval(recAreaPenParams))
    config.srcAreaPen = makePenFromParms(literal_eval(srcAreaPenParams))

    config.analysisCmap = self.settings.value('settings/colors/analysisCmap', 'CET-R4')     # from pg.colormap.listMaps()
    config.fold_OffCmap = self.settings.value('settings/colors/fold_OffCmap', 'CET-L4')     # from pg.colormap.listMaps()

    # sps information
    config.spsDialect = self.settings.value('settings/sps/spsDialect', 'NL')
    config.rpsBrushColor = self.settings.value('settings/sps/rpsBrushColor', '#772929FF')
    config.rpsPointSymbol = self.settings.value('settings/sps/rpsPointSymbol', 'o')
    config.rpsSymbolSize = self.settings.value('settings/sps/rpsSymbolSize', 25)
    config.spsBrushColor = self.settings.value('settings/sps/spsBrushColor', '#77FF2929')
    config.spsPointSymbol = self.settings.value('settings/sps/spsPointSymbol', 'o')
    config.spsSymbolSize = self.settings.value('settings/sps/spsSymbolSize', 25)

    # geometry information
    config.recBrushColor = self.settings.value('settings/geo/recBrushColor', '#772929FF')
    config.recPointSymbol = self.settings.value('settings/geo/recPointSymbol', 'o')
    config.recSymbolSize = self.settings.value('settings/geo/recSymbolSize', 25)
    config.srcBrushColor = self.settings.value('settings/geo/srcBrushColor', '#77FF2929')
    config.srcPointSymbol = self.settings.value('settings/geo/srcPointSymbol', 'o')
    config.srcSymbolSize = self.settings.value('settings/geo/srcSymbolSize', 25)

    # k-plot information
    config.kr_Stack = rng.read(self.settings.value('settings/k-plots/kr_Stack', '0;20;0.1'))
    config.kxyStack = rng.read(self.settings.value('settings/k-plots/kxyStack', '-5;5;0.05'))
    config.kxyArray = rng.read(self.settings.value('settings/k-plots/kxyArray', '-50;50;0.5'))

    # debug information
    # See: https://forum.qt.io/topic/108622/how-to-get-a-boolean-value-from-qsettings-correctly/8
    config.debug = self.settings.value('settings/debug/logging', False, type=bool)    # assume no debugging messages required
    config.ptvsd = self.settings.value('settings/debug/ptvsd', False, type=bool)      # assume no debugging in worker threads

    if config.debug:
        if console._console is None:                                                # pylint: disable=W0212 # unfortunately need access to protected member
            console.show_console()                                                  # opens the console for the first time
        else:
            console._console.setUserVisible(True)                                   # pylint: disable=W0212 # unfortunately need access to protected member
        print('print() to Python console has been enabled; Python console is opened')   # this message should always be printed
    else:
        print('print() to Python console has been disabled from now on')            # this message is the last one to be printed

    # miscellaneous information
    config.useNumba = self.settings.value('settings/misc/useNumba', False, type=bool)   # assume Numba not installed (and used) by default
    if haveNumba:                                                                       # can only do this when numba has been installed
        numba.config.DISABLE_JIT = not config.useNumba                                  # disable/enable numba pre-compilation in @jit decorator

    config.showUnfinished = self.settings.value('settings/misc/showUnfinished', False, type=bool)   # show unfinished code
    config.showSummaries = self.settings.value('settings/misc/showSummaries', False, type=bool)     # show/hide summary information in property pane


def writeSettings(self):
    # main window information
    self.settings.setValue('mainWindow/geometry', self.saveGeometry())          # save the main window geometry
    self.settings.setValue('mainWindow/state', self.saveState())                # and the window state too
    self.settings.setValue('settings/workingDirectory', self.workingDirectory)
    self.settings.setValue('settings/importDirectory', self.importDirectory)
    self.settings.setValue('settings/recentFileList', self.recentFileList)      # store list in settings

    # color and pen information
    self.settings.setValue('settings/colors/binAreaColor', config.binAreaColor)
    self.settings.setValue('settings/colors/cmpAreaColor', config.cmpAreaColor)
    self.settings.setValue('settings/colors/recAreaColor', config.recAreaColor)
    self.settings.setValue('settings/colors/srcAreaColor', config.srcAreaColor)
    self.settings.setValue('settings/colors/binAreaPen', str(makeParmsFromPen(config.binAreaPen)))
    self.settings.setValue('settings/colors/cmpAreaPen', str(makeParmsFromPen(config.cmpAreaPen)))
    self.settings.setValue('settings/colors/recAreaPen', str(makeParmsFromPen(config.recAreaPen)))
    self.settings.setValue('settings/colors/srcAreaPen', str(makeParmsFromPen(config.srcAreaPen)))
    self.settings.setValue('settings/colors/analysisCmap', config.analysisCmap)
    self.settings.setValue('settings/colors/fold_OffCmap', config.fold_OffCmap)

    # sps information
    self.settings.setValue('settings/sps/spsDialect', config.spsDialect)
    self.settings.setValue('settings/sps/rpsBrushColor', config.rpsBrushColor)
    self.settings.setValue('settings/sps/rpsPointSymbol', config.rpsPointSymbol)
    self.settings.setValue('settings/sps/rpsSymbolSize', config.rpsSymbolSize)
    self.settings.setValue('settings/sps/spsBrushColor', config.spsBrushColor)
    self.settings.setValue('settings/sps/spsPointSymbol', config.spsPointSymbol)
    self.settings.setValue('settings/sps/spsSymbolSize', config.spsSymbolSize)

    # geometry information
    self.settings.setValue('settings/geo/recBrushColor', config.recBrushColor)
    self.settings.setValue('settings/geo/recPointSymbol', config.recPointSymbol)
    self.settings.setValue('settings/geo/recSymbolSize', config.recSymbolSize)
    self.settings.setValue('settings/geo/srcBrushColor', config.srcBrushColor)
    self.settings.setValue('settings/geo/srcPointSymbol', config.srcPointSymbol)
    self.settings.setValue('settings/geo/srcSymbolSize', config.srcSymbolSize)

    # k-plot information
    self.settings.setValue('settings/k-plots/kr_Stack', rng.write(config.kr_Stack))
    self.settings.setValue('settings/k-plots/kxyStack', rng.write(config.kxyStack))
    self.settings.setValue('settings/k-plots/kxyArray', rng.write(config.kxyArray))

    # debug information
    self.settings.setValue('settings/debug/logging', config.debug)
    self.settings.setValue('settings/debug/ptvsd', config.ptvsd)

    # miscellaneous information
    self.settings.setValue('settings/misc/useNumba', config.useNumba)
    self.settings.setValue('settings/misc/showUnfinished', config.showUnfinished)
    self.settings.setValue('settings/misc/showSummaries', config.showSummaries)    # show/hide summary information in property pane
