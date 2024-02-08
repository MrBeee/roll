from pyqtgraph.graphicsItems.ScatterPlotItem import Symbols, renderSymbol
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QBrush, QIcon, QPen, QPixmap
from qgis.PyQt.QtWidgets import QComboBox


class MySymbolParameterItem(WidgetParameterItem):
    """
    Parameter type which displays a ComboBox containing a list of plotting symbols
    """

    symbolNames = [
        'circle',
        'square',
        'triangle (down)',
        'triangle (up)',
        'triangle (right)',
        'triangle (left)',
        'diamond',
        'plus',
        'cross',
        'pentagon',
        'hexagon',
        'star',
        'arrow (up)',
        'arrow (right)',
        'arrow (down)',
        'arrow (left)',
        'crosshair',
    ]

    def __init__(self, param, depth):
        self.symbolWidth = 20                                                   # Need to define *before* parent's init as parent 'makes' the widget
        self.symbolKeys = list(Symbols.keys())

        assert len(self.symbolNames) == len(self.symbolKeys), 'Error; the symbol list in pyqtgraph must have been altered'
        super().__init__(param, depth)

    @staticmethod
    def getsymbolNames():
        return MySymbolParameterItem.symbolNames

    @staticmethod
    def getsymbolKeys():
        return list(Symbols.keys())

    def makeWidget(self):
        w = QComboBox()
        w.setIconSize(QSize(self.symbolWidth, self.symbolWidth))
        w.setStyleSheet('border: 0px')

        for index, item in enumerate(self.symbolKeys):
            pixmap = QPixmap(self.symbolWidth, self.symbolWidth)               # create a pixmap as starting point for a QIcon
            pixmap.fill(Qt.white)                                               # create white background

            pen = QPen(Qt.black)                                                # create pen and brush
            pen.setWidthF(0.075)
            brush = QBrush(Qt.white)

            p = renderSymbol(item, self.symbolWidth * 0.75, pen, brush, pixmap)   # update pixmap with symbol
            icon = QIcon(p)                                                     # create the required icon

            w.addItem(icon, self.symbolNames[index])                            # add icon and string to the list
            # w.addItem(item)                                                   # for debugging, only add string to the list

        w.sigChanged = w.currentIndexChanged
        w.value = self.value                                                    # both functions defined below
        w.setValue = self.setValue
        self.hideWidget = False
        return w

    def value(self):
        try:
            index = self.symbolNames.index(self.widget.currentText())
        except ValueError:
            index = 0
        return self.symbolKeys[index]

    def setValue(self, val):
        try:
            index = self.symbolKeys.index(val)
        except ValueError:
            index = 0
        self.widget.setCurrentIndex(index)


class MySymbolParameter(Parameter):
    itemClass = MySymbolParameterItem


registerParameterType('mySymbols', MySymbolParameter, override=True)
