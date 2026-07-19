# coding=utf-8
import unittest

from pyqtgraph.parametertree import ParameterTree
from qgis.PyQt.QtGui import QColor, QVector3D

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey, getQgisApp

enumsModule = loadPluginModule('enums_and_int_flags')
myParametersModule = loadPluginModule('my_parameters')
rollBinningModule = loadPluginModule('roll_binning')
rollPatternModule = loadPluginModule('roll_pattern')
rollSeedModule = loadPluginModule('roll_seed')
rollWellModule = loadPluginModule('roll_well')

SeedType = enumsModule.SeedType
MySeedParameter = myParametersModule.MySeedParameter
MyPatternSeedParameter = myParametersModule.MyPatternSeedParameter
applyAnalysisParameters = myParametersModule.applyAnalysisParameters
applyBlockParameters = myParametersModule.applyBlockParameters
appendNewManagedParameterItem = myParametersModule.appendNewManagedParameterItem
applyConfigurationParameterValues = myParametersModule.applyConfigurationParameterValues
applyGridSeedPatternRefresh = myParametersModule.applyGridSeedPatternRefresh
applyNonGridSeedTypeState = myParametersModule.applyNonGridSeedTypeState
applyPatternSeedParameterValues = myParametersModule.applyPatternSeedParameterValues
applySeedTypeChange = myParametersModule.applySeedTypeChange
resolveGridSeedPatternRefreshState = myParametersModule.resolveGridSeedPatternRefreshState
applyRollParameterStepCount = myParametersModule.applyRollParameterStepCount
applyRollParameterIncrement = myParametersModule.applyRollParameterIncrement
applyRollListParameters = myParametersModule.applyRollListParameters
applyTemplateParameters = myParametersModule.applyTemplateParameters
applyPatternListSideEffects = myParametersModule.applyPatternListSideEffects
applyPatternMoveSideEffects = myParametersModule.applyPatternMoveSideEffects
applyPatternRemovalSideEffects = myParametersModule.applyPatternRemovalSideEffects
applyCircleParameters = myParametersModule.applyCircleParameters
applyBinMethodParameters = myParametersModule.applyBinMethodParameters
applyBinAnglesParameters = myParametersModule.applyBinAnglesParameters
applyBinOffsetParameters = myParametersModule.applyBinOffsetParameters
applyWellHeaderParameterChange = myParametersModule.applyWellHeaderParameterChange
applyGlobalGridParameters = myParametersModule.applyGlobalGridParameters
applyLocalGridParameters = myParametersModule.applyLocalGridParameters
applyPlaneParameters = myParametersModule.applyPlaneParameters
applyReflectorParameters = myParametersModule.applyReflectorParameters
applySpiralParameters = myParametersModule.applySpiralParameters
applySphereParameters = myParametersModule.applySphereParameters
applyUniqueOffsetParameters = myParametersModule.applyUniqueOffsetParameters
applyWellSamplingFromParameters = myParametersModule.applyWellSamplingFromParameters
findParameterTreeRoot = myParametersModule.findParameterTreeRoot
formatPreviewCountLabel = myParametersModule.formatPreviewCountLabel
formatPreviewPointSummary = myParametersModule.formatPreviewPointSummary
iterTemplateSeedParameters = myParametersModule.iterTemplateSeedParameters
previewSeedListCompositionSummary = myParametersModule.previewSeedListCompositionSummary
previewWellSummary = myParametersModule.previewWellSummary
refreshWellHeaderFromParameter = myParametersModule.refreshWellHeaderFromParameter
previewSeedShotCount = myParametersModule.previewSeedShotCount
previewTemplateSourceSummary = myParametersModule.previewTemplateSourceSummary
previewBlockSourceSummary = myParametersModule.previewBlockSourceSummary
BinningList = rollBinningModule.BinningList
BinningType = rollBinningModule.BinningType
RollPattern = rollPatternModule.RollPattern
RollSeed = rollSeedModule.RollSeed
RollWellError = rollWellModule.RollWellError


class _FakePreviewNode:
    def __init__(self, *, value=None, children=None, iterableChildren=None):
        self.opts = {'value': value}
        self._children = children or {}
        self._iterableChildren = iterableChildren or []

    def child(self, *names):
        node = self
        for name in names:
            node = node._children[name]
        return node

    def hasChildren(self):
        return bool(self._iterableChildren)

    def __iter__(self):
        return iter(self._iterableChildren)


def _makeGridSteps(planes, lines, points):
    return _FakePreviewNode(children={
        'Planes': _FakePreviewNode(children={'N': _FakePreviewNode(value=planes)}),
        'Lines': _FakePreviewNode(children={'N': _FakePreviewNode(value=lines)}),
        'Points': _FakePreviewNode(children={'N': _FakePreviewNode(value=points)}),
    })


def _makeSeed(*, seedType, source, grid=(1, 1, 1), circle=0, spiral=0, well=0):
    return _FakePreviewNode(children={
        'Source seed': _FakePreviewNode(value=source),
        'Seed type': _FakePreviewNode(value=seedType),
        'Grid grow steps': _makeGridSteps(*grid),
        'Circle grow steps': _FakePreviewNode(children={'Points': _FakePreviewNode(value=circle)}),
        'Spiral grow steps': _FakePreviewNode(children={'Points': _FakePreviewNode(value=spiral)}),
        'Well grow steps': _FakePreviewNode(children={'Points': _FakePreviewNode(value=well)}),
    })


def _makeTemplate(seeds, *, roll=(1, 1, 1)):
    return _FakePreviewNode(children={
        'Seed list': _FakePreviewNode(iterableChildren=seeds),
        'Roll steps': _makeGridSteps(*roll),
    })


def _makeBlock(templates):
    return _FakePreviewNode(children={
        'Template list': _FakePreviewNode(iterableChildren=templates),
    })


class _FakeSeedListChild(MySeedParameter):
    def __init__(self, source):
        self.names = {
            'Source seed': _FakePreviewNode(value=source),
        }


class _FakeSeedListNode:
    def __init__(self, children):
        self.childs = children


class _FakeWellPreviewParam:
    def __init__(self, *, fileValue, ahdInterval, points, decimals=3, errorText=None):
        self.opts = {'decimals': decimals}
        self.well = type('WellState', (), {'errorText': errorText})()
        self._children = {
            'Well file': _FakePreviewNode(value=fileValue),
            'AHD interval': _FakePreviewNode(value=ahdInterval),
            'Points': _FakePreviewNode(value=points),
        }

    def child(self, *names):
        if len(names) != 1:
            raise KeyError(names)
        return self._children[names[0]]


