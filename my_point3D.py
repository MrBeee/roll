from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtGui import QVector3D

from .my_group import MyGroupParameter, MyGroupParameterItem


class MyPoint3DParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        # param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 7)
        x = param.child('X').opts['value']
        y = param.child('Y').opts['value']
        z = param.child('Z').opts['value']
        t = f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        # val = param.opts.get('value', QVector3D())                              # get *value*  from param and provide default value
        # d = param.opts.get('decimals', 7)                                      # get nr of decimals from param and provide default value
        # vector = QVector3D(val)                                                 # if needed transform QPointF into vector
        # x = vector.x()                                                          # prepare label text
        # y = vector.y()
        # z = vector.z()
        # t = f'({x:.{d}g}, {y:.{d}g}, {z:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()


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

        self.addChild(dict(name='X', type='myFloat', value=self.vector.x(), default=self.vector.x(), decimals=d, enabled=e, readonly=r))    # myFloat
        self.addChild(dict(name='Y', type='myFloat', value=self.vector.y(), default=self.vector.y(), decimals=d, enabled=e, readonly=r))    # myFloat
        self.addChild(dict(name='Z', type='myFloat', value=self.vector.z(), default=self.vector.z(), decimals=d, enabled=e, readonly=r))    # myFloat

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

        # self.sigValueChanging.emit(self, self.value())  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def value(self):
        return self.vector


registerParameterType('myPoint3D', MyPoint3DParameter, override=True)
