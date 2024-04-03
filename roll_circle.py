"""
This module provides the Roll Circle Seed
"""
import math

from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollCircle:
    # by default no name
    def __init__(self, name: str = '') -> None:
        # input variables
        self.name = name                                                        # Seed name
        self.radius = 1000.0                                                    # circle radius
        self.azi0 = 0.0                                                         # start angle
        self.dist = 25.0                                                        # point interval along the circle

        # calculated variables
        self.points = 251                                                       # corresponding nr of points on circle

    def calcPointList(self, origin):
        r = self.radius
        p = self.azi0 * math.pi / 180.0
        d = self.dist
        n = self.points
        o = origin
        q = d / r

        # points to derive cdp coverage from
        pointList = []
        for i in range(int(n)):
            # current angle
            a = i * q + p
            x = math.cos(a) * r
            y = math.sin(a) * r
            v = QVector3D(x, y, 0)
            v += o
            pointList.append(v)

        return pointList

    def calcNoPoints(self):
        r = self.radius
        s = abs(self.dist)
        n = 1
        if s != 0:
            n = max(int(abs(math.floor(2 * math.pi * r / s))), 1)
        self.points = int(n)
        return n

    # we're in RollCircle here
    def calcBoundingRect(self, origin):
        center = origin.toPointF()
        offset = QPointF(self.radius, self.radius)
        boundingBox = QRectF(center - offset, center + offset)
        return boundingBox

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        circleElem = doc.createElement('circle')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            circleElem.appendChild(nameElement)

        circleElem.setAttribute('radius', str(self.radius))
        circleElem.setAttribute('azi0', str(self.azi0))
        circleElem.setAttribute('dist', str(self.dist))
        circleElem.setAttribute('points', str(self.points))

        parent.appendChild(circleElem)
        return circleElem

    def readXml(self, parent: QDomNode):
        circleElem = parent.namedItem('circle').toElement()
        if circleElem.isNull():
            return False

        nameElem = circleElem.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.radius = toFloat(circleElem.attribute('radius'))
        self.azi0 = toFloat(circleElem.attribute('azi0'))
        self.dist = toFloat(circleElem.attribute('dist'))
        self.points = toFloat(circleElem.attribute('points'))

        return True