class _FakeTreeNode:
    def __init__(self, *, name=None, children=None, iterableChildren=None, parent=None):
        self.name = name
        self._children = children or {}
        self._iterableChildren = iterableChildren or []
        self._parent = parent

        for child in self._children.values():
            child._parent = self
        for child in self._iterableChildren:
            child._parent = self

    def child(self, *names):
        node = self
        for name in names:
            node = node._children[name]
        return node

    def parent(self):
        return self._parent

    def __iter__(self):
        return iter(self._iterableChildren)


class _FakePatternSeedParam:
    def __init__(self, name):
        self.name = name
        self._parent = None

    def parent(self):
        return self._parent


class _FakePatternListParam:
    def __init__(self):
        self.calls = []

    def _syncSurveyPatternList(self):
        self.calls.append(('sync',))

    def refreshSeedPatternLists(self):
        self.calls.append(('refresh',))

    def _removePatternIndex(self, removedIndex):
        self.calls.append(('remove', removedIndex))

    def _swapPatternIndices(self, oldIndex, newIndex):
        self.calls.append(('swap', oldIndex, newIndex))


class _FakeValueParam:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value


class _FakeManagedVisibilityParam:
    def __init__(self, value=None):
        self._value = value
        self.opts = {}
        self.items = []
        self.setValueCalls = []
        self.limitsCalls = []

    def value(self):
        return self._value

    def setValue(self, value, blockSignal=None):
        self._value = value
        self.setValueCalls.append((value, blockSignal))

    def setOpts(self, **opts):
        self.opts.update(opts)

    def setLimits(self, limits):
        self.opts['limits'] = limits
        self.limitsCalls.append(limits)


class _FakeManagedListOwner:
    def __init__(self, *, names=None):
        self.names = names or {}


class _FakeCreatedManagedItem:
    def __init__(self, name):
        self.name = name


class _FakeVisibilityState:
    def __init__(self, *, showOrigin, showGrid, showPattern, showCircle, showSpiral, showWell):
        self.showOrigin = showOrigin
        self.showGrid = showGrid
        self.showPattern = showPattern
        self.showCircle = showCircle
        self.showSpiral = showSpiral
        self.showWell = showWell


class _FakeTreeChangeBlocker:
    def __init__(self, recorder):
        self.recorder = recorder

    def __enter__(self):
        self.recorder.append('enter')

    def __exit__(self, excType, exc, tb):
        self.recorder.append('exit')


class _FakeSeedTypeParameterController:
    def __init__(self):
        self.changed = object()
        self.blockerCalls = []
        self.parP = _FakeManagedVisibilityParam('Pattern-1')
        self.parO = _FakeManagedVisibilityParam()
        self.parG = _FakeManagedVisibilityParam()
        self.parC = _FakeManagedVisibilityParam()
        self.parS = _FakeManagedVisibilityParam()
        self.parW = _FakeManagedVisibilityParam()

    def treeChangeBlocker(self):
        return _FakeTreeChangeBlocker(self.blockerCalls)


class _FakeGridSeedRefreshState:
    def __init__(self, *, patterns, selectedPattern, visibilityState):
        self.patterns = patterns
        self.selectedPattern = selectedPattern
        self.visibilityState = visibilityState


class _FakeSeedRefreshStateHelper:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def refreshedPatternState(self, seedType, root):
        self.calls.append((seedType, root))
        return self.result


class _FakeSeedRefreshParameterController:
    def __init__(self, *, parTValue='Grid (rolling)', refreshState='refresh-state', parent=None):
        self.parT = _FakeValueParam(parTValue)
        self.seedStateHelper = _FakeSeedRefreshStateHelper(refreshState)
        self._parent = parent

    def parent(self):
        return self._parent


class _FakeSeedTypeRoutingStateHelper:
    def __init__(self, *, visibilityState, isGridSeedType):
        self.visibilityState = visibilityState
        self._isGridSeedType = isGridSeedType
        self.calls = []

    def applySeedType(self, seedType):
        self.calls.append(('applySeedType', seedType))
        return self.visibilityState

    def isGridSeedType(self, seedType):
        self.calls.append(('isGridSeedType', seedType))
        return self._isGridSeedType


class _FakeSeedTypeRoutingController(_FakeSeedTypeParameterController):
    def __init__(self, *, seedType, isGridSeedType, visibilityState):
        super().__init__()
        self.parT = _FakeValueParam(seedType)
        self.seedStateHelper = _FakeSeedTypeRoutingStateHelper(
            visibilityState=visibilityState,
            isGridSeedType=isGridSeedType,
        )
        self.refreshCalls = []

    def refreshPatternList(self, seedType=None):
        self.refreshCalls.append(seedType)


class _FakeWellStateHelper:
    def __init__(self, *, refreshSuccess=True):
        self.calls = []
        self.refreshSuccess = refreshSuccess

    def applySamplingConstraints(self, *, ahd0, dAhd, nAhd):
        self.calls.append(('applySamplingConstraints', ahd0, dAhd, nAhd))

    def refreshHeader(self):
        self.calls.append(('refreshHeader',))
        return self.refreshSuccess

    def refreshHeaderOrRaise(self):
        self.calls.append(('refreshHeader',))
        if not self.refreshSuccess:
            raise RollWellError('bad header')
        return True


class _FakeWellParameterController:
    def __init__(self, *, refreshSuccess=True, errorText='header failed'):
        self.wellStateHelper = _FakeWellStateHelper(refreshSuccess=refreshSuccess)
        self.parA = _FakeValueParam(10.0)
        self.parI = _FakeValueParam(2.5)
        self.parN = _FakeValueParam(8)
        self.well = type('WellState', (), {'errorText': errorText, 'name': 'old-file', 'crs': 'old-crs'})()
        self.calls = []

    def _syncSamplingFieldsFromWell(self):
        self.calls.append('syncSampling')

    def _syncOriginFieldsFromWell(self):
        self.calls.append('syncOrigin')

    def _refreshWellHeader(self, *, showWarning=False):
        self.calls.append(('refreshHeader', showWarning))


