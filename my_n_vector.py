from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtWidgets import QHBoxLayout, QSizePolicy, QSpacerItem, QWidget

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_preview_label import MyPreviewLabel


class NVectorPreviewLabel(MyPreviewLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onVectorChanging)

        opts = param.opts
        self.decimals = opts.get('decimals', 3)
        val = opts.get('value', None)

        self.onVectorChanging(None, val)

    def onVectorChanging(self, _, val):
        n = val[0]
        x = val[1].x()
        y = val[1].y()
        z = val[1].z()
        d = self.decimals

        self.setText(f'{n} : ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})')
        self.update()


class MyNVectorParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.itemWidget = QWidget()

        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.label = NVectorPreviewLabel(param)

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


class MyNVectorParameter(MyGroupParameter):

    itemClass = MyNVectorParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in myNVector Parameter opts')

        # self.precision = opts.get('precision', 2)

        d = opts.get('decimals', 3)
        s = opts.get('suffix', '')

        value = opts.get('value', [1, QVector3D(0.0, 0.0, 0.0)])
        self.count = value[0]
        self.vector = value[1]

        self.addChild(dict(name='count', type='int', value=self.count, default=self.count, limits=[1, None]))
        self.addChild(dict(name='direction', type='myVector', value=self.vector, default=self.vector, expanded=False, flat=True, decimals=d, suffix=s))

        self.parN = self.child('count')
        self.parD = self.child('direction')

        self.parN.sigValueChanged.connect(self.changed)
        self.parD.sigValueChanged.connect(self.changed)

    # update the values of the five children
    def changed(self):
        self.count = self.parN.value()
        self.vector = self.parD.value()
        self.sigValueChanging.emit(self, self.value())

    def value(self):
        return [self.count, self.vector]


registerParameterType('myNVector', MyNVectorParameter, override=True)
