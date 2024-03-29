from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from pyqtgraph.widgets.SpinBox import SpinBox


class MyNumericParameterItem(WidgetParameterItem):
    """
    Subclasses `WidgetParameterItem` similar to MyNumericParameterItem,
    It makes sure ints & floats are grey when disabled

    ==========================  =============================================================
    **Registered Types:**
    myInt                         Displays a :class:`SpinBox <pyqtgraph.SpinBox>` in integer mode.
    myFloat                       Displays a :class:`SpinBox <pyqtgraph.SpinBox>`.
    ==========================  =============================================================
    """

    def makeWidget(self):
        opts = self.param.opts
        t = opts['type']
        defs = {
            'value': 0,
            'min': None,
            'max': None,
            'step': 1.0,
            'dec': False,
            'siPrefix': False,
            'suffix': '',
            'decimals': 3,
        }

        if t == 'int' or t == 'myInt':                                          # myInt added to integer types
            defs['int'] = True
            defs['minStep'] = 1.0

        for k in defs:
            if k in opts:
                defs[k] = opts[k]

        if opts.get('limits') is not None:
            defs['min'], defs['max'] = opts['limits']

        w = SpinBox()
        w.setOpts(**defs)
        w.sigChanged = w.sigValueChanged
        w.sigChanging = w.sigValueChanging
        return w

    def updateDisplayLabel(self, value=None):
        if value is None:
            value = self.widget.lineEdit().text()
        super().updateDisplayLabel(value)

    def showEditor(self):
        super().showEditor()
        self.widget.selectNumber()  # select the numerical portion of the text for quick editing

    def limitsChanged(self, param, limits):
        self.widget.setOpts(bounds=limits)

    def optsChanged(self, param, opts):
        super().optsChanged(param, opts)
        sbOpts = {}

        if 'units' in opts and 'suffix' not in opts:
            sbOpts['suffix'] = opts['units']
        for k, v in opts.items():
            if k in self.widget.opts:
                sbOpts[k] = v

        if 'enabled' in opts:
            # use different foregrond color for disabled items. Very simple implementation; just grey it out
            if not opts['enabled']:
                self.displayLabel.setStyleSheet('color: grey')
            else:
                self.displayLabel.setStyleSheet('color: black')

        self.widget.setOpts(**sbOpts)
        self.updateDisplayLabel()


class MyIntParameter(Parameter):
    itemClass = MyNumericParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        Parameter.__init__(self, **opts)


class MyFloatParameter(Parameter):
    itemClass = MyNumericParameterItem

    def __init__(self, **opts):
        # opts['expanded'] = False                                              # to overrule user-requested options
        # opts['flat'] = True

        Parameter.__init__(self, **opts)


registerParameterType('myInt', MyIntParameter, override=True)
registerParameterType('myFloat', MyFloatParameter, override=True)

# Still to do; apply a similar approach for readonly bool and string :
# registerParameterItemType('myBool',  MyBoolParameter,  override=True)
# registerParameterItemType('myStr',   MyStrParameter,   override=True)
