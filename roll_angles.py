"""
This module provides the RollAngles Class to (dis-) allow certain angles during binning
"""
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toFloat


class RollAngles:
    def __init__(self, reflection: QPointF = QPointF(0, 45), azimuthal: QPointF = QPointF(0, 360)) -> None:  # assign default values
        self.reflection = reflection
        self.azimuthal = azimuthal

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        anglesElem = doc.createElement('angles')
        anglesElem.setAttribute('azimin', str(self.azimuthal.x()))
        anglesElem.setAttribute('azimax', str(self.azimuthal.y()))
        anglesElem.setAttribute('refmin', str(self.reflection.x()))
        anglesElem.setAttribute('refmax', str(self.reflection.y()))
        parent.appendChild(anglesElem)

        return anglesElem

    def readXml(self, parent: QDomNode):

        anglesElem = parent.namedItem('angles').toElement()
        if anglesElem.isNull():
            return False

        azimin = toFloat(anglesElem.attribute('azimin'))
        azimax = toFloat(anglesElem.attribute('azimax'))
        self.azimuthal.setX(min(azimin, azimax))
        self.azimuthal.setY(max(azimin, azimax))

        refmin = toFloat(anglesElem.attribute('refmin'))
        refmax = toFloat(anglesElem.attribute('refmax'))
        self.reflection.setX(min(refmin, refmax))
        self.reflection.setY(max(refmin, refmax))

        return True
