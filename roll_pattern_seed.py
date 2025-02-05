"""
This module provides Seed Class, core of the placement of src & rec points in a survey area
"""

import numpy as np
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPicture, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat
from .roll_grid import RollGrid


class RollPatternSeed:
    # assign default name value
    def __init__(self, name: str = 'seed-1') -> None:

        # input variables
        self.name = name                                                        # Seed name
        self.origin = QVector3D()                                               # Seed origin
        self.bAzimuth = False                                                   # 'True' if this seed has a pattern in direction of line direction
        self.color = QColor()                                                   # seed color to discriminate between different sources / receivers
        self.grid = RollGrid()                                                  # seed subtype

        # calculated variables
        self.boundingBox = QRectF()                                             # Constructs a null rectangle.size of the seed after all grow steps have been done
        self.pointList = []                                                     # point list derived from template seed(s)
        self.pointArray = None                                                  # numpy array derived from self.pointList; todo: need to get rid of self.pointList at some point !
        self.pointPicture = QPicture()                                          # pre-computing a QPicture object allows paint() to run much more quickly
        self.patternPicture = QPicture()                                        # pre-computing a QPicture object allows paint() to run much more quickly

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        seedElem = doc.createElement('seed')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            seedElem.appendChild(nameElement)

        seedElem.setAttribute('x0', str(round(self.origin.x(), 2)))
        seedElem.setAttribute('y0', str(round(self.origin.y(), 2)))
        seedElem.setAttribute('z0', str(round(self.origin.z(), 2)))

        seedElem.setAttribute('azi', str(self.bAzimuth))
        seedElem.setAttribute('argb', str(self.color.name(QColor.HexArgb)))

        self.grid.writeXml(seedElem, doc)

        parent.appendChild(seedElem)

        return seedElem

    def readXml(self, parent: QDomNode):
        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.origin.setX(toFloat(parent.attribute('x0')))
        self.origin.setY(toFloat(parent.attribute('y0')))
        self.origin.setZ(toFloat(parent.attribute('z0')))

        self.bAzimuth = parent.attribute('azi') == 'True'

        if parent.hasAttribute('argb'):                                         # rgb is there for backwards compatibility
            self.color = QColor(parent.attribute('argb'))
        elif parent.hasAttribute('rgb'):
            # provides backward compatibility with "rgb" attribute
            self.color = QColor(parent.attribute('rgb'))

        self.grid.readXml(parent)

    def calcBoundingRect(self):
        self.boundingBox = QRectF()                                             # Start with a null rectangle.size of the seed
        self.boundingBox = self.grid.calcBoundingRect(self.origin)              # grid (rolling = 0, stationary = 1)
        self.boundingBox = self.boundingBox.normalized()                        # normalize this rectangle

        # make sure that QRectF.intersected() '&' and united() '|' work as expected by giving seed a minimal size
        # this is required for the subsequent roll-steps in the template

        if self.boundingBox.width() == 0.0:
            self.boundingBox.setWidth(1.0e-6)                                   # give it very narrow width

        if self.boundingBox.height() == 0.0:
            self.boundingBox.setHeight(1.0e-6)                                  # give it very small height

        return self.boundingBox  # return  bounding rectangle

    def calcPointArray(self):
        length = max(len(self.pointList), 1)                                    # need 1 or more points for a valid numpy array
        self.pointArray = np.zeros(shape=(length, 3), dtype=np.float32)         # start with empty array of the right size and type

        for count, item in enumerate(self.pointList):
            self.pointArray[count, 0] = item.x()
            self.pointArray[count, 1] = item.y()
            self.pointArray[count, 2] = item.z()

    # def calcPointPicture(self):
    #     # create painter object to draw against
    #     painter = QPainter(self.pointPicture)
    #     painter.setPen(pg.mkPen('k'))
    #     painter.setBrush(self.color)
    #     painter.drawRect(QRectF(-5, -5, 10, 10))
    #     painter.end()
