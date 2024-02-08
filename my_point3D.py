from pyqtgraph.parametertree import registerParameterItemType, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem, SimpleParameter
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSpacerItem, QWidget

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_numerics import MyNumericParameterItem

registerParameterType('myGroup', MyGroupParameter, override=True)
registerParameterItemType('myFloat', MyNumericParameterItem, SimpleParameter, override=True)


class PointPreviewLabel(QLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onPointChanging)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        font = self.font()
        font.setPointSizeF(font.pointSize() - 0.5)
        self.setFont(font)
        self.setAlignment(Qt.AlignVCenter)

        opts = param.opts
        self.decimals = opts.get('decimals', 5)
        val = opts.get('value', QVector3D())

        self.onPointChanging(None, val)

    def onPointChanging(self, _, val):                                          # param unused and eplaced by _
        # if needed transform QPointF into vector

        vector = QVector3D(val)
        x = vector.x()                                                          # symbol size `val.color()` not used in the TextPreviewLabel
        y = vector.y()
        z = vector.z()
        d = self.decimals

        self.setText(f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})')
        self.update()


class MyPoint3DParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.itemWidget = QWidget()
        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.label = PointPreviewLabel(param)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)                                                    # spacing between elements
        layout.addSpacerItem(spacerItem)
        layout.addWidget(self.label)
        self.itemWidget.setLayout(layout)

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)


class MyPoint3DParameter(MyGroupParameter):

    itemClass = MyPoint3DParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyPoint3D Parameter opts')

        d = opts.get('decimals', 7)
        e = opts.get('enabled', True)
        r = opts.get('readonly', False)
        self.vector = QVector3D()
        self.vector = opts.get('value', QVector3D())

        self.addChild(dict(name='X', type='myFloat', value=self.vector.x(), default=self.vector.x(), decimals=d, enabled=e, readonly=r))
        self.addChild(dict(name='Y', type='myFloat', value=self.vector.y(), default=self.vector.y(), decimals=d, enabled=e, readonly=r))
        self.addChild(dict(name='Z', type='myFloat', value=self.vector.z(), default=self.vector.z(), decimals=d, enabled=e, readonly=r))

        self.parX = self.child('X')
        self.parY = self.child('Y')
        self.parZ = self.child('Z')

        self.parX.sigValueChanged.connect(self.changedX)
        self.parY.sigValueChanged.connect(self.changedY)
        self.parZ.sigValueChanged.connect(self.changedZ)

        self.sigValueChanged.connect(self.updateChildren)

    def setOpts(self, **opts):
        self.parX.setOpts(**opts)
        self.parY.setOpts(**opts)
        self.parZ.setOpts(**opts)

    def changedX(self):                                                          # update the values of the three children
        self.vector.setX(self.parX.value())

    def changedY(self):                                                          # update the values of the three children
        self.vector.setY(self.parY.value())

    def changedZ(self):                                                          # update the values of the three children
        self.vector.setZ(self.parZ.value())

    def value(self):
        return self.vector

    def setValue(self, value, blockSignal=None):                                # update value, children and preview widget
        super().setValue(value, blockSignal)
        if self.hasChildren():
            self.vector = value
            self.updateChildren()

    def updateChildren(self):
        self.parX.setValue(self.vector.x(), blockSignal=self.changedX)
        self.parY.setValue(self.vector.y(), blockSignal=self.changedY)
        self.parZ.setValue(self.vector.z(), blockSignal=self.changedZ)
        self.sigValueChanging.emit(self, self.vector)                           # notify preview widget


registerParameterType('myPoint3D', MyPoint3DParameter, override=True)
