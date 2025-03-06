import math

from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtGui import QVector3D

from .my_group import MyGroupParameter, MyGroupParameterItem

registerParameterType('myGroup', MyGroupParameter, override=True)


class MyVectorParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        # param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        x = param.child('dX').opts['value']
        y = param.child('dY').opts['value']
        z = param.child('dZ').opts['value']
        t = f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        # val = param.opts.get('value', QVector3D(0.0, 0.0, 0.0))
        # x = val.x()
        # y = val.y()
        # z = val.z()
        # t = f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()


class MyVectorParameter(MyGroupParameter):

    itemClass = MyVectorParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyVector Parameter opts')

        d = opts.get('decimals', 3)
        s = opts.get('suffix', None)

        self.vector = opts.get('value', QVector3D(0.0, 0.0, 0.0))

        self.addChild(dict(name='dX', type='float', value=self.vector.x(), default=self.vector.x(), decimals=d, suffix=s))
        self.addChild(dict(name='dY', type='float', value=self.vector.y(), default=self.vector.y(), decimals=d, suffix=s))
        self.addChild(dict(name='dZ', type='float', value=self.vector.z(), default=self.vector.z(), decimals=d, suffix=s))
        self.addChild(dict(name='azimuth', type='myFloat', value=0.0, default=0.0, enabled=False, readonly=True, decimals=d, suffix='deg'))   # set value through setAzimuth()    # myFloat
        self.addChild(dict(name='tilt', type='myFloat', value=0.0, default=0.0, enabled=False, readonly=True))                                # set value through setTilt()    # myFloat

        self.parX = self.child('dX')
        self.parY = self.child('dY')
        self.parZ = self.child('dZ')
        self.parA = self.child('azimuth')
        self.parT = self.child('tilt')

        self.setAzimuth()
        self.setTilt()

        self.parX.sigValueChanged.connect(self.changed)
        self.parY.sigValueChanged.connect(self.changed)
        self.parZ.sigValueChanged.connect(self.changed)

    def setAzimuth(self):
        azimuth = math.degrees(math.atan2(self.vector.y(), self.vector.x()))
        self.parA.setValue(azimuth)

    def setTilt(self):
        lengthXY = math.sqrt(self.vector.x() ** 2 + self.vector.y() ** 2)
        tilt = math.degrees(math.atan2(self.vector.z(), lengthXY))
        self.parT.setValue(tilt)

    # update the values of the five children
    def changed(self):
        self.vector.setX(self.parX.value())
        self.vector.setY(self.parY.value())
        self.vector.setZ(self.parZ.value())
        self.setAzimuth()
        self.setTilt()

        # self.sigValueChanging.emit(self, self.vector)

    def value(self):
        return self.vector


registerParameterType('myVector', MyVectorParameter, override=True)
