from pyqtgraph.graphicsItems.ScatterPlotItem import Symbols, renderSymbol
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QBrush, QIcon, QPen, QPixmap
from qgis.PyQt.QtWidgets import QComboBox


class MySymbolParameterItem(WidgetParameterItem):
    """Parameter type which displays a ComboBox containing a list of plotting symbols"""

    symbolDict = {
        'o': 'circle',
        's': 'square',
        't': 'triangle (down)',
        't1': 'triangle (up)',
        't2': 'triangle (right)',
        't3': 'triangle (left)',
        'd': 'diamond',
        '+': 'plus',
        'x': 'cross',
        'p': 'pentagon',
        'h': 'hexagon',
        'star': 'star',
        '|': 'line (vertical)',
        '_': 'line (horizontal)',
        'arrow_up': 'arrow (up)',
        'arrow_right': 'arrow (right)',
        'arrow_down': 'arrow (down)',
        'arrow_left': 'arrow (left)',
        'crosshair': 'crosshair',
    }

    def __init__(self, param, depth):
        self.symbolWidth = 20                                                   # Need to define *before* parent's init as parent 'makes' the widget
        self.symbolKeys = list(Symbols.keys())                                  # imported from pyqtgraph; has been extended with '|' and '_' in v0.13.7 !!!

        # assert len(self.symbolNames) == len(self.symbolKeys), 'Error; the symbol list in pyqtgraph must have been altered'
        super().__init__(param, depth)

    @staticmethod
    def getsymbolName(key) -> str:
        return MySymbolParameterItem.symbolDict.get(key, key)                   # use key as default name, in case there is no 'translation'

    def makeWidget(self):
        w = QComboBox()
        w.setIconSize(QSize(self.symbolWidth, self.symbolWidth))
        w.setStyleSheet('border: 0px')

        for key in self.symbolKeys:
            pixmap = QPixmap(self.symbolWidth, self.symbolWidth)                # create a pixmap as starting point for a QIcon
            pixmap.fill(Qt.GlobalColor.white)                                   # create white background

            pen = QPen(Qt.GlobalColor.black)                                    # create pen and brush
            pen.setWidthF(0.075)
            brush = QBrush(Qt.GlobalColor.white)

            p = renderSymbol(key, self.symbolWidth * 0.75, pen, brush, pixmap)  # update pixmap with symbol
            icon = QIcon(p)                                                     # create the required icon

            keyName = MySymbolParameterItem.symbolDict.get(key, key)            # use key as default name, in case there is no 'translation'
            w.addItem(icon, keyName)                                            # add icon and string to the list
            # w.addItem(key)                                                    # for debugging, only add string to the list

        w.sigChanged = w.currentIndexChanged
        w.value = self.value                                                    # both functions defined below
        w.setValue = self.setValue
        self.hideWidget = False
        return w

    def value(self):
        wanted = self.widget.currentText()
        for key, val in MySymbolParameterItem.symbolDict.items():
            if val == wanted:
                return key
        return wanted                                                           # can't translate, so it must be a 'proper' yet unknown value

    def setValue(self, val):
        for index in range(self.widget.count()):
            if self.widget.itemText(index) == val:
                self.widget.setCurrentIndex(index)
                return

        self.widget.setCurrentIndex(0)                                          # fallback option


class MySymbolParameter(Parameter):
    itemClass = MySymbolParameterItem


registerParameterType('mySymbols', MySymbolParameter, override=True)
