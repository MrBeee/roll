import math
import os

import numpy as np
import wellpathpy as wp
from pyqtgraph.parametertree import registerParameterItemType, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem, SimpleParameter
from qgis.PyQt.QtCore import QFileInfo, QSettings
from qgis.PyQt.QtGui import QColor, QVector3D
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
from .functions import read_well_header, read_wws_header
from .my_cmap import CmapParameter
from .my_crs import MyCrsParameter
from .my_crs2 import MyCrs2Parameter
from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_list import MyListParameter
from .my_marker import MyMarkerParameter
from .my_n_vector import MyNVectorParameter
from .my_numerics import MyNumericParameterItem
from .my_pen import MyPenParameter
from .my_point3D import MyPoint3DParameter
from .my_preview_label import MyPreviewLabel
from .my_rectf import MyRectParameter
from .my_slider import MySliderParameter
from .my_symbols import MySymbolParameter
from .my_vector import MyVectorParameter


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

        self.setText(f'{n} x ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})')
        self.update()


class MyRollParameterItem(MyGroupParameterItem):
    """modeled after PenParameterItem from pen.py in pyqtgraph"""

    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyRollPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='azimuth', type='myFloat', decimals=d, suffix='deg', enabled=False, readonly=True))     # set value through setAzimuth()
        self.addChild(dict(name='tilt', type='myFloat', decimals=d, suffix='deg', enabled=False, readonly=True))        # set value through setTilt()

        self.parN = self.child('N')
        self.parX = self.child('dX')
        self.parY = self.child('dY')
        self.parZ = self.child('dZ')
        self.parA = self.child('azimuth')
        self.parT = self.child('tilt')

        self.setAzimuth()
        self.setTilt()

        self.parN.sigValueChanged.connect(self.changed)
        self.parX.sigValueChanged.connect(self.changed)
        self.parY.sigValueChanged.connect(self.changed)
        self.parZ.sigValueChanged.connect(self.changed)

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
        self.sigValueChanging.emit(self, self.row)

    def value(self):
        return self.row


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

        self.setText(f'{n0*n1*n2} points ({n0} x {n1} x {n2})')
        self.update()


class MyRollListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyRollListPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        self.addChild(dict(name='Planes', type='MyRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[0], default=self.moveList[0]))
        self.addChild(dict(name='Lines', type='MyRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[1], default=self.moveList[1]))
        self.addChild(dict(name='Points', type='MyRoll', expanded=False, flat=True, decimals=d, suffix=s, value=self.moveList[2], default=self.moveList[2]))

        self.par0 = self.child('Planes')
        self.par1 = self.child('Lines')
        self.par2 = self.child('Points')

        self.par0.sigValueChanged.connect(self.changed)
        self.par1.sigValueChanged.connect(self.changed)
        self.par2.sigValueChanged.connect(self.changed)

    def changed(self):
        self.moveList[0] = self.par0.value()
        self.moveList[1] = self.par1.value()
        self.moveList[2] = self.par2.value()
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.moveList


class MyPlanePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 5)
        val = param.opts.get('value', None)

        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        dip = val.dip
        azi = val.azi
        z = val.anchor.z()
        d = self.decimals

        if dip == 0:
            self.setText(f'horizontal, depth={-z:.{d}g}m')
        else:
            self.setText(f'dipping, azi={azi:.{d}g}°, dip={dip:.{d}g}°')
        self.update()


class MyPlaneParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyPlanePreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        self.parO.sigTreeStateChanged.connect(self.changed)
        self.parA.sigValueChanged.connect(self.changed)
        self.parD.sigValueChanged.connect(self.changed)

    # update the values of the children
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

        self.setText(f'r={r:.{d}g}m, depth={-z:.{d}g}m')
        self.update()

    def onTreeStateChanged(self, param):
        print('>>> MySphereParameter.TreeStateChanged <<<')

        if not isinstance(param, MySphereParameter):
            raise ValueError("Need 'MySphereParameter' instances at this point")

        self.onValueChanging(None, param.sphere)                                # parameter info is lagging behind applied changes; need to investigate why !


class MySphereParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySpherePreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        # self.parO.sigTreeStateChanged.connect(self.changed)
        self.parO.sigValueChanged.connect(self.changed)
        self.parR.sigValueChanged.connect(self.changed)

    # update the values of the children
    def changed(self):
        self.sphere.origin = self.parO.value()
        self.sphere.radius = self.parR.value()
        self.sigValueChanging.emit(self, self.sphere)

    def value(self):
        return self.sphere


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

        self.setText(f'{n:.{d}g} points, ø{r:.{d}g}m, d{s:.{d}g}m')
        self.update()


class MyCircleParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyCirclePreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='Points', value=self.circle.points, type='myInt', decimals=d, enabled=False, readonly=True))

        self.parR = self.child('Radius')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.parR.sigValueChanged.connect(self.changed)
        self.parA.sigValueChanged.connect(self.changed)
        self.parI.sigValueChanged.connect(self.changed)

        self.changed()

    def changed(self):
        self.circle.radius = self.parR.value()
        self.circle.azi0 = self.parA.value()
        self.circle.dist = self.parI.value()
        n = self.circle.calcNoPoints()

        self.parN.setValue(n)
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

        self.setText(f'{n:.{d}g} points, ø{r1:.{d}g}-{r2:.{d}g}m, d{s:.{d}g}m')
        self.update()


class MySpiralParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySpiralPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='Points', value=self.spiral.points, type='myInt', decimals=d, enabled=False, readonly=True))

        self.parR1 = self.child('Min radius')
        self.parR2 = self.child('Max radius')
        self.parDr = self.child('Radius incr')
        self.parA = self.child('Start angle')
        self.parI = self.child('Point interval')
        self.parN = self.child('Points')

        self.parR1.sigValueChanged.connect(self.changed)
        self.parR2.sigValueChanged.connect(self.changed)
        self.parDr.sigValueChanged.connect(self.changed)
        self.parA.sigValueChanged.connect(self.changed)
        self.parI.sigValueChanged.connect(self.changed)
        self.parN.sigValueChanged.connect(self.changed)

        self.changed()

    def changed(self):
        self.spiral.radMin = self.parR1.value()
        self.spiral.radMax = self.parR2.value()
        self.spiral.radInc = self.parDr.value()
        self.spiral.azi0 = self.parA.value()
        self.spiral.dist = self.parI.value()
        n = self.spiral.calcNoPoints()

        self.parN.setValue(n)
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.spiral


class MyWellPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 5)
        val = param.opts.get('value', None)

        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        f = val.name
        s = val.dAhd
        n = val.nAhd
        d = self.decimals

        if not f is None and os.path.exists(f):
            f = QFileInfo(f).fileName()
            self.setText(f'{n:.{d}g} points, in {f}, d{s:.{d}g}m')
        else:
            self.setText('No valid well file selected')
        self.update()


class MyWellParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyWellPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        fileName = self.well.name if os.path.exists(self.well.name) else None

        self.addChild(dict(name='Well file', type='file', value=fileName, selectFile=fileName, acceptMode='AcceptOpen', fileMode='ExistingFile', viewMode='Detail', directory=directory, nameFilter=nameFilter))
        self.addChild(dict(name='Well origin', type='myPoint3D', value=self.well.orig, decimals=d, expanded=True, flat=True, enabled=False, readonly=True))
        self.addChild(dict(name='Well CRS', type='myCrs', value=self.well.crs, default=self.well.crs, expanded=False, flat=True))

        self.addChild(dict(name='AHD start', type='float', value=self.well.ahd0, decimals=d, limits=[0.0, None], suffix='m ref SRD', tip=tip))
        self.addChild(dict(name='AHD interval', type='float', value=self.well.dAhd, decimals=d, limits=[1.0, None], suffix='m'))
        self.addChild(dict(name='Points', type='int', value=self.well.nAhd, decimals=d, limits=[1, None]))

        self.parF = self.child('Well file')
        self.parO = self.child('Well origin')
        self.parC = self.child('Well CRS')
        self.parA = self.child('AHD start')
        self.parI = self.child('AHD interval')
        self.parN = self.child('Points')

        self.parF.sigValueChanged.connect(self.changedF)
        self.parC.sigValueChanged.connect(self.changedC)
        self.parA.sigValueChanged.connect(self.changedA)
        self.parI.sigValueChanged.connect(self.changedI)
        self.parN.sigValueChanged.connect(self.changedN)

        self.changedF()                                                         # this will initialise 'value'

    def changedF(self):
        f = self.well.name = self.parF.value()                                  # only the file has changed; rest comes from self.well object
        a = self.well.ahd0
        s = self.well.dAhd
        n = self.well.nAhd

        if f is None or not os.path.exists(f):
            return

        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
        # Note: datum = kb (kelly bushing), dfe (drill floor elevation), or rt (rotary table)

        ext = QFileInfo(f).suffix()
        if ext == 'wws':
            md, _, _ = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')   # inc, azi unused and replaced by _, _
            z = self.well.ahdMax = md[-1]                                       # maximum along-hole-depth
            print('max ah depth', self.well.ahdMax)

            td = a + (n - 1) * s
            if td > z:
                td = math.floor(z)
                n = 1                                                           # can only accommodate a single point
                self.well.nAhd = n
                self.well.ahd0 = td
                self.parN.setValue(n, blockSignal=self.changedN)
                self.parA.setValue(td, blockSignal=self.changedA)
            else:
                nMax = int((z - a + s) / s)                                     # max nr points that fit in the well
                self.well.nAhd = min(n, nMax)
                self.parN.setValue(n, blockSignal=self.changedN)

            # where is the well 'in space'? First see if there's a header file, to pull information from:
            hdrFile = os.path.splitext(f)[0]
            hdrFile = hdrFile + '.hdr'
            if os.path.exists(hdrFile):                                         # open the header file
                header = wp.read_header_json(hdrFile)                           # read header in json format, as described in header dict above
            else:
                header = read_wws_header(f)                                     # get header information from wws file itself

        elif ext == 'well':
            header, index = read_well_header(f)
            pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')   # read the 4 column ascii data; skip header rows
            # transpose array to 4 rows, and read these rows
            _, _, depth, md = pos2D.T                                           # north, east unused and replaced by _, _

            hdrFile = os.path.splitext(f)[0]                                    # the self-contained 'well' file does not require a separate header file;
            hdrFile = hdrFile + '.hdr'                                          # but a header file may be used to override the included header data
            if os.path.exists(hdrFile):                                         # open the header file
                header = wp.read_header_json(hdrFile)                           # read header in json format, as described in header dict above

            md = md.flatten()
            if header['elevation'] is None:                                     # no separate header file has been provided
                header['elevation'] = md[0] - depth[0]                          # use data itself to derive wellhead elevation

            z = self.well.ahdMax = md[-1]                                       # maximum along-hole-depth

            td = a + (n - 1) * s
            if td > z:
                td = math.floor(z)
                n = 1
                self.well.nAhd = n
                self.well.ahd0 = td
                self.parN.setValue(n, blockSignal=self.changedN)
                self.parA.setValue(td, blockSignal=self.changedA)
            else:
                nMax = int((z - a + s) / s)
                self.well.nAhd = min(n, nMax)
                self.parN.setValue(n, blockSignal=self.changedN)

        else:
            raise ValueError(f'unsupported file extension: {ext}')

        self.well.orig = QVector3D(header['surface_easting'], header['surface_northing'], header['elevation'])
        self.parO.setValue(self.well.orig)

        self.sigValueChanging.emit(self, self.value())

    def changedC(self):
        c = self.parC.value()

        if not c.isValid():
            QMessageBox.information(None, 'Invalid CRS', 'An invalid CRS has been selected.   \nPlease change Well CRS', QMessageBox.Ok)
            self.parC.setValue(self.well.crs)
            return False

        if c.isGeographic():
            QMessageBox.information(None, 'Invalid CRS', 'An invalid CRS has been selected (using lat/lon values)   \nPlease change Well CRS', QMessageBox.Ok)
            self.parC.setValue(self.well.crs)
            return False

        self.well.crs = c
        return True

    def changedA(self):
        a = self.well.ahd0 = self.parA.value()
        s = self.well.dAhd = self.parI.value()
        n = self.well.nAhd = self.parN.value()
        z = self.well.ahdMax

        if z is None:
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

        if z is None:
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

        if z is None:
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


class MySeedPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)
        val = param.opts.get('value', None)

        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        if val.type == 2:
            kind = 'circle'
            nSteps = len(val.pntList3D)
        elif val.type == 3:
            kind = 'spiral'
            nSteps = len(val.pntList3D)
        elif val.type == 4:
            kind = 'well'
            nSteps = len(val.pntList3D)
        else:
            kind = 'grid'
            nSteps = 1
            for growStep in val.grid.growList:                                           # iterate through all grow steps
                nSteps *= growStep.steps                                            # multiply seed's shots at each level

        if val.bSource:
            seed = 'src'
        else:
            seed = 'rec'

        self.setText(f'{kind} seed, {nSteps} {seed} points')
        self.update()


class MySeedParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySeedPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        self.addChild(dict(name='Grid grow steps', type='MyRollList', value=self.seed.grid.growList, default=self.seed.grid.growList, expanded=True, flat=True, decimals=d, suffix='m', brush='#add8e6'))
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
        self.parR.sigValueChanged.connect(self.sourceChanged)
        self.parL.sigValueChanged.connect(self.colorChanged)
        self.parO.sigValueChanged.connect(self.originChanged)
        self.parP.sigValueChanged.connect(self.patternChanged)

        self.parG.sigValueChanged.connect(self.gridChanged)
        self.parC.sigValueChanged.connect(self.circleChanged)
        self.parS.sigValueChanged.connect(self.spiralChanged)
        self.parW.sigValueChanged.connect(self.wellChanged)

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

    def sourceChanged(self):
        self.seed.bSource = self.parR.value()

    def colorChanged(self):
        self.seed.color = self.parL.value()

    def originChanged(self):
        self.seed.origin = self.parO.value()

    def patternChanged(self):
        pattern = self.parP.value()
        self.seed.patternNo = config.patternList.index(pattern) - 1

    def gridChanged(self):
        self.seed.grid.growList = self.parG.value()

    def circleChanged(self):
        self.seed.circle = self.parC.value()

    def spiralChanged(self):
        self.seed.spiral = self.parS.value()

    def wellChanged(self):
        self.seed.well = self.parW.value()

    def value(self):
        return self.seed

    def contextMenu(self, name=None):
        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            parent = self.parent()
            if isinstance(self.parent(), MySeedListParameter):
                index = parent.children().index(self)
                reply = QMessageBox.question(None, 'Please confirm', 'Delete selected seed ?', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.remove()
                    parent.seedList.pop(index)

        elif name == 'moveUp':
            parent = self.parent()
            if isinstance(self.parent(), MySeedListParameter):
                index = parent.children().index(self)
                if index > 0:
                    child = parent.children()[index]
                    parent.insertChild(index - 1, child, autoIncrementName=None, existOk=True)
                    seed = parent.seedList.pop(index)
                    parent.seedList.insert(index - 1, seed)

        elif name == 'moveDown':
            parent = self.parent()
            if isinstance(self.parent(), MySeedListParameter):
                n = len(parent.children())
                index = parent.children().index(self)
                if index < n - 1:
                    child = parent.children()[index]
                    parent.insertChild(index + 1, child, autoIncrementName=None, existOk=True)
                    seed = parent.seedList.pop(index)
                    parent.seedList.insert(index + 1, seed)

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


class MySeedListPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

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

        param.sigValueChanged.connect(self.onValueChanged)
        param.sigValueChanging.connect(self.onValueChanging)
        param.sigChildAdded.connect(self.onChildAdded)
        param.sigChildRemoved.connect(self.onChildRemoved)
        param.sigRemoved.connect(self.onRemoved)
        param.sigParentChanged.connect(self.onParentChanged)
        param.sigLimitsChanged.connect(self.onLimitsChanged)
        param.sigDefaultChanged.connect(self.onDefaultChanged)
        param.sigNameChanged.connect(self.onNameChanged)
        param.sigOptionsChanged.connect(self.onOptionsChanged)
        param.sigStateChanged.connect(self.onStateChanged)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

        self.decimals = param.opts.get('decimals', 3)

        # this widget is created **after** childs have been added in the __init__routine
        # so it is not notified through param.sigChildAdded() of any new childs at that stage
        # therefore do the following to provide initial label text.
        self.showSeeds(param)

    def showSeeds(self, param):
        nChilds = len(param.childs)
        nSource = 0

        if nChilds == 0:
            self.setText('No seeds')
        else:
            for ch in param.childs:
                if not isinstance(ch, MySeedParameter):
                    raise ValueError("Need 'MySeedParameter' instances at this point")
                seed = ch.names['Source seed']
                source = seed.opts['value']
                if source:
                    nSource += 1
                self.setText(f'{nSource} src seed(s) + {nChilds-nSource} rec seed(s)')
        self.update()

    def onValueChanged(self, val):
        print('>>> SeedList.ValueChanged <<<')
        self.showSeeds(val)

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        print('>>> SeedList.onValueChanging')
        self.showSeeds(param)

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        print('>>> SeedList.ChildAdded <<<')

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        print('>>> SeedList.ChildRemoved <<<')

    def onRemoved(self):
        print('>>> SeedList.Removed')

    def onParentChanged(self):
        print('>> SeedList.ParentChanged <<<')

    def onLimitsChanged(self):
        print('>>> SeedList.LimitsChanged')

    def onDefaultChanged(self):
        print('>>> SeedList.DefaultChanged')

    def onNameChanged(self):
        print('>>> SeedList.NameChanged')

    def onOptionsChanged(self, *_):                                             # change, info not used and replaced by *_
        print('>>> SeedList.OptionsChanged')

    def onStateChanged(self, param, _):                                         # info not used and replaced by _
        print('>>> SeedList.StateChanged >>>')
        self.showSeeds(param)

    def onTreeStateChanged(self, param):
        print('>>> SeedList.TreeStateChanged <<<')

        if not isinstance(param, MySeedListParameter):
            raise ValueError("Need 'MySeedListParameter' instances at this point")
        self.showSeeds(param)


class MySeedListParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySeedListPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        # for n, seed in enumerate(self.seedList):
        #   self.addChild(dict(name=f'Seed-{n+1}', type='mySeed',  value=seed,  default=seed,  expanded=(n==0), renamable=True, flat=True, decimals=5, suffix='m'))
        #   self.addChild(dict(name=seed.name, type='mySeed', value=seed, default=seed, expanded=(n==0),renamable=True, flat=True, decimals=5, suffix='m'))

        for seed in self.seedList:
            self.addChild(dict(name=seed.name, type='mySeed', value=seed, default=seed, expanded=True, renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)

        # self.sigValueChanging.emit(self, self.value())
        # self.sigValueChanged.emit(self, self.value())
        # self.sigStateChanged.emit(self, 'childAdded', '')
        # self.sigOptionsChanged.emit(self, **opts)

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

            self.seedList.append(seed)

            self.addChild(dict(name=newName, type='mySeed', value=seed, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            # try this:
            self.sigValueChanging.emit(self, self.value())


class MyTemplatePreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # param unused and replaced by _

        rl = val.rollList
        sl = val.seedList

        nTemplateShots = 0
        for s in sl:
            nSeedShots = 0
            if s.bSource:                                                       # Source seed
                nSeedShots = 1                                                  # at least one SP
                for growStep in s.grid.growList:                                # iterate through all grow steps
                    nSeedShots *= growStep.steps                                # multiply seed's shots at each level
                nTemplateShots += nSeedShots                                    # add to template's SPs

        for r in rl:
            nTemplateShots *= r.steps                                           # template is rolled a number of times

        self.setText(f'{len(sl)} seed(s), {nTemplateShots} src points')
        self.update()


class MyTemplateParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyTemplatePreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        self.addChild(dict(name='Roll steps', type='MyRollList', value=self.template.rollList, default=self.template.rollList, expanded=False, flat=True, decimals=d, suffix=s))
        self.addChild(dict(name='Seed list', type='mySeedList', value=self.template.seedList, brush='#add8e6', renamable=True, flat=True))

        self.parR = self.child('Roll steps')
        self.parS = self.child('Seed list')

        self.parR.sigValueChanged.connect(self.valueChanged)
        self.parS.sigValueChanged.connect(self.valueChanged)
        self.sigNameChanged.connect(self.nameChanged)
        self.sigContextMenu.connect(self.contextMenu)

    def nameChanged(self, _):
        self.template.name = self.name()

    def valueChanged(self):
        # self.template.rollList = self.parR.value()
        self.template.seedList = self.parS.value()
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.template

    def contextMenu(self, name=None):
        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            parent = self.parent()
            if isinstance(self.parent(), MyTemplateListParameter):
                index = parent.children().index(self)
                reply = QMessageBox.question(None, 'Please confirm', 'Delete selected template ?', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.remove()
                    parent.templateList.pop(index)

        elif name == 'moveUp':
            parent = self.parent()
            if isinstance(self.parent(), MyTemplateListParameter):
                index = parent.children().index(self)
                if index > 0:
                    child = parent.children()[index]
                    parent.insertChild(index - 1, child, autoIncrementName=None, existOk=True)
                    template = parent.templateList.pop(index)
                    parent.templateList.insert(index - 1, template)

        elif name == 'moveDown':
            parent = self.parent()
            if isinstance(self.parent(), MyTemplateListParameter):
                n = len(parent.children())
                index = parent.children().index(self)
                if index < n - 1:
                    child = parent.children()[index]
                    parent.insertChild(index + 1, child, autoIncrementName=None, existOk=True)
                    template = parent.templateList.pop(index)
                    parent.templateList.insert(index + 1, template)

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


# class TemplateListPreviewLabel(QLabel):
#     def __init__(self, param):
#         super().__init__()

#         # sigValueChanged   = QtCore.Signal(object, object)                 ## self, value   emitted when value is finished being edited
#         # sigValueChanging  = QtCore.Signal(object, object)                 ## self, value  emitted as value is being edited
#         # sigChildAdded     = QtCore.Signal(object, object, object)         ## self, child, index
#         # sigChildRemoved   = QtCore.Signal(object, object)                 ## self, child
#         # sigRemoved        = QtCore.Signal(object)                         ## self
#         # sigParentChanged  = QtCore.Signal(object, object)                 ## self, parent
#         # sigLimitsChanged  = QtCore.Signal(object, object)                 ## self, limits
#         # sigDefaultChanged = QtCore.Signal(object, object)                 ## self, default
#         # sigNameChanged    = QtCore.Signal(object, object)                 ## self, name
#         # sigOptionsChanged = QtCore.Signal(object, object)                 ## self, {opt:val, ...}

#         # Emitted when anything changes about this parameter at all.
#         # The second argument is a string indicating what changed ('value', 'childAdded', etc..)
#         # The third argument can be any extra information about the change
#         #
#         # sigStateChanged   = QtCore.Signal(object, object, object)         ## self, change, info

#         # emitted when any child in the tree changes state
#         # (but only if monitorChildren() is called)
#         # sigTreeStateChanged = QtCore.Signal(object, object)               ## self, changes
#         #                                                                   ## changes = [(param, change, info), ...]

#         param.sigValueChanged    .connect(self.onValueChanged)
#         param.sigValueChanging   .connect(self.onValueChanging)
#         param.sigChildAdded      .connect(self.onChildAdded)
#         param.sigChildRemoved    .connect(self.onChildRemoved)
#         param.sigRemoved         .connect(self.onRemoved)
#         param.sigParentChanged   .connect(self.onParentChanged)
#         param.sigLimitsChanged   .connect(self.onLimitsChanged)
#         param.sigDefaultChanged  .connect(self.onDefaultChanged)
#         param.sigNameChanged     .connect(self.onNameChanged)
#         param.sigOptionsChanged  .connect(self.onOptionsChanged)
#         param.sigStateChanged    .connect(self.onStateChanged)
#         param.sigTreeStateChanged.connect(self.onTreeStateChanged)

#         self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
#         font = self.font()
#         font.setPointSizeF(font.pointSize() - 0.5)
#         self.setFont(font)
#         self.setAlignment(Qt.AlignVCenter)

#         opts = param.opts
#         self.decimals = opts.get('decimals', 3)
#         val = opts.get('value', None)

#         # this widget is created **after** childs have been added in the __init__routine
#         # so it is not notified through param.sigChildAdded() of any new childs at that stage
#         # therefore do the following to provide initial label text.
#         self.showSeeds(param)

#     def showSeeds(self, param):
#         nChilds = len(param.childs)

#         if nChilds == 0:
#             self.setText('No emplates in block')
#         else:
#             self.setText(f'{nChilds} templates in block')
#         self.update()

#     def onValueChanged(self, val):
#         print('>>> TemplateList.ValueChanged')
#         self.showSeeds(val)

#     def onValueChanging(self, param, val):
#         print('>>> TemplateList.ValueChanging <<<')
#         self.showSeeds(param)

#     def onChildAdded(self, child, index):
#         print('>>> TemplateList.ChildAdded')

#     def onChildRemoved(self, child):
#         print('TemplateList.ChildRemoved')

#     def onRemoved(self):
#         print('>>> TemplateList.Removed <<<')

#     def onParentChanged(self):
#         print('>>> TemplateList.ParentChanged <<<')

#     def onLimitsChanged(self):
#         print('>>> TemplateList.LimitsChanged <<<')

#     def onDefaultChanged(self):
#         print('>>> TemplateList.DefaultChanged <<<')

#     def onNameChanged(self):
#         print('>>> TemplateList.NameChanged <<<')

#     def onOptionsChanged(self, change, info):
#         print('>>> TemplateList.OptionsChanged <<<')

#     def onStateChanged(self, param, info):
#         print('>>> TemplateList.StateChanged')
#         self.showSeeds(param)

#     def onTreeStateChanged(self, param):
#         print('>>> TemplateList.TreeStateChanged <<<')

#         if not isinstance(param, MyTemplateListParameter):
#             raise ValueError("Need 'MyTemplateListParameter' instances at this point")
#         self.showSeeds(param)

# class MyTemplateListParameterItem(MyGroupParameterItem):
#     def __init__(self, param, depth):
#         super().__init__(param, depth)
#         self.itemWidget = QWidget()

#         spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
#         self.label = TemplateListPreviewLabel(param)

#         layout = QHBoxLayout()
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(2)                                                    # spacing between elements
#         layout.addSpacerItem(spacerItem)
#         layout.addWidget(self.label)
#         self.itemWidget.setLayout(layout)

#     def treeWidgetChanged(self):
#         ParameterItem.treeWidgetChanged(self)
#         tw = self.treeWidget()
#         if tw is None:
#             return
#         tw.setItemWidget(self, 1, self.itemWidget)


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
            # self.addChild(dict(name=f'Template-{n+1}', type='myTemplate', value=template, default=template, expanded=(n==0), renamable=True, flat=True, decimals=5, suffix='m'))
            self.addChild(dict(name=template.name, type='myTemplate', value=template, default=template, expanded=(n == 0), renamable=True, flat=True, decimals=5, suffix='m'))

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

            # try this:
            self.sigValueChanging.emit(self, self.value())


class MyBlockPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        tl = val.templateList

        nBlockShots = 0
        for t in tl:
            nTemplateShots = 0
            for seed in t.seedList:
                nSeedShots = 0
                if seed.bSource:                                                # Source seed
                    nSeedShots = 1                                              # at least one SP
                    for growStep in seed.grid.growList:                         # iterate through all grow steps
                        nSeedShots *= growStep.steps                            # multiply seed's shots at each level
                    nTemplateShots += nSeedShots                                # add to template's SPs

            for roll in t.rollList:
                nTemplateShots *= roll.steps                                    # template is rolled a number of times
            nBlockShots += nTemplateShots

        self.setText(f'{len(tl)} template(s), {nBlockShots} src points')
        self.update()


class MyBlockParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBlockPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            parent = self.parent()
            if isinstance(self.parent(), MyBlockListParameter):
                index = parent.children().index(self)
                reply = QMessageBox.question(None, 'Please confirm', 'Delete selected block ?', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.remove()
                    parent.blockList.pop(index)

        elif name == 'moveUp':
            parent = self.parent()
            if isinstance(self.parent(), MyBlockListParameter):
                index = parent.children().index(self)
                if index > 0:
                    child = parent.children()[index]
                    parent.insertChild(index - 1, child, autoIncrementName=None, existOk=True)
                    block = parent.blockList.pop(index)
                    parent.blockList.insert(index - 1, block)

        elif name == 'moveDown':
            parent = self.parent()
            if isinstance(self.parent(), MyBlockListParameter):
                n = len(parent.children())
                index = parent.children().index(self)
                if index < n - 1:
                    child = parent.children()[index]
                    parent.insertChild(index + 1, child, autoIncrementName=None, existOk=True)
                    block = parent.blockList.pop(index)
                    parent.blockList.insert(index + 1, block)

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


# class BlockListPreviewLabel(QLabel):
#     def __init__(self, param):
#         super().__init__()

#         # sigValueChanged   = QtCore.Signal(object, object)                 ## self, value   emitted when value is finished being edited
#         # sigValueChanging  = QtCore.Signal(object, object)                 ## self, value  emitted as value is being edited
#         # sigChildAdded     = QtCore.Signal(object, object, object)         ## self, child, index
#         # sigChildRemoved   = QtCore.Signal(object, object)                 ## self, child
#         # sigRemoved        = QtCore.Signal(object)                         ## self
#         # sigParentChanged  = QtCore.Signal(object, object)                 ## self, parent
#         # sigLimitsChanged  = QtCore.Signal(object, object)                 ## self, limits
#         # sigDefaultChanged = QtCore.Signal(object, object)                 ## self, default
#         # sigNameChanged    = QtCore.Signal(object, object)                 ## self, name
#         # sigOptionsChanged = QtCore.Signal(object, object)                 ## self, {opt:val, ...}

#         # Emitted when anything changes about this parameter at all.
#         # The second argument is a string indicating what changed ('value', 'childAdded', etc..)
#         # The third argument can be any extra information about the change
#         #
#         # sigStateChanged   = QtCore.Signal(object, object, object)         ## self, change, info

#         # emitted when any child in the tree changes state
#         # (but only if monitorChildren() is called)
#         # sigTreeStateChanged = QtCore.Signal(object, object)               ## self, changes
#         #                                                                   ## changes = [(param, change, info), ...]
#         param.sigValueChanged    .connect(self.onValueChanged)
#         param.sigValueChanging   .connect(self.onValueChanging)
#         param.sigChildAdded      .connect(self.onChildAdded)
#         param.sigChildRemoved    .connect(self.onChildRemoved)
#         param.sigRemoved         .connect(self.onRemoved)
#         param.sigParentChanged   .connect(self.onParentChanged)
#         param.sigLimitsChanged   .connect(self.onLimitsChanged)
#         param.sigDefaultChanged  .connect(self.onDefaultChanged)
#         param.sigNameChanged     .connect(self.onNameChanged)
#         param.sigOptionsChanged  .connect(self.onOptionsChanged)
#         param.sigStateChanged    .connect(self.onStateChanged)
#         param.sigTreeStateChanged.connect(self.onTreeStateChanged)

#         self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
#         font = self.font()
#         font.setPointSizeF(font.pointSize() - 0.5)
#         self.setFont(font)
#         self.setAlignment(Qt.AlignVCenter)

#         opts = param.opts
#         self.decimals = opts.get('decimals', 3)
#         val = opts.get('value', None)

#         # this widget is created **after** childs have been added in the __init__routine
#         # so it is not notified through param.sigChildAdded() of any new childs at that stage
#         # therefore do the following to provide initial label text.
#         self.onValueChanging(None, val)

#     def onValueChanged(self, val):
#         print('>>> BlockList.ValueChanged <<<')

#     def onValueChanging(self, param, val):
#         if param is None:
#             return
#         nChilds = len(param.childs)

#         if nChilds == 0:
#             self.setText('No blocks in survey')
#         else:
#             self.setText(f'{nChilds} blocks in survey')
#         self.update()

#     def onChildAdded(self, child, index):
#         print('>>> BlockList.ChildAdded <<<')

#     def onChildRemoved(self, child):
#         print('>>> BlockList.ChildRemoved <<<')

#     def onRemoved(self):
#         print('>>> BlockList.Removed <<<')

#     def onParentChanged(self):
#         print('>>> BlockList.ParentChanged <<<')

#     def onLimitsChanged(self, limits):
#         print('>>> BlockList.LimitsChanged <<<')

#     def onDefaultChanged(self, default):
#         print('>>> BlockList.DefaultChanged <<<')

#     def onNameChanged(self, name):
#         print('>>> BlockList.NameChanged <<<')

#     def onOptionsChanged(self, options):
#         print('BlockList.OptionsChanged <<<')

#     def onStateChanged(self, change, info):
#         print('>>> BlockList.StateChanged <<<')

#     def onTreeStateChanged(self, changes):
#         print('>>> BlockList.TreeStateChanged <<<')
#         if not isinstance(changes, MyBlockListParameter):
#             raise ValueError("Need 'MyBlockListParameter' instances at this point")

# class MyBlockListParameterItem(MyGroupParameterItem):
#     def __init__(self, param, depth):
#         super().__init__(param, depth)
#         self.itemWidget = QWidget()

#         spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
#         self.label = BlockListPreviewLabel(param)

#         layout = QHBoxLayout()
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(2)                                                    # spacing between elements
#         layout.addSpacerItem(spacerItem)
#         layout.addWidget(self.label)
#         self.itemWidget.setLayout(layout)

#     def treeWidgetChanged(self):
#         ParameterItem.treeWidgetChanged(self)
#         tw = self.treeWidget()
#         if tw is None:
#             return
#         tw.setItemWidget(self, 1, self.itemWidget)


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
            # self.addChild(dict(name=f'Block-{n+1}', type='myBlock', value=block, default=block, expanded=(n==0), renamable=True, flat=True, decimals=5, suffix='m'))
            self.addChild(dict(name=block.name, type='myBlock', value=block, default=block, expanded=(n == 0), renamable=True, flat=True, decimals=5, suffix='m'))

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

            # try this:
            self.sigValueChanging.emit(self, self.value())

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        print('>>> onBlockListChildAdded <<<')

    def onChildRemoved(self, _):                                                # childunused and replaced by _
        print('>>> onBlockListChildRemoved <<<')


class MyPatternPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)
        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, *_):                                              # unused param, val replaced by *_
        n = 1
        x = 0.0
        y = 0.0
        z = 0.0
        d = self.decimals

        self.setText(f'{n} : ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})')
        self.update()


class MyPatternParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyPatternPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='Pattern grow steps', type='MyRollList', value=self.pattern.growList, default=self.pattern.growList, expanded=True, flat=True, brush='#add8e6', decimals=5, suffix='m'))

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
        ## name == 'rename' already resolved by self.editName() in MyGroupParameterItem
        if name == 'remove':
            parent = self.parent()
            if isinstance(self.parent(), MyPatternListParameter):
                index = parent.children().index(self)
                reply = QMessageBox.question(None, 'Please confirm', 'Delete selected pattern ?', QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.remove()
                    parent.patternList.pop(index)

        elif name == 'moveUp':
            parent = self.parent()
            if isinstance(self.parent(), MyPatternListParameter):
                index = parent.children().index(self)
                if index > 0:
                    child = parent.children()[index]
                    parent.insertChild(index - 1, child, autoIncrementName=None, existOk=True)
                    pattern = parent.patternList.pop(index)
                    parent.patternList.insert(index - 1, pattern)

        elif name == 'moveDown':
            parent = self.parent()
            if isinstance(self.parent(), MyPatternListParameter):
                n = len(parent.children())
                index = parent.children().index(self)
                if index < n - 1:
                    child = parent.children()[index]
                    parent.insertChild(index + 1, child, autoIncrementName=None, existOk=True)
                    pattern = parent.patternList.pop(index)
                    parent.patternList.insert(index + 1, pattern)

        elif name == 'preview':
            ...
        elif name == 'export':
            ...


# class PatternListPreviewLabel(QLabel):
#     def __init__(self, param):
#         super().__init__()

#         # sigValueChanged   = QtCore.Signal(object, object)                 ## self, value   emitted when value is finished being edited
#         # sigValueChanging  = QtCore.Signal(object, object)                 ## self, value  emitted as value is being edited
#         # sigChildAdded     = QtCore.Signal(object, object, object)         ## self, child, index
#         # sigChildRemoved   = QtCore.Signal(object, object)                 ## self, child
#         # sigRemoved        = QtCore.Signal(object)                         ## self
#         # sigParentChanged  = QtCore.Signal(object, object)                 ## self, parent
#         # sigLimitsChanged  = QtCore.Signal(object, object)                 ## self, limits
#         # sigDefaultChanged = QtCore.Signal(object, object)                 ## self, default
#         # sigNameChanged    = QtCore.Signal(object, object)                 ## self, name
#         # sigOptionsChanged = QtCore.Signal(object, object)                 ## self, {opt:val, ...}

#         # Emitted when anything changes about this parameter at all.
#         # The second argument is a string indicating what changed ('value', 'childAdded', etc..)
#         # The third argument can be any extra information about the change
#         #
#         # sigStateChanged   = QtCore.Signal(object, object, object)         ## self, change, info

#         # emitted when any child in the tree changes state
#         # (but only if monitorChildren() is called)
#         # sigTreeStateChanged = QtCore.Signal(object, object)               ## self, changes
#         #                                                                   ## changes = [(param, change, info), ...]
#         param.sigValueChanged    .connect(self.onValueChanged)
#         param.sigValueChanging   .connect(self.onValueChanging)
#         param.sigChildAdded      .connect(self.onChildAdded)
#         param.sigChildRemoved    .connect(self.onChildRemoved)
#         param.sigRemoved         .connect(self.onRemoved)
#         param.sigParentChanged   .connect(self.onParentChanged)
#         param.sigLimitsChanged   .connect(self.onLimitsChanged)
#         param.sigDefaultChanged  .connect(self.onDefaultChanged)
#         param.sigNameChanged     .connect(self.onNameChanged)
#         param.sigOptionsChanged  .connect(self.onOptionsChanged)
#         param.sigStateChanged    .connect(self.onStateChanged)
#         param.sigTreeStateChanged.connect(self.onTreeStateChanged)

#         self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
#         font = self.font()
#         font.setPointSizeF(font.pointSize() - 0.5)
#         self.setFont(font)
#         self.setAlignment(Qt.AlignVCenter)

#         opts = param.opts
#         self.decimals = opts.get('decimals', 3)
#         val = opts.get('value', None)

#         # this widget is created **after** childs have been added in the __init__routine
#         # so it is not notified through param.sigChildAdded() of any new childs at that stage
#         # therefore do the following to provide initial label text.
#         self.onValueChanging(None, val)

#     def onValueChanged(self, val):
#         print('>>> PatternList.ValueChanged <<<')

#     def onValueChanging(self, param, val):
#         if param is None:
#             return
#         nChilds = len(param.childs)

#         if nChilds == 0:
#             self.setText('No patterns in survey')
#         else:
#             self.setText(f'{nChilds} patterns in survey')
#         self.update()

#     def onChildAdded(self, child, index):
#         print('>>> PatternList.ChildAdded <<<')

#     def onChildRemoved(self, child):
#         print('>>> PatternList.ChildRemoved <<<')

#     def onRemoved(self):
#         print('>>> PatternList.Removed <<<')

#     def onParentChanged(self):
#         print('>>> PatternList.ParentChanged <<<')

#     def onLimitsChanged(self, limits):
#         print('>>> PatternList.LimitsChanged <<<')

#     def onDefaultChanged(self, default):
#         print('>>> PatternList.DefaultChanged <<<')

#     def onNameChanged(self, name):
#         print('>>> PatternList.NameChanged <<<')

#     def onOptionsChanged(self, options):
#         print('PatternList.OptionsChanged <<<')

#     def onStateChanged(self, change, info):
#         print('>>> PatternList.StateChanged <<<')

#     def onTreeStateChanged(self, changes):
#         print('>>> PatternList.TreeStateChanged <<<')
#         if not isinstance(changes, MyPatternListParameter):
#             raise ValueError("Need 'MyPatternListParameter' instances at this point")

# class MyPatternListParameterItem(MyGroupParameterItem):
#     def __init__(self, param, depth):
#         super().__init__(param, depth)
#         self.itemWidget = QWidget()

#         spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
#         self.label = PatternListPreviewLabel(param)

#         layout = QHBoxLayout()
#         layout.setContentsMargins(0, 0, 0, 0)
#         layout.setSpacing(2)                                                    # spacing between elements
#         layout.addSpacerItem(spacerItem)
#         layout.addWidget(self.label)
#         self.itemWidget.setLayout(layout)

#     def treeWidgetChanged(self):
#         ParameterItem.treeWidgetChanged(self)
#         tw = self.treeWidget()
#         if tw is None:
#             return
#         tw.setItemWidget(self, 1, self.itemWidget)


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

        # for n, pattern in enumerate(self.patternList):
        # self.addChild(dict(name=f'Block-{n+1}', type='myBlock', value=block, default=block, expanded=(n==0), renamable=True, flat=True, decimals=5, suffix='m'))
        # self.addChild(dict(name=pattern.name,   type='myPattern', value=pattern, default=pattern, expanded=(n==0), renamable=True, flat=True, decimals=5, suffix='m'))

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

            # try this:
            self.sigValueChanging.emit(self, self.value())

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        print('>>> onPatternListChildAdded <<<')

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        print('>>> onPatternListChildRemoved <<<')


class MyLocalGridPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)                           # decimals not used (yet)
        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        fold = val.fold

        if fold < 0:
            self.setText(f'{val.binSize.x()}x{val.binSize.y()}m, fold undefined')
        else:
            self.setText(f'{val.binSize.x()}x{val.binSize.y()}m, fold {fold} max')

        self.update()


class MyLocalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyLocalGridPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='Bin offset [x]', value=self.binGrid.shift.x(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Bin offset [y]', value=self.binGrid.shift.y(), type='float', decimals=d, suffix=s))
        self.addChild(dict(name='Stake nr @ origin', value=self.binGrid.stake.x(), type='float', decimals=d, suffix='#'))
        self.addChild(dict(name='Line nr @ origin', value=self.binGrid.stake.y(), type='float', decimals=d, suffix='#'))
        self.addChild(
            dict(
                name='Max fold',
                value=self.binGrid.fold,
                type='int',
            )
        )

        self.parBx = self.child('Bin size [x]')
        self.parBy = self.child('Bin size [y]')
        self.parDx = self.child('Bin offset [x]')
        self.parDy = self.child('Bin offset [y]')
        self.parLx = self.child('Stake nr @ origin')
        self.parLy = self.child('Line nr @ origin')
        self.parFo = self.child('Max fold')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        # local grid
        self.binGrid.binSize.setX(self.parBx.value())
        self.binGrid.binSize.setY(self.parBy.value())
        self.binGrid.shift.setX(self.parDx.value())
        self.binGrid.shift.setY(self.parDy.value())
        self.binGrid.stake.setX(self.parLx.value())
        self.binGrid.stake.setY(self.parLy.value())
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
        self.setText(f'o({x:,}, {y:,}), a={a:.{d}g} deg')
        self.update()


class MyGlobalGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyGlobalGridPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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


class MyBinGridPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)                           # decimals not used (yet)
        val = param.opts.get('value', None)

        self.onValueChanging(None, val)

    def onValueChanging(self, _, val):                                          # unused param replaced by _
        fold = val.fold

        if fold < 0:
            self.setText(f'{val.size.x()}x{val.size.y()}m, fold undefined')
        else:
            self.setText(f'{val.size.x()}x{val.size.y()}m, fold {fold} max')

        self.update()


class MyBinGridParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinGridPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


class MyBinGridParameter(MyGroupParameter):

    # itemClass = MyBinGridParameterItem
    itemClass = MyGroupParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBinGridParameter opts')

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
        self.binGrid.shift = self.parL.value().shift
        self.binGrid.stake = self.parL.value().stake
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
            self.setText(f'AoI < {y:.{d}g} deg')
        else:
            self.setText(f'{x:.{d}g} < AoI < {y:.{d}g} deg')
        self.update()


class MyBinAnglesParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinAnglesPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        #  read parameter changes here
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
            self.setText('rectangular constraints')
        elif r < x:
            self.setText('radial constraints')
        else:
            self.setText('mixed constraints')

        self.update()


class MyBinOffsetParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinOffsetPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
            self.setText('Not used')
        else:
            self.setText(f'@ {val.dOffset}m, {val.dAzimuth}°')
        self.update()


class MyUniqOffParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyUniqOffPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        self.addChild(
            dict(
                name='Apply pruning',
                value=self.unique.apply,
                type='bool',
            )
        )
        self.addChild(
            dict(
                name='Delta offset',
                value=self.unique.dOffset,
                type='float',
                decimals=d,
                suffix='m',
            )
        )
        self.addChild(
            dict(
                name='Delta azimuth',
                value=self.unique.dAzimuth,
                type='float',
                decimals=d,
                suffix='deg',
            )
        )

        self.parP = self.child('Apply pruning')
        self.parO = self.child('Delta offset')
        self.parA = self.child('Delta azimuth')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        #  read parameter changes here
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

        self.setText(f'{method} @ Vint={val.vint}m/s')
        self.update()


class MyBinMethodParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyBinMethodPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


class MyBinMethodParameter(MyGroupParameter):

    itemClass = MyBinMethodParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyBinMethodParameter opts')

        d = opts.get('decimals', 7)

        self.binning = RollBinning()
        self.binning = opts.get('value', self.binning)
        binningMethod = self.binning.method.value

        self.addChild(dict(name='Binning method', type='myList', value=binningList[binningMethod], default=binningList[binningMethod], limits=binningList))
        self.addChild(dict(name='Interval velocity', type='float', value=self.binning.vint, decimals=d, suffix='m/s'))

        self.parM = self.child('Binning method')
        self.parV = self.child('Interval velocity')

        self.sigTreeStateChanged.connect(self.changed)

    def changed(self):
        #  read parameter changes here
        index = binningList.index(self.parM.value())

        self.binning.method = BinningType(index)
        self.binning.vint = self.parV.value()
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return self.binning


class MyAnalysisPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()

        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)                       # decimals not used (yet)
        val = param.opts.get('value', None)
        self.onValueChanging(None, val)

    def onValueChanging(self, *_):                                          # unused param, val replaced by *_
        ...
        # binningMethod = val.binning.method.value
        # method = binningList[binningMethod]

        # self.setText(f"{method} @ Vint={val.binning.vint}m/s")
        # self.update()


class MyAnalysisParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MyAnalysisPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


class MyAnalysisParameter(MyGroupParameter):

    itemClass = MyAnalysisParameterItem

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

        self.parB.sigValueChanged.connect(self.changed)
        self.parA.sigValueChanged.connect(self.changed)
        self.parO.sigValueChanged.connect(self.changed)
        self.parU.sigValueChanged.connect(self.changed)
        self.parM.sigValueChanged.connect(self.changed)

    def changed(self):
        self.area = self.parB.value()
        self.angles = self.parA.value()

        # check if offsets are handled okay

        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return (self.area, self.angles, self.binning, self.offset, self.unique)


class MySurveyPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onValueChanging)

        self.decimals = param.opts.get('decimals', 3)                           # decimals not used (yet)
        val = param.opts.get('value', None)

        self.onValueChanging(None, val)

    def onValueChanging(self, *_):                                              # unused param, val replaced by *_
        # self.setText(val.name)
        self.update()


class MySurveyParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.setPreviewLabel(MySurveyPreviewLabel(param))

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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

        surTypes = [e.name for e in surveyType]

        self.addChild(
            dict(
                name='Survey configuration',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Survey CRS', type='myCrs', value=self.survey.crs, default=self.survey.crs),
                    dict(name='Survey type', type='myList', value=self.survey.type.name, default=self.survey.type.name, limits=surTypes),
                    dict(name='Survey name', type='str', value=self.survey.name, default=self.survey.name),
                ],
            )
        )

        self.addChild(dict(name='Survey analysis', type='myAnalysis', value=self.survey, default=self.survey, brush='#add8e6'))

        self.addChild(
            dict(
                name='Survey reflectors',
                type='myGroup',
                brush='#add8e6',
                children=[
                    dict(name='Dipping plane', type='myPlane', value=self.survey.globalPlane, expanded=False, flat=True),
                    dict(name='Buried sphere', type='mySphere', value=self.survey.sphere, expanded=False, flat=True),
                ],
            )
        )

        self.addChild(dict(name='Survey grid', type='myBinGrid', value=self.survey.grid, default=self.survey.grid, brush='#add8e6'))
        self.addChild(dict(name='Block list', type='myBlockList', value=self.survey.blockList, brush='#add8e6'))
        self.addChild(dict(name='Pattern list', type='myPatternList', value=self.survey.patternList, brush='#add8e6'))

    def value(self):
        return self.survey


