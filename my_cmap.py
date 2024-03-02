import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QComboBox

from .functions import natural_sort

# See: https://github.com/pyqtgraph/pyqtgraph/issues/1407
# See: https://docs.bokeh.org/en/latest/docs/reference/colors.html
# See: https://docs.bokeh.org/en/latest/docs/reference/palettes.html
# See: https://colorcet.holoviz.org/


class CmapParameterItem(WidgetParameterItem):
    """
    Parameter type which displays a ComboBox containing a list of color maps
    """

    def __init__(self, param, depth):
        self.cmapList = natural_sort(pg.colormap.listMaps())
        self.colorbarWidth = 120                                                # Need to define *before* parent's init as parent 'makes' the widget
        super().__init__(param, depth)

    def makeWidget(self):
        w = QComboBox()
        w.setIconSize(QSize(self.colorbarWidth, 20))
        w.setStyleSheet('border: 0px')

        for item in self.cmapList:
            cmap = pg.colormap.get(item)                                        # get the appropriate colormap
            brush = cmap.getBrush(span=(0.0, float(self.colorbarWidth)), orientation='horizontal')
            pixmap = QPixmap(self.colorbarWidth, 20)                            # create a pixmap as starting point for a QIcon
            pixmap.fill(Qt.white)                                               # create white background; not really needed; all is covered
            painter = QPainter(pixmap)                                          # paint the pixmap
            painter.setBrush(brush)
            painter.drawRect(pixmap.rect())
            painter.end()
            icon = QIcon(pixmap)                                                # create the required icon
            w.addItem(icon, item)                                               # add icon and string to the list

        w.sigChanged = w.currentIndexChanged
        w.value = w.currentText
        w.setValue = self.setValue                                              # the function defined below
        self.hideWidget = False
        return w

    def setValue(self, val):
        try:
            index = self.cmapList.index(val)
        except ValueError:
            index = 0
        self.widget.setCurrentIndex(index)


class CmapParameter(Parameter):
    itemClass = CmapParameterItem


registerParameterType('myCmap', CmapParameter, override=True)
