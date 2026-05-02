import contextlib
import math
import os

from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtCore import QFileInfo
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from .aux_functions import myPrint
from .enums_and_int_flags import SurveyType
from .my_cmap import MyCmapParameter
from .my_crs import MyCrsParameter
from .my_crs2 import MyCrs2Parameter
from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_list import MyListParameter
from .my_marker import MyMarkerParameter
from .my_n_vector import MyNVectorParameter
from .my_numerics import MyFloatParameter, MyIntParameter
from .my_pen import MyPenParameter
from .my_point2D import MyPoint2DParameter
from .my_point3D import MyPoint3DParameter
from .my_range import MyRangeParameter
from .my_rectf import MyRectParameter
from .my_slider import MySliderParameter
from .my_symbols import MySymbolParameter
from .my_vector import MyVectorParameter
from .parameter_aggregate_helpers import (analysisValuesFromParameters,
                                          analysisValuesFromSurvey,
                                          applyBlockValues,
                                          applyConfigurationValues,
                                          applyGlobalGridValues,
                                          applyLocalGridValues,
                                          applyTemplateValues,
                                          blockValuesFromBlock,
                                          configurationValuesFromSurvey,
                                          reflectorValuesFromParameters,
                                          reflectorValuesFromSurvey,
                                          templateValuesFromTemplate)
from .parameter_creation_helpers import (createAppendedTemplateSeed,
                                         createDefaultBlock,
                                         createDefaultTemplate)
from .parameter_list_helpers import (appendManagedParameterItem,
                                     moveManagedParameterItem,
                                     nextManagedChildName,
                                     removeManagedParameterItem,
                                     swapManagedParameterItems)
from .parameter_seed_well_helpers import (SeedParameterStateHelper,
                                          WellParameterStateHelper)
from .roll_angles import RollAngles
from .roll_bingrid import RollBinGrid
from .roll_binning import BinningList, BinningType, RollBinning
from .roll_block import RollBlock
from .roll_circle import RollCircle
from .roll_offset import RollOffset
from .roll_pattern import RollPattern
from .roll_pattern_seed import RollPatternSeed
from .roll_plane import RollPlane
from .roll_seed import RollSeed
from .roll_sphere import RollSphere
from .roll_spiral import RollSpiral
from .roll_survey import RollSurvey
from .roll_template import RollTemplate
from .roll_translate import RollTranslate
from .roll_unique import RollUnique
from .roll_well import RollWell

# This file contains a collections of parameters, as defined in pyQtGraph
# See: https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/parametertree/Parameter.html

# the following signals have been pre-defined for parameter objects:
#
# sigStateChanged(self, change, info)  Emitted when anything changes about this parameter at all.
#                                      The second argument is a string indicating what changed
#                                      ('value', 'childAdded', etc..)
#                                      The third argument can be any extra information about the change
# sigTreeStateChanged(self, changes)   Emitted when any child in the tree changes state
#                                      (but only if monitorChildren() is called)
#                                      the format of *changes* is [(param, change, info), ...]
# sigValueChanged(self, value)         Emitted when value is finished changing
# sigValueChanging(self, value)        Emitted immediately for all value changes, including during editing.
# sigChildAdded(self, child, index)    Emitted when a child is added
# sigChildRemoved(self, child)         Emitted when a child is removed
# sigRemoved(self)                     Emitted when this parameter is removed
# sigParentChanged(self, parent)       Emitted when this parameter's parent has changed
# sigLimitsChanged(self, limits)       Emitted when this parameter's limits have changed
# sigDefaultChanged(self, default)     Emitted when this parameter's default value has changed
# sigNameChanged(self, name)           Emitted when this parameter's name has changed
# sigOptionsChanged(self, opts)        Emitted when any of this parameter's options have changed
# sigContextMenu(self, name)           Emitted when a context menu was clicked

# These signals contain the following objects/information:
#
# sigValueChanged     = QtCore.Signal(object, object)                # self, value  emitted when value is finished being edited
# sigValueChanging    = QtCore.Signal(object, object)                # self, value  emitted as value is being edited
# sigChildAdded       = QtCore.Signal(object, object, object)        # self, child, index
# sigChildRemoved     = QtCore.Signal(object, object)                # self, child
# sigRemoved          = QtCore.Signal(object)                        # self
# sigParentChanged    = QtCore.Signal(object, object)                # self, parent
# sigLimitsChanged    = QtCore.Signal(object, object)                # self, limits
# sigDefaultChanged   = QtCore.Signal(object, object)                # self, default
# sigNameChanged      = QtCore.Signal(object, object)                # self, name
# sigOptionsChanged   = QtCore.Signal(object, object)                # self, {opt:val, ...}
# sigStateChanged     = QtCore.Signal(object, object, object)        # self, change, info
# sigTreeStateChanged = QtCore.Signal(object, object)                # self, changes
#                                                                    # changes = [(param, change, info), ...]


def bindChildParameters(owner, childBindings):
    for attrName, path in childBindings.items():
        if isinstance(path, (tuple, list)):
            child = owner.child(*path)
        else:
            child = owner.child(path)
        setattr(owner, attrName, child)


def connectValueChangedSignals(signalBindings):
    for param, handler in signalBindings:
        param.sigValueChanged.connect(handler)


def connectTreeStateChangedSignals(signalBindings):
    for param, handler in signalBindings:
        param.sigTreeStateChanged.connect(handler)


def addPreviewAngleIntervalPointChildren(owner, *, angleValue, distanceValue, pointsValue, decimals, distanceSuffix, tip, distanceDecimals=None):
    owner.addChild(dict(name='Start angle', value=angleValue, default=angleValue, type='float', decimals=decimals, suffix='°E', tip=tip))

    pointIntervalOpts = dict(name='Point interval', value=distanceValue, default=distanceValue, type='float', suffix=distanceSuffix, tip=tip)
    if distanceDecimals is not None:
        pointIntervalOpts['decimals'] = distanceDecimals
    owner.addChild(pointIntervalOpts)

    owner.addChild(dict(name='Points', value=pointsValue, default=pointsValue, type='myInt', decimals=decimals, enabled=False, readonly=True))


def bindPreviewAngleIntervalPointChildren(owner):
    bindChildParameters(owner, {
        'parA': 'Start angle',
        'parI': 'Point interval',
        'parN': 'Points',
    })


def addSeedColorOriginGridChildren(owner, seed, *, decimals):
    owner.addChild(dict(name='Seed color', type='color', value=seed.color, default=seed.color))
    owner.addChild(dict(name='Seed origin', type='myPoint3D', value=seed.origin, default=seed.origin, expanded=False, flat=True, decimals=decimals))
    owner.addChild(dict(name='Grid grow steps', type='myRollList', value=seed.grid.growList, default=seed.grid.growList, expanded=True, flat=True, decimals=decimals, suffix='m', brush='#add8e6'))


def bindSeedColorOriginGridChildren(owner):
    bindChildParameters(owner, {
        'parL': 'Seed color',
        'parO': 'Seed origin',
        'parG': 'Grid grow steps',
    })


def connectSeedColorOriginGridChangedSignals(owner, handler):
    connectValueChangedSignals([
        (owner.parL, handler),
        (owner.parO, handler),
        (owner.parG, handler),
    ])


def formatPreviewPointSummary(points, *, decimals=None, details=None):
    pointText = f'{points:.{decimals}g}' if decimals is not None else f'{points}'
    summary = f'{pointText} points'

    if details:
        if isinstance(details, (tuple, list)):
            details = ', '.join(part for part in details if part)
        if details:
            summary = f'{summary}, {details}'

    return summary


def previewGridStepPointCount(growStepParam):
    nPlane = growStepParam.child('Planes', 'N').opts['value']
    nLines = growStepParam.child('Lines', 'N').opts['value']
    nPoint = growStepParam.child('Points', 'N').opts['value']
    return nPlane * nLines * nPoint


def previewSeedShotCount(seedParam, *, rollStepParam=None, sourceOnly=False):
    if sourceOnly and not seedParam.child('Source seed').opts['value']:
        return 0

    seedType = seedParam.child('Seed type').opts['value']
    if seedType == 'Circle':
        return seedParam.child('Circle grow steps', 'Points').opts['value']
    if seedType == 'Spiral':
        return seedParam.child('Spiral grow steps', 'Points').opts['value']
    if seedType == 'Well':
        return seedParam.child('Well grow steps', 'Points').opts['value']

    nSeedShots = previewGridStepPointCount(seedParam.child('Grid grow steps'))
    if seedType == 'Grid (roll along)' and rollStepParam is not None:
        nSeedShots *= previewGridStepPointCount(rollStepParam)

    return nSeedShots


def previewTemplateSourceSummary(templateParam):
    seeds = templateParam.child('Seed list')
    nSeeds = 0
    nTemplateShots = 0

    if not seeds.hasChildren():
        return nSeeds, nTemplateShots

    rollStepParam = templateParam.child('Roll steps')
    for seed in seeds:
        nSeeds += 1
        nTemplateShots += previewSeedShotCount(seed, rollStepParam=rollStepParam, sourceOnly=True)

    return nSeeds, nTemplateShots


def previewBlockSourceSummary(blockParam):
    templates = blockParam.child('Template list')
    nTemplates = 0
    nBlockShots = 0

    if not templates.hasChildren():
        return nTemplates, nBlockShots

    for template in templates:
        nTemplates += 1
        _, nTemplateShots = previewTemplateSourceSummary(template)
        nBlockShots += nTemplateShots

    return nTemplates, nBlockShots


def formatPreviewCountLabel(count, noun, *, emptyText):
    if count == 0:
        return emptyText
    return f'{count} {noun}(s)'


def previewSeedListCompositionSummary(seedListParam):
    nChilds = len(seedListParam.childs)
    if nChilds == 0:
        return 'No seeds', True

    nSource = 0
    for child in seedListParam.childs:
        if not isinstance(child, MySeedParameter):
            raise ValueError("Need 'MySeedParameter' instances at this point")
        source = child.names['Source seed'].opts['value']
        if source:
            nSource += 1

    text = f'{nSource} src seed(s) + {nChilds - nSource} rec seed(s)'
    hasError = nSource == 0 or nChilds == nSource
    return text, hasError


