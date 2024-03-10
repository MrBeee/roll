from pyqtgraph.parametertree import registerParameterItemType
from pyqtgraph.parametertree.parameterTypes.basetypes import SimpleParameter, WidgetParameterItem
from pyqtgraph.widgets.SpinBox import SpinBox


class MyWidgetParameterItem(WidgetParameterItem):
    """
    ParameterTree item with:

      * label in second column for displaying value
      * simple widget for editing value (displayed instead of label when item is selected)
      * button that resets value to default

    This class can be subclassed by overriding makeWidget() to provide a custom widget.
    """

    def __init__(self, param, depth):
        WidgetParameterItem.__init__(self, param, depth)

    # the only reason to add this method is to stop PyLint from complaining
    def makeWidget(self):
        """
        Return a single widget whose position in the tree is determined by the
        value of self.asSubItem. If True, it will be placed in the second tree
        column, and if False, the first tree column of a child item.

        The widget must be given three attributes:

        ==========  ============================================================
        sigChanged  a signal that is emitted when the widget's value is changed
        value       a function that returns the value
        setValue    a function that sets the value
        ==========  ============================================================

        This function must be overridden by a subclass.
        """
        raise NotImplementedError

    # def optsChanged(self, param, opts):
    #     """Called when any options are changed that are not
    #     name, value, default, or limits"""
    #     ParameterItem.optsChanged(self, param, opts)                            # Call the base class first

    #     if 'enabled' in opts:
    #         # use different foregrond color for disabled items. Very simple implementation; just grey it out
    #         if not opts['enabled']:
    #             self.displayLabel.setStyleSheet('color: grey')
    #         else:
    #             self.displayLabel.setStyleSheet('color: black')

    #     super().optsChanged(param, opts)                                        # continue doing the usual stuff

    def optsChanged(self, param, opts):
        """Called when any options are changed that are not name, value, default, or limits"""
        super().optsChanged(param, opts)                                        # continue doing the usual stuff

        if 'enabled' in opts:
            # use different foregrond color for disabled items. Very simple implementation; just grey it out
            if not opts['enabled']:
                self.displayLabel.setStyleSheet('color: grey')
            else:
                self.displayLabel.setStyleSheet('color: black')


class MyNumericParameterItem(MyWidgetParameterItem):                            # make sure ints & floats are grey when disabled
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
        self.widget.setOpts(**sbOpts)
        self.updateDisplayLabel()


# registerParameterItemType('myFloat', MyNumericParameterItem, SimpleParameter, override=True)
# registerParameterItemType('myInt', MyNumericParameterItem, SimpleParameter, override=True)

# Still to do; apply the same approach for bool and string :
# registerParameterItemType('myBool',  MyBoolParameterItem,  SimpleParameter, override=True)
# registerParameterItemType('myStr',   MyStrParameterItem,   SimpleParameter, override=True)
