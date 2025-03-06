from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtCore import QPointF

from .my_group import MyGroupParameter, MyGroupParameterItem

registerParameterType('myGroup', MyGroupParameter, override=True)


class MyPoint2DParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        # param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 7)
        x = param.child('X').opts['value']
        y = param.child('Y').opts['value']
        t = f'({x:.{d}g}, {y:.{d}g})'

        # val = param.opts.get('value', QPointF())                                # get *value*  from param and provide default value
        # d = param.opts.get('decimals', 7)                                      # get nr of decimals from param and provide default value

        # point = QPointF(val)                                                    # if needed transform object into point
        # x = point.x()                                                           # prepare label text
        # y = point.y()
        # t = f'({x:.{d}g}, {y:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()


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

        # self.sigValueChanging.emit(self, self.value())  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def value(self):
        return self.point


registerParameterType('myPoint2D', MyPoint2DParameter, override=True)