def previewWellSummary(wellParam, *, pathExists=os.path.exists):
    f = wellParam.child('Well file').opts['value']
    s = wellParam.child('AHD interval').opts['value']
    n = wellParam.child('Points').opts['value']
    d = wellParam.opts.get('decimals', 3)

    if f is None:
        return 'No valid well file selected', False
    if wellParam.well.errorText is not None:
        return wellParam.well.errorText, True
    if pathExists(f):
        f = QFileInfo(f).fileName()
        return formatPreviewPointSummary(n, decimals=d, details=(f'in {f}', f'd{s:.{d}g}m')), False

    return 'No valid well file selected', True


def setManagedParameterVisibility(param, visible):
    param.setOpts(visible=visible)
    for item in getattr(param, 'items', []):
        item.setHidden(not visible)
        widget = getattr(item, 'widget', None)
        if widget is not None:
            widget.setHidden(not visible)
        itemWidget = getattr(item, 'itemWidget', None)
        if itemWidget is not None:
            itemWidget.setHidden(not visible)


def applySeedVisibilityState(visibilityState, *, originParam, gridParam, patternParam, circleParam, spiralParam, wellParam):
    setManagedParameterVisibility(originParam, visibilityState.showOrigin)
    setManagedParameterVisibility(gridParam, visibilityState.showGrid)
    setManagedParameterVisibility(patternParam, visibilityState.showPattern)
    setManagedParameterVisibility(circleParam, visibilityState.showCircle)
    setManagedParameterVisibility(spiralParam, visibilityState.showSpiral)
    setManagedParameterVisibility(wellParam, visibilityState.showWell)


def applySeedParameterValues(seed, seedStateHelper, *, sourceValue, colorValue, originValue, patternParam, gridGrowList):
    seed.bSource = sourceValue
    seed.color = colorValue
    seed.origin = originValue
    seedStateHelper.selectedPatternIndex(patternParam.opts['limits'], patternParam.value())
    seed.grid.growList = gridGrowList


def applyNonGridSeedTypeState(seedParam, visibilityState):
    with seedParam.treeChangeBlocker():
        seedParam.parP.setValue('<None>', blockSignal=seedParam.changed)

    applySeedVisibilityState(
        visibilityState,
        originParam=seedParam.parO,
        gridParam=seedParam.parG,
        patternParam=seedParam.parP,
        circleParam=seedParam.parC,
        spiralParam=seedParam.parS,
        wellParam=seedParam.parW,
    )


def applyGridSeedPatternRefresh(seedParam, refreshState):
    seedParam.parP.setLimits(refreshState.patterns)
    seedParam.parP.setValue(refreshState.selectedPattern, blockSignal=seedParam.changed)
    applySeedVisibilityState(
        refreshState.visibilityState,
        originParam=seedParam.parO,
        gridParam=seedParam.parG,
        patternParam=seedParam.parP,
        circleParam=seedParam.parC,
        spiralParam=seedParam.parS,
        wellParam=seedParam.parW,
    )


def resolveGridSeedPatternRefreshState(seedParam, seedType=None):
    if seedType is None:
        seedType = seedParam.parT.value()

    return seedParam.seedStateHelper.refreshedPatternState(seedType, findParameterTreeRoot(seedParam))


def applySeedTypeChange(seedParam):
    seedType = seedParam.parT.value()
    visibilityState = seedParam.seedStateHelper.applySeedType(seedType)

    if seedParam.seedStateHelper.isGridSeedType(seedType):
        seedParam.refreshPatternList(seedType=seedType)
    else:
        applyNonGridSeedTypeState(seedParam, visibilityState)


def findParameterTreeRoot(param):
    root = param
    while root is not None and root.parent() is not None:
        root = root.parent()
    return root


def iterParameterTree(param):
    yield param

    for child in param:
        yield from iterParameterTree(child)


def syncWellDirectoryForParameterTree(param, wellDirectory):
    root = findParameterTreeRoot(param)
    if root is None:
        return

    for treeParam in iterParameterTree(root):
        if hasattr(treeParam, 'wellDirectory'):
            treeParam.wellDirectory = wellDirectory

        wellFileParam = getattr(treeParam, 'parF', None)
        if wellFileParam is None or wellFileParam.name() != 'Well file':
            continue

        wellFileParam.opts['directory'] = wellDirectory
        if hasattr(wellFileParam, 'setOpts'):
            wellFileParam.setOpts(directory=wellDirectory)


def iterTemplateSeedParameters(param):
    root = findParameterTreeRoot(param)
    if root is None:
        return

    with contextlib.suppress(KeyError):
        for block in root.child('Block list'):
            for template in block.child('Template list'):
                for seedParam in template.child('Seed list'):
                    yield seedParam


def applyPatternListSideEffects(patternListParam):
    patternListParam._syncSurveyPatternList()
    patternListParam.refreshSeedPatternLists()


def applyPatternRemovalSideEffects(patternListParam, removedIndex):
    patternListParam._removePatternIndex(removedIndex)
    applyPatternListSideEffects(patternListParam)


def applyPatternMoveSideEffects(patternListParam, oldIndex, newIndex):
    patternListParam._swapPatternIndices(oldIndex, newIndex)
    applyPatternListSideEffects(patternListParam)


def applyWellSamplingFromParameters(wellParam):
    wellParam.wellStateHelper.applySamplingConstraints(
        ahd0=wellParam.parA.value(),
        dAhd=wellParam.parI.value(),
        nAhd=wellParam.parN.value(),
    )
    wellParam._syncSamplingFieldsFromWell()


def refreshWellHeaderFromParameter(wellParam, *, showWarning=False, warningHandler=QMessageBox.warning):
    success = wellParam.wellStateHelper.refreshHeader()
    wellParam._syncOriginFieldsFromWell()

    if success:
        applyWellSamplingFromParameters(wellParam)
    elif showWarning:
        warningHandler(None, 'Well Seed error', wellParam.well.errorText)

    return success


def applyWellHeaderParameterChange(wellParam, *, attributeName, value, showWarning, processEventsHandler=QApplication.processEvents):
    setattr(wellParam.well, attributeName, value)
    wellParam._refreshWellHeader(showWarning=showWarning)
    processEventsHandler()


def applyCircleParameters(circleParam):
    circleParam.circle.radius = circleParam.parR.value()
    circleParam.circle.azi0 = circleParam.parA.value()
    circleParam.circle.dist = circleParam.parI.value()
    circleParam.parN.setValue(circleParam.circle.calcNoPoints())


def applySpiralParameters(spiralParam):
    spiralParam.spiral.radMin = spiralParam.parR1.value()
    spiralParam.spiral.radMax = spiralParam.parR2.value()
    spiralParam.spiral.radInc = spiralParam.parDr.value()
    spiralParam.spiral.azi0 = spiralParam.parA.value()
    spiralParam.spiral.dist = spiralParam.parI.value()
    spiralParam.parN.setValue(spiralParam.spiral.calcNoPoints())


def applyLocalGridParameters(localGridParam):
    localGridParam.binGrid.binSize.setX(localGridParam.parBx.value())
    localGridParam.binGrid.binSize.setY(localGridParam.parBy.value())
    localGridParam.binGrid.binShift.setX(localGridParam.parDx.value())
    localGridParam.binGrid.binShift.setY(localGridParam.parDy.value())
    localGridParam.binGrid.stakeOrig.setX(localGridParam.parLx.value())
    localGridParam.binGrid.stakeOrig.setY(localGridParam.parLy.value())
    localGridParam.binGrid.stakeSize.setX(localGridParam.parSx.value())
    localGridParam.binGrid.stakeSize.setY(localGridParam.parSy.value())
    localGridParam.binGrid.fold = localGridParam.parFo.value()


def applyGlobalGridParameters(globalGridParam):
    globalGridParam.binGrid.orig.setX(globalGridParam.parOx.value())
    globalGridParam.binGrid.orig.setY(globalGridParam.parOy.value())
    globalGridParam.binGrid.scale.setX(globalGridParam.parSx.value())
    globalGridParam.binGrid.scale.setY(globalGridParam.parSy.value())
    globalGridParam.binGrid.angle = globalGridParam.parAz.value()


def applyBinAnglesParameters(binAnglesParam):
    binAnglesParam.angles.azimuthal.setX(binAnglesParam.parAx.value())
    binAnglesParam.angles.azimuthal.setY(binAnglesParam.parAy.value())
    binAnglesParam.angles.reflection.setX(binAnglesParam.parIx.value())
    binAnglesParam.angles.reflection.setY(binAnglesParam.parIy.value())


def applyBinOffsetParameters(binOffsetParam):
    xmin = binOffsetParam.parXmin.value()
    xmax = binOffsetParam.parXmax.value()
    ymin = binOffsetParam.parYmin.value()
    ymax = binOffsetParam.parYmax.value()
    rmin = binOffsetParam.parRmin.value()
    rmax = binOffsetParam.parRmax.value()

    binOffsetParam.offset.rctOffsets.setLeft(min(xmin, xmax))
    binOffsetParam.offset.rctOffsets.setRight(max(xmin, xmax))
    binOffsetParam.offset.rctOffsets.setTop(min(ymin, ymax))
    binOffsetParam.offset.rctOffsets.setBottom(max(ymin, ymax))
    binOffsetParam.offset.radOffsets.setX(min(rmin, rmax))
    binOffsetParam.offset.radOffsets.setY(max(rmin, rmax))


def applyUniqueOffsetParameters(uniqueOffsetParam):
    uniqueOffsetParam.unique.apply = uniqueOffsetParam.parP.value()
    uniqueOffsetParam.unique.write = uniqueOffsetParam.parR.value()
    uniqueOffsetParam.unique.dOffset = uniqueOffsetParam.parO.value()
    uniqueOffsetParam.unique.dAzimuth = uniqueOffsetParam.parA.value()


def applyBinMethodParameters(binMethodParam):
    index = BinningList.index(binMethodParam.parM.value())
    binMethodParam.binning.method = BinningType(index)
    binMethodParam.binning.vint = binMethodParam.parV.value()


def applyPlaneParameters(planeParam):
    planeParam.plane.anchor = planeParam.parO.value()
    planeParam.plane.azi = planeParam.parA.value()
    planeParam.plane.dip = planeParam.parD.value()


def applySphereParameters(sphereParam):
    sphereParam.sphere.origin = sphereParam.parO.value()
    sphereParam.sphere.radius = sphereParam.parR.value()


