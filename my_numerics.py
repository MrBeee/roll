from pyqtgraph.parametertree import registerParameterItemType
from pyqtgraph.parametertree.parameterTypes.basetypes import SimpleParameter
from pyqtgraph.parametertree.parameterTypes.numeric import NumericParameterItem


class MyNumericParameterItem(NumericParameterItem):                            # make sure ints & floats are grey when disabled
    """
    Subclasses `WidgetParameterItem` to provide the following types:

    ==========================  =============================================================
    **Registered Types:**
    int                         Displays a :class:`SpinBox <pyqtgraph.SpinBox>` in integer mode.
    float                       Displays a :class:`SpinBox <pyqtgraph.SpinBox>`.
    ==========================  =============================================================
    """

    def makeWidget(self):
        if self.param.opts['type'] == 'myFloat':
            self.param.opts['type'] = 'float'

        if self.param.opts['type'] == 'myFloat':
            self.param.opts['type'] = 'float'

        super().makeWidget()

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


registerParameterItemType('myFloat', MyNumericParameterItem, SimpleParameter, override=True)
registerParameterItemType('myInt', MyNumericParameterItem, SimpleParameter, override=True)

# Still to do; apply the same approach for bool and string :
# registerParameterItemType('myBool',  MyBoolParameterItem,  SimpleParameter, override=True)
# registerParameterItemType('myStr',   MyStrParameterItem,   SimpleParameter, override=True)
