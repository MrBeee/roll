import re

from pyqtgraph import functions as fn
from pyqtgraph.parametertree import Parameter, registerParameterType
from pyqtgraph.parametertree.parameterTypes import (PenParameter,
                                                    PenParameterItem)
from pyqtgraph.parametertree.parameterTypes.qtenum import QtEnumParameter
from pyqtgraph.Qt import mkQApp
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from .aux_functions import makePenFromParms


class MyPenParameterItem(PenParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        # hide the (non-functional) default button at the top level
        self.defaultBtn.setVisible(False)

    def updateDepth(self, depth):
        """
        Change set the item font to bold and increase the font size on outermost groups if desired.
        """
        app = mkQApp()
        palette = app.palette()
        background = palette.base().color()

        h, s, l, a = background.getHslF()
        lightness = 0.5 + (l - 0.5) * 0.8
        altBackground = QColor.fromHslF(h, s, lightness, a)

        flat = self.param.opts.get('flat', False)
        brush = self.param.opts.get('brush', None)

        for c in [0, 1]:
            font = self.font(c)
            if not flat:
                font.setBold(True)
            if depth == 0:
                if brush is not None:
                    self.setBackground(c, fn.mkColor(brush))
                elif not flat:
                    self.setBackground(c, background)
                    font.setPointSize(self.pointSize() + 1)
            else:
                if brush is not None:
                    self.setBackground(c, fn.mkColor(brush))
                elif not flat:
                    self.setBackground(c, altBackground)

            self.setForeground(c, palette.text().color())
            self.setFont(c, font)
        self.titleChanged()  # sets the size hint for column 0 which is based on the new font


class MyPenParameter(PenParameter):
    """
    ============== ========================================================
    **Options**
    flat           Defaults to False. Set True to avoid bold font usage
    ============== ========================================================
    """

    itemClass = MyPenParameterItem

    def __init__(self, **opts):
        self._initialPenValue = opts.get('value', opts.get('default', None))
        super().__init__(**opts)

        if self._initialPenValue is not None:
            self.pen = self.mkPen(self._initialPenValue)

        self._initialPenValue = None

    def _makeChildren(self, boundPen=None):
        initialValue = getattr(self, '_initialPenValue', None)
        if isinstance(initialValue, tuple) and len(initialValue) == 6:
            optsPen = makePenFromParms(initialValue)
        elif initialValue is not None:
            optsPen = fn.mkPen(initialValue)
        else:
            optsPen = boundPen or fn.mkPen()

        ps = Qt.PenStyle
        cs = Qt.PenCapStyle
        js = Qt.PenJoinStyle

        param = Parameter.create(
            name='Params',
            type='group',
            children=[
                dict(name='color', type='color', value=optsPen.color(), default=optsPen.color()),
                dict(name='width', type='int', limits=[0, None], value=optsPen.width(), default=optsPen.width()),
                QtEnumParameter(ps, searchObj=Qt, name='style', value=optsPen.style(), default=optsPen.style()),
                QtEnumParameter(cs, searchObj=Qt, name='capStyle', value=optsPen.capStyle(), default=optsPen.capStyle()),
                QtEnumParameter(js, searchObj=Qt, name='joinStyle', value=optsPen.joinStyle(), default=optsPen.joinStyle()),
                dict(name='cosmetic', type='bool', value=optsPen.isCosmetic(), default=optsPen.isCosmetic()),
            ],
        )

        for p in param:
            name = p.name()
            if p.type() == 'bool':
                attrName = f'is{name.title()}'
            else:
                attrName = name
            default = getattr(optsPen, attrName)()
            replace = r'\1 \2'
            title = re.sub(r'(\w)([A-Z])', replace, name)
            title = title.title().strip()
            p.setOpts(title=title, default=default)

        if boundPen is not None:
            self.updateFromPen(param, boundPen)
            for p in param:
                setName = f'set{p.name()[0].upper()}{p.name()[1:]}'
                setattr(boundPen, setName, p.setValue)
                newSetter = self.penPropertySetter
                if p.type() != 'color':
                    p.sigValueChanging.connect(newSetter)
                try:
                    p.sigValueChanged.disconnect(p._emitValueChanged)
                except RuntimeError:
                    # The child parameter was freshly created here, so a full disconnect is safe.
                    p.sigValueChanged.disconnect()
                p.sigValueChanged.connect(newSetter)

        return param


registerParameterType('myPen', MyPenParameter, override=True)
