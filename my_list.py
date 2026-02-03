from pyqtgraph import functions as fn
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import \
    WidgetParameterItem
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

        # refresh combo when limits change
        param.sigLimitsChanged.connect(self.updateLimits)
        param.sigOptionsChanged.connect(self.optsChanged)

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

    def updateLimits(self, param, limits):
        self.lst = list(limits) if limits is not None else []
        self._rebuildCombo()

    def optsChanged(self, param, opts):
        if 'limits' in opts:
            self.lst = list(opts['limits']) if opts['limits'] is not None else []
            self._rebuildCombo()

    def _rebuildCombo(self):
        if self.widget is None:
            return
        current = self.widget.currentText()
        self.widget.blockSignals(True)
        self.widget.clear()
        for item in self.lst:
            self.widget.addItem(item)
        # restore selection when possible
        if current in self.lst:
            self.widget.setCurrentIndex(self.lst.index(current))
        elif self.lst:
            self.widget.setCurrentIndex(0)
        self.widget.blockSignals(False)

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
