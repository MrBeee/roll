import math

from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QWidget

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_preview_label import MyPreviewLabel
from .my_slider import MySliderParameter
from .my_symbols import MySymbolParameter

registerParameterType('myGroup', MyGroupParameter, override=True)
registerParameterType('mySlider', MySliderParameter, override=True)
registerParameterType('mySymbols', MySymbolParameter, override=True)


class VectorPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onVectorChanging)

        opts = param.opts
        self.decimals = opts.get('decimals', 3)
        val = opts.get('value', QVector3D(0.0, 0.0, 0.0))

        self.onVectorChanging(None, val)

    def onVectorChanging(self, _, val):                                         # unused param replaced by _
        x = val.x()
        y = val.y()
        z = val.z()
        d = self.decimals

        self.setText(f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})')
        self.update()


class MyVectorParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.itemWidget = QWidget()

        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.vectorLabel = VectorPreviewLabel(param)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)                                                    # spacing between elements
        layout.addSpacerItem(spacerItem)
        layout.addWidget(self.vectorLabel)
        self.itemWidget.setLayout(layout)

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


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
        self.addChild(dict(name='azimuth', type='myFloat', value=0.0, enabled=False, readonly=True, decimals=d, suffix='deg'))   # set value through setAzimuth()    # myFloat
        self.addChild(dict(name='tilt', type='myFloat', value=0.0, enabled=False, readonly=True))                                # set value through setTilt()    # myFloat

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
        self.sigValueChanging.emit(self, self.vector)

    def value(self):
        return self.vector


registerParameterType('myVector', MyVectorParameter, override=True)
