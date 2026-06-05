from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import \
    WidgetParameterItem
from qgis.PyQt.QtWidgets import QLineEdit

from .roll_cfp import RollCfp


class MyFloatListParameterItem(WidgetParameterItem):
    def makeWidget(self):
        widget = QLineEdit()
        defaultStyle = 'border: 0px'
        invalidStyle = 'border: 2px solid #d9534f; border-radius: 2px;'
        widget.setStyleSheet(defaultStyle)

        def _refreshValidationStyle():
            _, isValid = RollCfp.parseFrequencyListInput(widget.text())
            widget.setStyleSheet(defaultStyle if isValid else invalidStyle)

        def _value():
            parsed, isValid = RollCfp.parseFrequencyListInput(widget.text())
            widget.setStyleSheet(defaultStyle if isValid else invalidStyle)
            if isValid:
                return RollCfp.normalizeFrequencyList(parsed)
            return self.param.value()

        def _setValue(value):
            widget.setText(RollCfp.writeFrequencyListDisplay(value))
            widget.setStyleSheet(defaultStyle)

        widget.textChanged.connect(lambda *_: _refreshValidationStyle())
        widget.sigChanged = widget.editingFinished
        widget.value = _value
        widget.setValue = _setValue
        self.hideWidget = False
        return widget


class MyFloatListParameter(Parameter):
    itemClass = MyFloatListParameterItem

    def __init__(self, **opts):
        value = RollCfp.normalizeFrequencyList(opts.get('value', [40.0]))
        opts['value'] = value
        Parameter.__init__(self, **opts)

    def setValue(self, value, blockSignal=None):
        normalized = RollCfp.normalizeFrequencyList(value)
        return Parameter.setValue(self, normalized, blockSignal)


registerParameterType('myFloatList', MyFloatListParameter, override=True)
