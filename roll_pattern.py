import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPicture
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toFloat
from .roll_pattern_seed import RollPatternSeed
from .roll_translate import RollTranslate


class RollPattern(pg.GraphicsObject):
    # assign default name value
    def __init__(self, name: str = 'pattern-1') -> None:
        pg.GraphicsObject.__init__(self)

        self.name: str = name                                                   # pattern name
        self.seedList: list[RollPatternSeed] = []                               # list of individual grid-seeds with their own grow steps
        self.boundingBox = QRectF()                                             # calculated pattern extent
        self.pointPicture = QPicture()                                          # pre-computed QPicture object that allows paint() to run much more quickly
        self.patternPicture = QPicture()                                        # pre-computed QPicture object that allows paint() to run much more quickly

    def calcBoundingRect(self):

        for seed in self.seedList:                                              # reset all seeds
            seed.boundingBox = QRectF()

        self.boundingBox = QRectF()                                             # reset boundingBox

        for seed in self.seedList:
            seedBounds = seed.calcBoundingRect()                                # get the seed's boundingbox
            self.boundingBox |= seedBounds                                      # add it to the existing boundingBox

        self.calcPatternPicture()                                               # calculate the pattern picture to speed up painting

        return self.boundingBox

    def boundingRect(self):
        # required for painting a pg.GraphicsObject

        return self.calcBoundingRect() if self.boundingBox.isEmpty() else self.boundingBox  # earlier derived

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        patternElem = doc.createElement('pattern')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            patternElem.appendChild(nameElement)

        seedsElem = doc.createElement('seed_list')
        patternElem.appendChild(seedsElem)

        for seed in self.seedList:
            seed.writeXml(seedsElem, doc)

        parent.appendChild(patternElem)

        return patternElem

    def readXml(self, parent: QDomNode):
        nameElem = parent.namedItem('name').toElement()                         # get the name first
        if not nameElem.isNull():
            self.name = nameElem.text()

        seedsElem = parent.namedItem('seed_list').toElement()                   # get the seeds
        s = seedsElem.firstChildElement('seed')

        if s.isNull():                                                          # old pattern format with implicit single seed (for backwards compatibility)
            seed = RollPatternSeed()                                            # create new seed
            seed.origin.setX(toFloat(parent.attribute('x0')))
            seed.origin.setY(toFloat(parent.attribute('y0')))
            seed.origin.setZ(toFloat(parent.attribute('z0')))

            if parent.hasAttribute('argb'):
                seed.color = QColor(parent.attribute('argb'))
            elif parent.hasAttribute('rgb'):
                seed.color = QColor(parent.attribute('rgb'))

            growListElem = parent.namedItem('grow_list').toElement()            # create growlist
            g = growListElem.firstChildElement('translate')

            if g.isNull():
                return False  # We need at least one grow step

            seed.grid.growList = []
            while not g.isNull():
                translate = RollTranslate()                                     # create translation
                translate.readXml(g)
                seed.grid.growList.append(translate)                            # add translation to seed grid-growlist
                g = g.nextSiblingElement('translate')

            seed.grid.normalizeGrowList()

            self.seedList.append(seed)

        else:                                                                   # new pattern format
            while not s.isNull():
                seed = RollPatternSeed()                                        # create the seed object
                seed.readXml(s)                                                 # parse the xml data

                self.seedList.append(seed)                                      # append to the seed list
                s = s.nextSiblingElement('seed')                                # and get the next one

        return True

    def calcPatternPicture(self):
        # pre-computing a QPicture object allows paint() to run much more quickly,
        # rather than re-drawing the shapes every time. First create the point picture

        self.patternPicture = QPicture()
        painter = QPainter(self.patternPicture)                                 # next create the pattern picture
        painter.setPen(pg.mkPen('k'))                                           # use a black pen for borders

        for seed in self.seedList:
            self.pointPicture = QPicture()
            # first create a 'pointPicture', to build up a pattern by repeating this
            pointPainter = QPainter(self.pointPicture)                          # create painter object to draw against
            pointPainter.setPen(pg.mkPen('k'))                                  # use a black pen
            pointPainter.setBrush(seed.color)                                   # use the seed's brush
            pointPainter.drawRect(QRectF(-2, -2, 4, 4))                         # draw a 4 x 4 m square
            pointPainter.end()                                                  # ready creating 4 x 4 m square, that can be accessed through self.pointPicture

            for origin in seed.grid.iterPoints(seed.origin):
                painter.drawPicture(origin.toPointF(), self.pointPicture)       # paint seed picture

        painter.end()

    def paint(self, painter, *_):                                               # used in wizard
        # the paint function actually is: paint(self, painter, option, widget) but option & widget are not being used
        painter.drawPicture(0, 0, self.patternPicture)

    def calcPatternPointArrays(self):
        # Calculate arrays directly for kx-ky response plots without building intermediate Python lists.

        totalPoints = 0
        for seed in self.seedList:
            growList = seed.grid.growList
            totalPoints += growList[0].steps * growList[1].steps * growList[2].steps

        patternPointsX = np.empty(totalPoints, dtype=np.float32)
        patternPointsY = np.empty(totalPoints, dtype=np.float32)

        index = 0
        for seed in self.seedList:
            for origin in seed.grid.iterPoints(seed.origin):
                patternPointsX[index] = origin.x()
                patternPointsY[index] = origin.y()
                index += 1

        return (patternPointsX, patternPointsY)

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy
