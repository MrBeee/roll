import math
import os

from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtCore import QFileInfo, QSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox

from . import config  # used to pass initial settings
from .classes import (
    BinningType,
    RollAngles,
    RollBinGrid,
    RollBinning,
    RollBlock,
    RollCircle,
    RollOffset,
    RollPattern,
    RollPlane,
    RollSeed,
    RollSphere,
    RollSpiral,
    RollSurvey,
    RollTemplate,
    RollTranslate,
    RollWell,
    binningList,
    surveyType,
)
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
from .my_preview_label import MyPreviewLabel
from .my_rectf import MyRectParameter
from .my_slider import MySliderParameter
from .my_symbols import MySymbolParameter
from .my_vector import MyVectorParameter


class MyBinAnglesPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _

        d = self.decimals
        y = val.reflection.y()
        x = val.reflection.x()

        if x == 0.0:
            t = f'AoI < {y:.{d}g} deg'
        else:
            t = f'{x:.{d}g} < AoI < {y:.{d}g} deg'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyBinAnglesPreviewLabel.ValueChanging | {t} <<<')


class MyBinAnglesParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinAnglesPreviewLabel(param))


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

        self.addChild(dict(name='Min azimuth', value=self.angles.azimuthal.x(), type='float', decimals=d, suffix='°E-ccw', limits=[0.0, 360.0], tip=tip1))
        self.addChild(dict(name='Max azimuth', value=self.angles.azimuthal.y(), type='float', decimals=d, suffix='°E-ccw', limits=[0.0, 360.0], tip=tip1))
        self.addChild(dict(name='Min inclination', value=self.angles.reflection.x(), type='float', decimals=d, suffix='°Aoi', limits=[0.0, 90.0], tip=tip2))
        self.addChild(dict(name='Max inclination', value=self.angles.reflection.y(), type='float', decimals=d, suffix='°Aoi', limits=[0.0, 90.0], tip=tip2))

        self.parAx = self.child('Min azimuth')
        self.parAy = self.child('Max azimuth')
        self.parIx = self.child('Min inclination')
        self.parIy = self.child('Max inclination')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.angles.azimuthal.setX(self.parAx.value())
        self.angles.azimuthal.setY(self.parAy.value())
        self.angles.reflection.setX(self.parIx.value())
        self.angles.reflection.setY(self.parIy.value())
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.angles


class MyBinOffsetPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        x = max(abs(val.rctOffsets.left()), abs(val.rctOffsets.right()))
        y = max(abs(val.rctOffsets.top()), abs(val.rctOffsets.bottom()))
        d = math.hypot(x, y)
        r = val.radOffsets.y()

        if r >= d:
            t = 'rectangular constraints'
        elif r < x:
            t = 'radial constraints'
        else:
            t = 'mixed constraints'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyBinOffsetPreviewLabel.ValueChanging | {t} <<<')


class MyBinOffsetParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinOffsetPreviewLabel(param))


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

        self.addChild(dict(name='Min x-offset', value=self.offset.rctOffsets.left(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Max x-offset', value=self.offset.rctOffsets.right(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Min y-offset', value=self.offset.rctOffsets.top(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Max y-offset', value=self.offset.rctOffsets.bottom(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Min r-offset', value=self.offset.radOffsets.x(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Max r-offset', value=self.offset.radOffsets.y(), type='float', decimals=d, suffix=s))

        self.parXmin = self.child('Min x-offset')
        self.parXmax = self.child('Max x-offset')
        self.parYmin = self.child('Min y-offset')
        self.parYmax = self.child('Max y-offset')
        self.parRmin = self.child('Min r-offset')
        self.parRmax = self.child('Max r-offset')

        self.sigTreeStateChanged.connect(self.changed)

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

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.offset


class MyUniqOffPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        if not val.apply:
            t = 'Not used'
        else:
            t = f'@ {val.dOffset}m, {val.dAzimuth}°'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyUniqOffPreviewLabel.ValueChanging | {t} <<<')


class MyUniqOffParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyUniqOffPreviewLabel(param))


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

        self.addChild(dict(name='Apply pruning', value=self.unique.apply, type='bool'))
        self.addChild(dict(name='Delta offset', value=self.unique.dOffset, type='float', decimals=d, suffix='m'))
        self.addChild(dict(name='Delta azimuth', value=self.unique.dAzimuth, type='float', decimals=d, suffix='deg'))

        self.parP = self.child('Apply pruning')
        self.parO = self.child('Delta offset')
        self.parA = self.child('Delta azimuth')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.unique.apply = self.parP.value()
        self.unique.dOffset = self.parO.value()
        self.unique.dAzimuth = self.parA.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.unique


class MyBinMethodPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        binningMethod = val.method.value
        method = binningList[binningMethod]
        t = f'{method} @ Vint={val.vint}m/s'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyBinMethodPreviewLabel.ValueChanging | {t} <<<')


class MyBinMethodParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinMethodPreviewLabel(param))


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

        self.addChild(dict(name='Binning method', type='myList', value=binningList[binningMethod], default=binningList[binningMethod], limits=binningList))
        self.addChild(dict(name='Interval velocity', type='float', value=self.binning.vint, decimals=d, suffix='m/s'))

        self.parM = self.child('Binning method')
        self.parV = self.child('Interval velocity')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        index = binningList.index(self.parM.value())
        self.binning.method = BinningType(index)
        self.binning.vint = self.parV.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.binning


class MyPlanePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.decimals = param.opts.get('decimals', 5)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        dip = val.dip
        azi = val.azi
        z = val.anchor.z()
        d = self.decimals

        if dip == 0:
            t = f'horizontal, depth={-z:.{d}g}m'
        else:
            t = f'dipping, azi={azi:.{d}g}°, dip={dip:.{d}g}°'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyPlanePreviewLabel.ValueChanging | {t} <<<')

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MyPlaneParameter.TreeStateChanged <<<')

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)


class MyPlaneParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyPlanePreviewLabel(param))


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

        self.addChild(dict(name='Plane anchor', type='myPoint3D', value=self.plane.anchor, decimals=d, suffix=s, expanded=False, flat=True))
        self.addChild(dict(name='Plane azimuth', type='float', value=self.plane.azi, decimals=d, suffix='°E-ccw'))
        self.addChild(dict(name='Plane dip', type='float', value=self.plane.dip, decimals=d, suffix='°', tip=tip))

        self.parO = self.child('Plane anchor')
        self.parA = self.child('Plane azimuth')
        self.parD = self.child('Plane dip')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.plane.anchor = self.parO.value()
        self.plane.azi = self.parA.value()
        self.plane.dip = self.parD.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.plane


class MySpherePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.decimals = param.opts.get('decimals', 5)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        r = val.radius
        z = val.origin.z()
        d = self.decimals
        t = f'r={r:.{d}g}m, depth={-z:.{d}g}m'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MySpherePreviewLabel.ValueChanging | {t} <<<')

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MySphereParameter.TreeStateChanged <<<')

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)


class MySphereParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySpherePreviewLabel(param))


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

        self.addChild(dict(name='Sphere origin', type='myPoint3D', value=self.sphere.origin, decimals=d, suffix=s, expanded=False, flat=True))
        self.addChild(dict(name='Sphere radius', type='float', value=self.sphere.radius, decimals=d, suffix=s))

        self.parO = self.child('Sphere origin')
        self.parR = self.child('Sphere radius')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.sphere.origin = self.parO.value()
        self.sphere.radius = self.parR.value()

        self.sigValueChanging.emit(self, self.sphere)

    def value(self):
        return self.sphere


class MyLocalGridPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        fold = val.fold

        if fold < 0:
            t = f'{val.binSize.x()}x{val.binSize.y()}m, fold undefined'
        else:
            t = f'{val.binSize.x()}x{val.binSize.y()}m, fold {fold} max'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyLocalGridPreviewLabel.ValueChanging | {t} <<<')


class MyLocalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyLocalGridPreviewLabel(param))


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

        self.addChild(dict(name='Bin size [x]', value=self.binGrid.binSize.x(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Bin size [y]', value=self.binGrid.binSize.y(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Bin offset [x]', value=self.binGrid.binShift.x(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Bin offset [y]', value=self.binGrid.binShift.y(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Stake nr @ origin', value=self.binGrid.stakeOrig.x(), type='float', decimals=d, suffix='#'))
        self.addChild(dict(name='Line nr @ origin', value=self.binGrid.stakeOrig.y(), type='float', decimals=d, suffix='#'))
        self.addChild(dict(name='Stake increments', value=self.binGrid.stakeSize.x(), type='float', decimals=d, suffix='m'))
        self.addChild(dict(name='Line increments', value=self.binGrid.stakeSize.y(), type='float', decimals=d, suffix='m'))
        self.addChild(dict(name='Max fold', value=self.binGrid.fold, type='int'))

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

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.binGrid


class MyGlobalGridPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        x = val.orig.x()
        y = val.orig.y()
        a = val.angle
        d = self.decimals
        # self.setText(f'o({x:.{d}g}, {y:.{d}g}), a={a:.{d}g} deg')
        # self.setText(f'o({x:,.{d}f}, {y:,.{d}f}), a={a:.{d}g} deg')
        t = f'o({x:,}, {y:,}), a={a:.{d}g} deg'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyGlobalGridPreviewLabel.ValueChanging | {t} <<<')


class MyGlobalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyGlobalGridPreviewLabel(param))


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

        self.addChild(dict(name='Bin origin   [E]', value=self.binGrid.orig.x(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Bin origin   [N]', value=self.binGrid.orig.y(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Scale factor [E]', value=self.binGrid.scale.x(), type='float', decimals=d, suffix='x'))
        self.addChild(dict(name='Scale factor [N]', value=self.binGrid.scale.y(), type='float', decimals=d, suffix='x'))
        self.addChild(dict(name='Azimuth', value=self.binGrid.angle, type='float', decimals=d, suffix='°E-ccw'))

        self.parOx = self.child('Bin origin   [E]')
        self.parOy = self.child('Bin origin   [N]')
        self.parSx = self.child('Scale factor [E]')
        self.parSy = self.child('Scale factor [N]')
        self.parAz = self.child('Azimuth')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        # global grid
        self.binGrid.orig.setX(self.parOx.value())
        self.binGrid.orig.setY(self.parOy.value())
        self.binGrid.scale.setX(self.parSx.value())
        self.binGrid.scale.setY(self.parSy.value())
        self.binGrid.angle = self.parAz.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.binGrid


class MyBlockPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        # these are the signals that a parameter can generate with some objects that clarify what happened
        # sigValueChanged   = QtCore.Signal(object, object)                 ## self, value  emitted when value is finished being edited
        # sigValueChanging  = QtCore.Signal(object, object)                 ## self, value  emitted as value is being edited
        # sigChildAdded     = QtCore.Signal(object, object, object)         ## self, child, index
        # sigChildRemoved   = QtCore.Signal(object, object)                 ## self, child
        # sigRemoved        = QtCore.Signal(object)                         ## self
        # sigParentChanged  = QtCore.Signal(object, object)                 ## self, parent
        # sigLimitsChanged  = QtCore.Signal(object, object)                 ## self, limits
        # sigDefaultChanged = QtCore.Signal(object, object)                 ## self, default
        # sigNameChanged    = QtCore.Signal(object, object)                 ## self, name
        # sigOptionsChanged = QtCore.Signal(object, object)                 ## self, {opt:val, ...}

        # Emitted when anything changes about this parameter at all.
        # The second argument is a string indicating what changed ('value', 'childAdded', etc..)
        # The third argument can be any extra information about the change
        #
        # sigStateChanged   = QtCore.Signal(object, object, object)         ## self, change, info

        # emitted when any child in the tree changes state
        # (but only if monitorChildren() is called)
        # sigTreeStateChanged = QtCore.Signal(object, object)               ## self, changes
        #                                                                   ## changes = [(param, change, info), ...]

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.showInformation(param)

    def showInformation(self, param):
        # block's source- and receiver boundaries are ignored
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

        self.setText(t)
        self.update()

        # print(f'+++{lineNo():5d} MyBlockPreviewLabel.showInformation | {t} +++')

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        # print(f'>>>{lineNo():5d} MyBlockPreviewLabel.ValueChanging <<<')

        self.showInformation(param)

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MyBlockParameter.TreeStateChanged <<<')

        self.showInformation(param)


class MyBlockParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBlockPreviewLabel(param))


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

        self.addChild(dict(name='Source boundary', type='myRectF', value=self.block.borders.srcBorder, flat=True, expanded=False))
        self.addChild(dict(name='Receiver boundary', type='myRectF', value=self.block.borders.recBorder, flat=True, expanded=False))
        self.addChild(dict(name='Template list', type='myTemplateList', value=self.block.templateList, flat=True, expanded=True, brush='#add8e6', decimals=5, suffix='m'))

        self.parS = self.child('Source boundary')
        self.parR = self.child('Receiver boundary')
        self.parT = self.child('Template list')

        self.parS.sigValueChanged.connect(self.valueChanged)
        self.parR.sigValueChanged.connect(self.valueChanged)
        self.parT.sigValueChanged.connect(self.valueChanged)

        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

    def nameChanged(self, _):
        self.block.name = self.name()

    def valueChanged(self):
        self.block.borders.recBorder = self.parR.value()
        self.block.borders.srcBorder = self.parS.value()
        self.block.templateList = self.parT.value()

        self.sigValueChanging.emit(self, self.value())

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
                parent.insertChild(index - 1, dict(name=block.name, type='myBlock', value=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                block = parent.blockList.pop(index)
                parent.blockList.insert(index + 1, block)
                parent.insertChild(index + 1, dict(name=block.name, type='myBlock', value=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


class MyTemplatePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.showInformation(param)

    def showInformation(self, param):
        nSeeds = 0
        nTemplateShots = 0

        seeds = param.child('Seed list')
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

        self.setText(t)
        self.update()

        # print(f'+++{lineNo():5d} MyTemplatePreviewLabel.showInformation | {t} +++')

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        # print(f'>>>{lineNo():5d} MyTemplatePreviewLabel.ValueChanging <<<')
        self.showInformation(param)

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MyTemplateParameter.TreeStateChanged <<<')

        self.showInformation(param)


class MyTemplateParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyTemplatePreviewLabel(param))


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

        self.addChild(dict(name='Roll steps', type='myRollList', value=self.template.rollList, default=self.template.rollList, expanded=True, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Seed list', type='mySeedList', value=self.template.seedList, brush='#add8e6', flat=True))

        self.parR = self.child('Roll steps')
        self.parS = self.child('Seed list')

        self.parR.sigValueChanged.connect(self.changed)
        self.parS.sigValueChanged.connect(self.changed)
        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

    def nameChanged(self, _):
        self.template.name = self.name()

    def changed(self):
        self.template.rollList = self.parR.value()
        self.template.seedList = self.parS.value()

        self.sigValueChanging.emit(self, self.value())

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
                parent.insertChild(index - 1, dict(name=template.name, type='myTemplate', value=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                template = parent.templateList.pop(index)
                parent.templateList.insert(index + 1, template)
                parent.insertChild(index + 1, dict(name=template.name, type='myTemplate', value=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


class MyRollListPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)                    # connect signal to slot

        val = param.opts.get('value', None)                                     # get *value*  from param and provide default (None)
        self.onValueChanging(None, val)                                         # initialize the label in __init__()

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        n0 = val[0].steps                                                       # prepare label text
        n1 = val[1].steps
        n2 = val[2].steps
        t = f'{n0*n1*n2} points ({n0} x {n1} x {n2})'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyRollListPreviewLabel.ValueChanging | {t} <<<')


class MyRollListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyRollListPreviewLabel(param))


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

        self.addChild(dict(name='Planes', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[0], default=self.moveList[0]))
        self.addChild(dict(name='Lines', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[1], default=self.moveList[1]))
        self.addChild(dict(name='Points', type='myRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[2], default=self.moveList[2]))

        self.par0 = self.child('Planes')
        self.par1 = self.child('Lines')
        self.par2 = self.child('Points')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.moveList[0] = self.par0.value()
        self.moveList[1] = self.par1.value()
        self.moveList[2] = self.par2.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.moveList


class MyRollPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        n = val.steps
        x = val.increment.x()
        y = val.increment.y()
        z = val.increment.z()
        d = self.decimals
        t = f'{n} x ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyRollPreviewLabel.ValueChanging | {t} <<<')


class MyRollParameterItem(MyGroupParameterItem):
    """modeled after PenParameterItem from pen.py in pyqtgraph"""

    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyRollPreviewLabel(param))


class MyRollParameter(MyGroupParameter):

    itemClass = MyRollParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyRollParameter opts')

        self.row = RollTranslate()
        self.row = opts.get('value', self.row)

        d = opts.get('decimals', 3)
        s = opts.get('suffix', '')

        self.addChild(dict(name='N', type='int', limits=[1, None], value=self.row.steps))
        self.addChild(dict(name='dX', type='float', decimals=d, suffix=s, value=self.row.increment.x()))
        self.addChild(dict(name='dY', type='float', decimals=d, suffix=s, value=self.row.increment.y()))
        self.addChild(dict(name='dZ', type='float', decimals=d, suffix=s, value=self.row.increment.z()))
        self.addChild(dict(name='azimuth', type='myFloat', decimals=d, suffix='deg', value=0.0, enabled=False, readonly=True))     # set value through setAzimuth()     # myFloat
        self.addChild(dict(name='tilt', type='myFloat', decimals=d, suffix='deg', value=0.0, enabled=False, readonly=True))        # set value through setTilt()    # myFloat

        self.parN = self.child('N')
        self.parX = self.child('dX')
        self.parY = self.child('dY')
        self.parZ = self.child('dZ')
        self.parA = self.child('azimuth')
        self.parT = self.child('tilt')

        self.setAzimuth()
        self.setTilt()

        self.sigTreeStateChanged.connect(self.changed)

    def setAzimuth(self):
        azimuth = math.degrees(math.atan2(self.row.increment.y(), self.row.increment.x()))
        self.parA.setValue(azimuth)

    def setTilt(self):
        lengthXY = math.sqrt(self.row.increment.x() ** 2 + self.row.increment.y() ** 2)
        tilt = math.degrees(math.atan2(self.row.increment.z(), lengthXY))
        self.parT.setValue(tilt)

    # update the values of the five children
    def changed(self):
        self.row.steps = self.parN.value()
        self.row.increment.setX(self.parX.value())
        self.row.increment.setY(self.parY.value())
        self.row.increment.setZ(self.parZ.value())
        self.setAzimuth()
        self.setTilt()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.row


class MySeedListPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.showInformation(param)

    def showInformation(self, param):
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

        self.setText(t)
        self.update()

        self.setErrorCondition(nSource == 0 or nChilds == nSource)

        # print(f'+++{lineNo():5d} MySeedListPreviewLabel.showInformation | {t} +++')

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        # print(f'>>>{lineNo():5d} MySeedListPreviewLabel.ValueChanging <<<')
        self.showInformation(param)

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MySeedListPreviewLabel.TreeStateChanged <<<')

        self.showInformation(param)


class MySeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySeedListPreviewLabel(param))


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

        if not isinstance(self.seedList, list):
            raise ValueError("Need 'list' instance at this point")

        nSeeds = len(self.seedList)
        if nSeeds < 2:
            raise ValueError('Need at least two seeds for a valid template')

        for n, seed in enumerate(self.seedList):
            self.addChild(dict(name=seed.name, type='mySeed', value=seed, default=seed, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)

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
            self.seedList.append(seed)

            # self.insertChild(0, dict(name=newName, type='mySeed', value=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.addChild(dict(name=newName, type='mySeed', value=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

            self.sigAddNew.emit(self, name)
            self.sigValueChanging.emit(self, self.value())


class MySeedPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        if val.type == 2:
            kind = 'circle'
            nSteps = len(val.pointList)
        elif val.type == 3:
            kind = 'spiral'
            nSteps = len(val.pointList)
        elif val.type == 4:
            kind = 'well'
            nSteps = len(val.pointList)
        else:
            kind = 'grid'
            nSteps = 1
            for growStep in val.grid.growList:                                  # iterate through all grow steps
                nSteps *= growStep.steps                                        # multiply seed's shots at each level

        if val.bSource:
            seed = 'src'
        else:
            seed = 'rec'

        t = f'{kind} seed, {nSteps} {seed} points'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MySeedPreviewLabel.ValueChanging | {t} <<<')

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MySeedPreviewLabel.TreeStateChanged <<<')

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)


class MySeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySeedPreviewLabel(param))


class MySeedParameter(MyGroupParameter):

    itemClass = MySeedParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True
        opts['context'] = {'rename': 'Rename', 'remove': 'Remove', 'moveUp': 'Move up', 'moveDown': 'Move dn', 'separator': '----', 'preview': 'Preview', 'export': 'Export'}
        opts['tip'] = 'Right click to manage seed'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in mySeed Parameter opts')

        self.seed = RollSeed()
        self.seed = opts.get('value', self.seed)

        d = opts.get('decimals', 7)

        self.seedTypes = ['Grid (roll along)', 'Grid (stationary)', 'Circle', 'Spiral', 'Well']
        self.addChild(dict(name='Seed type', type='myList', value=self.seedTypes[self.seed.type], default=self.seedTypes[self.seed.type], limits=self.seedTypes, brush='#add8e6'))
        self.addChild(dict(name='Source seed', type='bool', value=self.seed.bSource))
        self.addChild(dict(name='Seed color', type='color', value=self.seed.color))
        self.addChild(dict(name='Seed origin', type='myPoint3D', value=self.seed.origin, expanded=False, flat=True, decimals=d))

        # A 'global' patternList has been defined using config.py as a backdoor;
        # as patterns are defined on a seperate (not-easy-to-access) branch in the RollSurvey object
        pl = config.patternList
        if self.seed.type > 1:
            nPattern = 0
        else:
            nPattern = self.seed.patternNo + 1
            if nPattern >= len(pl):
                nPattern = 0
        self.addChild(dict(name='Seed pattern', type='myList', value=pl[nPattern], default=pl[nPattern], limits=pl))

        self.addChild(dict(name='Grid grow steps', type='myRollList', value=self.seed.grid.growList, default=self.seed.grid.growList, expanded=True, flat=True, decimals=d, suffix='m', brush='#add8e6'))
        self.addChild(dict(name='Circle grow steps', type='myCircle', value=self.seed.circle, default=self.seed.circle, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
        self.addChild(dict(name='Spiral grow steps', type='mySpiral', value=self.seed.spiral, default=self.seed.spiral, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'
        self.addChild(dict(name='Well grow steps', type='myWell', value=self.seed.well, default=self.seed.well, expanded=True, flat=True, brush='#add8e6'))   # , brush='#add8e6'

        self.parT = self.child('Seed type')
        self.parR = self.child('Source seed')
        self.parL = self.child('Seed color')
        self.parO = self.child('Seed origin')
        self.parP = self.child('Seed pattern')

        self.parG = self.child('Grid grow steps')
        self.parC = self.child('Circle grow steps')
        self.parS = self.child('Spiral grow steps')
        self.parW = self.child('Well grow steps')

        self.parT.sigValueChanged.connect(self.typeChanged)

        self.parR.sigValueChanged.connect(self.changed)
        self.parL.sigValueChanged.connect(self.changed)
        self.parO.sigValueChanged.connect(self.changed)
        self.parP.sigValueChanged.connect(self.changed)
        self.parG.sigValueChanged.connect(self.changed)
        self.parC.sigValueChanged.connect(self.changed)
        self.parS.sigValueChanged.connect(self.changed)
        self.parW.sigValueChanged.connect(self.changed)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

        self.typeChanged()

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
        self.seed.circle = self.parC.value()
        self.seed.spiral = self.parS.value()
        self.seed.well = self.parW.value()

        self.sigValueChanging.emit(self, self.value())

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
                parent.insertChild(index - 1, dict(name=seed.name, type='mySeed', value=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                seed = parent.seedList.pop(index)
                parent.seedList.insert(index + 1, seed)
                parent.insertChild(index + 1, dict(name=seed.name, type='mySeed', value=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


class MyCirclePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 5)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        r = val.radius
        s = val.dist
        n = val.points
        d = self.decimals
        t = f'{n:.{d}g} points, ø{r:.{d}g}m, d{s:.{d}g}m'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MyCirclePreviewLabel.ValueChanging | {t} <<<')


class MyCircleParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyCirclePreviewLabel(param))


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

        self.addChild(dict(name='Radius', value=self.circle.radius, type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Start angle', value=self.circle.azi0, type='float', decimals=d, suffix='°E', tip=tip))
        self.addChild(dict(name='Point interval', value=self.circle.dist, type='float', suffix=s, tip=tip))
        self.addChild(dict(name='Points', value=self.circle.points, type='myInt', decimals=d, enabled=False, readonly=True))    # myInt

        self.parR = self.child('Radius')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.sigTreeStateChanged.connect(self.changed)
        self.changed()

    def changed(self):
        self.circle.radius = self.parR.value()
        self.circle.azi0 = self.parA.value()
        self.circle.dist = self.parI.value()
        self.parN.setValue(self.circle.calcNoPoints())

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.circle


class MySpiralPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 5)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        r1 = val.radMin * 2
        r2 = val.radMax * 2
        s = val.dist
        n = val.points
        d = self.decimals
        t = f'{n:.{d}g} points, ø{r1:.{d}g}-{r2:.{d}g}m, d{s:.{d}g}m'

        self.setText(t)
        self.update()

        # print(f'>>>{lineNo():5d} MySpiralPreviewLabel.ValueChanging | {t} <<< ')


class MySpiralParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySpiralPreviewLabel(param))


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

        self.addChild(dict(name='Min radius', value=self.spiral.radMin, type='float', decimals=d, suffix='m'))
        self.addChild(dict(name='Max radius', value=self.spiral.radMax, type='float', decimals=d, suffix='m'))
        self.addChild(dict(name='Radius incr', value=self.spiral.radInc, type='float', decimals=d, suffix='m/360°'))
        self.addChild(dict(name='Start angle', value=self.spiral.azi0, type='float', decimals=d, suffix='°E', tip=tip))
        self.addChild(dict(name='Point interval', value=self.spiral.dist, type='float', decimals=d, suffix='m', tip=tip))
        self.addChild(dict(name='Points', value=self.spiral.points, type='myInt', decimals=d, enabled=False, readonly=True))    # myInt

        self.parR1 = self.child('Min radius')
        self.parR2 = self.child('Max radius')
        self.parDr = self.child('Radius incr')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.sigTreeStateChanged.connect(self.changed)

        self.changed()

    def changed(self):
        self.spiral.radMin = self.parR1.value()
        self.spiral.radMax = self.parR2.value()
        self.spiral.radInc = self.parDr.value()
        self.spiral.azi0 = self.parA.value()
        self.spiral.dist = self.parI.value()
        self.parN.setValue(self.spiral.calcNoPoints())

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.spiral


class MyWellPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.decimals = param.opts.get('decimals', 5)

        self.showInformation(param)

    def showInformation(self, param):
        c = param.child('Well CRS').opts['value']
        f = param.child('Well file').opts['value']
        s = param.child('AHD interval').opts['value']
        n = param.child('Points').opts['value']

        d = self.decimals
        e = False

        if not f is None and os.path.exists(f):                                 # check filename first
            f = QFileInfo(f).fileName()
            t = f'{n:.{d}g} points, in {f}, d{s:.{d}g}m'
            e = False
            if not c.isValid():                                                 # file available; next check CRS
                t = 'An invalid CRS has been selected'
                e = True
            elif c.isGeographic():
                t = 'No valid CRS (use of lat/lon angles)'
                e = True
        else:
            t = 'No valid well file selected'
            e = True

        self.setText(t)
        self.setErrorCondition(e)
        self.update()

        # print(f'+++{lineNo():5d} MyWellPreviewLabel.showInformation | {t} +++')

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        # print(f'>>>{lineNo():5d} MyWellPreviewLabel.ValueChanging <<<')

        self.showInformation(param)

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MySeedPreviewLabel.TreeStateChanged <<<')

        self.showInformation(param)


class MyWellParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyWellPreviewLabel(param))


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

        d = opts.get('decimals', 7)

        settings = QSettings(config.organization, config.application)
        directory = settings.value('settings/workingDirectory', '')             # start folder for well selection

        nameFilter = 'Deviation files [md,inc,azi] (*.wws);;OpendTect files [n,e,z,md] (*.well);;All files (*.*)'
        tip = 'SRD = Seismic Reference Datum; the horizontal surface at which TWT is assumed to be zero'
        fileName = self.well.name if self.well.name is not None and os.path.exists(self.well.name) else None

        self.addChild(dict(name='Well file', type='file', value=fileName, selectFile=fileName, acceptMode='AcceptOpen', fileMode='ExistingFile', viewMode='Detail', directory=directory, nameFilter=nameFilter))
        self.addChild(dict(name='Well CRS', type='myCrs', value=self.well.crs, default=self.well.crs, expanded=False, flat=True))
        self.addChild(dict(name='Origin [well]', type='myPoint3D', value=self.well.origW, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))
        self.addChild(dict(name='Origin [global]', type='myPoint2D', value=self.well.origG, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))
        self.addChild(dict(name='Origin [local]', type='myPoint2D', value=self.well.origL, decimals=d, expanded=False, flat=True, enabled=False, readonly=True))

        self.addChild(dict(name='AHD start', type='float', value=self.well.ahd0, decimals=d, limits=[0.0, None], suffix='m ref SRD', tip=tip))
        self.addChild(dict(name='AHD interval', type='float', value=self.well.dAhd, decimals=d, limits=[1.0, None], suffix='m'))
        self.addChild(dict(name='Points', type='int', value=self.well.nAhd, decimals=d, limits=[1, None]))

        self.parC = self.child('Well CRS')
        self.parF = self.child('Well file')
        self.parA = self.child('AHD start')
        self.parI = self.child('AHD interval')
        self.parN = self.child('Points')

        self.parC.sigValueChanged.connect(self.changedC)
        self.parF.sigValueChanged.connect(self.changedF)
        self.parA.sigValueChanged.connect(self.changedA)
        self.parI.sigValueChanged.connect(self.changedI)
        self.parN.sigValueChanged.connect(self.changedN)

        self.changedF()                                                         # this will initialise 'value'

    def changedF(self):
        f = self.well.name = self.parF.value()                                  # file name has changed
        if f is None or not os.path.exists(f):
            return

        self.well.readHeader(config.surveyCrs, config.glbTransform)

        self.child('Origin [well]', 'X').setValue(self.well.origW.x())
        self.child('Origin [well]', 'Y').setValue(self.well.origW.y())
        self.child('Origin [well]', 'Z').setValue(self.well.origW.z())

        x = self.child('Origin [global]', 'X').setValue(self.well.origG.x())
        y = self.child('Origin [global]', 'Y').setValue(self.well.origG.y())

        x = self.child('Origin [local]', 'X').setValue(self.well.origL.x())
        y = self.child('Origin [local]', 'Y').setValue(self.well.origL.y())

        self.changedA()

    def changedC(self):
        self.well.crs = self.parC.value()

        if not self.well.crs.isValid():
            QMessageBox.information(None, 'Invalid CRS', 'An invalid CRS has been selected.   \nPlease change Well CRS', QMessageBox.Ok)
            return

        if self.well.crs.isGeographic():
            QMessageBox.information(None, 'Invalid CRS', 'A geographic CRS has been selected (using lat/lon values)   \nPlease change Well CRS', QMessageBox.Ok)
            return

        if self.well.name is None or not os.path.exists(self.well.name):
            return

        self.well.readHeader(config.surveyCrs, config.glbTransform)

        x = self.child('Origin [global]', 'X').setValue(self.well.origG.x())        # these will  be different with a different well-CRS
        y = self.child('Origin [global]', 'Y').setValue(self.well.origG.y())

        x = self.child('Origin [local]', 'X').setValue(self.well.origL.x())
        y = self.child('Origin [local]', 'Y').setValue(self.well.origL.y())

        self.changedA()                                                         # check ahd0 and nr of allowed intervals

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

        self.sigValueChanging.emit(self, self.value())

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

        self.sigValueChanging.emit(self, self.value())

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

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.well


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

        for n, template in enumerate(self.templateList):
            self.addChild(dict(name=template.name, type='myTemplate', value=template, default=template, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)

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

            self.addChild(dict(name=newName, type='myTemplate', value=template, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())


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

        if not isinstance(self.blockList, list):
            raise ValueError("Need 'BlockList' instance at this point")

        nBlocks = len(self.blockList)
        if nBlocks == 0:
            raise ValueError('Need at least one block at this point')

        for n, block in enumerate(self.blockList):
            self.addChild(dict(name=block.name, type='myBlock', value=block, default=block, expanded=(n < 2), renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

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
            self.addChild(dict(name=newName, type='myBlock', value=block, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # print(f'>>>{lineNo():5d} BlockList.ChildAdded <<<')
        pass

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # print(f'>>>{lineNo():5d} BlockList.ChildRemoved <<<')
        pass


class MyPatternPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.showInformation(param)

    def showInformation(self, param):

        nPlane = param.child('Pattern grow steps', 'Planes', 'N').opts['value']
        nLines = param.child('Pattern grow steps', 'Lines', 'N').opts['value']
        nPoint = param.child('Pattern grow steps', 'Points', 'N').opts['value']
        nPoints = nPlane * nLines * nPoint

        t = f'{nPoints} points ({nPlane} x {nLines} x {nPoint})'

        self.setText(t)
        self.update()

        # print(f'+++{lineNo():5d} MyPatternPreviewLabel.showInformation | {t} +++')

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        # print(f'>>>{lineNo():5d} MyPatternPreviewLabel.ValueChanging <<<')

        self.showInformation(param)

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        # print(f'>>>{lineNo():5d} MyPatternPreviewLabel.TreeStateChanged <<<')

        self.showInformation(param)


class MyPatternParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyPatternPreviewLabel(param))


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

        d = opts.get('decimals', 7)

        self.pattern = RollPattern()
        self.pattern = opts.get('value', self.pattern)

        self.addChild(dict(name='Pattern origin', type='myPoint3D', value=self.pattern.origin, expanded=False, flat=True, decimals=d))
        self.addChild(dict(name='Pattern color', type='color', value=self.pattern.color))
        self.addChild(dict(name='Pattern grow steps', type='myRollList', value=self.pattern.growList, default=self.pattern.growList, expanded=True, flat=True, brush='#add8e6', decimals=5, suffix='m'))

        self.parC = self.child('Pattern color')
        self.parO = self.child('Pattern origin')
        self.parG = self.child('Pattern grow steps')

        self.parC.sigValueChanged.connect(self.colorChanged)
        self.parG.sigValueChanged.connect(self.growListChanged)
        self.parO.sigValueChanged.connect(self.originChanged)

        self.sigContextMenu.connect(self.contextMenu)
        self.sigNameChanged.connect(self.nameChanged)

    def nameChanged(self, _):
        self.pattern.name = self.name()

    def colorChanged(self):
        self.pattern.color = self.parC.value()

    def growListChanged(self):
        self.pattern.growList = self.parG.value()

    def originChanged(self):
        self.pattern.origin = self.parO.value()

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
                parent.insertChild(index - 1, dict(name=pattern.name, type='myPattern', value=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'moveDown':
            n = len(parent.children())
            if index < n - 1:
                self.remove()

                pattern = parent.patternList.pop(index)
                parent.patternList.insert(index + 1, pattern)
                parent.insertChild(index + 1, dict(name=pattern.name, type='myPattern', value=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


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

        for pattern in self.patternList:
            self.addChild(dict(name=pattern.name, type='myPattern', value=pattern, default=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

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
            self.addChild(dict(name=newName, type='myPattern', value=pattern, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # print(f'>>>{lineNo():5d} PatternList.ChildAdded <<<')
        pass

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # print(f'>>>{lineNo():5d} PatternList.ChildRemoved <<<')
        pass


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

        self.addChild(dict(name='Local grid', value=self.binGrid, type='myLocalGrid', expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Global grid', value=self.binGrid, type='myGlobalGrid', expanded=False, flat=True, decimals=d, suffix=s))

        self.parL = self.child('Local grid')
        self.parG = self.child('Global grid')
        self.parL.sigTreeStateChanged.connect(self.changedL)
        self.parG.sigTreeStateChanged.connect(self.changedG)

    def changedL(self):
        # local grid
        self.binGrid.binSize = self.parL.value().binSize
        self.binGrid.binShift = self.parL.value().binShift
        self.binGrid.stakeOrig = self.parL.value().stakeOrig
        self.binGrid.stakeSize = self.parL.value().stakeSize
        self.binGrid.fold = self.parL.value().fold

        self.sigValueChanging.emit(self, self.value())

    def changedG(self):
        # global grid
        self.binGrid.orig = self.parG.value().orig
        self.binGrid.scale = self.parG.value().scale
        self.binGrid.angle = self.parG.value().angle

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.binGrid


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

        self.addChild(dict(name='Binning area', type='myRectF', value=self.area, expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Binning angles', type='myBinAngles', value=self.angles, expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Binning offsets', type='myBinOffset', value=self.offset, expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Unique offsets', type='myUniqOff', value=self.unique, expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Binning method', type='myBinMethod', value=self.binning, expanded=False, flat=True, decimals=d, suffix=s))

        self.parB = self.child('Binning area')
        self.parA = self.child('Binning angles')
        self.parO = self.child('Binning offsets')
        self.parU = self.child('Unique offsets')
        self.parM = self.child('Binning method')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.area = self.parB.value()
        self.angles = self.parA.value()
        self.offset = self.parO.value()
        self.unique = self.parU.value()
        self.binning = self.parM.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return (self.area, self.angles, self.binning, self.offset, self.unique)


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

        self.addChild(dict(name='Dipping plane', type='myPlane', value=self.plane, expanded=False, flat=True))
        self.addChild(dict(name='Buried sphere', type='mySphere', value=self.sphere, expanded=False, flat=True))

        self.parP = self.child('Dipping plane')
        self.parS = self.child('Buried sphere')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.plane = self.parP.value()
        self.sphere = self.parS.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return (self.plane, self.sphere)


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
        surTypes = [e.name for e in surveyType]

        self.addChild(dict(name='Survey CRS', type='myCrs2', value=self.crs, default=self.crs, expanded=False, flat=True))
        self.addChild(dict(name='Survey type', type='myList', value=self.typ.name, default=self.typ.name, limits=surTypes))
        self.addChild(dict(name='Survey name', type='str', value=self.nam, default=self.nam))

        self.parC = self.child('Survey CRS')
        self.parT = self.child('Survey type')
        self.parN = self.child('Survey name')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        self.crs = self.parC.value()
        self.typ = self.parT.value()
        self.nam = self.parN.value()

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return (self.crs, self.typ, self.nam)


class MySurveyPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, *_):                                              # unused param, val replaced by *_
        ...
        # self.setText(val.name)
        # self.update()


class MySurveyParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySurveyPreviewLabel(param))


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

        self.addChild(dict(brush=brush, name='Survey configuration', type='myConfiguration', value=self.survey))
        self.addChild(dict(brush=brush, name='Survey analysis', type='myAnalysis', value=self.survey, default=self.survey))
        self.addChild(dict(brush=brush, name='Survey reflectors', type='myReflectors', value=self.survey, default=self.survey))
        self.addChild(dict(brush=brush, name='Survey grid', type='myGrid', value=self.survey.grid, default=self.survey.grid))
        self.addChild(dict(brush=brush, name='Block list', type='myBlockList', value=self.survey.blockList))
        self.addChild(dict(brush=brush, name='Pattern list', type='myPatternList', value=self.survey.patternList))

    def value(self):
        return self.survey


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
    registerParameterType('mySeed', MySeedParameter, override=True)
    registerParameterType('mySeedList', MySeedListParameter, override=True)
    registerParameterType('mySphere', MySphereParameter, override=True)
    registerParameterType('mySpiral', MySpiralParameter, override=True)
    registerParameterType('mySurvey', MySurveyParameter, override=True)
    registerParameterType('myTemplate', MyTemplateParameter, override=True)
    registerParameterType('myTemplateList', MyTemplateListParameter, override=True)
    registerParameterType('myUniqOff', MyUniqOffParameter, override=True)
    registerParameterType('myWell', MyWellParameter, override=True)
