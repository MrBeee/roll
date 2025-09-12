import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPicture, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat
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

        if self.boundingBox.isEmpty():
            return self.calcBoundingRect()
        else:
            return self.boundingBox                                             # earlier derived

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

    def writeXmlOld(self, parent: QDomNode, doc: QDomDocument):
        seedElem = doc.createElement('pattern')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            seedElem.appendChild(nameElement)

        # seedElem.setAttribute('x0', str(self.origin.x()))
        # seedElem.setAttribute('y0', str(self.origin.y()))
        # seedElem.setAttribute('z0', str(self.origin.z()))
        # seedElem.setAttribute('argb', str(self.color.name(QColor.NameFormat.HexArgb)))
        growListElem = doc.createElement('grow_list')
        seedElem.appendChild(growListElem)

        for grow in self.growList:
            grow.writeXml(growListElem, doc)

        parent.appendChild(seedElem)

        return seedElem

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

            while not g.isNull():
                translate = RollTranslate()                                     # create translation
                translate.readXml(g)
                seed.grid.growList.append(translate)                            # add translation to seed grid-growlist
                g = g.nextSiblingElement('translate')

            self.seedList.append(seed)

        else:                                                                   # new pattern format
            while not s.isNull():
                seed = RollPatternSeed()                                        # create the seed object
                seed.readXml(s)                                                 # parse the xml data

                self.seedList.append(seed)                                      # append to the seed list
                s = s.nextSiblingElement('seed')                                # and get the next one

        return True

    def readXmlOld(self, parent: QDomNode):
        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        # self.origin.setX(toFloat(parent.attribute('x0')))
        # self.origin.setY(toFloat(parent.attribute('y0')))
        # self.origin.setZ(toFloat(parent.attribute('z0')))
        # if parent.hasAttribute('argb'):
        #     self.color = QColor(parent.attribute('argb'))
        # elif parent.hasAttribute('rgb'):
        #     self.color = QColor(parent.attribute('rgb'))

        growListElem = parent.namedItem('grow_list').toElement()
        g = growListElem.firstChildElement('translate')

        if g.isNull():
            return False  # We need at least one grow step

        while not g.isNull():
            translate = RollTranslate()
            translate.readXml(g)
            self.growList.append(translate)
            g = g.nextSiblingElement('translate')

    def calcPatternPicture(self):
        # pre-computing a QPicture object allows paint() to run much more quickly,
        # rather than re-drawing the shapes every time. First create the point picture

        painter = QPainter(self.patternPicture)                                 # next create the pattern picture
        painter.setPen(pg.mkPen('k'))                                           # use a black pen for borders

        for seed in self.seedList:
            # first create a 'pointPicture', to build up a pattern by repeating this
            pointPainter = QPainter(self.pointPicture)                          # create painter object to draw against
            pointPainter.setPen(pg.mkPen('k'))                                  # use a black pen
            pointPainter.setBrush(seed.color)                                   # use the seed's brush
            pointPainter.drawRect(QRectF(-2, -2, 4, 4))                         # draw a 4 x 4 m square
            pointPainter.end()                                                  # ready creating 4 x 4 m square, that can be accessed through self.pointPicture

            length = len(seed.grid.growList)                                    # how deep is the grow list ?
            # assert length == 3, 'there always need to be 3 roll steps / grow steps'

            if length == 0:
                painter.drawLine(0, -7.5, 0, 7.5)
                painter.drawLine(-7.5, 0, 7.5, 0)
            elif length == 1:
                for i in range(seed.grid.growList[0].steps):                    # iterate over 1st step
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct location
                    origin = off0 + seed.origin                                 # we now have the correct location
                    painter.drawPicture(origin.toPointF(), self.pointPicture)   # paint seed point picture

            elif length == 2:
                for i in range(seed.grid.growList[0].steps):                    # iterate over 1st step
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct location

                    for j in range(seed.grid.growList[1].steps):
                        off1 = off0 + seed.grid.growList[1].increment * j       # we now have the correct location

                        origin = off1 + seed.origin                             # start at templateOffset and add seed's origin
                        painter.drawPicture(origin.toPointF(), self.pointPicture)   # paint seed picture

            elif length == 3:
                for i in range(seed.grid.growList[0].steps):
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct location

                    for j in range(seed.grid.growList[1].steps):
                        off1 = off0 + seed.grid.growList[1].increment * j       # we now have the correct location

                        for k in range(seed.grid.growList[2].steps):
                            off2 = off1 + seed.grid.growList[2].increment * k   # we now have the correct location

                            origin = off2 + seed.origin                         # start at templateOffset and add seed's origin
                            painter.drawPicture(origin.toPointF(), self.pointPicture)   # paint seed picture
            else:
                # do something recursively; not implemented yet
                raise NotImplementedError('More than three grow steps currently not allowed.')

        painter.end()

    def paint(self, painter, *_):                                               # used in wizard
        # the paint function actually is: paint(self, painter, option, widget) but option & widget are not being used
        painter.drawPicture(0, 0, self.patternPicture)

    def calcPatternPointLists(self):
        # Get two lists of all x- and y-locations; only used in calcPatternPointArrays()
        # todo: merge calcPatternPointLists() into calcPatternPointArrays()

        patternPointsX = []
        patternPointsY = []

        for seed in self.seedList:
            length = len(seed.grid.growList)                                    # how deep is the grow list ?

            assert length == 3, 'there always need to be 3 roll steps / grow steps'

            if length == 0:
                patternPointsX.append(0.0)                                      # add to the x-list
                patternPointsY.append(0.0)                                      # add to the y-list

            elif length == 1:
                for i in range(seed.grid.growList[0].steps):                    # iterate over 1st step
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct offset
                    origin = off0 + seed.origin                                 # we now have the correct location
                    patternPointsX.append(origin.x())                           # add to the x-list
                    patternPointsY.append(origin.y())                           # add to the y-list

            elif length == 2:
                for i in range(seed.grid.growList[0].steps):                    # iterate over 1st step
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct offset
                    for j in range(seed.grid.growList[1].steps):                # we now have the correct location
                        off1 = off0 + seed.grid.growList[1].increment * j       # iterate over 2nd step
                        origin = off1 + seed.origin                             # start at offset and add seed's origin
                        patternPointsX.append(origin.x())                       # add to the x-list
                        patternPointsY.append(origin.y())                       # add to the y-list

            elif length == 3:
                for i in range(seed.grid.growList[0].steps):
                    off0 = QVector3D(0.0, 0.0, 0.0)                             # always start at (0, 0, 0)
                    off0 += seed.grid.growList[0].increment * i                 # we now have the correct location
                    for j in range(seed.grid.growList[1].steps):
                        off1 = off0 + seed.grid.growList[1].increment * j       # we now have the correct location
                        for k in range(seed.grid.growList[2].steps):
                            off2 = off1 + seed.grid.growList[2].increment * k   # we now have the correct location
                            origin = off2 + seed.origin                         # start at templateOffset and add seed's origin
                            patternPointsX.append(origin.x())                   # add to the x-list
                            patternPointsY.append(origin.y())                   # add to the y-list

        return (patternPointsX, patternPointsY)

    def calcPatternPointArrays(self):
        # this uses calcPatternPointLists() to convert a list into an ndarray
        # it is only used to calculate the kxky response of a pattern in 'Patterns' and the 'Analysis -> Kx-Ky Stack' tab

        x, y = self.calcPatternPointLists()
        return (np.array(x, dtype=np.float32), np.array(y, dtype=np.float32))

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy
