import numpy as np
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import Emitter, WidgetParameterItem
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

# for range slider:
# See: https://stackoverflow.com/questions/67028200/pyqt5-qslider-two-positions
# See: https://pypi.org/project/QtRangeSlider/


class MySliderParameterItem(WidgetParameterItem):
    slider: QSlider
    span: np.ndarray
    charSpan: np.ndarray

    def __init__(self, param, depth):
        # Bind emitter to self to avoid garbage collection
        self.emitter = Emitter()
        self.sigChanging = self.emitter.sigChanging
        self._suffix = None
        super().__init__(param, depth)

    def updateDisplayLabel(self, value=None):
        if value is None:
            value = self.param.value()
        value = str(value)
        if self._suffix is None:
            suffixTxt = ''
        else:
            suffixTxt = f' {self._suffix}'
        self.displayLabel.setText(value + suffixTxt)

    def setSuffix(self, suffix):
        self._suffix = suffix
        # self._updateLabel(self.slider.value())                                # _updateLabel does not exist, making 'suffix' option unusable (exception)

    def makeWidget(self):
        param = self.param
        opts = param.opts
        opts.setdefault('limits', [0, 0])
        self._suffix = opts.get('suffix')

        self.slider = QSlider()
        self.slider.setOrientation(Qt.Orientation.Horizontal)

        # See: https://doc.qt.io/qt-5/stylesheet-examples.html#customizing-qslider
        self.slider.setStyleSheet(
            'QSlider::groove:horizontal {background-color: #f0f0f0; border: 1px solid #5c5c5c; margin: 0px 0px; height:  4px; }\n'
            'QSlider::handle:horizontal {background-color: #ffed70; border: 1px solid #5c5c5c; margin:-5px 0px; height: 14px; width: 7px; }\n'
        )
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        w = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)                                   # set to match row-height of other controls
        w.setLayout(layout)
        layout.addWidget(lbl)
        layout.addWidget(self.slider)

        def setValue(v):
            self.slider.setValue(self.spanToSliderValue(v))

        def getValue():
            return self.span[self.slider.value()].item()

        def vChanged(v):
            lbl.setText(self.prettyTextValue(v))

        self.slider.valueChanged.connect(vChanged)

        def onMove(pos):
            self.sigChanging.emit(self, self.span[pos].item())

        self.slider.sliderMoved.connect(onMove)

        w.setValue = setValue
        w.value = getValue
        w.sigChanged = self.slider.valueChanged
        w.sigChanging = self.sigChanging
        self.optsChanged(param, opts)
        return w

    def spanToSliderValue(self, v):
        return int(np.argmin(np.abs(self.span - v)))

    def prettyTextValue(self, v):
        if self._suffix is None:
            suffixTxt = ''
        else:
            suffixTxt = f' {self._suffix}'
        format_ = self.param.opts.get('format', None)
        cspan = self.charSpan
        if format_ is None:
            format_ = f'{{0:>{cspan.dtype.itemsize}}}{suffixTxt}'
        return format_.format(cspan[v].decode())

    def optsChanged(self, param, opts):
        try:
            super().optsChanged(param, opts)
        except AttributeError:
            # This may trigger while building the parameter before the widget is fully constructed.
            # This is fine, since errors are from the parent scope which will stabilize after the widget is
            # constructed anyway
            pass
        span = opts.get('span', None)
        if span is None:
            step = opts.get('step', 1)
            start, stop = opts.get('limits', param.opts['limits'])
            # Add a bit to 'stop' since python slicing excludes the last value
            span = np.arange(start, stop + step, step)
        precision = opts.get('precision', 2)
        if precision is not None:
            span = span.round(precision)
        self.span = span
        self.charSpan = np.char.array(span)
        w = self.slider
        w.setMinimum(0)
        w.setMaximum(len(span) - 1)
        if 'suffix' in opts:
            self.setSuffix(opts['suffix'])
            self.slider.valueChanged.emit(self.slider.value())

    def limitsChanged(self, param, limits):
        self.optsChanged(param, dict(limits=limits))


class MySliderParameter(Parameter):
    """
    ============== ========================================================
    **Options**
    limits         [start, stop] numbers
    step:          Defaults to 1, the spacing between each slider tick
    span:          Instead of limits + step, span can be set to specify
                   the range of slider options (e.g. np.linspace(-pi, pi, 100))
    format:        Format string to determine number of decimals to show, etc.
                   Defaults to display based on span dtype
    precision:     int number of decimals to keep for float tick spaces
    ============== ========================================================
    """

    itemClass = MySliderParameterItem


registerParameterType('mySlider', MySliderParameter, override=True)
