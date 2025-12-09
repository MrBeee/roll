import math
import os

from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtCore import QFileInfo, QPointF
from qgis.PyQt.QtGui import QColor, QVector3D
from qgis.PyQt.QtWidgets import QApplication, QMessageBox

from . import config  # used to pass initial settings
from .aux_functions import myPrint
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
from .roll_angles import RollAngles
from .roll_bingrid import RollBinGrid
from .roll_binning import BinningList, BinningType, RollBinning
from .roll_block import RollBlock
from .roll_circle import RollCircle
from .roll_offset import RollOffset
from .roll_pattern import RollPattern
from .roll_pattern_seed import RollPatternSeed
from .roll_plane import RollPlane
from .roll_seed import RollSeed, SeedType
from .roll_sphere import RollSphere
from .roll_spiral import RollSpiral
from .roll_survey import RollSurvey, SurveyType
from .roll_template import RollTemplate
from .roll_translate import RollTranslate
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
# sigValueChanged     = QtCore.Signal(object, object)                ## self, value  emitted when value is finished being edited
# sigValueChanging    = QtCore.Signal(object, object)                ## self, value  emitted as value is being edited
# sigChildAdded       = QtCore.Signal(object, object, object)        ## self, child, index
# sigChildRemoved     = QtCore.Signal(object, object)                ## self, child
# sigRemoved          = QtCore.Signal(object)                        ## self
# sigParentChanged    = QtCore.Signal(object, object)                ## self, parent
# sigLimitsChanged    = QtCore.Signal(object, object)                ## self, limits
# sigDefaultChanged   = QtCore.Signal(object, object)                ## self, default
# sigNameChanged      = QtCore.Signal(object, object)                ## self, name
# sigOptionsChanged   = QtCore.Signal(object, object)                ## self, {opt:val, ...}
# sigStateChanged     = QtCore.Signal(object, object, object)        ## self, change, info
# sigTreeStateChanged = QtCore.Signal(object, object)                ## self, changes
#                                                                    ## changes = [(param, change, info), ...]


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

### class MyBinAngles #########################################################


class MyBinAnglesParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        maxInc = param.child('Max inclination').opts['value']
        minInc = param.child('Min inclination').opts['value']

        d = param.opts.get('decimals', 3)
        if minInc == 0.0:
            t = f'AoI < {maxInc:.{d}g} deg'
        else:
            t = f'{minInc:.{d}g} < AoI < {maxInc:.{d}g} deg'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parAx = self.child('Min azimuth')
        self.parAy = self.child('Max azimuth')
        self.parIx = self.child('Min inclination')
        self.parIy = self.child('Max inclination')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.angles.azimuthal.setX(self.parAx.value())
        self.angles.azimuthal.setY(self.parAy.value())
        self.angles.reflection.setX(self.parIx.value())
        self.angles.reflection.setY(self.parIy.value())

    def value(self):
        return self.angles


### class MyBinOffset #########################################################


class MyBinOffsetParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

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

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parXmin = self.child('Min x-offset')
        self.parXmax = self.child('Max x-offset')
        self.parYmin = self.child('Min y-offset')
        self.parYmax = self.child('Max y-offset')
        self.parRmin = self.child('Min r-offset')
        self.parRmax = self.child('Max r-offset')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        #  read parameter changes here
        xmin = self.parXmin.value()
        xmax = self.parXmax.value()
        ymin = self.parYmin.value()
        ymax = self.parYmax.value()
        rmin = self.parRmin.value()
        rmax = self.parRmax.value()

        self.offset.rctOffsets.setLeft(min(xmin, xmax))
        self.offset.rctOffsets.setRight(max(xmin, xmax))
        self.offset.rctOffsets.setTop(min(ymin, ymax))
        self.offset.rctOffsets.setBottom(max(ymin, ymax))
        self.offset.radOffsets.setX(min(rmin, rmax))
        self.offset.radOffsets.setY(max(rmin, rmax))

    def value(self):
        return self.offset


### class MyUniqOff ###########################################################


class MyUniqOffParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        apply = param.child('Apply pruning').opts['value']
        dOffset = param.child('Delta offset').opts['value']
        dAzimuth = param.child('Delta azimuth').opts['value']

        if not apply:
            t = 'Not used'
        else:
            t = f'@ {dOffset}m, {dAzimuth}°'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.unique = RollOffset()
        self.unique = opts.get('value', self.unique)

        tip = 'Write back rounded offset- and azimuth values back to analysis results'
        with self.treeChangeBlocker():
            self.addChild(dict(name='Apply pruning', value=self.unique.apply, default=self.unique.apply, type='bool'))
            self.addChild(dict(name='Write rounded', value=self.unique.write, default=self.unique.write, type='bool', tip=tip))
            self.addChild(dict(name='Delta offset', value=self.unique.dOffset, default=self.unique.dOffset, type='float', decimals=d, suffix='m'))
            self.addChild(dict(name='Delta azimuth', value=self.unique.dAzimuth, default=self.unique.dAzimuth, type='float', decimals=d, suffix='deg'))

        self.parP = self.child('Apply pruning')
        self.parR = self.child('Write rounded')
        self.parO = self.child('Delta offset')
        self.parA = self.child('Delta azimuth')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.unique.apply = self.parP.value()
        self.unique.write = self.parR.value()
        self.unique.dOffset = self.parO.value()
        self.unique.dAzimuth = self.parA.value()

    def value(self):
        return self.unique


### class MyBinMethod #########################################################


class MyBinMethodParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        binMethod = param.child('Binning method').opts['value']
        vInterval = param.child('Interval velocity').opts['value']
        t = f'{binMethod} @ Vint={vInterval}m/s'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parM = self.child('Binning method')
        self.parV = self.child('Interval velocity')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        index = BinningList.index(self.parM.value())
        self.binning.method = BinningType(index)
        self.binning.vint = self.parV.value()

    def value(self):
        return self.binning


### class MyPlane #############################################################


class MyPlaneParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 5)
        dip = param.child('Plane dip').opts['value']
        azi = param.child('Plane azimuth').opts['value']
        z = param.child('Plane anchor').opts['value'].z()

        if dip == 0:
            t = f'horizontal, depth={-z:.{d}g}m'
        else:
            t = f'dipping, azi={azi:.{d}g}°, dip={dip:.{d}g}°'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parO = self.child('Plane anchor')
        self.parA = self.child('Plane azimuth')
        self.parD = self.child('Plane dip')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.plane.anchor = self.parO.value()
        self.plane.azi = self.parA.value()
        self.plane.dip = self.parD.value()

    def value(self):
        return self.plane


### class MySphere ############################################################


class MySphereParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 5)
        r = param.child('Sphere radius').opts['value']
        z = param.child('Sphere origin').opts['value'].z()
        t = f'r={r:.{d}g}m, depth={-z:.{d}g}m'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parO = self.child('Sphere origin')
        self.parR = self.child('Sphere radius')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.sphere.origin = self.parO.value()
        self.sphere.radius = self.parR.value()

    def value(self):
        return self.sphere


### class MyLocalGrid #########################################################


class MyLocalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        fold = param.child('Max fold').opts['value']
        xBin = param.child('Bin size [x]').opts['value']
        yBin = param.child('Bin size [y]').opts['value']

        if fold < 0:
            t = f'{xBin} x {yBin}m, fold undefined'
        else:
            t = f'{xBin}x{yBin}m, fold {fold} max'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parBx = self.child('Bin size [x]')
        self.parBy = self.child('Bin size [y]')
        self.parDx = self.child('Bin offset [x]')
        self.parDy = self.child('Bin offset [y]')
        self.parLx = self.child('Stake nr @ origin')
        self.parLy = self.child('Line nr @ origin')
        self.parSx = self.child('Stake increments')
        self.parSy = self.child('Line increments')
        self.parFo = self.child('Max fold')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        # local grid
        self.binGrid.binSize.setX(self.parBx.value())
        self.binGrid.binSize.setY(self.parBy.value())
        self.binGrid.binShift.setX(self.parDx.value())
        self.binGrid.binShift.setY(self.parDy.value())
        self.binGrid.stakeOrig.setX(self.parLx.value())
        self.binGrid.stakeOrig.setY(self.parLy.value())
        self.binGrid.stakeSize.setX(self.parSx.value())
        self.binGrid.stakeSize.setY(self.parSy.value())
        self.binGrid.fold = self.parFo.value()

    def value(self):
        return self.binGrid


### class MyGlobalGrid ########################################################


class MyGlobalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        e = param.child('Bin origin   [E]').opts['value']
        n = param.child('Bin origin   [N]').opts['value']
        a = param.child('Azimuth').opts['value']
        t = f'o({e:,}, {n:,}), a={a:.{d}g} deg'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parOx = self.child('Bin origin   [E]')
        self.parOy = self.child('Bin origin   [N]')
        self.parSx = self.child('Scale factor [E]')
        self.parSy = self.child('Scale factor [N]')
        self.parAz = self.child('Azimuth')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        # global grid
        self.binGrid.orig.setX(self.parOx.value())
        self.binGrid.orig.setY(self.parOy.value())
        self.binGrid.scale.setX(self.parSx.value())
        self.binGrid.scale.setY(self.parSy.value())
        self.binGrid.angle = self.parAz.value()

    def value(self):
        return self.binGrid


### class MyBlock #############################################################


class MyBlockParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        QApplication.processEvents()

    def showPreviewInformation(self, param):
        templates = param.child('Template list')
        nTemplates = 0
        nBlockShots = 0
        if templates.hasChildren():
            for template in templates:
                nTemplates += 1
                nTemplateShots = 0

                seeds = template.child('Seed list')
                if seeds.hasChildren():
                    for seed in seeds:
                        nSeedShots = 0
                        bSource = seed.child('Source seed').opts['value']

                        if bSource:
                            seedType = seed.child('Seed type').opts['value']
                            if seedType == 'Circle':
                                nSeedShots = seed.child('Circle grow steps', 'Points').opts['value']
                            elif seedType == 'Spiral':
                                nSeedShots = seed.child('Spiral grow steps', 'Points').opts['value']
                            elif seedType == 'Well':
                                nSeedShots = seed.child('Well grow steps', 'Points').opts['value']
                            else:
                                # grid stationary or rolling
                                nPlane = seed.child('Grid grow steps', 'Planes', 'N').opts['value']
                                nLines = seed.child('Grid grow steps', 'Lines', 'N').opts['value']
                                nPoint = seed.child('Grid grow steps', 'Points', 'N').opts['value']
                                nSeedShots = nPlane * nLines * nPoint

                                if seedType == 'Grid (roll along)':
                                    # only the rolling shots are afffected by roll along operations
                                    nPlane = template.child('Roll steps', 'Planes', 'N').opts['value']
                                    nLines = template.child('Roll steps', 'Lines', 'N').opts['value']
                                    nPoint = template.child('Roll steps', 'Points', 'N').opts['value']
                                    nRollSteps = nPlane * nLines * nPoint
                                    nSeedShots *= nRollSteps

                            nTemplateShots += nSeedShots
                nBlockShots += nTemplateShots

        t = f'{nTemplates} template(s), {int(nBlockShots + 0.5)} src points'

        QApplication.processEvents()

        self.previewLabel.setText(t)
        self.previewLabel.update()
        # myPrint(f'>>>{lineNo():5d} MyBlockParameterItem.showPreviewInformation | t = {t} <<<')


