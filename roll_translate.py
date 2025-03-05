"""
This module provides the Roll Translate Class to grow and roll a seed
"""
import math

from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollTranslate:
    # assign default name value
    def __init__(self, name: str = '') -> None:
        self.name = name
        self.steps = 1                                                          # Minimum (default) value
        self.increment = QVector3D()                                            # zero x, y, z values
        self.azim = None                                                        # direction undetermined
        self.tilt = None                                                        # direction undetermined

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

        if self.azim is None:
            self.azim = math.degrees(math.atan2(self.increment.y(), self.increment.x()))

        if self.tilt is None:
            lengthXY = math.sqrt(self.increment.x() ** 2 + self.increment.y() ** 2)
            self.tilt = math.degrees(math.atan2(self.increment.z(), lengthXY))

        translateElem.setAttribute('azim', str(self.azim))
        translateElem.setAttribute('tilt', str(self.tilt))

        parent.appendChild(translateElem)

        return translateElem

    def readXml(self, parent: QDomNode):

        # The parent node has translate as tagname, so no need to find it first
        if parent.isNull():
            return False

        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.steps = int(parent.attribute('n'))
        self.increment.setX(toFloat(parent.attribute('dx')))
        self.increment.setY(toFloat(parent.attribute('dy')))
        self.increment.setZ(toFloat(parent.attribute('dz')))

        if parent.hasAttribute('azim'):                                         # rgb is there for backwards compatibility
            self.azim = toFloat(parent.attribute('azim'))
        else:
            self.azim = math.degrees(math.atan2(self.increment.y(), self.increment.x()))

        if parent.hasAttribute('tilt'):                                         # rgb is there for backwards compatibility
            self.tilt = toFloat(parent.attribute('tilt'))
        else:
            lengthXY = math.sqrt(self.increment.x() ** 2 + self.increment.y() ** 2)
            self.tilt = math.degrees(math.atan2(self.increment.z(), lengthXY))

        return True
