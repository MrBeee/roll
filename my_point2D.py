from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtWidgets import QHBoxLayout, QSizePolicy, QSpacerItem, QWidget

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_preview_label import MyPreviewLabel

registerParameterType('myGroup', MyGroupParameter, override=True)


class MyPoint2DPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onPointChanging)                    # connect signal to slot

        self.decimals = param.opts.get('decimals', 7)                           # get nr of decimals from param and provide default value
        val = param.opts.get('value', QPointF())                              # get *value*  from param and provide default value
        self.onPointChanging(None, val)                                         # initialize the label in __init__()

    def onPointChanging(self, _, val):                                          # param unused and eplaced by _
        point = QPointF(val)                                                    # if needed transform object into point

        x = point.x()                                                          # prepare label text
        y = point.y()
        d = self.decimals

        self.setText(f'({x:.{d}g}, {y:.{d}g})')
        self.update()


class MyPoint2DParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.itemWidget = QWidget()
        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.label = MyPoint2DPreviewLabel(param)

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


class MyPoint2DParameter(MyGroupParameter):

    itemClass = MyPoint2DParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyPoint2D Parameter opts')

        d = opts.get('decimals', 7)
        e = opts.get('enabled', True)
        r = opts.get('readonly', False)

        self.point = QPointF()
        self.point = opts.get('value', QPointF())

        self.addChild(dict(name='X', type='myFloat', value=self.point.x(), default=self.point.x(), decimals=d, enabled=e, readonly=r))    # myFloat
        self.addChild(dict(name='Y', type='myFloat', value=self.point.y(), default=self.point.y(), decimals=d, enabled=e, readonly=r))    # myFloat

        self.parX = self.child('X')
        self.parY = self.child('Y')

        self.parX.sigValueChanged.connect(self.changed)
        self.parY.sigValueChanged.connect(self.changed)

    def changed(self):
        self.point.setX(self.parX.value())                                     # update the values of the three children
        self.point.setY(self.parY.value())
        self.sigValueChanging.emit(self, self.value())                          # inform the preview label on the changes

    def value(self):
        return self.point


registerParameterType('myPoint2D', MyPoint2DParameter, override=True)
