from pyqtgraph import functions as fn
from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes import PenParameter, PenParameterItem
from pyqtgraph.Qt import mkQApp
from qgis.PyQt.QtGui import QColor


class MyPenParameterItem(PenParameterItem):
    # def __init__(self, param, depth):
    #     super().__init__(param, depth)

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


registerParameterType('myPen', MyPenParameter, override=True)