class _FakeCircleState:
    def __init__(self, pointCount=12):
        self.radius = None
        self.azi0 = None
        self.dist = None
        self._pointCount = pointCount

    def calcNoPoints(self):
        return self._pointCount


class _FakeCircleParameterController:
    def __init__(self):
        self.circle = _FakeCircleState(pointCount=14)
        self.parR = _FakeValueParam(25.0)
        self.parA = _FakeValueParam(30.0)
        self.parI = _FakeValueParam(5.0)
        self.parN = _FakeValueParam(None)


class _FakeSpiralState:
    def __init__(self, pointCount=18):
        self.radMin = None
        self.radMax = None
        self.radInc = None
        self.azi0 = None
        self.dist = None
        self._pointCount = pointCount

    def calcNoPoints(self):
        return self._pointCount


class _FakeSpiralParameterController:
    def __init__(self):
        self.spiral = _FakeSpiralState(pointCount=21)
        self.parR1 = _FakeValueParam(10.0)
        self.parR2 = _FakeValueParam(40.0)
        self.parDr = _FakeValueParam(2.0)
        self.parA = _FakeValueParam(45.0)
        self.parI = _FakeValueParam(6.5)
        self.parN = _FakeValueParam(None)


class _FakeAxisState:
    def __init__(self):
        self.x = None
        self.y = None

    def setX(self, value):
        self.x = value

    def setY(self, value):
        self.y = value


class _FakeLocalGridParameterController:
    def __init__(self):
        self.binGrid = type('GridState', (), {
            'binSize': _FakeAxisState(),
            'binShift': _FakeAxisState(),
            'stakeOrig': _FakeAxisState(),
            'stakeSize': _FakeAxisState(),
            'fold': None,
        })()
        self.parBx = _FakeValueParam(12.5)
        self.parBy = _FakeValueParam(25.0)
        self.parDx = _FakeValueParam(1.5)
        self.parDy = _FakeValueParam(2.5)
        self.parLx = _FakeValueParam(1001.0)
        self.parLy = _FakeValueParam(2002.0)
        self.parSx = _FakeValueParam(50.0)
        self.parSy = _FakeValueParam(75.0)
        self.parFo = _FakeValueParam(8)


class _FakeGlobalGridParameterController:
    def __init__(self):
        self.binGrid = type('GridState', (), {
            'orig': _FakeAxisState(),
            'scale': _FakeAxisState(),
            'angle': None,
        })()
        self.parOx = _FakeValueParam(123.0)
        self.parOy = _FakeValueParam(456.0)
        self.parSx = _FakeValueParam(1.1)
        self.parSy = _FakeValueParam(0.9)
        self.parAz = _FakeValueParam(33.0)


class _FakeBinAnglesParameterController:
    def __init__(self):
        self.angles = type('AnglesState', (), {
            'azimuthal': _FakeAxisState(),
            'reflection': _FakeAxisState(),
        })()
        self.parAx = _FakeValueParam(330.0)
        self.parAy = _FakeValueParam(30.0)
        self.parIx = _FakeValueParam(5.0)
        self.parIy = _FakeValueParam(45.0)


class _FakeRectOffsetState:
    def __init__(self):
        self.left = None
        self.right = None
        self.top = None
        self.bottom = None

    def setLeft(self, value):
        self.left = value

    def setRight(self, value):
        self.right = value

    def setTop(self, value):
        self.top = value

    def setBottom(self, value):
        self.bottom = value


class _FakeRadialOffsetState:
    def __init__(self):
        self.x = None
        self.y = None

    def setX(self, value):
        self.x = value

    def setY(self, value):
        self.y = value


class _FakeBinOffsetParameterController:
    def __init__(self):
        self.offset = type('OffsetState', (), {
            'rctOffsets': _FakeRectOffsetState(),
            'radOffsets': _FakeRadialOffsetState(),
        })()
        self.parXmin = _FakeValueParam(50.0)
        self.parXmax = _FakeValueParam(-25.0)
        self.parYmin = _FakeValueParam(80.0)
        self.parYmax = _FakeValueParam(-10.0)
        self.parRmin = _FakeValueParam(120.0)
        self.parRmax = _FakeValueParam(40.0)


class _FakeUniqueOffsetState:
    def __init__(self):
        self.apply = None
        self.write = None
        self.dOffset = None
        self.aziSlots = None


class _FakeUniqueOffsetParameterController:
    def __init__(self):
        self.unique = _FakeUniqueOffsetState()
        self.parP = _FakeValueParam(True)
        self.parR = _FakeValueParam(False)
        self.parO = _FakeValueParam(25.0)
        self.parA = _FakeValueParam(7)


class _FakeBinMethodState:
    def __init__(self):
        self.method = None
        self.vint = None


class _FakeBinMethodParameterController:
    def __init__(self):
        self.binning = _FakeBinMethodState()
        self.parM = _FakeValueParam(BinningList[2])
        self.parV = _FakeValueParam(2350.0)


class _FakePlaneState:
    def __init__(self):
        self.anchor = None
        self.azi = None
        self.dip = None


class _FakePlaneParameterController:
    def __init__(self):
        self.plane = _FakePlaneState()
        self.parO = _FakeValueParam(QVector3D(1.0, 2.0, -300.0))
        self.parA = _FakeValueParam(120.0)
        self.parD = _FakeValueParam(15.0)


class _FakeSphereState:
    def __init__(self):
        self.origin = None
        self.radius = None


class _FakeSphereParameterController:
    def __init__(self):
        self.sphere = _FakeSphereState()
        self.parO = _FakeValueParam(QVector3D(10.0, 20.0, -500.0))
        self.parR = _FakeValueParam(250.0)


class _FakeReflectorParameterController:
    def __init__(self):
        self.reflectorValues = None
        self.parP = _FakeValueParam('plane-value')
        self.parS = _FakeValueParam('sphere-value')


class _FakeAnalysisParameterController:
    def __init__(self):
        self.analysisValues = None
        self.parB = _FakeValueParam('area-value')
        self.parA = _FakeValueParam('angles-value')
        self.parM = _FakeValueParam('binning-value')
        self.parO = _FakeValueParam('offset-value')
        self.parU = _FakeValueParam('unique-value')


class _FakeBlockBordersState:
    def __init__(self):
        self.srcBorder = 'original-src'
        self.recBorder = 'original-rec'