class MyBlockParameter(MyGroupParameter):

    itemClass = MyBlockParameterItem

    def __init__(self, **opts):

        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage block'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBlockParameter opts')

        self.block = RollBlock()
        self.block = opts.get('value', self.block)
        directory = opts.get('directory', None)


        with self.treeChangeBlocker():
            self.addChild(dict(name='Source boundary', type='myRectF', value=self.block.borders.srcBorder, default=self.block.borders.srcBorder, flat=True, expanded=False))
            self.addChild(dict(name='Receiver boundary', type='myRectF', value=self.block.borders.recBorder, default=self.block.borders.recBorder, flat=True, expanded=False))
            self.addChild(dict(name='Template list', type='myTemplateList', value=self.block.templateList, default=self.block.templateList, flat=True, expanded=True, brush='#add8e6', decimals=5, suffix='m', directory=directory))

        self.parS = self.child('Source boundary')
        self.parR = self.child('Receiver boundary')
        self.parT = self.child('Template list')

        self.parS.sigValueChanged.connect(self.changed)
        self.parR.sigValueChanged.connect(self.changed)
        self.parT.sigValueChanged.connect(self.changed)

        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def nameChanged(self, _):
        self.block.name = self.name()

    def changed(self):
        self.block.borders.recBorder = self.parR.value()
        self.block.borders.srcBorder = self.parS.value()
        self.block.templateList = self.parT.value()

    def value(self):
        return self.block

    def contextMenu(self, name=None):
        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyBlockListParameter):
            raise ValueError("Need 'MyBlockListParameter' instances at this point")

        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            reply = QMessageBox.question(None, 'Please confirm', 'Delete selected block ?', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove()
                parent.blockList.pop(index)
                parent.sigChildRemoved.emit(self, parent)

        elif name == 'moveUp':
            if index > 0:
                self.remove()

                block = parent.blockList.pop(index)
                parent.blockList.insert(index - 1, block)
                parent.insertChild(index - 1, dict(name=block.name, type='myBlock', value=block, default=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                block = parent.blockList.pop(index)
                parent.blockList.insert(index + 1, block)
                parent.insertChild(index + 1, dict(name=block.name, type='myBlock', value=block, default=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


### class MyTemplate ##########################################################


class MyTemplateParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        nSeeds = 0
        nTemplateShots = 0

        seeds = param.child('Seed list')
        t = 'No seeds defined'
        if seeds.hasChildren():
            for seed in seeds:
                nSeeds += 1
                bSource = seed.child('Source seed').opts['value']

                if bSource:
                    seedType = seed.child('Seed type').opts['value']
                    if seedType == 'Circle':
                        nSeedShots = seed.child('Circle grow steps', 'Points').opts['value']
                    elif seedType == 'Spiral':
                        nSeedShots = seed.child('Spiral grow steps', 'Points').opts['value']
                    elif seedType == 'Well':
                        nSeedShots = seed.child('Well grow steps', 'Points').opts['value']
                    else:
                        # grid stationary or rolling
                        nPlane = seed.child('Grid grow steps', 'Planes', 'N').opts['value']
                        nLines = seed.child('Grid grow steps', 'Lines', 'N').opts['value']
                        nPoint = seed.child('Grid grow steps', 'Points', 'N').opts['value']

                        nSeedShots = nPlane * nLines * nPoint

                        if seedType == 'Grid (roll along)':
                            # only the rolling shots are afffected by roll along operations
                            nPlane = param.child('Roll steps', 'Planes', 'N').opts['value']
                            nLines = param.child('Roll steps', 'Lines', 'N').opts['value']
                            nPoint = param.child('Roll steps', 'Points', 'N').opts['value']

                            nRollSteps = nPlane * nLines * nPoint
                            nSeedShots *= nRollSteps

                    nTemplateShots += nSeedShots

            t = f'{nSeeds} seed(s), {int(nTemplateShots + 0.5)} src points'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        template = RollTemplate()
        self.template = opts.get('value', template)
        directory = opts.get('directory', None)

        with self.treeChangeBlocker():
            self.addChild(dict(name='Roll steps', type='myRollList', value=self.template.rollList, default=self.template.rollList, expanded=True, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Seed list', type='myTemplateSeedList', value=self.template.seedList, default=self.template.seedList, brush='#add8e6', flat=True, directory=directory))

        self.parR = self.child('Roll steps')
        self.parS = self.child('Seed list')

        self.parR.sigValueChanged.connect(self.changed)
        self.parS.sigValueChanged.connect(self.changed)
        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def nameChanged(self, _):

        self.template.name = self.name()

    def changed(self):
        self.template.rollList = self.parR.value()
        self.template.seedList = self.parS.value()

    def value(self):
        return self.template

    def contextMenu(self, name=None):
        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyTemplateListParameter):
            raise ValueError("Need 'MyTemplateListParameter' instances at this point")

        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            reply = QMessageBox.question(None, 'Please confirm', 'Delete selected template ?', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove()
                parent.templateList.pop(index)
                parent.sigChildRemoved.emit(self, parent)

        elif name == 'moveUp':
            if index > 0:
                self.remove()

                template = parent.templateList.pop(index)
                parent.templateList.insert(index - 1, template)
                parent.insertChild(index - 1, dict(name=template.name, type='myTemplate', value=template, default=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                template = parent.templateList.pop(index)
                parent.templateList.insert(index + 1, template)
                parent.insertChild(index + 1, dict(name=template.name, type='myTemplate', value=template, default=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


### class MyRollList ##########################################################


class MyRollListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        nPlane = param.child('Planes', 'N').opts['value']
        nLines = param.child('Lines', 'N').opts['value']
        nPoint = param.child('Points', 'N').opts['value']

        nRollSteps = nPlane * nLines * nPoint
        t = f'{nRollSteps} points ({nPlane} x {nLines} x {nPoint})'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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
        # paramList defined here, as the childs may be substituted by different children, due to MyRollParameters moving up/down in the list
        paramList = [self.child('Planes'), self.child('Lines'), self.child('Points')]

        self.moveList[0] = paramList[0].value()
        self.moveList[1] = paramList[1].value()
        self.moveList[2] = paramList[2].value()

    def value(self):
        return self.moveList


### class MyRoll ##############################################################


class MyRollParameterItem(MyGroupParameterItem):                      # modeled after PenParameterItem from pen.py in pyqtgraph
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        n = param.child('N').opts['value']
        x = param.child('dX').opts['value']
        y = param.child('dY').opts['value']
        z = param.child('dZ').opts['value']
        t = f'{n} x ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.parN = self.child('N')
        self.parX = self.child('dX')
        self.parY = self.child('dY')
        self.parZ = self.child('dZ')
        self.parA = self.child('azim')
        self.parT = self.child('tilt')

        self.parN.sigValueChanged.connect(self.changedN)
        self.parX.sigValueChanged.connect(self.changedXYZ)
        self.parY.sigValueChanged.connect(self.changedXYZ)
        self.parZ.sigValueChanged.connect(self.changedXYZ)
        self.parA.sigValueChanged.connect(self.changedA)
        self.parT.sigValueChanged.connect(self.changedT)

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
        self.row.steps = self.parN.value()
        self.sigValueChanging.emit(self, self.value())
        # myPrint(f'>>>{lineNo():5d} MyRollParameter.changedN <<<')

    def changedXYZ(self):
        self.row.increment.setX(self.parX.value())
        self.row.increment.setY(self.parY.value())
        self.row.increment.setZ(self.parZ.value())

        self.setAzimuth()
        self.setTilt()
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
                    name0 = parent.childs[index - 0].name()
                    name1 = parent.childs[index - 1].name()

                    parent.childs[index - 0].remove()
                    parent.childs[index - 1].remove()

                    move0 = parent.moveList[index - 0]                          # get value of move parameters
                    move1 = parent.moveList[index - 1]

                    parent.insertChild(index - 1, dict(name=name1, type='myRoll', value=move0, default=move0, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
                    parent.insertChild(index - 0, dict(name=name0, type='myRoll', value=move1, default=move1, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

                    move0 = parent.moveList.pop(index)                          # get the move list in the right order
                    parent.moveList.insert(index - 1, move0)
                    parent.changed()                                            # update the parent

                    value = parent.value()
                    myPrint(value)

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                with parent.treeChangeBlocker():

                    name0 = parent.childs[index + 0].name()
                    name1 = parent.childs[index + 1].name()

                    parent.childs[index + 1].remove()
                    parent.childs[index + 0].remove()

                    move1 = parent.moveList[index + 1]
                    move0 = parent.moveList[index + 0]                          # get value of move parameters

                    parent.insertChild(index + 0, dict(name=name0, type='myRoll', value=move1, default=move1, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
                    parent.insertChild(index + 1, dict(name=name1, type='myRoll', value=move0, default=move0, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

                    move0 = parent.moveList.pop(index)                          # get the move list in the right order
                    parent.moveList.insert(index + 1, move0)
                    parent.changed()                                            # update the parent

                    value = parent.value()
                    myPrint(value)

                    # self.remove()
                    # name = self.name()
                    # move = parent.moveList.pop(index)
                    # parent.moveList.insert(index + 1, move)
                    # parent.insertChild(index + 1, dict(name=name, type='myRoll', value=move, expanded=False, flat=True, decimals=5, suffix='m'))


### class MySeedList ##########################################################


class MySeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        QApplication.processEvents()

    def showPreviewInformation(self, param):
        nChilds = len(param.childs)
        nSource = 0

        if nChilds == 0:
            t = 'No seeds'
        else:
            for child in param.childs:
                if not isinstance(child, MySeedParameter):
                    raise ValueError("Need 'MySeedParameter' instances at this point")
                seed = child.names['Source seed']
                source = seed.opts['value']
                if source:
                    nSource += 1
                t = f'{nSource} src seed(s) + {nChilds - nSource} rec seed(s)'

        self.previewLabel.setErrorCondition(nSource == 0 or nChilds == nSource)
        self.previewLabel.setText(t)
        self.previewLabel.update()
        # myPrint(f'>>>{lineNo():5d} MySeedListParameterItem.showPreviewInformation | t = {t} <<<')


class MySeedListParameter(MyGroupParameter):

    itemClass = MySeedListParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new Seed'}
        opts['tip'] = 'Right click to add seeds'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySeedListParameter opts')

        self.seedList = [RollSeed()]
        self.seedList = opts.get('value', self.seedList)
        self.directory = opts.get('directory', None)

        if not isinstance(self.seedList, list):
            raise ValueError("Need 'list' instance at this point")

        nSeeds = len(self.seedList)
        if nSeeds < 2:
            raise ValueError('Need at least two seeds for a valid template')

        with self.treeChangeBlocker():
            for n, seed in enumerate(self.seedList):
                self.addChild(dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m', directory=self.directory))

        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def value(self):
        return self.seedList

    def contextMenu(self, name=None):
        if name == 'addNew':
            n = len(self.names) + 1
            newName = f'Seed-{n}'
            while newName in self.names:
                n += 1
                newName = f'Seed-{n}'

            # this solution gives preference to source seeds over receiver seeds, provided at least one receiver seed is present
            # this is useful for templates (e.g. zigzag) where multiple source seeds are combined with a single receiver seed
            haveReceiverSeed = False
            for s in self.seedList:
                if s.bSource is False:                                          # there's at least one receiver seed present
                    haveReceiverSeed = True
                    break

            seed = RollSeed(newName)
            if haveReceiverSeed:
                seed.bSource = True
                seed.color = QColor('#77ff0000')
            else:
                seed.bSource = False
                seed.color = QColor('#7700b0f0')

            # using append/addChild instead of insert(0, ...) will add the item at the end of the list
            # self.seedList.insert(0, seed)
            # self.insertChild(0, dict(name=newName, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

            self.seedList.append(seed)
            self.addChild(dict(name=newName, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m', directory=self.directory))

            self.sigAddNew.emit(self, name)
            self.sigValueChanging.emit(self, self.value())


### class MyPatternSeedList ##########################################################


class MyPatternSeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        nChilds = len(param.childs)
        if nChilds == 0:
            t = 'No pattern seeds'
        else:
            t = f'{nChilds} pattern seed(s)'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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
            n = len(self.names) + 1
            newName = f'Seed-{n}'
            while newName in self.names:
                n += 1
                newName = f'Seed-{n}'

            seed = RollPatternSeed(newName)
            if len(self.seedList) > 0:
                seed.color = self.seedList[-1].color                            # default to last color
            else:
                seed.color = QColor('#77ff0000')                                # empty list; just make it blue

            # using append/addChild instead of insert(0, ...) will add the item at the end of the list
            # self.seedList.insert(0, seed)
            # self.insertChild(0, dict(name=newName, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

            self.seedList.append(seed)
            self.addChild(dict(name=newName, type='myPatternSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

            self.sigAddNew.emit(self, name)
            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()


### class MySeed ##############################################################


class MySeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        bSource = param.child('Source seed').opts['value']
        seedType = param.child('Seed type').opts['value']
        if seedType == 'Circle' or seedType == 'Spiral' or seedType == 'Well':
            pointList = param.opts.get('value', None).pointList                 # at some point we need to get rid of the pointList -> pointArray
            nSteps = len(pointList)
        else:
            # grid stationary or rolling
            nPlane = param.child('Grid grow steps', 'Planes', 'N').opts['value']
            nLines = param.child('Grid grow steps', 'Lines', 'N').opts['value']
            nPoint = param.child('Grid grow steps', 'Points', 'N').opts['value']
            nSteps = nPlane * nLines * nPoint

        # todo: check why seed = 0 for circle, spiral and well
        seed = 'src' if bSource else 'rec'
        t = f'{seedType} seed, {nSteps} {seed} points'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        self.seed = RollSeed()
        self.seed = opts.get('value', self.seed)
        directory = opts.get('directory', None)


        d = opts.get('decimals', 7)

        # A 'global' patternList has been defined using config.py as a backdoor;
        # as patterns are defined on a seperate (not-easy-to-access) branch in the RollSurvey object
        if self.seed.type > SeedType.fixedGrid:                                 # the assumption is that there are no patterns in circels, spirals and wells
            nPattern = 0
        else:
            nPattern = self.seed.patternNo + 1
            if nPattern >= len(config.patternList):
                nPattern = 0

        self.seedTypes = ['Grid (roll along)', 'Grid (stationary)', 'Circle', 'Spiral', 'Well']
        with self.treeChangeBlocker():
            self.addChild(dict(name='Seed type', type='myList', value=self.seedTypes[self.seed.type], default=self.seedTypes[self.seed.type], limits=self.seedTypes, brush='#add8e6'))
            self.addChild(dict(name='Source seed', type='bool', value=self.seed.bSource, default=self.seed.bSource))
            self.addChild(dict(name='Seed color', type='color', value=self.seed.color, default=self.seed.color))
            self.addChild(dict(name='Seed origin', type='myPoint3D', value=self.seed.origin, default=self.seed.origin, expanded=False, flat=True, decimals=d))

            self.addChild(dict(name='Seed pattern', type='myList', value=config.patternList[nPattern], default=config.patternList[nPattern], limits=config.patternList))
            self.addChild(dict(name='Grid grow steps', type='myRollList', value=self.seed.grid.growList, default=self.seed.grid.growList, expanded=True, flat=True, decimals=d, suffix='m', brush='#add8e6'))

            self.addChild(dict(name='Circle grow steps', type='myCircle', value=self.seed.circle, default=self.seed.circle, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
            self.addChild(dict(name='Spiral grow steps', type='mySpiral', value=self.seed.spiral, default=self.seed.spiral, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
            self.addChild(dict(name='Well grow steps', type='myWell', value=self.seed.well, default=self.seed.well, expanded=True, flat=True, brush='#add8e6', directory=directory))   # , brush='#add8e6'

        self.parT = self.child('Seed type')
        self.parR = self.child('Source seed')
        self.parL = self.child('Seed color')
        self.parO = self.child('Seed origin')
        self.parP = self.child('Seed pattern')

        self.parG = self.child('Grid grow steps')

        # circle spiral and well slow things down a lot
        self.parC = self.child('Circle grow steps')
        self.parS = self.child('Spiral grow steps')
        self.parW = self.child('Well grow steps')

        self.parT.sigValueChanged.connect(self.typeChanged)

        self.parR.sigValueChanged.connect(self.changed)
        self.parL.sigValueChanged.connect(self.changed)
        self.parO.sigValueChanged.connect(self.changed)
        self.parP.sigValueChanged.connect(self.changed)
        self.parG.sigValueChanged.connect(self.changed)

        # circle spiral and well slow things down a lot
        self.parC.sigValueChanged.connect(self.changed)
        self.parS.sigValueChanged.connect(self.changed)
        self.parW.sigValueChanged.connect(self.changed)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        self.typeChanged()

        QApplication.processEvents()

    def nameChanged(self, _):
        self.seed.name = self.name()

    def typeChanged(self):
        seedType = self.parT.value()
        self.seed.type = self.seedTypes.index(seedType)

        if seedType == 'Well':
            self.parO.show(False)
        else:
            self.parO.show(True)

        self.parG.show(seedType == 'Grid (roll along)' or seedType == 'Grid (stationary)')
        self.parP.show(seedType == 'Grid (roll along)' or seedType == 'Grid (stationary)')

        self.parC.show(seedType == 'Circle')
        self.parS.show(seedType == 'Spiral')
        self.parW.show(seedType == 'Well')

    def changed(self):
        self.seed.bSource = self.parR.value()
        self.seed.color = self.parL.value()
        self.seed.origin = self.parO.value()
        self.seed.patternNo = config.patternList.index(self.parP.value()) - 1
        self.seed.grid.growList = self.parG.value()

        # self.seed.circle = self.parC.value()
        # self.seed.spiral = self.parS.value()
        # self.seed.well = self.parW.value()

    def value(self):
        return self.seed

    def contextMenu(self, name=None):

        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MySeedListParameter):
            raise ValueError("Need 'MySeedListParameter' instances at this point")

        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            reply = QMessageBox.question(None, 'Please confirm', 'Delete selected seed ?', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove()

                parent.seedList.pop(index)
                parent.sigChildRemoved.emit(self, parent)

        elif name == 'moveUp':
            if index > 0:
                self.remove()

                seed = parent.seedList.pop(index)
                parent.seedList.insert(index - 1, seed)
                parent.insertChild(index - 1, dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                seed = parent.seedList.pop(index)
                parent.seedList.insert(index + 1, seed)
                parent.insertChild(index + 1, dict(name=seed.name, type='myTemplateSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...
        QApplication.processEvents()


### class MyPatternSeed ##############################################################


class MyPatternSeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        nPlane = param.child('Grid grow steps', 'Planes', 'N').opts['value']
        nLines = param.child('Grid grow steps', 'Lines', 'N').opts['value']
        nPoint = param.child('Grid grow steps', 'Points', 'N').opts['value']
        nSteps = nPlane * nLines * nPoint
        t = f'{nSteps} points'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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
            self.addChild(dict(name='Seed color', type='color', value=self.seed.color, default=self.seed.color))
            self.addChild(dict(name='Seed origin', type='myPoint3D', value=self.seed.origin, default=self.seed.origin, expanded=False, flat=True, decimals=d))
            self.addChild(dict(name='Grid grow steps', type='myRollList', value=self.seed.grid.growList, default=self.seed.grid.growList, expanded=True, flat=True, decimals=d, suffix='m', brush='#add8e6'))

        self.parL = self.child('Seed color')
        self.parO = self.child('Seed origin')
        self.parG = self.child('Grid grow steps')

        self.parL.sigValueChanged.connect(self.changed)
        self.parO.sigValueChanged.connect(self.changed)
        self.parG.sigValueChanged.connect(self.changed)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        QApplication.processEvents()

    def nameChanged(self, _):
        self.seed.name = self.name()

    def changed(self):
        self.seed.color = self.parL.value()
        self.seed.origin = self.parO.value()
        self.seed.grid.growList = self.parG.value()

    def value(self):
        return self.seed

    def contextMenu(self, name=None):

        parent = self.parent()
        index = parent.children().index(self)

        if not isinstance(parent, MyPatternSeedListParameter):
            raise ValueError("Need 'MyPatternSeedListParameter' instances at this point")

        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            reply = QMessageBox.question(None, 'Please confirm', 'Delete selected seed ?', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove()

                parent.seedList.pop(index)
                parent.sigChildRemoved.emit(self, parent)

        elif name == 'moveUp':
            if index > 0:
                self.remove()

                seed = parent.seedList.pop(index)
                parent.seedList.insert(index - 1, seed)
                parent.insertChild(index - 1, dict(name=seed.name, type='myPatternSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                seed = parent.seedList.pop(index)
                parent.seedList.insert(index + 1, seed)
                parent.insertChild(index + 1, dict(name=seed.name, type='myPatternSeed', value=seed, default=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...

        QApplication.processEvents()


### class MyCircle ############################################################


class MyCircleParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        r = param.child('Radius').opts['value']
        s = param.child('Point interval').opts['value']
        n = param.child('Points').opts['value']
        t = f'{n:.{d}g} points, ø{r:.{d}g}m, d{s:.{d}g}m'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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
            self.addChild(dict(name='Start angle', value=self.circle.azi0, default=self.circle.azi0, type='float', decimals=d, suffix='°E', tip=tip))
            self.addChild(dict(name='Point interval', value=self.circle.dist, default=self.circle.dist, type='float', suffix=s, tip=tip))
            self.addChild(dict(name='Points', value=self.circle.points, default=self.circle.points, type='myInt', decimals=d, enabled=False, readonly=True))    # myInt

        self.parR = self.child('Radius')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.circle.radius = self.parR.value()
        self.circle.azi0 = self.parA.value()
        self.circle.dist = self.parI.value()
        self.parN.setValue(self.circle.calcNoPoints())

    def value(self):
        return self.circle


### class MySpiral ############################################################


class MySpiralParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        r1 = param.child('Min radius').opts['value']
        r2 = param.child('Max radius').opts['value']
        s = param.child('Point interval').opts['value']
        n = param.child('Points').opts['value']
        t = f'{n:.{d}g} points, ø{r1:.{d}g}-{r2:.{d}g}m, d{s:.{d}g}m'

        self.previewLabel.setText(t)
        self.previewLabel.update()
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
            self.addChild(dict(name='Start angle', value=self.spiral.azi0, default=self.spiral.azi0, type='float', decimals=d, suffix='°E', tip=tip))
            self.addChild(dict(name='Point interval', value=self.spiral.dist, default=self.spiral.dist, type='float', decimals=d, suffix='m', tip=tip))
            self.addChild(dict(name='Points', value=self.spiral.points, default=self.spiral.points, type='myInt', decimals=d, enabled=False, readonly=True))    # myInt

        self.parR1 = self.child('Min radius')
        self.parR2 = self.child('Max radius')
        self.parDr = self.child('Radius incr')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.spiral.radMin = self.parR1.value()
        self.spiral.radMax = self.parR2.value()
        self.spiral.radInc = self.parDr.value()
        self.spiral.azi0 = self.parA.value()
        self.spiral.dist = self.parI.value()
        self.parN.setValue(self.spiral.calcNoPoints())

    def value(self):
        return self.spiral


### class MyWell ##############################################################


class MyWellParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        f = param.child('Well file').opts['value']
        s = param.child('AHD interval').opts['value']
        n = param.child('Points').opts['value']
        d = param.opts.get('decimals', 3)
        e = False

        if f is None:
            t = 'No valid well file selected'
            e = False
        elif param.well.errorText is not None:
            t = param.well.errorText
            e = True
        elif os.path.exists(f):                                         # check filename first
            f = QFileInfo(f).fileName()
            t = f'{n:.{d}g} points, in {f}, d{s:.{d}g}m'
        else:
            t = 'No valid well file selected'
            e = True

        self.previewLabel.setErrorCondition(e)
        self.previewLabel.setText(t)
        self.previewLabel.update()
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
        directory = opts.get('directory', None)

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

        self.parC = self.child('Well CRS')
        self.parF = self.child('Well file')
        self.parA = self.child('AHD start')
        self.parI = self.child('AHD interval')
        self.parN = self.child('Points')

        self.parW = self.child('Origin [well]')
        self.parG = self.child('Origin [global]')
        self.parL = self.child('Origin [local]')

        self.parC.sigValueChanged.connect(self.changedC)
        self.parF.sigValueChanged.connect(self.changedF)
        self.parA.sigValueChanged.connect(self.changedA)
        self.parI.sigValueChanged.connect(self.changedI)
        self.parN.sigValueChanged.connect(self.changedN)
        QApplication.processEvents()

    def changedF(self):
        self.well.name = self.parF.value()                                      # file name has changed

        success = self.well.readHeader(config.surveyCrs, config.glbTransform)
        if not success:
            self.well.origW = QVector3D(-999.0, -999.0, -999.0)
            self.well.origG = QPointF(-999.0, -999.0)
            self.well.origL = QPointF(-999.0, -999.0)

        self.parW.child('X').setValue(self.well.origW.x())                      # well origin in well CRS coordinates
        self.parW.child('Y').setValue(self.well.origW.y())
        self.parW.child('Z').setValue(self.well.origW.z())

        self.parG.child('X').setValue(self.well.origG.x())                      # well origin in survey global coordinates
        self.parG.child('Y').setValue(self.well.origG.y())

        self.parL.child('X').setValue(self.well.origL.x())                      # well origin in survey local coordinates
        self.parL.child('Y').setValue(self.well.origL.y())

        if success:
            self.changedA()                                                     # check ahd0 and nr of allowed intervals
        else:
            self.sigValueChanging.emit(self, self.value())                      # todo: check necessity of this statement

        QApplication.processEvents()

    def changedC(self):
        self.well.crs = self.parC.value()

        success = self.well.readHeader(config.surveyCrs, config.glbTransform)
        if not success:
            self.well.origW = QVector3D(-999.0, -999.0, -999.0)
            self.well.origG = QPointF(-999.0, -999.0)
            self.well.origL = QPointF(-999.0, -999.0)
            QMessageBox.warning(None, 'Well Seed error', self.well.errorText)

        self.parW.child('X').setValue(self.well.origW.x())                      # well origin in well CRS coordinates
        self.parW.child('Y').setValue(self.well.origW.y())
        self.parW.child('Z').setValue(self.well.origW.z())

        self.parG.child('X').setValue(self.well.origG.x())                      # well origin in survey global coordinates
        self.parG.child('Y').setValue(self.well.origG.y())

        self.parL.child('X').setValue(self.well.origL.x())                      # well origin in survey local coordinates
        self.parL.child('Y').setValue(self.well.origL.y())

        if success:
            self.changedA()                                                     # check ahd0 and nr of allowed intervals
        else:
            self.sigValueChanging.emit(self, self.value())                      # todo: check necessity of this statement

        QApplication.processEvents()

    def changedA(self):
        a = self.well.ahd0 = self.parA.value()
        s = self.well.dAhd = self.parI.value()
        n = self.well.nAhd = self.parN.value()
        z = self.well.ahdMax

        if z < 0.0:
            return

        # do integrity checks here
        td = math.floor(z)
        if a >= td:
            nMax = 1
            self.well.nAhd = nMax
            self.well.ahd0 = td
            self.parN.setValue(nMax, blockSignal=self.changedN)
            self.parA.setValue(td, blockSignal=self.changedA)
        else:
            nMax = int((z - a + s) / s)
            n = min(n, nMax)
            self.well.nAhd = n
            self.parN.setValue(n, blockSignal=self.changedN)

    def changedI(self):
        a = self.well.ahd0 = self.parA.value()
        s = self.well.dAhd = self.parI.value()
        n = self.well.nAhd = self.parN.value()
        z = self.well.ahdMax

        if z < 0.0:
            return

        # do integrity checks here
        td = math.floor(z)
        if a >= td:
            nMax = 1
            self.well.nAhd = nMax
            self.well.ahd0 = td
            self.parN.setValue(nMax, blockSignal=self.changedN)
            self.parA.setValue(td, blockSignal=self.changedA)
        else:
            td = a + (n - 1) * s
            nMax = int((z - a + s) / s)
            n = min(n, nMax)
            self.well.nAhd = n
            self.parN.setValue(n, blockSignal=self.changedN)

    def changedN(self):
        a = self.well.ahd0 = self.parA.value()
        s = self.well.dAhd = self.parI.value()
        n = self.well.nAhd = self.parN.value()
        z = self.well.ahdMax

        if z < 0.0:
            return

        # do integrity checks here
        td = math.floor(z)
        if a >= td:
            nMax = 1
            self.well.nAhd = nMax
            self.well.ahd0 = td
            self.parN.setValue(nMax, blockSignal=self.changedN)
            self.parA.setValue(td, blockSignal=self.changedA)
        else:
            td = a + (n - 1) * s
            nMax = int((z - a + s) / s)
            n = min(n, nMax)
            self.well.nAhd = n
            self.parN.setValue(n, blockSignal=self.changedN)

    def value(self):
        return self.well


### class MyTemplateList ######################################################


class MyTemplateListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new template'}
        opts['tip'] = 'Right click to add a new template'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyTemplateListParameter opts')

        self.templateList = [RollTemplate()]
        self.templateList = opts.get('value', self.templateList)

        if not isinstance(self.templateList, list):
            raise ValueError("Need 'list' instance at this point")

        nTemplates = len(self.templateList)
        if nTemplates == 0:
            raise ValueError('Need at least one template at this point')

        with self.treeChangeBlocker():
            for n, template in enumerate(self.templateList):
                self.addChild(dict(name=template.name, type='myTemplate', value=template, default=template, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)

        QApplication.processEvents()

    def value(self):
        return self.childs

    def contextMenu(self, name=None):

        if name == 'addNew':
            n = len(self.names) + 1
            newName = f'Template-{n}'
            while newName in self.names:
                n += 1
                newName = f'Template-{n}'

            template = RollTemplate(newName)
            seed1 = RollSeed('Seed-1')
            seed2 = RollSeed('Seed-2')
            seed1.bSource = True
            seed2.bSource = False
            seed1.color = QColor('#77ff0000')
            seed2.color = QColor('#7700b0f0')

            template.seedList.append(seed1)
            template.seedList.append(seed2)
            self.templateList.append(template)

            self.addChild(dict(name=newName, type='myTemplate', value=template, default=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()


### class MyBlockList #########################################################


class MyBlockListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new block'}
        opts['tip'] = 'Right click to add a new block'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBlockListParameter opts')

        self.blockList = [RollBlock()]
        self.blockList = opts.get('value', self.blockList)

        directory = opts.get('directory', None)

        if not isinstance(self.blockList, list):
            raise ValueError("Need 'BlockList' instance at this point")

        nBlocks = len(self.blockList)
        # allow for empty blockList, in case the user has not yet created any blocks
        # if nBlocks == 0:
        #     raise ValueError('Need at least one block at this point')

        with self.treeChangeBlocker():
            for block in self.blockList:
                self.addChild(dict(name=block.name, type='myBlock', value=block, default=block, expanded=(nBlocks == 1), renamable=True, flat=True, decimals=5, suffix='m', directory=directory))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

        QApplication.processEvents()

    def value(self):
        return self.blockList

    def contextMenu(self, name=None):

        if name == 'addNew':
            n = len(self.names) + 1
            newName = f'Block-{n}'
            while newName in self.names:
                n += 1
                newName = f'Block-{n}'

            block = RollBlock(newName)
            template = RollTemplate()
            seed1 = RollSeed('Seed-1')
            seed2 = RollSeed('Seed-2')
            seed1.bSource = True
            seed2.bSource = False
            seed1.color = QColor('#77ff0000')
            seed2.color = QColor('#7700b0f0')

            template.seedList.append(seed1)
            template.seedList.append(seed2)
            block.templateList.append(template)

            self.blockList.append(block)
            self.addChild(dict(name=newName, type='myBlock', value=block, default=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # myPrint(f'>>>{lineNo():5d} BlockList.ChildAdded <<<')
        ...

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # myPrint(f'>>>{lineNo():5d} BlockList.ChildRemoved <<<')
        ...

    ### class MyPattern ##########################################################


class MyPatternParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

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

        self.previewLabel.setText(t)
        self.previewLabel.update()
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

        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            reply = QMessageBox.question(None, 'Please confirm', 'Delete selected pattern ?', QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.remove()

                parent.patternList.pop(index)
                parent.sigChildRemoved.emit(self, parent)

        elif name == 'moveUp':
            if index > 0:
                self.remove()

                pattern = parent.patternList.pop(index)
                parent.patternList.insert(index - 1, pattern)
                parent.insertChild(index - 1, dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                pattern = parent.patternList.pop(index)
                parent.patternList.insert(index + 1, pattern)
                parent.insertChild(index + 1, dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...

        QApplication.processEvents()


### class MyPatternList #######################################################


class MyPatternListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new pattern'}
        opts['tip'] = 'Right click to add a new pattern'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyPatternListParameter opts')

        self.patternList = [RollPattern()]
        self.patternList = opts.get('value', self.patternList)

        if not isinstance(self.patternList, list):
            raise ValueError("Need 'list' instance at this point")

        with self.treeChangeBlocker():
            for pattern in self.patternList:
                self.addChild(dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

        QApplication.processEvents()

    def value(self):
        return self.patternList

    def contextMenu(self, name=None):

        if name == 'addNew':
            n = len(self.names) + 1
            newName = f'Pattern-{n}'
            while newName in self.names:
                n += 1
                newName = f'Pattern-{n}'

            pattern = RollPattern(newName)

            self.patternList.append(pattern)
            self.addChild(dict(name=newName, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # myPrint(f'>>>{lineNo():5d} PatternList.ChildAdded <<<')
        ...

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # myPrint(f'>>>{lineNo():5d} PatternList.ChildRemoved <<<')
        ...


### class MyGrid ##############################################################


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

        self.parL = self.child('Local grid')
        self.parG = self.child('Global grid')
        self.parL.sigTreeStateChanged.connect(self.changedL)
        self.parG.sigTreeStateChanged.connect(self.changedG)

        QApplication.processEvents()

    def changedL(self):
        # local grid
        self.binGrid.binSize = self.parL.value().binSize
        self.binGrid.binShift = self.parL.value().binShift
        self.binGrid.stakeOrig = self.parL.value().stakeOrig
        self.binGrid.stakeSize = self.parL.value().stakeSize
        self.binGrid.fold = self.parL.value().fold

    def changedG(self):
        # global grid
        self.binGrid.orig = self.parG.value().orig
        self.binGrid.scale = self.parG.value().scale
        self.binGrid.angle = self.parG.value().angle

    def value(self):
        return self.binGrid


### class MyAnalysis ##########################################################


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

        # survey limits
        self.area = self.survey.output.rctOutput
        self.angles = self.survey.angles
        self.binning = self.survey.binning
        self.offset = self.survey.offset
        self.unique = self.survey.unique

        with self.treeChangeBlocker():
            self.addChild(dict(name='Binning area', type='myRectF', value=self.area, default=self.area, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning angles', type='myBinAngles', value=self.angles, default=self.angles, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning offsets', type='myBinOffset', value=self.offset, default=self.offset, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Unique offsets', type='myUniqOff', value=self.unique, default=self.unique, expanded=False, flat=True, decimals=d, suffix=s))
            self.addChild(dict(name='Binning method', type='myBinMethod', value=self.binning, default=self.binning, expanded=False, flat=True, decimals=d, suffix=s))

        self.parB = self.child('Binning area')
        self.parA = self.child('Binning angles')
        self.parO = self.child('Binning offsets')
        self.parU = self.child('Unique offsets')
        self.parM = self.child('Binning method')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.area = self.parB.value()
        self.angles = self.parA.value()
        self.offset = self.parO.value()
        self.unique = self.parU.value()
        self.binning = self.parM.value()

    def value(self):
        return (self.area, self.angles, self.binning, self.offset, self.unique)


### class MyReflector #########################################################


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

        # survey reflectors
        self.plane = self.survey.globalPlane
        self.sphere = self.survey.globalSphere

        with self.treeChangeBlocker():
            self.addChild(dict(name='Dipping plane', type='myPlane', value=self.plane, default=self.plane, expanded=False, flat=True))
            self.addChild(dict(name='Buried sphere', type='mySphere', value=self.sphere, default=self.sphere, expanded=False, flat=True))

        self.parP = self.child('Dipping plane')
        self.parS = self.child('Buried sphere')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.plane = self.parP.value()
        self.sphere = self.parS.value()

    def value(self):
        return (self.plane, self.sphere)


### class MyConfiguration #####################################################


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
        self.crs = self.survey.crs
        self.typ = self.survey.type
        self.nam = self.survey.name
        surTypes = [e.name for e in SurveyType]

        with self.treeChangeBlocker():
            self.addChild(dict(name='Survey CRS', type='myCrs2', value=self.crs, default=self.crs, expanded=False, flat=True))
            self.addChild(dict(name='Survey type', type='myList', value=self.typ.name, default=self.typ.name, limits=surTypes))
            self.addChild(dict(name='Survey name', type='str', value=self.nam, default=self.nam))

        self.parC = self.child('Survey CRS')
        self.parT = self.child('Survey type')
        self.parN = self.child('Survey name')

        self.sigTreeStateChanged.connect(self.changed)
        QApplication.processEvents()

    def changed(self):
        self.crs = self.parC.value()
        self.typ = self.parT.value()
        self.nam = self.parN.value()

    def value(self):
        return (self.crs, self.typ, self.nam)


### class MySurvey ############################################################


# MySurveyParameterItem and MySurveyParameter are currently not being used.
class MySurveyParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        t = 'Not yet implemented'
        self.previewLabel.setText(t)
        self.previewLabel.update()
        # myPrint(f'>>>{lineNo():5d} MySurveyParameterItem.showPreviewInformation | t = {t} <<<')


class MySurveyParameter(MyGroupParameter):

    itemClass = MySurveyParameterItem

    def __init__(self, **opts):

        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in mySurvey Parameter opts')

        self.survey = RollSurvey()                                              # (re)set the survey object
        self.survey = opts.get('value', self.survey)

        brush = '#add8e6'

        with self.treeChangeBlocker():
            self.addChild(dict(brush=brush, name='Survey configuration', type='myConfiguration', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey analysis', type='myAnalysis', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey reflectors', type='myReflectors', value=self.survey, default=self.survey))
            self.addChild(dict(brush=brush, name='Survey grid', type='myGrid', value=self.survey.grid, default=self.survey.grid))
            self.addChild(dict(brush=brush, name='Block list', type='myBlockList', value=self.survey.blockList, default=self.survey.blockList))
            self.addChild(dict(brush=brush, name='Pattern list', type='myPatternList', value=self.survey.patternList, default=self.survey.patternList))

        QApplication.processEvents()

    def value(self):
        return self.survey


### method registerAllParameterTypes ##########################################


def registerAllParameterTypes():

    # first, register *simple* parameters, already defined in other files
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
