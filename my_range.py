from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtGui import QVector3D

from .my_group import MyGroupParameter, MyGroupParameterItem


class MyRangeParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        d = param.opts.get('decimals', 3)
        min_ = param.child('Min').value()
        max_ = param.child('Max').value()
        stp_ = param.child('Step').value()
        pnt_ = param.child('Points').value()
        pnt_ = round((max_ - min_) / stp_) + 1
        t = f'[{min_:.{d}g} to {max_:.{d}g}] {pnt_:.{d}g} steps @ {stp_:.{d}g}'

        self.previewLabel.setText(t)
        self.previewLabel.update()


class MyRangeParameter(MyGroupParameter):

    itemClass = MyRangeParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyRange Parameter opts')

        s = opts.get('suffix', None)
        d = self.decimals = opts.get('decimals', 7)
        r = True if opts.get('fixedMin', False) is True else False
        x = True if opts.get('twoDim', False) is True else False

        # A QVector3D(x, y, z) object is 'abused' to represent QVector3D(min, max, step)
        self.range = opts.get('value', QVector3D(0.0, 1.0, 0.1))
        min_ = self.range.x()      # avoid using 'min' and 'max'; these are builtin functions
        max_ = self.range.y()
        stp_ = self.range.z()
        pnt_ = round((max_ - min_) / stp_) + 1

        self.addChild(dict(name='Min', type='myFloat', value=self.range.x(), default=self.range.x(), decimals=d, readonly=r, suffix=s))
        self.addChild(dict(name='Max', type='myFloat', value=self.range.y(), default=self.range.y(), decimals=d, suffix=s))
        self.addChild(dict(name='Step', type='myFloat', value=self.range.z(), default=self.range.z(), decimals=d, suffix=s))
        self.addChild(dict(name='Points', type='myInt', value=pnt_, default=pnt_, enabled=False, readonly=True, suffix='#'))   # set value through setPoints()
        self.addChild(dict(name='Points 2D', type='myInt', value=pnt_**2, default=pnt_**2, enabled=False, readonly=True, suffix='#'))   # set value through setPoints()

        self.parMin = self.child('Min')
        self.parMax = self.child('Max')
        self.parStp = self.child('Step')
        self.parPnt = self.child('Points')
        self.parP2D = self.child('Points 2D')
        self.parP2D.show(x)   # only show for a 2D range

        self.parMin.sigValueChanged.connect(self.minChanged)
        self.parMax.sigValueChanged.connect(self.maxChanged)
        self.parStp.sigValueChanged.connect(self.stpChanged)

    def setPoints(self):
        min_ = self.range.x()      # avoid using 'min' and 'max'; these are builtin functions
        max_ = self.range.y()
        stp_ = self.range.z()
        pnt_ = round((max_ - min_) / stp_) + 1
        self.parPnt.setValue(pnt_)
        self.parP2D.setValue(pnt_**2)

    def minChanged(self):
        min_ = self.parMin.value()
        self.range.setX(min_)
        # if the minimum changes; the overall number of points wil change as well
        self.setPoints()

        # self.sigValueChanging.emit(self, self.value())  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def maxChanged(self):
        max_ = self.parMax.value()
        self.range.setY(max_)
        self.setPoints()

        # self.sigValueChanging.emit(self, self.value())  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def stpChanged(self):
        stp_ = self.parStp.value()
        self.range.setZ(stp_)
        # if the step size changes; the overall number of points wil change as well
        self.setPoints()

        # self.sigValueChanging.emit(self, self.value())  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    def value(self):
        return self.range

    @staticmethod
    def write(vector: QVector3D, decimals=7) -> str:
        d = decimals
        return f'{vector.x():.{d}g};{vector.y():.{d}g};{vector.z():.{d}g}'

    @staticmethod
    def read(stringValue) -> QVector3D:
        parts = stringValue.split(';')
        vector = QVector3D(float(parts[0]), float(parts[1]), float(parts[2]))
        return vector


registerParameterType('myRange', MyRangeParameter, override=True)
