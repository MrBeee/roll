from pyqtgraph import functions as fn
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from qgis.PyQt.QtWidgets import QComboBox


class MyListParameterItem(WidgetParameterItem):
    """
    Parameter type which displays a basic list, allowing for a background color
    """

    def __init__(self, param, depth):
        self.lst = param.opts.get('limits', [])                                  # do this first; widget used in super()
        super().__init__(param, depth)

        brush = self.param.opts.get('brush', None)
        for c in [0, 1]:
            if brush is not None:
                self.setBackground(c, fn.mkColor(brush))

    def makeWidget(self):
        w = QComboBox()
        w.setStyleSheet('border: 0px')

        for item in self.lst:
            w.addItem(item)                                                     # add string to the list

        w.sigChanged = w.currentIndexChanged
        w.value = w.currentText
        w.setValue = self.setValue                                              # the function defined below
        self.hideWidget = False
        return w

    def setValue(self, val):
        try:
            index = self.lst.index(val)
        except ValueError:
            index = 0
        self.widget.setCurrentIndex(index)


class MyListParameter(Parameter):

    itemClass = MyListParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        Parameter.__init__(self, **opts)

        self.lst = []
        self.lst = opts.get('value', self.lst)


registerParameterType('myList', MyListParameter, override=True)
