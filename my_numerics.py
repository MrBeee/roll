from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import \
    WidgetParameterItem
from pyqtgraph.widgets.SpinBox import SpinBox
from qgis.PyQt.QtGui import QPalette

NUMERIC_EDITOR_HEIGHT = 24
NUMERIC_LINE_EDIT_HEIGHT = 22


class MyNumericSpinBox(SpinBox):
    def __init__(self):
        super().__init__()
        self.sigChanged = self.sigValueChanged
        self.sigChanging = self.sigValueChanging

        palette = self.palette()
        baseColor = palette.color(QPalette.ColorRole.Base)
        palette.setColor(QPalette.ColorRole.Base, baseColor)
        palette.setColor(QPalette.ColorRole.Button, baseColor)
        palette.setColor(QPalette.ColorRole.Window, baseColor)
        self.setPalette(palette)
        self.lineEdit().setPalette(palette)
        self.setAutoFillBackground(True)
        self.lineEdit().setAutoFillBackground(True)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), NUMERIC_EDITOR_HEIGHT))
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setHeight(max(hint.height(), NUMERIC_EDITOR_HEIGHT))
        return hint


class MyNumericParameterItem(WidgetParameterItem):
    """
    Numeric parameter item with a slightly taller editor and stable background.

    ==========================  =============================================================
    **Registered Types:**
    myInt                         Displays a :class:`SpinBox <pyqtgraph.SpinBox>` in integer mode.
    myFloat                       Displays a :class:`SpinBox <pyqtgraph.SpinBox>`.
    ==========================  =============================================================
    """

    def __init__(self, param, depth):
        super().__init__(param, depth)

        rowHint = self.sizeHint(1)
        rowHint.setHeight(max(rowHint.height(), NUMERIC_EDITOR_HEIGHT))
        self.setSizeHint(1, rowHint)

    def makeWidget(self):
        opts = self.param.opts
        defs = {
            'value': 0,
            'min': None,
            'max': None,
            'step': 1.0,
            'dec': False,
            'siPrefix': False,
            'suffix': '',
            'decimals': 3,
            'compactHeight': False,
        }

        if opts['type'] in ('int', 'myInt'):
            defs['int'] = True
            defs['minStep'] = 1.0

        for k in defs:
            if k in opts:
                defs[k] = opts[k]

        if opts.get('limits') is not None:
            defs['min'], defs['max'] = opts['limits']

        w = MyNumericSpinBox()
        w.setOpts(**defs)
        w.setFixedHeight(NUMERIC_EDITOR_HEIGHT)
        w.setFrame(False)
        w.lineEdit().setFrame(False)
        w.lineEdit().setFixedHeight(NUMERIC_LINE_EDIT_HEIGHT)
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


class MyFloatParameter(Parameter):
    itemClass = MyNumericParameterItem


registerParameterType('myInt', MyIntParameter, override=True)
registerParameterType('myFloat', MyFloatParameter, override=True)

# Still to do; apply a similar approach for readonly bool and string :
# registerParameterItemType('myBool',  MyBoolParameter,  override=True)
# registerParameterItemType('myStr',   MyStrParameter,   override=True)
