# roll_seed.py
import weakref

"""
This module provides Seed Class, at the core of the placement of src & rec points in a survey area
"""

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPicture, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toFloat
from .enums_and_int_flags import SeedType
from .roll_circle import RollCircle
from .roll_grid import RollGrid
from .roll_spiral import RollSpiral
from .roll_translate import RollTranslate
from .roll_well import RollWell


class RollSeed:
    # assign default name value
    def __init__(self, name: str = 'seed-1') -> None:
        # input variables
        self.name = name                                                        # Seed name
        self.origin = QVector3D()                                               # Seed origin
        self.bSource = False                                                    # 'True' if this is a source point seed (receiver = 'False')
        self.bAzimuth = False                                                   # 'True' if this seed has a pattern in direction of line direction
        self.patternNo = -1                                                     # Pattern index serialized in survey file (-1 if no pattern is used)
        self._survey_ref = None                                                 # weakref to RollSurvey

        self.color = QColor()                                                   # color of seed to discriminate different sources / receivers

        # seed subtypes
        self.type = SeedType.rollingGrid                                        # Seed type 0 = rolling [default], 1 = fixed, 2 = circle, 3 = spiral, 4 = well
        self.grid = RollGrid()
        self.circle = RollCircle()
        self.spiral = RollSpiral()
        self.well = RollWell()

        # calculated variables
        self.boundingBox = QRectF()                                             # Constructs a null rectangle.size of the seed after all grow steps have been done
        # self.salvo = QLineF()                                                 # draws line From FIRST to LAST point of FIRST grow step (quick draw)
        self.pointList = []                                                     # point list for non-grid seeds to display points and to derive cdp coverage from
        # todo: need to get rid of self.pointList at some point !
        self.pointArray = None                                                  # numpy array to derive cdp coverage from
        self.blockBorder = QRectF()                                             # inherited from seed -> template -> block's srcBorder / recBorder depending on seed type

        self.pointPicture = None                                                # calculated on the fly; with marine surveys the nr of seeds > 100,000, and only a few are rendered at the same time
        self.patternPicture = None                                              # calculated on the fly; with marine surveys the nr of seeds > 100,000, and only a few are rendered at the same time
        # note, in the end, there shall ALWAYS be a pointPicture defined, but NOT ALWAYS a patternPicture, depending on seedType, etc

        self.rendered = False                                                   # prevent painting stationary seeds multiple times due to roll-along of other seeds

    def setSurvey(self, survey):
        self._survey_ref = weakref.ref(survey) if survey is not None else None

    @property
    def survey(self):
        return self._survey_ref() if self._survey_ref else None                 # return the referenced survey, or None if not set

    @property
    def pattern(self):
        if self.patternNo < 0:
            return None
        survey = self.survey
        return survey.getPattern(self.patternNo) if survey else None            # return the pattern object from the survey, or None if not found

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

        # todo: solve the following issue:
        # **somewhere** in the code 'self.type' becomes an int instead of a SeedType
        # most likely this occurs in the parameter handling
        # workaround: first cast the int to a SeedType, before taking its value attribute

        self.type = SeedType(self.type)                                         # ugly

        seedElem.setAttribute('typno', str(self.type.value))                    # make sure we save the **value** of the IntFlag (i.e. an integer number)
        seedElem.setAttribute('argb', str(self.color.name(QColor.NameFormat.HexArgb)))

        if self.type < SeedType.circle:
            self.grid.writeXml(seedElem, doc)

        elif self.type == SeedType.circle:
            self.circle.writeXml(seedElem, doc)

        elif self.type == SeedType.spiral:
            self.spiral.writeXml(seedElem, doc)

        elif self.type == SeedType.well:
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

        self.type = SeedType(int(parent.attribute('typno')))                    # convert string -> int -> SeedType

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

        if self.type < SeedType.circle:
            self.grid.readXml(parent)

        elif self.type == SeedType.circle:
            self.circle.readXml(parent)

        elif self.type == SeedType.spiral:
            self.spiral.readXml(parent)

        elif self.type == SeedType.well:
            self.well.readXml(parent)

    def calcBoundingRect(self):                                                 # Note: we're in a RollSeed here
        self.boundingBox = QRectF()                                             # Start with a null rectangle.size of the seed

        if self.type < SeedType.circle:
            self.boundingBox = self.grid.calcBoundingRect(self.origin)          # grid (rolling = 0, stationary = 1)

        elif self.type == SeedType.circle:
            self.boundingBox = self.circle.calcBoundingRect(self.origin)

        elif self.type == SeedType.spiral:
            self.boundingBox = self.spiral.calcBoundingRect(self.origin)

        elif self.type == SeedType.well:
            self.boundingBox = self.well.calcBoundingRect()
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

        if self.type < SeedType.circle:                                         # for grid based seeds, the point array can be calculated directly from the grow steps
            while len(self.grid.growList) < 3:                                  # First, make sure there are always three grow steps for every seed
                self.grid.growList.insert(0, RollTranslate())

            nSteps = 1
            for growStep in self.grid.growList:                                 # iterate through all grow steps
                nSteps *= growStep.steps                                        # multiply seed's shots at each level

            self.pointArray = np.zeros(shape=(nSteps, 3), dtype=np.float32)     # start with empty array of the right size and type

            # iterate over all three ranges, update counter for each new point
            count = 0
            for i in range(self.grid.growList[0].steps):
                off0 = QVector3D(self.origin)
                off0 += self.grid.growList[0].increment * i

                for j in range(self.grid.growList[1].steps):
                    off1 = off0 + self.grid.growList[1].increment * j

                    for k in range(self.grid.growList[2].steps):
                        off2 = off1 + self.grid.growList[2].increment * k

                        self.pointArray[count, 0] = off2.x()
                        self.pointArray[count, 1] = off2.y()
                        self.pointArray[count, 2] = off2.z()
                        count += 1

        else:  # for all other seeds (circles, spirals and wells), they can be derived from the pointList, needed to plot individual points

            length = max(len(self.pointList), 1)                                    # need 1 or more points for a valid numpy array
            self.pointArray = np.zeros(shape=(length, 3), dtype=np.float32)         # start with empty array of the right size and type

            for count, item in enumerate(self.pointList):
                self.pointArray[count, 0] = item.x()
                self.pointArray[count, 1] = item.y()
                self.pointArray[count, 2] = item.z()

    def getPointPicture(self):
        if self.pointPicture is None:

            # create one first, and then prepare the square
            self.pointPicture = QPicture()
            painter = QPainter(self.pointPicture)
            painter.setPen(pg.mkPen('k'))
            painter.setBrush(self.color)
            painter.drawRect(QRectF(-5, -5, 10, 10))
            painter.end()
        return self.pointPicture

    def calcPointPicture(self):
        # effectively superseded by getPointPicture(self)

        # create painter object to draw against
        painter = QPainter(self.pointPicture)
        painter.setPen(pg.mkPen('k'))
        painter.setBrush(self.color)
        painter.drawRect(QRectF(-5, -5, 10, 10))
        painter.end()
