"""
This module provides the Roll Translate Class to grow and roll a seed
"""
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollTranslate:
    # assign default name value
    def __init__(self, name: str = '') -> None:
        self.name = name
        # Minimum (default) value
        self.steps = 1
        self.increment = QVector3D()
        self.azimuth = 0.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        translateElem = doc.createElement('translate')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            translateElem.appendChild(nameElement)

        translateElem.setAttribute('n', str(self.steps))
        translateElem.setAttribute('dx', str(self.increment.x()))
        translateElem.setAttribute('dy', str(self.increment.y()))
        translateElem.setAttribute('dz', str(self.increment.z()))

        parent.appendChild(translateElem)

        return translateElem

    def readXml(self, parent: QDomNode):

        # The parent node has translate as tagname, so no need to find it first
        if parent.isNull():
            return False

        self.steps = int(parent.attribute('n'))
        self.increment.setX(toFloat(parent.attribute('dx')))
        self.increment.setY(toFloat(parent.attribute('dy')))
        self.increment.setZ(toFloat(parent.attribute('dyz')))

        return True
