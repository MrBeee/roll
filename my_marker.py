import pyqtgraph as pg
from pyqtgraph.graphicsItems.ScatterPlotItem import renderSymbol
from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QPen, QPixmap
from qgis.PyQt.QtWidgets import (QHBoxLayout, QLabel, QSizePolicy, QSpacerItem,
                                 QWidget)

from .my_group import MyGroupParameter, MyGroupParameterItem
from .my_slider import MySliderParameter
from .my_symbols import MySymbolParameter, MySymbolParameterItem

registerParameterType('myGroup', MyGroupParameter, override=True)
registerParameterType('mySlider', MySliderParameter, override=True)
registerParameterType('mySymbols', MySymbolParameter, override=True)


class PointMarker:                                                              # class containing all marker setings
    def __init__(self, sym, col, siz):

        self._symbol = sym
        self._color = col
        self._size = siz

    def getAllAttributes(self):
        return (self._symbol, self._color, self._size)

    def setAllAttributes(self, symbol, color, size):
        self._symbol = symbol
        self._color = color
        self._size = size

    def symbol(self):
        return self._symbol

    def setSymbol(self, symbol):
        assert isinstance(symbol, str), 'Argument of wrong type!'
        self._symbol = symbol

    def color(self):
        return pg.mkColor(self._color)

    def setColor(self, color):
        self._color = color

    def size(self):
        return self._size

    def setSize(self, size):
        self._size = size


class SymbolPreviewLabel(QLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onMarkerChanging)

        opts = param.opts
        sym = opts.get('symbol', 'o')
        col = opts.get('color', 'y')
        siz = opts.get('size', 25)
        val = PointMarker(sym, col, siz)
        self.onMarkerChanging(None, val)

    def onMarkerChanging(self, _, val):

        sym = val.symbol()                                                      # symbol size `val.size()` not used in the SymbolPreviewLabel
        col = val.color()

        h = self.size().height()                                                # get pixmap size
        h = min(h, 20)
        pixmap = QPixmap(h, h)                                                  # create a pixmap to be added to QLabel
        pixmap.fill(Qt.white)                                                   # create white background

        pen = QPen(Qt.black)                                                    # create pen and brush
        pen.setWidthF(0.075)                                                    # need to scale back pen size
        brush = QBrush(col)                                                     # fill with proper color
        p = renderSymbol(sym, h * 0.75, pen, brush, pixmap)                     # update pixmap with symbol
        self.setPixmap(p)
        self.update()


class TextPreviewLabel(QLabel):
    def __init__(self, param):
        super().__init__()
        param.sigValueChanging.connect(self.onMarkerChanging)

        self.symbolKeys = MySymbolParameterItem.getsymbolKeys()                 # get from my_symbols.py
        self.symbolNames = MySymbolParameterItem.getsymbolNames()               # get from my_symbols.py
        assert len(self.symbolNames) == len(self.symbolKeys), 'Error; the symbol list in pyqtgraph must have been altered'

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        font = self.font()
        font.setPointSizeF(font.pointSize() - 0.5)
        self.setFont(font)
        self.setAlignment(Qt.AlignVCenter)

        opts = param.opts
        sym = opts.get('symbol', 'o')
        col = opts.get('color', 'y')
        siz = opts.get('size', 25)
        val = PointMarker(sym, col, siz)
        self.onMarkerChanging(None, val)

    def onMarkerChanging(self, _, val):
        sym = val.symbol()                                                      # symbol size `val.color()` not used in the TextPreviewLabel
        siz = val.size()

        index = self.symbolKeys.index(sym)
        val = self.symbolNames[index]

        self.setText(f'{val} [{siz}]')
        self.update()


class MyMarkerParameterItem(MyGroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)
        self.itemWidget = QWidget()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)                                                    # spacing between elements
        spacerItem = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addSpacerItem(spacerItem)

        self.markerLabel = SymbolPreviewLabel(param)
        self.textLabel = TextPreviewLabel(param)

        for child in self.markerLabel, self.textLabel:
            layout.addWidget(child)
        self.itemWidget.setLayout(layout)

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        # tw.setItemWidget(self, 1, self.markerLabel)
        tw.setItemWidget(self, 1, self.itemWidget)


class MyMarkerParameter(MyGroupParameter):

    itemClass = MyMarkerParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MyMarker Parameter opts')

        sym = opts.get('symbol', 'o')
        col = opts.get('color', 'y')
        siz = opts.get('size', 25)
        self.marker = PointMarker(sym, col, siz)

        self.addChild(dict(name='Symbol', value=self.marker.symbol(), default=self.marker.symbol(), type='mySymbols'))
        self.addChild(dict(name='Color', value=self.marker.color(), default=self.marker.color(), type='color'))
        self.addChild(dict(name='Size', value=self.marker.size(), default=self.marker.size(), type='mySlider', limits=[1, 100]))

        self.symPar = self.child('Symbol')
        self.colPar = self.child('Color')
        self.sizPar = self.child('Size')

        self.symPar.sigValueChanged.connect(self.symChanged)
        self.colPar.sigValueChanged.connect(self.colChanged)
        self.sizPar.sigValueChanged.connect(self.sizChanged)

    # update the values of the three children
    def symChanged(self):
        self.marker.setSymbol(self.symPar.value())
        self.sigValueChanging.emit(self, self.marker)

    def colChanged(self):
        self.marker.setColor(self.colPar.value())
        self.sigValueChanging.emit(self, self.marker)

    def sizChanged(self):
        self.marker.setSize(self.sizPar.value())
        self.sigValueChanging.emit(self, self.marker)

    def value(self):
        return self.marker


registerParameterType('myMarker', MyMarkerParameter, override=True)
