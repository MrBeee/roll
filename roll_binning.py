"""
This module provides the binning method and medium velocity
"""
from enum import Enum

from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class BinningType(Enum):
    cmp = 0
    plane = 1
    sphere = 2


BinningList = [
    'Cmp binning',
    'Dipping plane',
    'Buried sphere',
]


class RollBinning:
    def __init__(self, method=BinningType.cmp, vint=2000.0) -> None:  # assign default values
        self.method = method
        self.vint = vint

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        binningElem = doc.createElement('binning')

        binningElem.setAttribute('method', str(self.method.name))
        binningElem.setAttribute('vint', str(self.vint))

        parent.appendChild(binningElem)

        return binningElem

    def readXml(self, parent: QDomNode):

        binningElem = parent.namedItem('binning').toElement()
        if binningElem.isNull():
            return False

        self.method = BinningType[(binningElem.attribute('method'))]
        self.vint = toFloat(binningElem.attribute('vint'), 2000.0)

        return True
