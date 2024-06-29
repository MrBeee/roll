"""
This module provides the Roll Grid Class
"""

from qgis.PyQt.QtCore import QLineF, QRectF
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat, toInt
from .roll_translate import RollTranslate


class RollGrid:
    # by default no name
    def __init__(self, name: str = '') -> None:
        # input variables
        self.name = name                                                        # Seed name
        self.bRoll = True                                                       # default is a rolling seed (type= 0)
        self.growList: list[RollTranslate] = []                                 # list of (max 3) grow steps

        # calculated variables
        self.salvo = QLineF()                                                   # draws line From FIRST to LAST point of FIRST grow step (quick draw)
        self.points = 0                                                         # nr of points on grid

    def calcPointList(self, origin):
        while len(self.growList) < 3:                                           # First, make sure there are three grow steps for every seed
            self.growList.insert(0, RollTranslate())

        pointList = []

        # iterate over all three ranges
        for i in range(self.growList[0].steps):
            off0 = QVector3D(origin)
            off0 += self.growList[0].increment * i

            for j in range(self.growList[1].steps):
                off1 = off0 + self.growList[1].increment * j

                for k in range(self.growList[2].steps):
                    # we now have the correct location
                    off2 = off1 + self.growList[2].increment * k

                    # append point to list
                    pointList.append(off2)

        xMin = 1.0e34
        xMax = -1.0e34
        yMin = 1.0e34
        yMax = -1.0e34
        for point in pointList:
            xMin = min(xMin, point[0])
            xMax = max(xMax, point[0])
            yMin = min(yMin, point[1])
            yMax = max(yMax, point[1])
        # print('grid seed point list - x', xMin, xMax, '- y', yMin, yMax)

        self.points = len(pointList)
        return pointList

    # we're in a RollGrid here
    def calcBoundingRect(self, origin):
        # create QRectF by applying grow steps
        pointIter = QVector3D(origin)                                           # declare new object to start iterating from
        for growStep in self.growList:                                          # iterate through all grow steps
            for _ in range(growStep.steps - 1):                                 # we have to subtract 1 here' to get from deployments to roll steps
                pointIter += growStep.increment                                 # shift the iteration point with the appropriate amount

        boundingBox = QRectF(origin.toPointF(), pointIter.toPointF())           # create a rect from origin + shifted point
        return boundingBox

    def calcSalvoLine(self, origin):
        nPoints = 0                                                             # The salvo is a line from first to last point in the last (lowest) growstep
        if self.growList:                                                       # the list is not empty
            nPoints = self.growList[-1].steps - 1                               # use the last grow step; length is 1 shorter than nr of points

        if self.growList[-1].increment == 0 or nPoints == 0:
            lineLength = QVector3D(1.0e-3, 1.0e-3, 0.0)                         # avoid a null line; give it a minimum size
        else:
            lineLength = self.growList[-1].increment * nPoints                  # calculate the line length

        endPoint = origin + lineLength                                          # set the endPoint
        self.salvo = QLineF(origin.toPointF(), endPoint.toPointF())             # this is the unshifted line

        assert self.salvo.length() > 0.0, "avoid salvo's of zero length"

        # print(f"SALV= x1:{self.salvo.x1():11.2f} y1:{self.salvo.y1():11.2f}, x2:{self.salvo.x2():11.2f} y2:{self.salvo.y2():11.2f}")

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        gridElem = doc.createElement('grid')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            gridElem.appendChild(nameElement)

        gridElem.setAttribute('roll', str(self.bRoll))
        gridElem.setAttribute('points', str(self.points))

        for grow in self.growList:
            # if grow.steps > 1:
            grow.writeXml(gridElem, doc)

        parent.appendChild(gridElem)
        return gridElem

    def readXml(self, parent: QDomNode):
        gridElem = parent.namedItem('grid').toElement()
        if not gridElem.isNull():
            nameElem = gridElem.namedItem('name').toElement()
            if not nameElem.isNull():
                self.name = nameElem.text()

            self.bRoll = gridElem.attribute('roll') == 'True'
            self.points = toInt(gridElem.attribute('points'))

            g = gridElem.firstChildElement('translate')
            if g.isNull():
                return False  # We need at least one grow step
            while not g.isNull():
                translate = RollTranslate()
                translate.readXml(g)
                self.growList.append(translate)
                g = g.nextSiblingElement('translate')

            return True

        growListElem = parent.namedItem('grow_list').toElement()
        if not growListElem.isNull():
            # print("   'grow_list' present")

            nameElem = growListElem.namedItem('name').toElement()
            if not nameElem.isNull():
                self.name = nameElem.text()

            self.bRoll = growListElem.attribute('roll') == 'True'
            self.points = toFloat(growListElem.attribute('points'))

            g = growListElem.firstChildElement('translate')
            if g.isNull():
                return False  # We need at least one grow step
            while not g.isNull():
                translate = RollTranslate()
                translate.readXml(g)
                self.growList.append(translate)
                g = g.nextSiblingElement('translate')

            return True

        return True
