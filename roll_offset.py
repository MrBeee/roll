"""
This module provides the Roll Offset class
"""

from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toFloat


class RollOffset:
    def __init__(self) -> None:  # assign default values
        self.rctOffsets = QRectF()
        self.radOffsets = QPointF()

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        offsetElem = doc.createElement('offset')
        offsetElem.setAttribute('xmin', str(self.rctOffsets.left()))
        offsetElem.setAttribute('xmax', str(self.rctOffsets.right()))
        offsetElem.setAttribute('ymin', str(self.rctOffsets.top()))
        offsetElem.setAttribute('ymax', str(self.rctOffsets.bottom()))

        offsetElem.setAttribute('rmin', str(self.radOffsets.x()))
        offsetElem.setAttribute('rmax', str(self.radOffsets.y()))
        parent.appendChild(offsetElem)

        return offsetElem

    def readXml(self, parent: QDomNode):

        offsetElem = parent.namedItem('offset').toElement()
        if offsetElem.isNull():
            return False

        xmin = toFloat(offsetElem.attribute('xmin'))
        xmax = toFloat(offsetElem.attribute('xmax'))
        self.rctOffsets.setLeft(min(xmin, xmax))
        self.rctOffsets.setRight(max(xmin, xmax))

        ymin = toFloat(offsetElem.attribute('ymin'))
        ymax = toFloat(offsetElem.attribute('ymax'))
        self.rctOffsets.setTop(min(ymin, ymax))
        self.rctOffsets.setBottom(max(ymin, ymax))

        rmin = toFloat(offsetElem.attribute('rmin'))
        rmax = toFloat(offsetElem.attribute('rmax'))
        self.radOffsets.setX(min(rmin, rmax))
        self.radOffsets.setY(max(rmin, rmax))

        return True