def applyReflectorParameters(reflectorsParam):
    reflectorsParam.reflectorValues = reflectorValuesFromParameters(
        plane=reflectorsParam.parP.value(),
        sphere=reflectorsParam.parS.value(),
    )


def applyAnalysisParameters(analysisParam):
    analysisParam.analysisValues = analysisValuesFromParameters(
        area=analysisParam.parB.value(),
        angles=analysisParam.parA.value(),
        binning=analysisParam.parM.value(),
        offset=analysisParam.parO.value(),
        unique=analysisParam.parU.value(),
    )


def applyBlockParameters(blockParam):
    blockParam.blockValues = applyBlockValues(
        blockParam.block,
        srcBorder=blockParam.parS.value(),
        recBorder=blockParam.parR.value(),
        templateList=blockParam.parT.value(),
    )


def applyTemplateParameters(templateParam):
    templateParam.templateValues = applyTemplateValues(
        templateParam.template,
        rollList=templateParam.parR.value(),
        seedList=templateParam.parS.value(),
    )


def applyRollListParameters(rollListParam):
    # Re-read the current children because MyRollParameter items can be reordered.
    paramList = [rollListParam.child('Planes'), rollListParam.child('Lines'), rollListParam.child('Points')]

    rollListParam.moveList[0] = paramList[0].value()
    rollListParam.moveList[1] = paramList[1].value()
    rollListParam.moveList[2] = paramList[2].value()


def applyRollParameterIncrement(rollParam):
    rollParam.row.increment.setX(rollParam.parX.value())
    rollParam.row.increment.setY(rollParam.parY.value())
    rollParam.row.increment.setZ(rollParam.parZ.value())

    rollParam.setAzimuth()
    rollParam.setTilt()


def applyRollParameterStepCount(rollParam):
    rollParam.row.steps = rollParam.parN.value()
    rollParam.sigValueChanging.emit(rollParam, rollParam.value())


def applyPatternSeedParameterValues(patternSeedParam):
    patternSeedParam.seed.color = patternSeedParam.parL.value()
    patternSeedParam.seed.origin = patternSeedParam.parO.value()
    patternSeedParam.seed.grid.growList = patternSeedParam.parG.value()


def applyConfigurationParameterValues(configurationParam):
    configurationParam.configurationValues = applyConfigurationValues(
        configurationParam.survey,
        crs=configurationParam.parC.value(),
        typ=configurationParam.parT.value(),
        nam=configurationParam.parN.value(),
    )


def appendNewManagedParameterItem(parentParam, managedList, *, baseName, createValue, childFactory, menuName='addNew', afterAppend=None, appendItemFn=appendManagedParameterItem):
    newName = nextManagedChildName(parentParam.names, baseName)
    value = createValue(newName)
    appendItemFn(
        parentParam,
        managedList,
        value,
        name=newName,
        childFactory=childFactory,
        menuName=menuName,
        afterAppend=afterAppend,
    )
    return value


# The class ParameterTree has been subclassed from the pyqtgraph TreeWidget class
# See: https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/parametertree/ParameterTree.html#ParameterTree.addParameters

# The class ParameterItem has been subclassed from the QtWidgets.QTreeWidgetItem class
# See: https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/parametertree/ParameterItem.html#ParameterItem

# Signals hand slots for ParameterItems have been wired up as follows:
# param.sigValueChanged.connect(self.valueChanged)
# param.sigChildAdded.connect(self.childAdded)
# param.sigChildRemoved.connect(self.childRemoved)
# param.sigNameChanged.connect(self.nameChanged)
# param.sigLimitsChanged.connect(self.limitsChanged)
# param.sigDefaultChanged.connect(self.defaultChanged)
# param.sigOptionsChanged.connect(self.optsChanged)
# param.sigParentChanged.connect(self.parentChanged)

# class MyBinAngles #########################################################


class MyBinAnglesParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        maxInc = param.child('Max inclination').opts['value']
        minInc = param.child('Min inclination').opts['value']

        d = param.opts.get('decimals', 3)
        if minInc == 0.0:
            t = f'AoI < {maxInc:.{d}g} deg'
        else:
            t = f'{minInc:.{d}g} < AoI < {maxInc:.{d}g} deg'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyBinAnglesParameterItem.showPreviewInformation | t = {t} <<<')


