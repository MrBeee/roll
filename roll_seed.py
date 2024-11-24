"""
This module provides Seed Class, core of the placement of src & rec points in a survey area
"""

from enum import Enum

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPicture, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat
from .roll_circle import RollCircle
from .roll_grid import RollGrid
from .roll_spiral import RollSpiral
from .roll_well import RollWell

# todo: replace integers by class SeedType for seed type indication


class SeedType(Enum):
    rollingGrid = 0
    fixedGrid = 1
    circle = 2
    spiral = 3
    well = 4


class RollSeed:
    # assign default name value
    def __init__(self, name: str = 'seed-1') -> None:
        # input variables
        self.name = name                                                        # Seed name
        self.origin = QVector3D()                                               # Seed origin
        self.bSource = False                                                    # 'True' if this is a source point seed (receiver = 'False')
        self.bAzimuth = False                                                   # 'True' if this seed has a pattern in direction of line direction
        self.patternNo = -1                                                     # Pattern index serialized in survey file (-1 if name not found)
        self.color = QColor()                                                   # color of seed to discriminate different sources / receivers

        # seed subtypes
        self.type = 0                                                           # Seed type 0 = rolling [default], 1 = fixed, 2 = circle, 3 = spiral, 4 = well
        self.grid = RollGrid()
        self.circle = RollCircle()
        self.spiral = RollSpiral()
        self.well = RollWell()

        # calculated variables
        self.boundingBox = QRectF()                                             # Constructs a null rectangle.size of the seed after all grow steps have been done
        # self.salvo = QLineF()                                                 # draws line From FIRST to LAST point of FIRST grow step (quick draw)
        self.pointList = []                                                     # point list to derive cdp coverage from
        self.pointArray = None                                                  # numpy array to derive cdp coverage from
        self.blockBorder = QRectF()                                             # inherited from seed -> template -> block's srcBorder / recBorder depending on seed type
        self.pointPicture = QPicture()                                          # pre-computing a QPicture object allows paint() to run much more quickly
        self.patternPicture = QPicture()                                        # pre-computing a QPicture object allows paint() to run much more quickly
        self.rendered = False                                                   # prevent painting stationary seeds multiple times due to roll-along of other seeds

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

        seedElem.setAttribute('src', str(self.bSource))
        seedElem.setAttribute('azi', str(self.bAzimuth))
        seedElem.setAttribute('patno', str(self.patternNo))
        seedElem.setAttribute('typno', str(self.type))
        seedElem.setAttribute('argb', str(self.color.name(QColor.HexArgb)))

        if self.type < 2:
            self.grid.writeXml(seedElem, doc)
        elif self.type == 2:
            self.circle.writeXml(seedElem, doc)
        elif self.type == 3:
            self.spiral.writeXml(seedElem, doc)
        elif self.type == 4:
            self.well.writeXml(seedElem, doc)

        parent.appendChild(seedElem)

        return seedElem

    def readXml(self, parent: QDomNode):
        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.origin.setX(toFloat(parent.attribute('x0')))
        self.origin.setY(toFloat(parent.attribute('y0')))
        self.origin.setZ(toFloat(parent.attribute('z0')))

        self.bSource = parent.attribute('src') == 'True'
        self.bAzimuth = parent.attribute('azi') == 'True'
        self.patternNo = int(parent.attribute('patno'))
        self.type = int(parent.attribute('typno'))

        if parent.hasAttribute('argb'):
            self.color = QColor(parent.attribute('argb'))
        elif parent.hasAttribute('rgb'):
            # provides backward compatibility with "rgb" attribute
            self.color = QColor(parent.attribute('rgb'))
        else:                                                                   # fallback; in case of missing attribute
            if self.bSource:
                # light red
                self.color = QColor('#77FF8989')
            else:
                # light blue
                self.color = QColor('#7787A4D9')

        if self.type < 2:
            self.grid.readXml(parent)
        elif self.type == 2:
            self.circle.readXml(parent)
        elif self.type == 3:
            self.spiral.readXml(parent)
        elif self.type == 4:
            self.well.readXml(parent)

    # we're in a RollSeed here
    def calcBoundingRect(self):
        self.boundingBox = QRectF()                                             # Start with a null rectangle.size of the seed

        if self.type < 2:
            self.boundingBox = self.grid.calcBoundingRect(self.origin)          # grid (rolling = 0, stationary = 1)

        elif self.type == 2:                                                    # circle
            self.boundingBox = self.circle.calcBoundingRect(self.origin)

        elif self.type == 3:                                                    # spiral
            self.boundingBox = self.spiral.calcBoundingRect(self.origin)

        elif self.type == 4:                                                    # well
            self.boundingBox = self.well.polygon.boundingRect()
            # can be more precise by only using the list of in-well points instead of the whole well trajectory

        # normalize this rectangle
        self.boundingBox = self.boundingBox.normalized()

        # make sure that QRectF.intersected() '&' and united() '|' work as expected by giving seed a minimal size
        # this is required for the subsequent roll-steps in the template
        if self.boundingBox.width() == 0.0:
            # give it very narrow width
            self.boundingBox.setWidth(1.0e-6)

        if self.boundingBox.height() == 0.0:
            # give it very small height
            self.boundingBox.setHeight(1.0e-6)

        return self.boundingBox  # return  bounding rectangle

    def calcPointArray(self):
        length = max(len(self.pointList), 1)                                    # need 1 or more points for a valid numpy array
        self.pointArray = np.zeros(shape=(length, 3), dtype=np.float32)         # start with empty array of the right size and type

        for count, item in enumerate(self.pointList):
            self.pointArray[count, 0] = item.x()
            self.pointArray[count, 1] = item.y()
            self.pointArray[count, 2] = item.z()

    def calcPointPicture(self):
        # create painter object to draw against
        painter = QPainter(self.pointPicture)
        painter.setPen(pg.mkPen('k'))
        painter.setBrush(self.color)
        painter.drawRect(QRectF(-5, -5, 10, 10))
        painter.end()