# first, register some simple parameters, already defined in other files
registerParameterItemType('myFloat', MyNumericParameterItem, SimpleParameter, override=True)
registerParameterItemType('myInt', MyNumericParameterItem, SimpleParameter, override=True)

# then, register the parameters, already defined in other files
registerParameterType('cmap', CmapParameter, override=True)
registerParameterType('myCrs', MyCrsParameter, override=True)
registerParameterType('myCrs2', MyCrs2Parameter, override=True)
registerParameterType('myGroup', MyGroupParameter, override=True)
registerParameterType('myList', MyListParameter, override=True)
registerParameterType('myMarker', MyMarkerParameter, override=True)
registerParameterType('myNVector', MyNVectorParameter, override=True)
registerParameterType('myPen', MyPenParameter, override=True)
registerParameterType('myPoint3D', MyPoint3DParameter, override=True)
registerParameterType('myRectF', MyRectParameter, override=True)
registerParameterType('mySlider', MySliderParameter, override=True)
registerParameterType('mySymbols', MySymbolParameter, override=True)
registerParameterType('myVector', MyVectorParameter, override=True)

# next, register parameters, defined in this  file
registerParameterType('MyRoll', MyRollParameter, override=True)
registerParameterType('MyRollList', MyRollListParameter, override=True)
registerParameterType('myCircle', MyCircleParameter, override=True)
registerParameterType('mySpiral', MySpiralParameter, override=True)
registerParameterType('myWell', MyWellParameter, override=True)
registerParameterType('mySphere', MySphereParameter, override=True)
registerParameterType('myPlane', MyPlaneParameter, override=True)
registerParameterType('mySeed', MySeedParameter, override=True)
registerParameterType('mySeedList', MySeedListParameter, override=True)
registerParameterType('myTemplate', MyTemplateParameter, override=True)
registerParameterType('myTemplateList', MyTemplateListParameter, override=True)
registerParameterType('myBlock', MyBlockParameter, override=True)
registerParameterType('myBlockList', MyBlockListParameter, override=True)
registerParameterType('myBinGrid', MyBinGridParameter, override=True)
registerParameterType('myLocalGrid', MyLocalGridParameter, override=True)
registerParameterType('myGlobalGrid', MyGlobalGridParameter, override=True)
registerParameterType('myAnalysis', MyAnalysisParameter, override=True)
registerParameterType('myBinOffset', MyBinOffsetParameter, override=True)
registerParameterType('myBinAngles', MyBinAnglesParameter, override=True)
registerParameterType('myUniqOff', MyUniqOffParameter, override=True)
registerParameterType('myBinMethod', MyBinMethodParameter, override=True)
registerParameterType('myPattern', MyPatternParameter, override=True)
registerParameterType('myPatternList', MyPatternListParameter, override=True)
registerParameterType('mySurvey', MySurveyParameter, override=True)
