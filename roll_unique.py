"""
This module sets binning parameters for "unique fold"
"""
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollUnique:
    # assign default values
    def __init__(self) -> None:
        self.apply = False
        self.dOffset = 200.0
        self.dAzimuth = 180.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        uniqueElem = doc.createElement('unique')
        uniqueElem.setAttribute('apply', str(self.apply))
        uniqueElem.setAttribute('deltaoff', str(self.dOffset))
        uniqueElem.setAttribute('deltaazi', str(self.dAzimuth))
        parent.appendChild(uniqueElem)

        return uniqueElem

    def readXml(self, parent: QDomNode):

        uniqueElem = parent.namedItem('unique').toElement()
        if uniqueElem.isNull():
            return False

        self.apply = uniqueElem.attribute('apply') == 'True'
        self.dOffset = toFloat(uniqueElem.attribute('deltaoff'))
        self.dAzimuth = toFloat(uniqueElem.attribute('deltaazi'))

        return True
