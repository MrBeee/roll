from pyqtgraph.parametertree import registerParameterType
from qgis.PyQt.QtCore import QRectF

from .functions import lineNo
from .my_group import MyGroupParameter, MyGroupParameterItem


class MyRectParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.createAndInitPreviewLabel(param)

        param.sigValueChanging.connect(self.onValueChanging)
        param.sigTreeStateChanged.connect(self.onTreeStateChanged)

    def showPreviewInformation(self, param):
        val = param.opts.get('value', QRectF())
        d = param.opts.get('decimals', 5)

        rect = QRectF(val)                                                      # make local copy

        if rect.isNull():
            t = 'Unrestricted'
        else:
            Xmin = rect.left()
            Xmax = rect.right()
            Ymin = rect.top()
            Ymax = rect.bottom()
            t = f'x:({Xmin:.{d}g}¦{Xmax:.{d}g}), y:({Ymin:.{d}g}¦{Ymax:.{d}g})'

        self.previewLabel.setText(t)
        self.previewLabel.update()


class MyRectParameter(MyGroupParameter):

    itemClass = MyRectParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyRect Parameter opts')

        d = opts.get('decimals', 5)
        e = opts.get('enabled', True)
        r = opts.get('readonly', False)
        self.rect = opts.get('value', QRectF())

        self.addChild(dict(name='Xmin', type='myFloat', decimals=d, enabled=e, readonly=r, value=self.rect.left(), default=self.rect.left()))    # myFloat
        self.addChild(dict(name='Xmax', type='myFloat', decimals=d, enabled=e, readonly=r, value=self.rect.right(), default=self.rect.right()))    # myFloat
        self.addChild(dict(name='Ymin', type='myFloat', decimals=d, enabled=e, readonly=r, value=self.rect.top(), default=self.rect.top()))    # myFloat
        self.addChild(dict(name='Ymax', type='myFloat', decimals=d, enabled=e, readonly=r, value=self.rect.bottom(), default=self.rect.bottom()))    # myFloat

        self.parXmin = self.child('Xmin')
        self.parXmax = self.child('Xmax')
        self.parYmin = self.child('Ymin')
        self.parYmax = self.child('Ymax')

        self.parXmin.sigValueChanged.connect(self.changed)
        self.parXmax.sigValueChanged.connect(self.changed)
        self.parYmin.sigValueChanged.connect(self.changed)
        self.parYmax.sigValueChanged.connect(self.changed)

    def setOpts(self, **opts):
        self.parXmin.setOpts(**opts)
        self.parXmax.setOpts(**opts)
        self.parYmin.setOpts(**opts)
        self.parYmax.setOpts(**opts)

    # update the values of the four children
    def changed(self):
        xmin = self.parXmin.value()
        xmax = self.parXmax.value()
        self.rect.setLeft(min(xmin, xmax))                                     # always set first
        self.rect.setRight(max(xmin, xmax))

        ymin = self.parYmin.value()
        ymax = self.parYmax.value()
        self.rect.setTop(min(ymin, ymax))                                    # always set first
        self.rect.setBottom(max(ymin, ymax))

        self.sigValueChanging.emit(self, self.rect)

    def value(self):
        return self.rect


registerParameterType('myRectF', MyRectParameter, override=True)