class _FakeBlockState:
    def __init__(self):
        self.borders = _FakeBlockBordersState()
        self.templateList = ['old-template']


class _FakeBlockParameterController:
    def __init__(self):
        self.block = _FakeBlockState()
        self.blockValues = None
        self.parS = _FakeValueParam('src-value')
        self.parR = _FakeValueParam('rec-value')
        self.parT = _FakeValueParam(['template-a', 'template-b'])


class _FakeTemplateState:
    def __init__(self):
        self.rollList = ['old-roll']
        self.seedList = ['old-seed']


class _FakeTemplateParameterController:
    def __init__(self):
        self.template = _FakeTemplateState()
        self.templateValues = None
        self.parR = _FakeValueParam(['roll-a', 'roll-b', 'roll-c'])
        self.parS = _FakeValueParam(['seed-a', 'seed-b'])


class _FakeManagedChild:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class _FakeRollListParameterController:
    def __init__(self):
        self.moveList = ['old-plane', 'old-line', 'old-point']
        self._children = {
            'Planes': _FakeManagedChild('plane-value'),
            'Lines': _FakeManagedChild('line-value'),
            'Points': _FakeManagedChild('point-value'),
        }

    def child(self, name):
        return self._children[name]


class _FakeVector3State:
    def __init__(self):
        self.x = None
        self.y = None
        self.z = None

    def setX(self, value):
        self.x = value

    def setY(self, value):
        self.y = value

    def setZ(self, value):
        self.z = value


class _FakeRollRowState:
    def __init__(self):
        self.steps = None
        self.increment = _FakeVector3State()


class _FakeSignalRecorder:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _FakeRollParameterController:
    def __init__(self):
        self.row = _FakeRollRowState()
        self.parN = _FakeValueParam(6)
        self.parX = _FakeValueParam(12.5)
        self.parY = _FakeValueParam(-7.0)
        self.parZ = _FakeValueParam(3.5)
        self.sigValueChanging = _FakeSignalRecorder()
        self.calls = []

    def value(self):
        return self.row

    def setAzimuth(self):
        self.calls.append('azimuth')

    def setTilt(self):
        self.calls.append('tilt')


class _FakePatternSeedState:
    def __init__(self):
        self.color = None
        self.origin = None
        self.grid = type('GridState', (), {'growList': None})()


class _FakePatternSeedParameterController:
    def __init__(self):
        self.seed = _FakePatternSeedState()
        self.parL = _FakeValueParam('seed-color')
        self.parO = _FakeValueParam('seed-origin')
        self.parG = _FakeValueParam(['grow-a', 'grow-b', 'grow-c'])


class _FakeConfigurationSurveyState:
    def __init__(self):
        self.crs = 'old-crs'
        self.type = type('SurveyTypeState', (), {'name': 'Orthogonal'})()
        self.name = 'Old-Survey'


class _FakeConfigurationParameterController:
    def __init__(self):
        self.survey = _FakeConfigurationSurveyState()
        self.configurationValues = None
        self.parC = _FakeValueParam('new-crs')
        self.parT = _FakeValueParam('Marine')
        self.parN = _FakeValueParam('Renamed-Survey')


def _isParameterVisible(param):
    return param.opts.get('visible', True)


class MySeedParameterVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.qgisApp, _, _, self.parent = getQgisApp()
        self.survey = createTestSurvey()
        self.survey.patternList = [RollPattern('Pattern-1')]

        self.seed = RollSeed('Seed-1')
        self.parameter = MySeedParameter(name='Seed-1', value=self.seed, survey=self.survey)
        self.tree = ParameterTree(parent=self.parent)
        self.tree.setParameters(self.parameter, showTop=False)
        self.qgisApp.processEvents()

    def tearDown(self):
        self.tree.clear()
        self.tree.deleteLater()
        self.parameter = None
        self.qgisApp.processEvents()

    def testSeedPatternOnlyVisibleForGridSeeds(self):
        self.assertTrue(_isParameterVisible(self.parameter.parP))
        self.assertEqual(self.parameter.seed.type, SeedType.rollingGrid)

        self.parameter.parP.setValue('Pattern-1')
        self.qgisApp.processEvents()
        self.assertEqual(self.parameter.seed.patternNo, 0)

        self.parameter.parT.setValue('Circle')
        self.qgisApp.processEvents()

        self.assertEqual(self.parameter.seed.type, SeedType.circle)
        self.assertEqual(self.parameter.seed.patternNo, -1)
        self.assertEqual(self.parameter.parP.value(), '<None>')
        self.assertFalse(_isParameterVisible(self.parameter.parP))

        self.parameter.parT.setValue('Grid (stationary)')
        self.qgisApp.processEvents()

        self.assertEqual(self.parameter.seed.type, SeedType.fixedGrid)
        self.assertTrue(_isParameterVisible(self.parameter.parP))
        self.assertEqual(self.parameter.parP.value(), '<None>')

    def testRefreshPatternListKeepsSelectedPatternForGridSeed(self):
        patternTwo = RollPattern('Pattern-2')
        self.survey.patternList.append(patternTwo)
        self.parameter.seed.patternNo = 1

        self.parameter.refreshPatternList(seedType='Grid (stationary)')
        self.qgisApp.processEvents()

        self.assertEqual(self.parameter.parP.opts['limits'], ['<None>', 'Pattern-1', 'Pattern-2'])
        self.assertEqual(self.parameter.parP.value(), 'Pattern-2')
        self.assertTrue(_isParameterVisible(self.parameter.parP))


