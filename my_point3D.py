from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtWidgets import QHBoxLayout, QSizePolicy, QSpacerItem, QWidget

from .my_group import MyGroupParameter, MyGroupParameterItem

# from .my_numerics import MyNumericParameterItem
from .my_preview_label import MyPreviewLabel

registerParameterType('myGroup', MyGroupParameter, override=True)
# registerParameterItemType('myFloat', MyNumericParameterItem, SimpleParameter, override=True)


class PointPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onPointChanging)                    # connect signal to slot

        self.decimals = param.opts.get('decimals', 7)                           # get nr of decimals from param and provide default value
        val = param.opts.get('value', QVector3D())                              # get *value*  from param and provide default value
        self.onPointChanging(None, val)                                         # initialize the label in __init__()

    def onPointChanging(self, _, val):                                          # param unused and eplaced by _
        vector = QVector3D(val)                                                 # if needed transform QPointF into vector

        x = vector.x()                                                          # prepare label text
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
    """major change in implementation. See roll-2024-02-29 folder"""

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

        self.addChild(dict(name='X', type='float', value=self.vector.x(), default=self.vector.x(), decimals=d, enabled=e, readonly=r))    # myFloat
        self.addChild(dict(name='Y', type='float', value=self.vector.y(), default=self.vector.y(), decimals=d, enabled=e, readonly=r))    # myFloat
        self.addChild(dict(name='Z', type='float', value=self.vector.z(), default=self.vector.z(), decimals=d, enabled=e, readonly=r))    # myFloat

        self.parX = self.child('X')
        self.parY = self.child('Y')
        self.parZ = self.child('Z')

        self.parX.sigValueChanged.connect(self.changed)
        self.parY.sigValueChanged.connect(self.changed)
        self.parZ.sigValueChanged.connect(self.changed)

    def changed(self):
        self.vector.setX(self.parX.value())                                     # update the values of the three children
        self.vector.setY(self.parY.value())
        self.vector.setZ(self.parZ.value())
        self.sigValueChanging.emit(self, self.value())                          # inform the preview label on the changes

    def value(self):
        return self.vector


registerParameterType('myPoint3D', MyPoint3DParameter, override=True)
