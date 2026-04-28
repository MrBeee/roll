from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QGraphicsEllipseItem, QPen

# see: https://stackoverflow.com/questions/77569582/how-to-color-only-part-which-is-needed-in-qgraphicsellipseitem
# See: https://pyqtgraph.readthedocs.io/en/latest/api_reference/colormap.html for colormap usage


class SmoothCircleItem(QGraphicsEllipseItem):
    _colors = None
    _colorAngle = 0
    _colorRanges = None

    def __init__(self, x=0, y=0, radius=1, colors=None, angle=0):
        super().__init__(x - radius, y - radius, radius * 2, radius * 2)
        self.setPen(QPen(Qt.red, 2))
        if colors is None:
            colors = (Qt.blue, Qt.transparent, Qt.red, Qt.transparent)
        self.setColors(colors, angle)

    def setColors(self, colors, angle=None):
        # acceptable values for "colors" are lists or tuples of:
        # - QColor, Qt.GlobalColor (or their int values)
        # - list/tuples of [color, position]
        if isinstance(colors[0], (QColor, Qt.GlobalColor, int)):
            # accept an arbitrary list of colors that splits the ellipse
            # assigning identical parts to each color
            _colors = []
            ratio = 1 / len(colors)
            pos = 0
            for c in colors:
                if not isinstance(c, QColor):
                    c = QColor(c)
                _colors.append((c, pos))
                pos += ratio
            colors = _colors

        else:
            # accept iterables in the form of [color, pos], with positions
            # in real ranges between 0.0 and 1.0
            colors = sorted([(c, p % 1.0) for c, p in colors], key=lambda cd: cd[1])

        # create an internal list of colors in the following form:
        # [color, start, extent]
        first = colors[0]
        last = [first[0], first[1] % 1.0]
        self._colors = [last]
        for color, pos in colors[1:]:
            last.append((pos - last[-1]))
            colorData = [color, pos]
            self._colors.append(colorData)
            last = colorData
        if len(colors) > 1:
            last.append(1.0 + first[1] - last[-1])
        else:
            last.append(1.0)

        if self._colorAngle == angle:
            self._update()
        elif isinstance(angle, (int, float)):
            self.setColorAngle(angle)

    def setColorAngle(self, angle):
        angle = angle % 360
        if self._colorAngle != angle:
            self._colorAngle = angle
            self._update()

    def _update(self):
        if self._colorAngle:
            # adjust the start values based on the angle
            realAngle = self._colorAngle / 360
            values = [(c, (s + realAngle) % 1, e) for c, s, e in self._colors]
        else:
            values = self._colors

        # update angles using QPainter angles, which are in sixteenths
        self._colorRanges = [(c, int(s * 5760), int(e * 5760)) for c, s, e in values]
        self.update()

    def paint(self, qp, opt, widget=None):
        rect = self.rect()
        qp.save()
        qp.setPen(Qt.NoPen)
        for color, start, extent in self._colorRanges:
            qp.setBrush(color)
            qp.drawPie(rect, start, extent)
        qp.restore()
        super().paint(qp, opt, widget)

    def setBrush(self, brush):
        grad = brush.gradient()
        if grad is None or grad.type() != grad.ConicalGradient:
            return
        self.setColors([(stop[1], stop[0]) for stop in grad.stops()])