class MyBinAnglesParameter(MyGroupParameter):

    itemClass = MyBinAnglesParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBinAnglesParameter opts')

        d = opts.get('decimals', 7)

        self.angles = RollAngles()
        self.angles = opts.get('value', self.angles)

        tip1 = 'for angles around 0° use min > max. E.g. from 330° (min) to 30° (max)'
        tip2 = 'incidence angles are not used with the Cmp binning method'

        with self.treeChangeBlocker():
            self.addChild(dict(name='Min azimuth', value=self.angles.azimuthal.x(), default=self.angles.azimuthal.x(), type='float', decimals=d, suffix='°E-ccw', limits=[0.0, 360.0], tip=tip1))
            self.addChild(dict(name='Max azimuth', value=self.angles.azimuthal.y(), default=self.angles.azimuthal.y(), type='float', decimals=d, suffix='°E-ccw', limits=[0.0, 360.0], tip=tip1))
            self.addChild(dict(name='Min inclination', value=self.angles.reflection.x(), default=self.angles.reflection.x(), type='float', decimals=d, suffix='°Aoi', limits=[0.0, 90.0], tip=tip2))
            self.addChild(dict(name='Max inclination', value=self.angles.reflection.y(), default=self.angles.reflection.y(), type='float', decimals=d, suffix='°Aoi', limits=[0.0, 90.0], tip=tip2))

        bindChildParameters(self, {
            'parAx': 'Min azimuth',
            'parAy': 'Max azimuth',
            'parIx': 'Min inclination',
            'parIy': 'Max inclination',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyBinAnglesParameters(self)

    def value(self):
        return self.angles


# class MyBinOffset #########################################################


class MyBinOffsetParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        xMin = param.child('Min x-offset').opts['value']
        xMax = param.child('Max x-offset').opts['value']
        yMin = param.child('Min y-offset').opts['value']
        yMax = param.child('Max y-offset').opts['value']
        rMax = param.child('Max r-offset').opts['value']

        x = max(abs(xMin), abs(xMax))
        y = max(abs(yMin), abs(yMax))
        d = math.hypot(x, y)
        r = rMax

        if r >= d:
            t = 'rectangular constraints'
        elif r < x:
            t = 'radial constraints'
        else:
            t = 'mixed constraints'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyBinOffsetParameterItem.showPreviewInformation | t = {t} <<<')


class MyBinOffsetParameter(MyGroupParameter):

    itemClass = MyBinOffsetParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBinOffsetParameter opts')

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        self.offset = RollOffset()
        self.offset = opts.get('value', self.offset)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Min x-offset', value=self.offset.rctOffsets.left(), default=self.offset.rctOffsets.left(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Max x-offset', value=self.offset.rctOffsets.right(), default=self.offset.rctOffsets.right(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Min y-offset', value=self.offset.rctOffsets.top(), default=self.offset.rctOffsets.top(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Max y-offset', value=self.offset.rctOffsets.bottom(), default=self.offset.rctOffsets.bottom(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Min r-offset', value=self.offset.radOffsets.x(), default=self.offset.radOffsets.x(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Max r-offset', value=self.offset.radOffsets.y(), default=self.offset.radOffsets.y(), type='float', decimals=d, suffix=s))

        bindChildParameters(self, {
            'parXmin': 'Min x-offset',
            'parXmax': 'Max x-offset',
            'parYmin': 'Min y-offset',
            'parYmax': 'Max y-offset',
            'parRmin': 'Min r-offset',
            'parRmax': 'Max r-offset',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyBinOffsetParameters(self)

    def value(self):
        return self.offset


# class MyUniqOff ###########################################################


class MyUniqOffParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        apply = param.child('Apply pruning').opts['value']
        dOffset = param.child('Delta offset').opts['value']
        dAzimuth = param.child('Delta azimuth').opts['value']

        if not apply:
            t = 'Not used'
        else:
            t = f'@ {dOffset}m, {dAzimuth}°'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyUniqOffParameterItem.showPreviewInformation | t = {t} <<<')


class MyUniqOffParameter(MyGroupParameter):

    itemClass = MyUniqOffParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyUniqOffParameter opts')

        d = opts.get('decimals', 7)
        self.unique = opts.get('value', RollUnique())

        tip = 'Write back rounded offset- and azimuth values back to analysis results'
        with self.treeChangeBlocker():
            self.addChild(dict(name='Apply pruning', value=self.unique.apply, default=self.unique.apply, type='bool'))
            self.addChild(dict(name='Write rounded', value=self.unique.write, default=self.unique.write, type='bool', tip=tip))
            self.addChild(dict(name='Delta offset', value=self.unique.dOffset, default=self.unique.dOffset, type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Delta azimuth', value=self.unique.dAzimuth, default=self.unique.dAzimuth, type='float', decimals=d, suffix='deg'))

        bindChildParameters(self, {
            'parP': 'Apply pruning',
            'parR': 'Write rounded',
            'parO': 'Delta offset',
            'parA': 'Delta azimuth',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyUniqueOffsetParameters(self)

    def value(self):
        return self.unique


# class MyBinMethod #########################################################


class MyBinMethodParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        binMethod = param.child('Binning method').opts['value']
        vInterval = param.child('Interval velocity').opts['value']
        t = f'{binMethod} @ Vint={vInterval}m/s'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyBinMethodParameterItem.showPreviewInformation | t = {t} <<<')


class MyBinMethodParameter(MyGroupParameter):

    itemClass = MyBinMethodParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBinMethodParameter opts')

        self.binning = RollBinning()
        self.binning = opts.get('value', self.binning)

        d = opts.get('decimals', 7)
        binningMethod = self.binning.method.value

        with self.treeChangeBlocker():
            self.addChild(dict(name='Binning method', type='myList', value=BinningList[binningMethod], default=BinningList[binningMethod], limits=BinningList))
            self.addChild(dict(name='Interval velocity', type='float', value=self.binning.vint, default=self.binning.vint, decimals=d, suffix='m/s'))

        bindChildParameters(self, {
            'parM': 'Binning method',
            'parV': 'Interval velocity',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyBinMethodParameters(self)

    def value(self):
        return self.binning


# class MyPlane #############################################################


class MyPlaneParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 5)
        dip = param.child('Plane dip').opts['value']
        azi = param.child('Plane azimuth').opts['value']
        z = param.child('Plane anchor').opts['value'].z()

        if dip == 0:
            t = f'horizontal, depth={-z:.{d}g}m'
        else:
            t = f'dipping, azi={azi:.{d}g}°, dip={dip:.{d}g}°'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyPlaneParameterItem.showPreviewInformation | t = {t} <<<')


class MyPlaneParameter(MyGroupParameter):

    itemClass = MyPlaneParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyPlaneParameter opts')

        self.plane = RollPlane()
        self.plane = opts.get('value', self.plane)

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')
        tip = 'plane is dipping upwards in the azimuth direction'

        with self.treeChangeBlocker():
            self.addChild(dict(name='Plane anchor', type='myPoint3D', value=self.plane.anchor, default=self.plane.anchor, decimals=d, suffix=s, expanded=False, flat=True))
            self.addChild(dict(name='Plane azimuth', type='float', value=self.plane.azi, default=self.plane.azi, decimals=d, suffix='°E-ccw'))
            self.addChild(dict(name='Plane dip', type='float', value=self.plane.dip, default=self.plane.dip, decimals=d, suffix='°', tip=tip))

        bindChildParameters(self, {
            'parO': 'Plane anchor',
            'parA': 'Plane azimuth',
            'parD': 'Plane dip',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyPlaneParameters(self)

    def value(self):
        return self.plane


# class MySphere ############################################################


class MySphereParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 5)
        r = param.child('Sphere radius').opts['value']
        z = param.child('Sphere origin').opts['value'].z()
        t = f'r={r:.{d}g}m, depth={-z:.{d}g}m'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MySphereParameterItem.showPreviewInformation | t = {t} <<<')


class MySphereParameter(MyGroupParameter):

    itemClass = MySphereParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySphereParameter opts')

        self.sphere = RollSphere()
        self.sphere = opts.get('value', self.sphere)

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        with self.treeChangeBlocker():
            self.addChild(dict(name='Sphere origin', type='myPoint3D', value=self.sphere.origin, default=self.sphere.origin, decimals=d, suffix=s, expanded=False, flat=True))
            self.addChild(dict(name='Sphere radius', type='float', value=self.sphere.radius, default=self.sphere.radius, decimals=d, suffix=s))

        bindChildParameters(self, {
            'parO': 'Sphere origin',
            'parR': 'Sphere radius',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applySphereParameters(self)

    def value(self):
        return self.sphere


# class MyLocalGrid #########################################################


class MyLocalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        fold = param.child('Max fold').opts['value']
        xBin = param.child('Bin size [x]').opts['value']
        yBin = param.child('Bin size [y]').opts['value']

        if fold < 0:
            t = f'{xBin} x {yBin}m, fold undefined'
        else:
            t = f'{xBin}x{yBin}m, fold {fold} max'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyLocalGridParameterItem.showPreviewInformation | t = {t} <<<')


class MyLocalGridParameter(MyGroupParameter):

    itemClass = MyLocalGridParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyLocalGridParameter opts')

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        self.binGrid = RollBinGrid()
        self.binGrid = opts.get('value', self.binGrid)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Bin size [x]', value=self.binGrid.binSize.x(), default=self.binGrid.binSize.x(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Bin size [y]', value=self.binGrid.binSize.y(), default=self.binGrid.binSize.y(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Bin offset [x]', value=self.binGrid.binShift.x(), default=self.binGrid.binShift.x(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Bin offset [y]', value=self.binGrid.binShift.y(), default=self.binGrid.binShift.y(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Stake nr @ origin', value=self.binGrid.stakeOrig.x(), default=self.binGrid.stakeOrig.x(), type='float', decimals=d, suffix='#'))
            self.addChild(dict(name='Line nr @ origin', value=self.binGrid.stakeOrig.y(), default=self.binGrid.stakeOrig.y(), type='float', decimals=d, suffix='#'))
            self.addChild(dict(name='Stake increments', value=self.binGrid.stakeSize.x(), default=self.binGrid.stakeSize.x(), type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Line increments', value=self.binGrid.stakeSize.y(), default=self.binGrid.stakeSize.y(), type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Max fold', value=self.binGrid.fold, default=self.binGrid.fold, type='int'))

        bindChildParameters(self, {
            'parBx': 'Bin size [x]',
            'parBy': 'Bin size [y]',
            'parDx': 'Bin offset [x]',
            'parDy': 'Bin offset [y]',
            'parLx': 'Stake nr @ origin',
            'parLy': 'Line nr @ origin',
            'parSx': 'Stake increments',
            'parSy': 'Line increments',
            'parFo': 'Max fold',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyLocalGridParameters(self)

    def value(self):
        return self.binGrid


# class MyGlobalGrid ########################################################


class MyGlobalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        e = param.child('Bin origin   [E]').opts['value']
        n = param.child('Bin origin   [N]').opts['value']
        a = param.child('Azimuth').opts['value']
        t = f'o({e:,}, {n:,}), a={a:.{d}g} deg'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyGlobalGridParameterItem.showPreviewInformation | t = {t} <<<')


class MyGlobalGridParameter(MyGroupParameter):

    itemClass = MyGlobalGridParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyGlobalGridParameter opts')

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        self.binGrid = RollBinGrid()
        self.binGrid = opts.get('value', self.binGrid)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Bin origin   [E]', value=self.binGrid.orig.x(), default=self.binGrid.orig.x(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Bin origin   [N]', value=self.binGrid.orig.y(), default=self.binGrid.orig.y(), type='float', decimals=d, suffix=s))
            self.addChild(dict(name='Scale factor [E]', value=self.binGrid.scale.x(), default=self.binGrid.scale.x(), type='float', decimals=d, suffix='x'))
            self.addChild(dict(name='Scale factor [N]', value=self.binGrid.scale.y(), default=self.binGrid.scale.y(), type='float', decimals=d, suffix='x'))
            self.addChild(dict(name='Azimuth', value=self.binGrid.angle, default=self.binGrid.angle, type='float', decimals=d, suffix='°E-ccw'))

        bindChildParameters(self, {
            'parOx': 'Bin origin   [E]',
            'parOy': 'Bin origin   [N]',
            'parSx': 'Scale factor [E]',
            'parSy': 'Scale factor [N]',
            'parAz': 'Azimuth',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyGlobalGridParameters(self)

    def value(self):
        return self.binGrid


# class MyBlock #############################################################


class MyBlockParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

        QApplication.processEvents()

    def showPreviewInformation(self, param):
        nTemplates, nBlockShots = previewBlockSourceSummary(param)

        t = f'{nTemplates} template(s), {int(nBlockShots + 0.5)} src points'

        QApplication.processEvents()

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyBlockParameterItem.showPreviewInformation | t = {t} <<<')


class MyBlockParameter(MyGroupParameter):

    itemClass = MyBlockParameterItem

    def __init__(self, **opts):

        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage block'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBlockParameter opts')

        self.block = opts.get('value', RollBlock())
        self.survey = opts.get('survey', None)
        self.wellDirectory = opts.get('wellDirectory', None)
        self.blockValues = blockValuesFromBlock(self.block)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Source boundary', type='myRectF', value=self.blockValues.srcBorder, default=self.blockValues.srcBorder, flat=True, expanded=False))
            self.addChild(dict(name='Receiver boundary', type='myRectF', value=self.blockValues.recBorder, default=self.blockValues.recBorder, flat=True, expanded=False))
            self.addChild(dict(name='Template list', type='myTemplateList', value=self.blockValues.templateList, default=self.blockValues.templateList, flat=True, expanded=True, brush='#add8e6', decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey))  # noqa: E501

        bindChildParameters(self, {
            'parS': 'Source boundary',
            'parR': 'Receiver boundary',
            'parT': 'Template list',
        })

        connectValueChangedSignals([
            (self.parS, self.changed),
            (self.parR, self.changed),
            (self.parT, self.changed),
        ])

        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def nameChanged(self, _):
        self.block.name = self.name()

    def changed(self):
        applyBlockParameters(self)

    def value(self):
        return self.block

    def contextMenu(self, name=None):
        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyBlockListParameter):
            raise ValueError("Need 'MyBlockListParameter' instances at this point")

        # name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            removeManagedParameterItem(
                self,
                parent,
                parent.blockList,
                index,
                confirmRemoval=lambda: QMessageBox.question(None, 'Please confirm', 'Delete selected block ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes,
            )

        elif name == 'moveUp':
            moveManagedParameterItem(
                self,
                parent,
                parent.blockList,
                index,
                offset=-1,
                childFactory=lambda block: dict(name=block.name, type='myBlock', value=block, default=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'moveDown':
            moveManagedParameterItem(
                self,
                parent,
                parent.blockList,
                index,
                offset=1,
                childFactory=lambda block: dict(name=block.name, type='myBlock', value=block, default=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


# class MyTemplate ##########################################################


class MyTemplateParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        nSeeds, nTemplateShots = previewTemplateSourceSummary(param)
        t = 'No seeds defined'
        if nSeeds > 0:
            t = f'{nSeeds} seed(s), {int(nTemplateShots + 0.5)} src points'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyTemplateParameterItem.showPreviewInformation | t = {t} <<<')


class MyTemplateParameter(MyGroupParameter):

    itemClass = MyTemplateParameterItem

    def __init__(self, **opts):

        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage template'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyTemplateParameter opts')

        d = opts.get('decimals', 5)
        s = opts.get('suffix', 'm')

        self.template = opts.get('value', RollTemplate())
        self.survey = opts.get('survey', None)
        self.wellDirectory = opts.get('wellDirectory', None)
        self.templateValues = templateValuesFromTemplate(self.template)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Roll steps', type='myRollList', value=self.templateValues.rollList, default=self.templateValues.rollList, expanded=True, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Seed list', type='myTemplateSeedList', value=self.templateValues.seedList, default=self.templateValues.seedList, brush='#add8e6', flat=True, wellDirectory=self.wellDirectory, survey=self.survey))  # noqa: E501
        bindChildParameters(self, {
            'parR': 'Roll steps',
            'parS': 'Seed list',
        })

        connectValueChangedSignals([
            (self.parR, self.changed),
            (self.parS, self.changed),
        ])
        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def nameChanged(self, _):

        self.template.name = self.name()

    def changed(self):
        applyTemplateParameters(self)

    def value(self):
        return self.template

    def contextMenu(self, name=None):
        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyTemplateListParameter):
            raise ValueError("Need 'MyTemplateListParameter' instances at this point")

        # name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            removeManagedParameterItem(
                self,
                parent,
                parent.templateList,
                index,
                confirmRemoval=lambda: QMessageBox.question(None, 'Please confirm', 'Delete selected template ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes,  # noqa: E501
            )

        elif name == 'moveUp':
            moveManagedParameterItem(
                self,
                parent,
                parent.templateList,
                index,
                offset=-1,
                childFactory=lambda template: dict(name=template.name, type='myTemplate', value=template, default=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'moveDown':
            moveManagedParameterItem(
                self,
                parent,
                parent.templateList,
                index,
                offset=1,
                childFactory=lambda template: dict(name=template.name, type='myTemplate', value=template, default=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


# class MyRollList ##########################################################


class MyRollListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        nPlane = param.child('Planes', 'N').opts['value']
        nLines = param.child('Lines', 'N').opts['value']
        nPoint = param.child('Points', 'N').opts['value']

        nRollSteps = nPlane * nLines * nPoint
        t = formatPreviewPointSummary(nRollSteps, details=f'({nPlane} x {nLines} x {nPoint})')

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyRollListParameterItem.showPreviewInformation | t = {t} <<<')


class MyRollListParameter(MyGroupParameter):

    itemClass = MyRollListParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyRollListParameter opts')

        d = opts.get('decimals', 5)
        s = opts.get('suffix', 'm')

        self.moveList = [RollTranslate(), RollTranslate(), RollTranslate()]
        self.moveList = opts.get('value', self.moveList)

        while len(self.moveList) < 3:
            self.moveList.insert(0, RollTranslate())                                # First, make sure there are ALWAYS 3 grow steps for every grid

        with self.treeChangeBlocker():
            self.addChild(dict(name='Planes', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[0], default=self.moveList[0]))
            self.addChild(dict(name='Lines', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[1], default=self.moveList[1]))
            self.addChild(dict(name='Points', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[2], default=self.moveList[2]))

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyRollListParameters(self)

    def value(self):
        return self.moveList


# class MyRoll ##############################################################


class MyRollParameterItem(MyGroupParameterItem):                      # modeled after PenParameterItem from pen.py in pyqtgraph
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        n = param.child('N').opts['value']
        x = param.child('dX').opts['value']
        y = param.child('dY').opts['value']
        z = param.child('dZ').opts['value']
        t = f'{n} x ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyRollParameterItem.showPreviewInformation | t = {t} <<<')


class MyRollParameter(MyGroupParameter):

    itemClass = MyRollParameterItem

    def __init__(self, **opts):

        opts['context'] = {'moveUp': 'Move up', 'moveDown': 'Move dn'}
        opts['tip'] = 'Right click to change position; please keep largest nr of points at bottom of the list'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyRollParameter opts')

        self.row = RollTranslate()
        self.row = opts.get('value', self.row)

        d = opts.get('decimals', 3)
        s = opts.get('suffix', '')
        a = self.row.azim
        t = self.row.tilt

        with self.treeChangeBlocker():
            self.addChild(dict(name='N', type='int', limits=[1, None], value=self.row.steps, default=self.row.steps))
            self.addChild(dict(name='dX', type='float', decimals=d, suffix=s, value=self.row.increment.x(), default=self.row.increment.x()))
            self.addChild(dict(name='dY', type='float', decimals=d, suffix=s, value=self.row.increment.y(), default=self.row.increment.y()))
            self.addChild(dict(name='dZ', type='float', decimals=d, suffix=s, value=self.row.increment.z(), default=self.row.increment.z()))
            self.addChild(dict(name='azim', type='myFloat', decimals=d, suffix='deg', value=a, default=a, enabled=False, readonly=True))     # set value through setAzimuth()     # myFloat
            self.addChild(dict(name='tilt', type='myFloat', decimals=d, suffix='deg', value=t, default=t, enabled=False, readonly=True))     # set value through setTilt()    # myFloat

        bindChildParameters(self, {
            'parN': 'N',
            'parX': 'dX',
            'parY': 'dY',
            'parZ': 'dZ',
            'parA': 'azim',
            'parT': 'tilt',
        })

        connectValueChangedSignals([
            (self.parN, self.changedN),
            (self.parX, self.changedXYZ),
            (self.parY, self.changedXYZ),
            (self.parZ, self.changedXYZ),
            (self.parA, self.changedA),
            (self.parT, self.changedT),
        ])

        QApplication.processEvents()

    def changedA(self):                                                         # not used; readonly parameter to block signal
        pass

    def changedT(self):                                                         # not used; readonly parameter to block signal
        pass

    def setAzimuth(self):
        azimuth = math.degrees(math.atan2(self.row.increment.y(), self.row.increment.x()))
        self.parA.setValue(azimuth, blockSignal=self.changedA)
        # myPrint(f'>>>{lineNo():5d} MyRollParameter.setAzimuth <<<')

    def setTilt(self):
        lengthXY = math.sqrt(self.row.increment.x() ** 2 + self.row.increment.y() ** 2)
        tilt = math.degrees(math.atan2(self.row.increment.z(), lengthXY))
        self.parT.setValue(tilt, blockSignal=self.changedT)
        # myPrint(f'>>>{lineNo():5d} MyRollParameter.setTilt <<<')

    # update the values of the five children
    def changedN(self):
        applyRollParameterStepCount(self)
        # myPrint(f'>>>{lineNo():5d} MyRollParameter.changedN <<<')

    def changedXYZ(self):
        applyRollParameterIncrement(self)
        # myPrint(f'>>>{lineNo():5d} MyRollParameter.changedXYZ <<<')

    def value(self):
        return self.row

    def contextMenu(self, name=None):
        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyRollListParameter):
            raise ValueError("Need 'MyRollListParameter' instances at this point")

        if name == 'moveUp':
            if index > 0:
                with parent.treeChangeBlocker():
                    swapManagedParameterItems(
                        parent,
                        parent.moveList,
                        index,
                        offset=-1,
                        childFactory=lambda childName, value: dict(
                            name=childName,
                            type='myRoll',
                            value=value,
                            default=value,
                            expanded=False,
                            renamable=True,
                            flat=True,
                            decimals=5,
                            suffix='m',
                        ),
                    )
                    parent.changed()                                            # update the parent

                    value = parent.value()
                    myPrint(value)

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                with parent.treeChangeBlocker():
                    swapManagedParameterItems(
                        parent,
                        parent.moveList,
                        index,
                        offset=1,
                        childFactory=lambda childName, value: dict(
                            name=childName,
                            type='myRoll',
                            value=value,
                            default=value,
                            expanded=False,
                            renamable=True,
                            flat=True,
                            decimals=5,
                            suffix='m',
                        ),
                    )
                    parent.changed()                                            # update the parent

                    value = parent.value()
                    myPrint(value)


# class MySeedList ##########################################################


class MySeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

        QApplication.processEvents()

    def showPreviewInformation(self, param):
        t, hasError = previewSeedListCompositionSummary(param)
        self.previewLabel.setErrorCondition(hasError)
        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MySeedListParameterItem.showPreviewInformation | t = {t} <<<')


class MySeedListParameter(MyGroupParameter):

    itemClass = MySeedListParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new Seed'}
        opts['tip'] = 'Right click to add seeds'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySeedListParameter opts')

        self.survey = opts.get('survey', None)                                  # weak reference to survey object
        self.seedList = opts.get('value', [RollSeed()])
        self.wellDirectory = opts.get('wellDirectory', None)

        # bind existing seeds to survey (optional)
        if self.survey is not None:
            for seed in self.seedList:
                seed.setSurvey(self.survey)

        if not isinstance(self.seedList, list):
            raise ValueError("Need 'list' instance at this point")

        nSeeds = len(self.seedList)
        if nSeeds < 2:
            raise ValueError('Need at least two seeds for a valid template')

        with self.treeChangeBlocker():
            for n, seed in enumerate(self.seedList):
                self.addChild(dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey))  # noqa: E501

        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def value(self):
        return self.seedList

    def contextMenu(self, name=None):
        if name == 'addNew':
            newName = nextManagedChildName(self.names, 'Seed')

            seed = createAppendedTemplateSeed(newName, self.seedList, self.survey)
            appendManagedParameterItem(
                self,
                self.seedList,
                seed,
                name=newName,
                childFactory=lambda childName, childSeed: dict(name=childName, type='myTemplateSeed', value=childSeed, default=childSeed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
                menuName=name,
            )


# class MyPatternSeedList ##########################################################


class MyPatternSeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        t = formatPreviewCountLabel(len(param.childs), 'pattern seed', emptyText='No pattern seeds')

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyPatternSeedListParameterItem.showPreviewInformation | t = {t} <<<')


class MyPatternSeedListParameter(MyGroupParameter):

    itemClass = MyPatternSeedListParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new Seed'}
        opts['tip'] = 'Right click to add seeds'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySeedListParameter opts')

        self.seedList = [RollPatternSeed()]
        self.seedList = opts.get('value', self.seedList)

        if not isinstance(self.seedList, list):
            raise ValueError("Need 'list' instance at this point")

        with self.treeChangeBlocker():
            for n, seed in enumerate(self.seedList):
                self.addChild(dict(name=seed.name, type='myPatternSeed', value=seed, default=seed, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def value(self):
        return self.seedList

    def contextMenu(self, name=None):

        if name == 'addNew':
            newName = nextManagedChildName(self.names, 'Seed')

            seed = RollPatternSeed(newName)
            if len(self.seedList) > 0:
                seed.color = self.seedList[-1].color                            # default to last color
            else:
                seed.color = QColor('#77ff0000')                                # empty list; just make it blue

            appendManagedParameterItem(
                self,
                self.seedList,
                seed,
                name=newName,
                childFactory=lambda childName, childSeed: dict(name=childName, type='myPatternSeed', value=childSeed, default=childSeed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
                menuName=name,
            )
            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()


# class MySeed ##############################################################


class MySeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        bSource = param.child('Source seed').opts['value']
        seedType = param.child('Seed type').opts['value']
        if seedType == 'Circle':
            nSteps = param.child('Circle grow steps', 'Points').opts['value']
        elif seedType == 'Spiral':
            nSteps = param.child('Spiral grow steps', 'Points').opts['value']
        elif seedType == 'Well':
            nSteps = param.child('Well grow steps', 'Points').opts['value']
        else:
            # grid stationary or rolling
            nPlane = param.child('Grid grow steps', 'Planes', 'N').opts['value']
            nLines = param.child('Grid grow steps', 'Lines', 'N').opts['value']
            nPoint = param.child('Grid grow steps', 'Points', 'N').opts['value']
            nSteps = nPlane * nLines * nPoint

        seed = 'src' if bSource else 'rec'
        t = f'{seedType} seed, {nSteps} {seed} points'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MySeedParameterItem.showPreviewInformation | t = {t} <<<')


class MySeedParameter(MyGroupParameter):

    itemClass = MySeedParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True
        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage seed'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in myTemplateSeed Parameter opts')

        self.seed = opts.get('value', RollSeed())
        self.survey = self.seed.survey or opts.get('survey', None)              # to avoid using config.py as a backdoor
        if self.survey is not None:
            self.seed.setSurvey(self.survey)

        self.wellDirectory = opts.get('wellDirectory', None)
        d = opts.get('decimals', 7)

        self.seedStateHelper = SeedParameterStateHelper(self.seed, self.survey)
        patterns = self.seedStateHelper.patternNames()
        nPattern = self.seedStateHelper.initialPatternIndex(patterns)

        self.seedTypes = list(self.seedStateHelper.seedTypes)
        with self.treeChangeBlocker():
            self.addChild(dict(name='Seed type', type='myList', value=self.seedTypes[self.seed.type], default=self.seedTypes[self.seed.type], limits=self.seedTypes, brush='#add8e6'))
            self.addChild(dict(name='Source seed', type='bool', value=self.seed.bSource, default=self.seed.bSource))
            addSeedColorOriginGridChildren(self, self.seed, decimals=d)

            self.addChild(dict(name='Seed pattern', type='myList', value=patterns[nPattern], default=patterns[nPattern], limits=patterns))
            self.addChild(dict(name='Circle grow steps', type='myCircle', value=self.seed.circle, default=self.seed.circle, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
            self.addChild(dict(name='Spiral grow steps', type='mySpiral', value=self.seed.spiral, default=self.seed.spiral, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
            self.addChild(dict(name='Well grow steps', type='myWell', value=self.seed.well, default=self.seed.well, expanded=True, flat=True, brush='#add8e6', wellDirectory=self.wellDirectory, survey=self.survey))     # noqa: E501 # , brush='#add8e6'

        bindChildParameters(self, {
            'parT': 'Seed type',
            'parR': 'Source seed',
            'parP': 'Seed pattern',
            'parC': 'Circle grow steps',
            'parS': 'Spiral grow steps',
            'parW': 'Well grow steps',
        })
        bindSeedColorOriginGridChildren(self)

        connectValueChangedSignals([
            (self.parT, self.typeChanged),
            (self.parR, self.changed),
            (self.parP, self.changed),
            (self.parC, self.changed),
            (self.parS, self.changed),
            (self.parW, self.changed),
        ])
        connectSeedColorOriginGridChangedSignals(self, self.changed)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        self.typeChanged()

        QApplication.processEvents()

    def nameChanged(self, _):
        self.seed.name = self.name()

    def _updateSeedTypeVisibility(self, seedType=None):
        if seedType is None:
            seedType = self.parT.value()

        applySeedVisibilityState(
            self.seedStateHelper.visibilityState(seedType),
            originParam=self.parO,
            gridParam=self.parG,
            patternParam=self.parP,
            circleParam=self.parC,
            spiralParam=self.parS,
            wellParam=self.parW,
        )

    def typeChanged(self):
        applySeedTypeChange(self)

    def changed(self):
        applySeedParameterValues(
            self.seed,
            self.seedStateHelper,
            sourceValue=self.parR.value(),
            colorValue=self.parL.value(),
            originValue=self.parO.value(),
            patternParam=self.parP,
            gridGrowList=self.parG.value(),
        )

        # self.seed.circle = self.parC.value()
        # self.seed.spiral = self.parS.value()
        # self.seed.well = self.parW.value()

    def value(self):
        return self.seed

    def refreshPatternList(self, seedType=None):
        refreshState = resolveGridSeedPatternRefreshState(self, seedType=seedType)
        applyGridSeedPatternRefresh(self, refreshState)

    def contextMenu(self, name=None):

        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MySeedListParameter):
            raise ValueError("Need 'MySeedListParameter' instances at this point")

        # name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            removeManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                confirmRemoval=lambda: QMessageBox.question(None, 'Please confirm', 'Delete selected seed ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes,
            )

        elif name == 'moveUp':
            moveManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                offset=-1,
                childFactory=lambda seed: dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'moveDown':
            moveManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                offset=1,
                childFactory=lambda seed: dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
            )

        elif name == 'preview':
            ...
        elif name == 'export':
            ...
        QApplication.processEvents()


# class MyPatternSeed ##############################################################


class MyPatternSeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        nPlane = param.child('Grid grow steps', 'Planes', 'N').opts['value']
        nLines = param.child('Grid grow steps', 'Lines', 'N').opts['value']
        nPoint = param.child('Grid grow steps', 'Points', 'N').opts['value']
        nSteps = nPlane * nLines * nPoint
        t = formatPreviewPointSummary(nSteps)

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyPatternSeedParameterItem.showPreviewInformation | t = {t} <<<')


class MyPatternSeedParameter(MyGroupParameter):

    itemClass = MyPatternSeedParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True
        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage seed'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in myPatternSeed Parameter opts')

        self.seed = RollSeed()
        self.seed = opts.get('value', self.seed)

        d = opts.get('decimals', 7)

        with self.treeChangeBlocker():
            addSeedColorOriginGridChildren(self, self.seed, decimals=d)

        bindSeedColorOriginGridChildren(self)

        connectSeedColorOriginGridChangedSignals(self, self.changed)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        QApplication.processEvents()

    def nameChanged(self, _):
        self.seed.name = self.name()

    def changed(self):
        applyPatternSeedParameterValues(self)

    def value(self):
        return self.seed

    def contextMenu(self, name=None):

        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyPatternSeedListParameter):
            raise ValueError("Need 'MyPatternSeedListParameter' instances at this point")

        # name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            removeManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                confirmRemoval=lambda: QMessageBox.question(None, 'Please confirm', 'Delete selected seed ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes,
            )

        elif name == 'moveUp':
            moveManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                offset=-1,
                childFactory=lambda seed: dict(name=seed.name, type='myPatternSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
            )

        elif name == 'moveDown':
            moveManagedParameterItem(
                self,
                parent,
                parent.seedList,
                index,
                offset=1,
                childFactory=lambda seed: dict(name=seed.name, type='myPatternSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
            )

        elif name == 'preview':
            ...
        elif name == 'export':
            ...

        QApplication.processEvents()


# class MyCircle ############################################################


class MyCircleParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        r = param.child('Radius').opts['value']
        s = param.child('Point interval').opts['value']
        n = param.child('Points').opts['value']
        t = formatPreviewPointSummary(n, decimals=d, details=(f'ø{r:.{d}g}m', f'd{s:.{d}g}m'))

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyCircleParameterItem.showPreviewInformation | t = {t} <<<')


class MyCircleParameter(MyGroupParameter):

    itemClass = MyCircleParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyCircleParameter opts')

        self.circle = RollCircle()
        self.circle = opts.get('value', self.circle)

        d = opts.get('decimals', 5)
        s = opts.get('suffix', 'm')
        tip = 'for a clockwise circle, use negative point interval values'

        with self.treeChangeBlocker():
            self.addChild(dict(name='Radius', value=self.circle.radius, default=self.circle.radius, type='float', decimals=d, suffix=s))
            addPreviewAngleIntervalPointChildren(self, angleValue=self.circle.azi0, distanceValue=self.circle.dist, pointsValue=self.circle.points, decimals=d, distanceSuffix=s, tip=tip)

        bindChildParameters(self, {
            'parR': 'Radius',
        })
        bindPreviewAngleIntervalPointChildren(self)

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyCircleParameters(self)

    def value(self):
        return self.circle


# class MySpiral ############################################################


class MySpiralParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        r1 = param.child('Min radius').opts['value']
        r2 = param.child('Max radius').opts['value']
        s = param.child('Point interval').opts['value']
        n = param.child('Points').opts['value']
        t = formatPreviewPointSummary(n, decimals=d, details=(f'ø{r1:.{d}g}-{r2:.{d}g}m', f'd{s:.{d}g}m'))

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MySpiralParameterItem.showPreviewInformation | t = {t} <<<')


class MySpiralParameter(MyGroupParameter):

    itemClass = MySpiralParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySpiralParameter opts')

        self.spiral = RollSpiral()
        self.spiral = opts.get('value', self.spiral)

        d = opts.get('decimals', 5)
        tip = 'for a clockwise spiral, use negative point interval values'

        with self.treeChangeBlocker():
            self.addChild(dict(name='Min radius', value=self.spiral.radMin, default=self.spiral.radMin, type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Max radius', value=self.spiral.radMax, default=self.spiral.radMax, type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Radius incr', value=self.spiral.radInc, default=self.spiral.radInc, type='float', decimals=d, suffix='m/360°'))
            addPreviewAngleIntervalPointChildren(self, angleValue=self.spiral.azi0, distanceValue=self.spiral.dist, pointsValue=self.spiral.points, decimals=d, distanceSuffix='m', tip=tip, distanceDecimals=d)

        bindChildParameters(self, {
            'parR1': 'Min radius',
            'parR2': 'Max radius',
            'parDr': 'Radius incr',
        })
        bindPreviewAngleIntervalPointChildren(self)

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applySpiralParameters(self)

    def value(self):
        return self.spiral


# class MyWell ##############################################################


class MyWellParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        t, e = previewWellSummary(param)
        self.updatePreviewLabelText(t, errorCondition=e)
        # myPrint(f'>>>{lineNo():5d} MyWellParameterItem.showPreviewInformation | t = {t} <<<')


class MyWellParameter(MyGroupParameter):

    itemClass = MyWellParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyWellParameter opts')

        self.well = RollWell()
        self.well = opts.get('value', self.well)
        directory = opts.get('wellDirectory', None)

        self.survey = self.well.survey or opts.get('survey', None)
        self.wellStateHelper = WellParameterStateHelper(self.well, self.survey)
        self.wellStateHelper.bindSurvey()

        d = opts.get('decimals', 7)

        nameFilter = 'Well files (*.wws *.well);;Deviation files [md,inc,azi] (*.wws);;OpendTect files [n,e,z,md] (*.well);;All files (*.*)'
        tip = 'SRD = Seismic Reference Datum; the horizontal surface at which TWT is assumed to be zero'

        #  don't do the following time-consuming check here, it is done in changedF()
        # name = self.well.name if self.well.name is not None and os.path.exists(self.well.name) else None
        f = self.well.name

        with self.treeChangeBlocker():
            self.addChild(dict(name='Well file', type='file', value=f, default=f, selectFile=f, acceptMode='AcceptOpen', directory=directory,
                               fileMode='ExistingFile', viewMode='Detail', nameFilter=nameFilter, tip='Select well file (wws or well format)'))
            self.addChild(dict(name='Well CRS', type='myCrs', value=self.well.crs, default=self.well.crs, expanded=False, flat=True))
            self.addChild(dict(name='Origin [well]', type='myPoint3D', value=self.well.origW, default=self.well.origW, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))
            self.addChild(dict(name='Origin [global]', type='myPoint2D', value=self.well.origG, default=self.well.origG, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))
            self.addChild(dict(name='Origin [local]', type='myPoint2D', value=self.well.origL, default=self.well.origL, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))

            self.addChild(dict(name='AHD start', type='float', value=self.well.ahd0, default=self.well.ahd0, decimals=d, limits=[0.0, None], suffix='m ref SRD', tip=tip))
            self.addChild(dict(name='AHD interval', type='float', value=self.well.dAhd, default=self.well.dAhd, decimals=d, limits=[1.0, None], suffix='m'))
            self.addChild(dict(name='Points', type='int', value=self.well.nAhd, default=self.well.nAhd, decimals=d, limits=[1, None]))

        bindChildParameters(self, {
            'parC': 'Well CRS',
            'parF': 'Well file',
            'parA': 'AHD start',
            'parI': 'AHD interval',
            'parN': 'Points',
            'parW': 'Origin [well]',
            'parG': 'Origin [global]',
            'parL': 'Origin [local]',
        })

        connectValueChangedSignals([
            (self.parC, self.changedC),
            (self.parF, self.changedF),
            (self.parA, self.changedA),
            (self.parI, self.changedI),
            (self.parN, self.changedN),
        ])
        QApplication.processEvents()

    def _syncOriginFieldsFromWell(self):
        originValues = self.wellStateHelper.originValues()
        self.parW.child('X').setValue(originValues['well'][0])
        self.parW.child('Y').setValue(originValues['well'][1])
        self.parW.child('Z').setValue(originValues['well'][2])

        self.parG.child('X').setValue(originValues['global'][0])
        self.parG.child('Y').setValue(originValues['global'][1])

        self.parL.child('X').setValue(originValues['local'][0])
        self.parL.child('Y').setValue(originValues['local'][1])

    def _syncSamplingFieldsFromWell(self):
        ahd0, dAhd, nAhd = self.wellStateHelper.samplingValues()
        self.parA.setValue(ahd0, blockSignal=self.changedA)
        self.parI.setValue(dAhd, blockSignal=self.changedI)
        self.parN.setValue(nAhd, blockSignal=self.changedN)

    def _refreshWellHeader(self, *, showWarning=False):
        return refreshWellHeaderFromParameter(self, showWarning=showWarning)

    def changedF(self):
        applyWellHeaderParameterChange(self, attributeName='name', value=self.parF.value(), showWarning=False)

    def changedC(self):
        applyWellHeaderParameterChange(self, attributeName='crs', value=self.parC.value(), showWarning=True)

    def changedA(self):
        applyWellSamplingFromParameters(self)

    def changedI(self):
        applyWellSamplingFromParameters(self)

    def changedN(self):
        applyWellSamplingFromParameters(self)

    def value(self):
        return self.well


# class MyTemplateList ######################################################


class MyTemplateListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new template'}
        opts['tip'] = 'Right click to add a new template'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyTemplateListParameter opts')

        self.templateList = opts.get('value', [RollTemplate()])
        self.survey = opts.get('survey', None)
        self.wellDirectory = opts.get('wellDirectory', None)

        if not isinstance(self.templateList, list):
            raise ValueError("Need 'list' instance at this point")

        nTemplates = len(self.templateList)
        if nTemplates == 0:
            raise ValueError('Need at least one template at this point')

        with self.treeChangeBlocker():
            for n, template in enumerate(self.templateList):
                self.addChild(dict(name=template.name, type='myTemplate', value=template, default=template, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey))  # noqa: E501

        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def value(self):
        return self.templateList

    def contextMenu(self, name=None):

        if name == 'addNew':
            appendNewManagedParameterItem(
                self,
                self.templateList,
                baseName='Template',
                createValue=lambda childName: createDefaultTemplate(childName, self.survey),
                childFactory=lambda childName, childTemplate: dict(name=childName, type='myTemplate', value=childTemplate, default=childTemplate, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
                menuName=name,
            )

        QApplication.processEvents()


# class MyBlockList #########################################################


class MyBlockListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new block'}
        opts['tip'] = 'Right click to add a new block'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBlockListParameter opts')

        self.blockList = opts.get('value', [RollBlock()])
        self.survey = opts.get('survey', None)
        self.wellDirectory = opts.get('wellDirectory', None)

        if not isinstance(self.blockList, list):
            raise ValueError("Need 'BlockList' instance at this point")

        nBlocks = len(self.blockList)
        # allow for empty blockList, in case the user has not yet created any blocks
        # if nBlocks == 0:
        #     raise ValueError('Need at least one block at this point')

        with self.treeChangeBlocker():
            for block in self.blockList:
                self.addChild(dict(name=block.name, type='myBlock', value=block, default=block, expanded=(nBlocks == 1), renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey))  # noqa: E501

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

        QApplication.processEvents()

    def value(self):
        return self.blockList

    def contextMenu(self, name=None):

        if name == 'addNew':
            appendNewManagedParameterItem(
                self,
                self.blockList,
                baseName='Block',
                createValue=lambda childName: createDefaultBlock(childName, self.survey),
                childFactory=lambda childName, childBlock: dict(name=childName, type='myBlock', value=childBlock, default=childBlock, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', wellDirectory=self.wellDirectory, survey=self.survey),  # noqa: E501
                menuName=name,
            )

        QApplication.processEvents()

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # myPrint(f'>>>{lineNo():5d} BlockList.ChildAdded <<<')
        ...

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # myPrint(f'>>>{lineNo():5d} BlockList.ChildRemoved <<<')
        ...

# class MyPattern   #########################################################


class MyPatternParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        nElements = 0
        seeds = param.child('Seed list')
        if seeds.hasChildren():
            for seed in seeds:

                # grid seed
                nPlane = seed.child('Grid grow steps', 'Planes', 'N').opts['value']
                nLines = seed.child('Grid grow steps', 'Lines', 'N').opts['value']
                nPoint = seed.child('Grid grow steps', 'Points', 'N').opts['value']

                nElements += nPlane * nLines * nPoint

        t = f'{nElements} elements(s)'

        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MyPatternParameterItem.showPreviewInformation | t = {t} <<<')


class MyPatternParameter(MyGroupParameter):

    itemClass = MyPatternParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True
        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage seed'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in myPattern Parameter opts')

        self.pattern = RollPattern()
        self.pattern = opts.get('value', self.pattern)

        self.addChild(dict(name='Seed list', type='myPatternSeedList', value=self.pattern.seedList, default=self.pattern.seedList, brush='#add8e6', flat=True))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        QApplication.processEvents()

    def nameChanged(self, _):
        self.pattern.name = self.name()

    def value(self):
        return self.pattern

    def contextMenu(self, name=None):

        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyPatternListParameter):
            raise ValueError("Need 'MyPatternListParameter' instances at this point")

        # name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            removeManagedParameterItem(
                self,
                parent,
                parent.patternList,
                index,
                confirmRemoval=lambda: QMessageBox.question(None, 'Please confirm', 'Delete selected pattern ?', QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes,
                afterRemove=lambda removedIndex: applyPatternRemovalSideEffects(parent, removedIndex),
            )

        elif name == 'moveUp':
            moveManagedParameterItem(
                self,
                parent,
                parent.patternList,
                index,
                offset=-1,
                childFactory=lambda pattern: dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
                afterMove=lambda oldIndex, newIndex, _pattern: applyPatternMoveSideEffects(parent, oldIndex, newIndex),
            )

        elif name == 'moveDown':
            moveManagedParameterItem(
                self,
                parent,
                parent.patternList,
                index,
                offset=1,
                childFactory=lambda pattern: dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
                afterMove=lambda oldIndex, newIndex, _pattern: applyPatternMoveSideEffects(parent, oldIndex, newIndex),
            )

        elif name == 'preview':
            ...
        elif name == 'export':
            ...

        QApplication.processEvents()


# class MyPatternList #######################################################


class MyPatternListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new pattern'}
        opts['tip'] = 'Right click to add a new pattern'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyPatternListParameter opts')

        self.patternList = opts.get('value', [RollPattern()])
        self.survey = opts.get('survey', None)

        if not isinstance(self.patternList, list):
            raise ValueError("Need 'list' instance at this point")

        with self.treeChangeBlocker():
            for pattern in self.patternList:
                self.addChild(dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)
        self.sigTreeStateChanged.connect(self.onTreeStateChanged)

        QApplication.processEvents()

    def onTreeStateChanged(self, *_):
        # Any change in pattern list (rename, move, add, remove) must refresh seeds
        applyPatternListSideEffects(self)

    def value(self):
        return self.patternList

    def _syncSurveyPatternList(self):
        if self.survey is not None:
            self.survey.setPatternList(self.patternList)

    def _swapPatternIndices(self, i, j):
        if i == j:
            return
        for seedParam in iterTemplateSeedParameters(self):
            if seedParam.seed.patternNo == i:
                seedParam.seed.patternNo = j
            elif seedParam.seed.patternNo == j:
                seedParam.seed.patternNo = i

    def _removePatternIndex(self, removed_index):
        for seedParam in iterTemplateSeedParameters(self):
            patternNo = seedParam.seed.patternNo
            if patternNo == removed_index:
                seedParam.seed.patternNo = -1  # <None>
            elif patternNo > removed_index:
                seedParam.seed.patternNo = patternNo - 1

    def contextMenu(self, name=None):

        if name == 'addNew':
            appendNewManagedParameterItem(
                self,
                self.patternList,
                baseName='Pattern',
                createValue=RollPattern,
                childFactory=lambda childName, childPattern: dict(name=childName, type='myPattern', value=childPattern, default=childPattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'),
                menuName=name,
                afterAppend=lambda _pattern: applyPatternListSideEffects(self),
            )

        QApplication.processEvents()

    def refreshSeedPatternLists(self):
        for seedParam in iterTemplateSeedParameters(self):
            seedParam.refreshPatternList()

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        applyPatternListSideEffects(self)
        # myPrint(f'>>>{lineNo():5d} PatternList.ChildAdded <<<')

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        applyPatternListSideEffects(self)
        # myPrint(f'>>>{lineNo():5d} PatternList.ChildRemoved <<<')


# class MyGrid ##############################################################


class MyGridParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyGridParameter opts')

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        self.binGrid = RollBinGrid()
        self.binGrid = opts.get('value', self.binGrid)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Local grid', value=self.binGrid, default=self.binGrid, type='myLocalGrid', expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Global grid', value=self.binGrid, default=self.binGrid, type='myGlobalGrid', expanded=False, flat=True, decimals=d, suffix=s))

        bindChildParameters(self, {
            'parL': 'Local grid',
            'parG': 'Global grid',
        })
        connectTreeStateChangedSignals([
            (self.parL, self.changedL),
            (self.parG, self.changedG),
        ])

        QApplication.processEvents()

    def changedL(self):
        self.binGrid = applyLocalGridValues(self.binGrid, self.parL.value())

    def changedG(self):
        self.binGrid = applyGlobalGridValues(self.binGrid, self.parG.value())

    def value(self):
        return self.binGrid


# class MyAnalysis ##########################################################


class MyAnalysisParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyAnalysisParameter opts')

        d = opts.get('decimals', 7)
        s = opts.get('suffix', 'm')

        survey = RollSurvey()
        self.survey = opts.get('value', survey)
        self.analysisValues = analysisValuesFromSurvey(self.survey)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Binning area', type='myRectF', value=self.analysisValues.area, default=self.analysisValues.area, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning angles', type='myBinAngles', value=self.analysisValues.angles, default=self.analysisValues.angles, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning offsets', type='myBinOffset', value=self.analysisValues.offset, default=self.analysisValues.offset, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Unique offsets', type='myUniqOff', value=self.analysisValues.unique, default=self.analysisValues.unique, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning method', type='myBinMethod', value=self.analysisValues.binning, default=self.analysisValues.binning, expanded=False, flat=True, decimals=d, suffix=s))

        bindChildParameters(self, {
            'parB': 'Binning area',
            'parA': 'Binning angles',
            'parO': 'Binning offsets',
            'parU': 'Unique offsets',
            'parM': 'Binning method',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyAnalysisParameters(self)

    def value(self):
        return self.analysisValues.asTuple()


# class MyReflector #########################################################


class MyReflectorsParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyReflectorsParameter opts')

        survey = RollSurvey()
        self.survey = opts.get('value', survey)

        self.reflectorValues = reflectorValuesFromSurvey(self.survey)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Dipping plane', type='myPlane', value=self.reflectorValues.plane, default=self.reflectorValues.plane, expanded=False, flat=True))
            self.addChild(dict(name='Buried sphere', type='mySphere', value=self.reflectorValues.sphere, default=self.reflectorValues.sphere, expanded=False, flat=True))

        bindChildParameters(self, {
            'parP': 'Dipping plane',
            'parS': 'Buried sphere',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyReflectorParameters(self)

    def value(self):
        return self.reflectorValues.asTuple()


# class MyConfiguration #####################################################


class MyConfigurationParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyConfigurationParameter opts')

        survey = RollSurvey()
        self.survey = opts.get('value', survey)

        # survey Configuration
        # the use of 'type' caused errors: 'str' object is not callable error in python. Solved by using 'typ' and 'nam' instead
        # see: https://stackoverflow.com/questions/6039605/why-does-code-like-str-str-cause-a-typeerror-but-only-the-second-time
        self.configurationValues = configurationValuesFromSurvey(self.survey)
        surTypes = SurveyType.names()

        with self.treeChangeBlocker():
            self.addChild(dict(name='Survey CRS', type='myCrs2', value=self.configurationValues.crs, default=self.configurationValues.crs, expanded=False, flat=True))
            self.addChild(dict(name='Survey type', type='myList', value=self.configurationValues.typ, default=self.configurationValues.typ, limits=surTypes))
            self.addChild(dict(name='Survey name', type='str', value=self.configurationValues.nam, default=self.configurationValues.nam))

        bindChildParameters(self, {
            'parC': 'Survey CRS',
            'parT': 'Survey type',
            'parN': 'Survey name',
        })

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        applyConfigurationParameterValues(self)

    def value(self):
        return self.configurationValues.asTuple()


# class MySurvey ############################################################


# MySurveyParameterItem and MySurveyParameter are currently not being used.
class MySurveyParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.initializePreviewItem(param)

    def showPreviewInformation(self, param):
        t = 'Not yet implemented'
        self.updatePreviewLabelText(t)
        # myPrint(f'>>>{lineNo():5d} MySurveyParameterItem.showPreviewInformation | t = {t} <<<')


class MySurveyParameter(MyGroupParameter):

    itemClass = MySurveyParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in mySurvey Parameter opts')

        self.survey = opts.get('value', RollSurvey())

        brush = '#add8e6'

        with self.treeChangeBlocker():
            self.addChild(dict(brush=brush, name='Survey configuration', type='myConfiguration', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey analysis', type='myAnalysis', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey reflectors', type='myReflectors', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey grid', type='myGrid', value=self.survey.grid, default=self.survey.grid))
            self.addChild(dict(brush=brush, name='Block list', type='myBlockList', value=self.survey.blockList, default=self.survey.blockList, survey=self.survey))
            self.addChild(dict(brush=brush, name='Pattern list', type='myPatternList', value=self.survey.patternList, default=self.survey.patternList, survey=self.survey))

        QApplication.processEvents()

    def value(self):
        return self.survey


# method registerAllParameterTypes ##########################################


def registerAllParameterTypes():

    # first, register *simple* parameters, already defined in other files
    registerParameterType('int', MyIntParameter, override=True)
    registerParameterType('float', MyFloatParameter, override=True)
    registerParameterType('myInt', MyIntParameter, override=True)
    registerParameterType('myFloat', MyFloatParameter, override=True)

    # then, register the parameters, already defined in other files
    registerParameterType('myCmap', MyCmapParameter, override=True)
    registerParameterType('myCrs', MyCrsParameter, override=True)
    registerParameterType('myCrs2', MyCrs2Parameter, override=True)
    registerParameterType('myGroup', MyGroupParameter, override=True)
    registerParameterType('myList', MyListParameter, override=True)
    registerParameterType('myMarker', MyMarkerParameter, override=True)
    registerParameterType('myNVector', MyNVectorParameter, override=True)
    registerParameterType('myPen', MyPenParameter, override=True)
    registerParameterType('myPoint2D', MyPoint2DParameter, override=True)
    registerParameterType('myPoint3D', MyPoint3DParameter, override=True)
    registerParameterType('myRange', MyRangeParameter, override=True)
    registerParameterType('myRectF', MyRectParameter, override=True)
    registerParameterType('mySlider', MySliderParameter, override=True)
    registerParameterType('mySymbols', MySymbolParameter, override=True)
    registerParameterType('myVector', MyVectorParameter, override=True)

    # next, register parameters, defined in this  file
    registerParameterType('myAnalysis', MyAnalysisParameter, override=True)
    registerParameterType('myBinAngles', MyBinAnglesParameter, override=True)
    registerParameterType('myGrid', MyGridParameter, override=True)
    registerParameterType('myBinMethod', MyBinMethodParameter, override=True)
    registerParameterType('myBinOffset', MyBinOffsetParameter, override=True)
    registerParameterType('myBlock', MyBlockParameter, override=True)
    registerParameterType('myBlockList', MyBlockListParameter, override=True)
    registerParameterType('myCircle', MyCircleParameter, override=True)
    registerParameterType('myConfiguration', MyConfigurationParameter, override=True)
    registerParameterType('myGlobalGrid', MyGlobalGridParameter, override=True)
    registerParameterType('myLocalGrid', MyLocalGridParameter, override=True)
    registerParameterType('myPattern', MyPatternParameter, override=True)
    registerParameterType('myPatternList', MyPatternListParameter, override=True)
    registerParameterType('myPlane', MyPlaneParameter, override=True)
    registerParameterType('myReflectors', MyReflectorsParameter, override=True)
    registerParameterType('myRoll', MyRollParameter, override=True)
    registerParameterType('myRollList', MyRollListParameter, override=True)
    registerParameterType('myTemplateSeed', MySeedParameter, override=True)
    registerParameterType('myPatternSeed', MyPatternSeedParameter, override=True)
    registerParameterType('myTemplateSeedList', MySeedListParameter, override=True)
    registerParameterType('myPatternSeedList', MyPatternSeedListParameter, override=True)
    registerParameterType('mySphere', MySphereParameter, override=True)
    registerParameterType('mySpiral', MySpiralParameter, override=True)
    registerParameterType('mySurvey', MySurveyParameter, override=True)
    registerParameterType('myTemplate', MyTemplateParameter, override=True)
    registerParameterType('myTemplateList', MyTemplateListParameter, override=True)
    registerParameterType('myUniqOff', MyUniqOffParameter, override=True)
    registerParameterType('myWell', MyWellParameter, override=True)