class MyPatternSeedParameterTest(unittest.TestCase):
    def setUp(self):
        self.qgisApp, _, _, self.parent = getQgisApp()
        self.seed = RollSeed('PatternSeed-1')
        self.parameter = MyPatternSeedParameter(name='PatternSeed-1', value=self.seed)
        self.tree = ParameterTree(parent=self.parent)
        self.tree.setParameters(self.parameter, showTop=False)
        self.qgisApp.processEvents()

    def tearDown(self):
        self.tree.clear()
        self.tree.deleteLater()
        self.parameter = None
        self.qgisApp.processEvents()

    def testSharedSeedRowsUpdateBackingSeed(self):
        newColor = QColor('#ff0000')
        newOrigin = QVector3D(10.0, 20.0, 30.0)

        self.parameter.parL.setValue(newColor)
        self.parameter.parO.parX.setValue(newOrigin.x())
        self.parameter.parO.parY.setValue(newOrigin.y())
        self.parameter.parO.parZ.setValue(newOrigin.z())
        self.parameter.parG.child('Planes', 'N').setValue(3)
        self.qgisApp.processEvents()

        self.assertEqual(self.parameter.seed.color.name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(self.parameter.seed.origin, newOrigin)
        self.assertEqual(self.parameter.seed.grid.growList[0].steps, 3)


class MyParameterPreviewSummaryHelperTest(unittest.TestCase):
    def testAppendNewManagedParameterItemAllocatesNameAndAppendsCreatedValue(self):
        parentParam = _FakeManagedListOwner(names={'Template-1': object()})
        managedList = []
        appendedCalls = []

        created = appendNewManagedParameterItem(
            parentParam,
            managedList,
            baseName='Template',
            createValue=_FakeCreatedManagedItem,
            childFactory=lambda childName, childValue: {'name': childName, 'value': childValue},
            appendItemFn=lambda parent, itemList, value, **kwargs: appendedCalls.append((parent, itemList, value, kwargs)),
        )

        self.assertEqual(created.name, 'Template-2')
        self.assertEqual(len(appendedCalls), 1)
        parent, itemList, value, kwargs = appendedCalls[0]
        self.assertIs(parent, parentParam)
        self.assertIs(itemList, managedList)
        self.assertIs(value, created)
        self.assertEqual(kwargs['name'], 'Template-2')
        self.assertEqual(kwargs['menuName'], 'addNew')
        self.assertIsNone(kwargs['afterAppend'])
        self.assertEqual(kwargs['childFactory']('Template-2', created), {'name': 'Template-2', 'value': created})

    def testAppendNewManagedParameterItemPassesExplicitMenuNameAndAfterAppend(self):
        parentParam = _FakeManagedListOwner(names={})
        managedList = []
        appendedCalls = []
        afterAppend = object()

        appendNewManagedParameterItem(
            parentParam,
            managedList,
            baseName='Pattern',
            createValue=_FakeCreatedManagedItem,
            childFactory=lambda childName, childValue: {'name': childName, 'value': childValue},
            menuName='context-add',
            afterAppend=afterAppend,
            appendItemFn=lambda parent, itemList, value, **kwargs: appendedCalls.append(kwargs),
        )

        self.assertEqual(appendedCalls[0]['name'], 'Pattern-1')
        self.assertEqual(appendedCalls[0]['menuName'], 'context-add')
        self.assertIs(appendedCalls[0]['afterAppend'], afterAppend)

    def testApplyCircleParametersUpdatesGeometryAndPointCount(self):
        circleParam = _FakeCircleParameterController()

        applyCircleParameters(circleParam)

        self.assertEqual(circleParam.circle.radius, 25.0)
        self.assertEqual(circleParam.circle.azi0, 30.0)
        self.assertEqual(circleParam.circle.dist, 5.0)
        self.assertEqual(circleParam.parN.value(), 14)

    def testApplySpiralParametersUpdatesGeometryAndPointCount(self):
        spiralParam = _FakeSpiralParameterController()

        applySpiralParameters(spiralParam)

        self.assertEqual(spiralParam.spiral.radMin, 10.0)
        self.assertEqual(spiralParam.spiral.radMax, 40.0)
        self.assertEqual(spiralParam.spiral.radInc, 2.0)
        self.assertEqual(spiralParam.spiral.azi0, 45.0)
        self.assertEqual(spiralParam.spiral.dist, 6.5)
        self.assertEqual(spiralParam.parN.value(), 21)

    def testApplyLocalGridParametersUpdatesGridFields(self):
        localGridParam = _FakeLocalGridParameterController()

        applyLocalGridParameters(localGridParam)

        self.assertEqual(localGridParam.binGrid.binSize.x, 12.5)
        self.assertEqual(localGridParam.binGrid.binSize.y, 25.0)
        self.assertEqual(localGridParam.binGrid.binShift.x, 1.5)
        self.assertEqual(localGridParam.binGrid.binShift.y, 2.5)
        self.assertEqual(localGridParam.binGrid.stakeOrig.x, 1001.0)
        self.assertEqual(localGridParam.binGrid.stakeOrig.y, 2002.0)
        self.assertEqual(localGridParam.binGrid.stakeSize.x, 50.0)
        self.assertEqual(localGridParam.binGrid.stakeSize.y, 75.0)
        self.assertEqual(localGridParam.binGrid.fold, 8)

    def testApplyGlobalGridParametersUpdatesGridFields(self):
        globalGridParam = _FakeGlobalGridParameterController()

        applyGlobalGridParameters(globalGridParam)

        self.assertEqual(globalGridParam.binGrid.orig.x, 123.0)
        self.assertEqual(globalGridParam.binGrid.orig.y, 456.0)
        self.assertEqual(globalGridParam.binGrid.scale.x, 1.1)
        self.assertEqual(globalGridParam.binGrid.scale.y, 0.9)
        self.assertEqual(globalGridParam.binGrid.angle, 33.0)

    def testApplyBinAnglesParametersUpdatesAngleRanges(self):
        binAnglesParam = _FakeBinAnglesParameterController()

        applyBinAnglesParameters(binAnglesParam)

        self.assertEqual(binAnglesParam.angles.azimuthal.x, 330.0)
        self.assertEqual(binAnglesParam.angles.azimuthal.y, 30.0)
        self.assertEqual(binAnglesParam.angles.reflection.x, 5.0)
        self.assertEqual(binAnglesParam.angles.reflection.y, 45.0)

    def testApplyBinOffsetParametersNormalizesOffsetRanges(self):
        binOffsetParam = _FakeBinOffsetParameterController()

        applyBinOffsetParameters(binOffsetParam)

        self.assertEqual(binOffsetParam.offset.rctOffsets.left, -25.0)
        self.assertEqual(binOffsetParam.offset.rctOffsets.right, 50.0)
        self.assertEqual(binOffsetParam.offset.rctOffsets.top, -10.0)
        self.assertEqual(binOffsetParam.offset.rctOffsets.bottom, 80.0)
        self.assertEqual(binOffsetParam.offset.radOffsets.x, 40.0)
        self.assertEqual(binOffsetParam.offset.radOffsets.y, 120.0)

    def testApplyUniqueOffsetParametersUpdatesPruningState(self):
        uniqueOffsetParam = _FakeUniqueOffsetParameterController()

        applyUniqueOffsetParameters(uniqueOffsetParam)

        self.assertTrue(uniqueOffsetParam.unique.apply)
        self.assertFalse(uniqueOffsetParam.unique.write)
        self.assertEqual(uniqueOffsetParam.unique.dOffset, 25.0)
        self.assertEqual(uniqueOffsetParam.unique.aziSlots, 7)

    def testApplyBinMethodParametersMapsSelectedMethodAndVelocity(self):
        binMethodParam = _FakeBinMethodParameterController()

        applyBinMethodParameters(binMethodParam)

        self.assertEqual(binMethodParam.binning.method, BinningType.sphere)
        self.assertEqual(binMethodParam.binning.vint, 2350.0)

    def testApplyPlaneParametersUpdatesPlaneFields(self):
        planeParam = _FakePlaneParameterController()

        applyPlaneParameters(planeParam)

        self.assertEqual(planeParam.plane.anchor, QVector3D(1.0, 2.0, -300.0))
        self.assertEqual(planeParam.plane.azi, 120.0)
        self.assertEqual(planeParam.plane.dip, 15.0)

    def testApplySphereParametersUpdatesSphereFields(self):
        sphereParam = _FakeSphereParameterController()

        applySphereParameters(sphereParam)

        self.assertEqual(sphereParam.sphere.origin, QVector3D(10.0, 20.0, -500.0))
        self.assertEqual(sphereParam.sphere.radius, 250.0)

    def testApplyReflectorParametersUpdatesTupleState(self):
        reflectorsParam = _FakeReflectorParameterController()

        applyReflectorParameters(reflectorsParam)

        self.assertEqual(reflectorsParam.reflectorValues.asTuple(), ('plane-value', 'sphere-value'))

    def testApplyAnalysisParametersUpdatesTupleState(self):
        analysisParam = _FakeAnalysisParameterController()

        applyAnalysisParameters(analysisParam)

        self.assertEqual(
            analysisParam.analysisValues.asTuple(),
            ('area-value', 'angles-value', 'binning-value', 'offset-value', 'unique-value'),
        )

    def testApplyBlockParametersUpdatesTupleStateAndBackingBlock(self):
        blockParam = _FakeBlockParameterController()

        applyBlockParameters(blockParam)

        self.assertEqual(
            blockParam.blockValues.asTuple(),
            ('src-value', 'rec-value', ['template-a', 'template-b']),
        )
        self.assertEqual(blockParam.block.borders.srcBorder, 'src-value')
        self.assertEqual(blockParam.block.borders.recBorder, 'rec-value')
        self.assertEqual(blockParam.block.templateList, ['template-a', 'template-b'])

    def testApplyTemplateParametersUpdatesTupleStateAndBackingTemplate(self):
        templateParam = _FakeTemplateParameterController()

        applyTemplateParameters(templateParam)

        self.assertEqual(
            templateParam.templateValues.asTuple(),
            (['roll-a', 'roll-b', 'roll-c'], ['seed-a', 'seed-b']),
        )
        self.assertEqual(templateParam.template.rollList, ['roll-a', 'roll-b', 'roll-c'])
        self.assertEqual(templateParam.template.seedList, ['seed-a', 'seed-b'])

    def testApplyRollListParametersUpdatesMoveListFromCurrentChildren(self):
        rollListParam = _FakeRollListParameterController()

        applyRollListParameters(rollListParam)

        self.assertEqual(rollListParam.moveList, ['plane-value', 'line-value', 'point-value'])

    def testApplyRollParameterIncrementUpdatesVectorAndRefreshesAngles(self):
        rollParam = _FakeRollParameterController()

        applyRollParameterIncrement(rollParam)

        self.assertEqual(rollParam.row.increment.x, 12.5)
        self.assertEqual(rollParam.row.increment.y, -7.0)
        self.assertEqual(rollParam.row.increment.z, 3.5)
        self.assertEqual(rollParam.calls, ['azimuth', 'tilt'])

    def testApplyRollParameterStepCountUpdatesStepsAndEmitsValueChange(self):
        rollParam = _FakeRollParameterController()

        applyRollParameterStepCount(rollParam)

        self.assertEqual(rollParam.row.steps, 6)
        self.assertEqual(rollParam.sigValueChanging.calls, [(rollParam, rollParam.row)])

    def testApplyPatternSeedParameterValuesUpdatesSeedFields(self):
        patternSeedParam = _FakePatternSeedParameterController()

        applyPatternSeedParameterValues(patternSeedParam)

        self.assertEqual(patternSeedParam.seed.color, 'seed-color')
        self.assertEqual(patternSeedParam.seed.origin, 'seed-origin')
        self.assertEqual(patternSeedParam.seed.grid.growList, ['grow-a', 'grow-b', 'grow-c'])

    def testApplyConfigurationParameterValuesUpdatesTupleStateAndSurvey(self):
        configurationParam = _FakeConfigurationParameterController()

        applyConfigurationParameterValues(configurationParam)

        self.assertEqual(configurationParam.configurationValues.asTuple(), ('new-crs', 'Marine', 'Renamed-Survey'))
        self.assertEqual(configurationParam.survey.crs, 'new-crs')
        self.assertEqual(configurationParam.survey.type.name, 'Marine')
        self.assertEqual(configurationParam.survey.name, 'Renamed-Survey')

    def testApplyNonGridSeedTypeStateClearsPatternAndUpdatesVisibility(self):
        seedParam = _FakeSeedTypeParameterController()
        visibilityState = _FakeVisibilityState(
            showOrigin=True,
            showGrid=False,
            showPattern=False,
            showCircle=True,
            showSpiral=False,
            showWell=False,
        )

        applyNonGridSeedTypeState(seedParam, visibilityState)

        self.assertEqual(seedParam.blockerCalls, ['enter', 'exit'])
        self.assertEqual(seedParam.parP.value(), '<None>')
        self.assertEqual(seedParam.parP.setValueCalls, [('<None>', seedParam.changed)])
        self.assertTrue(seedParam.parO.opts['visible'])
        self.assertFalse(seedParam.parG.opts['visible'])
        self.assertFalse(seedParam.parP.opts['visible'])
        self.assertTrue(seedParam.parC.opts['visible'])
        self.assertFalse(seedParam.parS.opts['visible'])
        self.assertFalse(seedParam.parW.opts['visible'])

    def testApplyGridSeedPatternRefreshUpdatesPatternLimitsSelectionAndVisibility(self):
        seedParam = _FakeSeedTypeParameterController()
        refreshState = _FakeGridSeedRefreshState(
            patterns=['<None>', 'Pattern-1', 'Pattern-2'],
            selectedPattern='Pattern-2',
            visibilityState=_FakeVisibilityState(
                showOrigin=True,
                showGrid=True,
                showPattern=True,
                showCircle=False,
                showSpiral=False,
                showWell=False,
            ),
        )

        applyGridSeedPatternRefresh(seedParam, refreshState)

        self.assertEqual(seedParam.parP.limitsCalls, [['<None>', 'Pattern-1', 'Pattern-2']])
        self.assertEqual(seedParam.parP.value(), 'Pattern-2')
        self.assertEqual(seedParam.parP.setValueCalls, [('Pattern-2', seedParam.changed)])
        self.assertTrue(seedParam.parO.opts['visible'])
        self.assertTrue(seedParam.parG.opts['visible'])
        self.assertTrue(seedParam.parP.opts['visible'])
        self.assertFalse(seedParam.parC.opts['visible'])
        self.assertFalse(seedParam.parS.opts['visible'])
        self.assertFalse(seedParam.parW.opts['visible'])

    def testResolveGridSeedPatternRefreshStateUsesExplicitSeedTypeAndRoot(self):
        root = _FakeTreeNode(name='root')
        branch = _FakeTreeNode(name='branch', parent=root)
        seedParam = _FakeSeedRefreshParameterController(parent=branch)

        refreshState = resolveGridSeedPatternRefreshState(seedParam, seedType='Grid (stationary)')

        self.assertEqual(refreshState, 'refresh-state')
        self.assertEqual(seedParam.seedStateHelper.calls, [('Grid (stationary)', root)])

    def testResolveGridSeedPatternRefreshStateFallsBackToCurrentSeedType(self):
        root = _FakeTreeNode(name='root')
        seedParam = _FakeSeedRefreshParameterController(parTValue='Circle', parent=root)

        refreshState = resolveGridSeedPatternRefreshState(seedParam)

        self.assertEqual(refreshState, 'refresh-state')
        self.assertEqual(seedParam.seedStateHelper.calls, [('Circle', root)])

    def testApplySeedTypeChangeRoutesGridSeedTypesToRefresh(self):
        visibilityState = _FakeVisibilityState(
            showOrigin=True,
            showGrid=True,
            showPattern=True,
            showCircle=False,
            showSpiral=False,
            showWell=False,
        )
        seedParam = _FakeSeedTypeRoutingController(
            seedType='Grid (stationary)',
            isGridSeedType=True,
            visibilityState=visibilityState,
        )

        applySeedTypeChange(seedParam)

        self.assertEqual(
            seedParam.seedStateHelper.calls,
            [('applySeedType', 'Grid (stationary)'), ('isGridSeedType', 'Grid (stationary)')],
        )
        self.assertEqual(seedParam.refreshCalls, ['Grid (stationary)'])
        self.assertEqual(seedParam.parP.setValueCalls, [])

    def testApplySeedTypeChangeRoutesNonGridSeedTypesToVisibilityHelper(self):
        visibilityState = _FakeVisibilityState(
            showOrigin=True,
            showGrid=False,
            showPattern=False,
            showCircle=True,
            showSpiral=False,
            showWell=False,
        )
        seedParam = _FakeSeedTypeRoutingController(
            seedType='Circle',
            isGridSeedType=False,
            visibilityState=visibilityState,
        )

        applySeedTypeChange(seedParam)

        self.assertEqual(
            seedParam.seedStateHelper.calls,
            [('applySeedType', 'Circle'), ('isGridSeedType', 'Circle')],
        )
        self.assertEqual(seedParam.refreshCalls, [])
        self.assertEqual(seedParam.blockerCalls, ['enter', 'exit'])
        self.assertEqual(seedParam.parP.setValueCalls, [('<None>', seedParam.changed)])
        self.assertFalse(seedParam.parP.opts['visible'])
        self.assertTrue(seedParam.parC.opts['visible'])

    def testApplyWellSamplingFromParametersUsesLiveFieldValues(self):
        wellParam = _FakeWellParameterController()

        applyWellSamplingFromParameters(wellParam)

        self.assertEqual(wellParam.wellStateHelper.calls, [('applySamplingConstraints', 10.0, 2.5, 8)])
        self.assertEqual(wellParam.calls, ['syncSampling'])

    def testApplyWellHeaderParameterChangeUpdatesFieldRefreshesHeaderAndProcessesEvents(self):
        wellParam = _FakeWellParameterController()

        applyWellHeaderParameterChange(
            wellParam,
            attributeName='name',
            value='new-file.wws',
            showWarning=False,
        )

        self.assertEqual(wellParam.well.name, 'new-file.wws')
        self.assertEqual(wellParam.calls, [('refreshHeader', False)])

    def testRefreshWellHeaderFromParameterRefreshesOriginsAndSamplingOnSuccess(self):
        wellParam = _FakeWellParameterController(refreshSuccess=True)

        success = refreshWellHeaderFromParameter(wellParam)

        self.assertTrue(success)
        self.assertEqual(
            wellParam.wellStateHelper.calls,
            [('refreshHeader',), ('applySamplingConstraints', 10.0, 2.5, 8)],
        )
        self.assertEqual(wellParam.calls, ['syncOrigin', 'syncSampling'])

    def testRefreshWellHeaderFromParameterWarnsOnFailureWhenRequested(self):
        wellParam = _FakeWellParameterController(refreshSuccess=False, errorText='bad header')
        warningCalls = []

        success = refreshWellHeaderFromParameter(
            wellParam,
            showWarning=True,
            warningHandler=lambda parent, title, text: warningCalls.append((parent, title, text)),
        )

        self.assertFalse(success)
        self.assertEqual(wellParam.wellStateHelper.calls, [('refreshHeader',)])
        self.assertEqual(wellParam.calls, ['syncOrigin'])
        self.assertEqual(warningCalls, [(None, 'Well Seed error', 'bad header')])

    def testApplyPatternListSideEffectsRunsSyncThenRefresh(self):
        patternListParam = _FakePatternListParam()

        applyPatternListSideEffects(patternListParam)

        self.assertEqual(patternListParam.calls, [('sync',), ('refresh',)])

    def testApplyPatternRemovalSideEffectsUpdatesIndicesThenRefreshes(self):
        patternListParam = _FakePatternListParam()

        applyPatternRemovalSideEffects(patternListParam, 3)

        self.assertEqual(patternListParam.calls, [('remove', 3), ('sync',), ('refresh',)])

    def testApplyPatternMoveSideEffectsUpdatesIndicesThenRefreshes(self):
        patternListParam = _FakePatternListParam()

        applyPatternMoveSideEffects(patternListParam, 1, 2)

        self.assertEqual(patternListParam.calls, [('swap', 1, 2), ('sync',), ('refresh',)])

    def testFindParameterTreeRootClimbsToTopParameter(self):
        seedParam = _FakePatternSeedParam('Seed-A')
        seedList = _FakeTreeNode(name='Seed list', iterableChildren=[seedParam])
        template = _FakeTreeNode(name='Template-A', children={'Seed list': seedList})
        templateList = _FakeTreeNode(name='Template list', iterableChildren=[template])
        block = _FakeTreeNode(name='Block-A', children={'Template list': templateList})
        root = _FakeTreeNode(name='Root', children={'Block list': _FakeTreeNode(name='Block list', iterableChildren=[block])})

        self.assertIs(findParameterTreeRoot(seedParam), root)

    def testIterTemplateSeedParametersYieldsNestedTemplateSeeds(self):
        seedA = _FakePatternSeedParam('Seed-A')
        seedB = _FakePatternSeedParam('Seed-B')
        templateOne = _FakeTreeNode(name='Template-A', children={'Seed list': _FakeTreeNode(name='Seed list', iterableChildren=[seedA])})
        templateTwo = _FakeTreeNode(name='Template-B', children={'Seed list': _FakeTreeNode(name='Seed list', iterableChildren=[seedB])})
        blockOne = _FakeTreeNode(name='Block-A', children={'Template list': _FakeTreeNode(name='Template list', iterableChildren=[templateOne])})
        blockTwo = _FakeTreeNode(name='Block-B', children={'Template list': _FakeTreeNode(name='Template list', iterableChildren=[templateTwo])})
        root = _FakeTreeNode(name='Root', children={'Block list': _FakeTreeNode(name='Block list', iterableChildren=[blockOne, blockTwo])})

        self.assertEqual([seed.name for seed in iterTemplateSeedParameters(root)], ['Seed-A', 'Seed-B'])

    def testFormatPreviewCountLabelUsesEmptyTextForZero(self):
        self.assertEqual(formatPreviewCountLabel(0, 'pattern seed', emptyText='No pattern seeds'), 'No pattern seeds')

    def testFormatPreviewCountLabelFormatsNonZeroCount(self):
        self.assertEqual(formatPreviewCountLabel(3, 'pattern seed', emptyText='No pattern seeds'), '3 pattern seed(s)')

    def testFormatPreviewPointSummaryWithoutDetails(self):
        self.assertEqual(formatPreviewPointSummary(12), '12 points')

    def testFormatPreviewPointSummaryWithDecimalsAndDetails(self):
        summary = formatPreviewPointSummary(12.3456, decimals=3, details=('o12.3m', 'd5.68m'))

        self.assertEqual(summary, '12.3 points, o12.3m, d5.68m')

    def testPreviewSeedShotCountAppliesRollAlongMultiplierForSourceSeed(self):
        seed = _makeSeed(seedType='Grid (roll along)', source=True, grid=(2, 3, 4))
        rollSteps = _makeGridSteps(5, 1, 2)

        self.assertEqual(previewSeedShotCount(seed, rollStepParam=rollSteps, sourceOnly=True), 240)

    def testPreviewTemplateSourceSummaryCountsAllSeedsAndOnlySourceShots(self):
        template = _makeTemplate([
            _makeSeed(seedType='Grid (stationary)', source=False, grid=(9, 9, 9)),
            _makeSeed(seedType='Circle', source=True, circle=6),
            _makeSeed(seedType='Grid (roll along)', source=True, grid=(2, 2, 2)),
        ], roll=(3, 1, 1))

        self.assertEqual(previewTemplateSourceSummary(template), (3, 30))

    def testPreviewBlockSourceSummaryAggregatesTemplateShots(self):
        block = _makeBlock([
            _makeTemplate([_makeSeed(seedType='Circle', source=True, circle=5)]),
            _makeTemplate([_makeSeed(seedType='Well', source=True, well=7), _makeSeed(seedType='Grid (stationary)', source=False, grid=(8, 8, 8))]),
        ])

        self.assertEqual(previewBlockSourceSummary(block), (2, 12))

    def testPreviewSeedListCompositionSummaryReturnsEmptyState(self):
        self.assertEqual(previewSeedListCompositionSummary(_FakeSeedListNode([])), ('No seeds', True))

    def testPreviewSeedListCompositionSummaryCountsSourceAndReceiverSeeds(self):
        seedList = _FakeSeedListNode([
            _FakeSeedListChild(True),
            _FakeSeedListChild(False),
            _FakeSeedListChild(False),
        ])

        self.assertEqual(previewSeedListCompositionSummary(seedList), ('1 src seed(s) + 2 rec seed(s)', False))

    def testPreviewWellSummaryUsesErrorTextWhenPresent(self):
        param = _FakeWellPreviewParam(fileValue='C:/tmp/test.wws', ahdInterval=5.0, points=12, errorText='header failed')

        self.assertEqual(previewWellSummary(param, pathExists=lambda _: True), ('header failed', True))

    def testPreviewWellSummaryFormatsValidFileSummary(self):
        param = _FakeWellPreviewParam(fileValue='C:/tmp/test.wws', ahdInterval=5.0, points=12.25, decimals=3)

        self.assertEqual(previewWellSummary(param, pathExists=lambda _: True), ('12.2 points, in test.wws, d5m', False))

    def testPreviewWellSummaryFlagsMissingFilePath(self):
        param = _FakeWellPreviewParam(fileValue='C:/tmp/missing.wws', ahdInterval=5.0, points=12)

        self.assertEqual(previewWellSummary(param, pathExists=lambda _: False), ('No valid well file selected', True))


if __name__ == '__main__':
    unittest.main()
