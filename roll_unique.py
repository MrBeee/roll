"""
This module sets binning parameters for "unique fold"
"""
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toBool, toFloat


class RollUnique:
    # assign default values
    def __init__(self) -> None:
        self.apply = False
        self.write = False
        self.dOffset = 200.0
        self.dAzimuth = 5.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        uniqueElem = doc.createElement('unique')
        uniqueElem.setAttribute('apply', str(self.apply))
        uniqueElem.setAttribute('write', str(self.write))
        uniqueElem.setAttribute('deltaoff', str(self.dOffset))
        uniqueElem.setAttribute('deltaazi', str(self.dAzimuth))
        parent.appendChild(uniqueElem)

        return uniqueElem

    def readXml(self, parent: QDomNode):

        uniqueElem = parent.namedItem('unique').toElement()
        if uniqueElem.isNull():
            return False

        self.apply = toBool(uniqueElem.attribute('apply'), False)
        self.write = toBool(uniqueElem.attribute('write'), False)
        self.dOffset = toFloat(uniqueElem.attribute('deltaoff'))
        self.dAzimuth = toFloat(uniqueElem.attribute('deltaazi'))

        return True
