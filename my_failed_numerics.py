import builtins

from pyqtgraph.parametertree import Parameter, registerParameterItemType
from pyqtgraph.parametertree.parameterTypes.basetypes import WidgetParameterItem
from pyqtgraph.widgets.SpinBox import SpinBox


class MyNumericParameterItem(WidgetParameterItem):                            # make sure ints & floats are grey when disabled
    """
    Subclasses `WidgetParameterItem` to provide the following types:

    ==========================  =============================================================
    **Registered Types:**
    int                         Displays a :class:`SpinBox <pyqtgraph.SpinBox>` in integer mode.
    float                       Displays a :class:`SpinBox <pyqtgraph.SpinBox>`.
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
        if t == 'int':
            defs['int'] = True
            defs['minStep'] = 1.0
        for k in defs:
            if k in opts:
                defs[k] = opts[k]
        if 'limits' in opts:
            defs['min'], defs['max'] = opts['limits']
        w = SpinBox()
        w.setOpts(**defs)
        w.sigChanged = w.sigValueChanged
        w.sigChanging = w.sigValueChanging
        return w

    def updateDisplayLabel(self, value=None):
        """Update the display label to reflect the value of the parameter."""
        if value is None:
            value = self.widget.lineEdit().text()
        super().updateDisplayLabel(value)

    def showEditor(self):
        super().showEditor()
        self.widget.selectNumber()  # select the numerical portion of the text for quick editing

    def limitsChanged(self, param, limits):
        self.widget.setOpts(bounds=limits)

    def optsChanged(self, param, opts):
        """Called when any options are changed that are not name, value, default, or limits"""
        super().optsChanged(param, opts)

        if 'enabled' in opts:
            # use different foregrond color for disabled items. Very simple implementation; just grey it out
            if not opts['enabled']:
                self.displayLabel.setStyleSheet('color: grey')
            else:
                self.displayLabel.setStyleSheet('color: black')

        sbOpts = {}
        if 'units' in opts and 'suffix' not in opts:
            sbOpts['suffix'] = opts['units']
        for k, v in opts.items():
            if k in self.widget.opts:
                sbOpts[k] = v
        self.widget.setOpts(**sbOpts)
        self.updateDisplayLabel()


class MySimpleParameter(Parameter):
    def __init__(self, *args, **kargs):
        """
        Initialize the parameter.

        This is normally called implicitly through :meth:`Parameter.create`.
        The keyword arguments available to :meth:`Parameter.__init__` are
        applicable.
        """
        Parameter.__init__(self, *args, **kargs)

    def _interpretValue(self, v):
        typ = self.opts['type']

        if typ == 'myInt':
            typ = 'int'
        elif typ == 'myFloat':
            typ = 'float'

        def _missing_interp(v):
            # Assume raw interpretation
            return v
            # Or:
            # raise TypeError(f'No interpreter found for type {typ}')

        interpreter = getattr(builtins, typ, _missing_interp)
        return interpreter(v)


registerParameterItemType('myFloat', MyNumericParameterItem, MySimpleParameter, override=True)
registerParameterItemType('myInt', MyNumericParameterItem, MySimpleParameter, override=True)

# Still to do; apply the same approach for bool and string :
# registerParameterItemType('myBool',  MyBoolParameterItem,  MySimpleParameter, override=True)
# registerParameterItemType('myStr',   MyStrParameterItem,   MySimpleParameter, override=True)
