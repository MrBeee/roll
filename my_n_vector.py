from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtGui import QVector3D

from .my_group import MyGroupParameter, MyGroupParameterItem


class MyNVectorParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        val = param.opts.get('value', None)
        d = param.opts.get('decimals', 3)

        n = val[0]
        x = val[1].x()
        y = val[1].y()
        z = val[1].z()
        t = f'{n} : ({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()


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
