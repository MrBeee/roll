import pyqtgraph as pg
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPicture, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat
from .roll_translate import RollTranslate


class RollPattern(pg.GraphicsObject):
    # assign default name value
    def __init__(self, name: str = 'pattern-1') -> None:
        pg.GraphicsObject.__init__(self)

        # pattern name
        self.name: str = name
        # seed origin
        self.origin = QVector3D()
        # list of (max 3) grow steps
        self.growList: list[RollTranslate] = []
        # color of seed to discriminate different sources / receivers
        self.color = QColor()

        # calculated pattern extent
        self.boundingBox = QRectF()
        # pre-computing a QPicture object allows paint() to run much more quickly
        self.pointPicture = QPicture()
        # pre-computing a QPicture object allows paint() to run much more quickly
        self.patternPicture = QPicture()

    def resetBoundingRect(self):
        # Constructs a null rectangle.size of the seed
        self.boundingBox = QRectF()

    def calcBoundingRect(self):
        # declare new object to start iterating from
        pointIter = QVector3D(self.origin)
        for growStep in self.growList:                                          # iterate through all grow steps
            # we have to subtract 1 here' to get from deployments to roll steps
            for _ in range(growStep.steps - 1):
                # shift the iteration point with the appropriate amount
                pointIter += growStep.increment

        # create a rect from origin + shifted point
        self.boundingBox = QRectF(self.origin.toPointF(), pointIter.toPointF())
        # normalize this rectangle
        self.boundingBox = self.boundingBox.normalized()

        # make sure that QRectF.intersected() '&' and united() '|' work as expected by giving seed a minimal size
        if self.boundingBox.width() == 0.0:
            # give it very narrow width
            self.boundingBox.setWidth(1.0e-6)
        if self.boundingBox.height() == 0.0:
            # give it very small height
            self.boundingBox.setHeight(1.0e-6)

        self.calcPatternPicture()

        return self.boundingBox  # return  bounding rectangle

    # required for painting a pg.GraphicsObject
    def boundingRect(self):
        if self.boundingBox.isEmpty():
            return self.calcBoundingRect()
        else:
            # EARLIER derived
            return self.boundingBox

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        seedElem = doc.createElement('pattern')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            seedElem.appendChild(nameElement)

        seedElem.setAttribute('x0', str(self.origin.x()))
        seedElem.setAttribute('y0', str(self.origin.y()))
        seedElem.setAttribute('z0', str(self.origin.z()))
        seedElem.setAttribute('argb', str(self.color.name(QColor.HexArgb)))
        growListElem = doc.createElement('grow_list')
        seedElem.appendChild(growListElem)

        for grow in self.growList:
            grow.writeXml(growListElem, doc)

        parent.appendChild(seedElem)

        return seedElem

    def readXml(self, parent: QDomNode):
        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.origin.setX(toFloat(parent.attribute('x0')))
        self.origin.setY(toFloat(parent.attribute('y0')))
        self.origin.setZ(toFloat(parent.attribute('z0')))
        if parent.hasAttribute('argb'):
            self.color = QColor(parent.attribute('argb'))
        elif parent.hasAttribute('rgb'):
            self.color = QColor(parent.attribute('rgb'))

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
        # create painter object to draw against
        painter = QPainter(self.pointPicture)
        painter.setPen(pg.mkPen('k'))
        painter.setBrush(self.color)
        painter.drawRect(QRectF(-2, -2, 4, 4))
        painter.end()

        # next create the pattern picture
        painter = QPainter(self.patternPicture)
        # use a black pen for borders
        painter.setPen(pg.mkPen('k'))
        # blue / red
        painter.setBrush(self.color)

        # how deep is the grow list ?
        length = len(self.growList)

        if length == 0:
            painter.drawLine(0, -7.5, 0, 7.5)
            painter.drawLine(-7.5, 0, 7.5, 0)
        elif length == 1:
            # iterate over 1st step
            for i in range(self.growList[0].steps):
                # always start at (0, 0, 0)
                off0 = QVector3D(0.0, 0.0, 0.0)
                # we now have the correct location
                off0 += self.growList[0].increment * i

                # we now have the correct location
                origin = off0 + self.origin
                # paint seed point picture
                painter.drawPicture(origin.toPointF(), self.pointPicture)

        elif length == 2:
            # iterate over 1st step
            for i in range(self.growList[0].steps):
                # always start at (0, 0, 0)
                off0 = QVector3D(0.0, 0.0, 0.0)
                # we now have the correct location
                off0 += self.growList[0].increment * i

                for j in range(self.growList[1].steps):
                    # we now have the correct location
                    off1 = off0 + self.growList[1].increment * j

                    # start at templateOffset and add seed's origin
                    origin = off1 + self.origin
                    # paint seed picture
                    painter.drawPicture(origin.toPointF(), self.pointPicture)

        elif length == 3:
            for i in range(self.growList[0].steps):
                # always start at (0, 0, 0)
                off0 = QVector3D(0.0, 0.0, 0.0)
                # we now have the correct location
                off0 += self.growList[0].increment * i

                for j in range(self.growList[1].steps):
                    # we now have the correct location
                    off1 = off0 + self.growList[1].increment * j

                    for k in range(self.growList[2].steps):
                        # we now have the correct location
                        off2 = off1 + self.growList[2].increment * k

                        # start at templateOffset and add seed's origin
                        origin = off2 + self.origin
                        # paint seed picture
                        painter.drawPicture(origin.toPointF(), self.pointPicture)
        else:
            # do something recursively; not  implemented yet
            raise NotImplementedError('More than three grow steps currently not allowed.')
        painter.end()

    def paint(self, painter, *_):                                               # used in wizard
        # the paint function actually is: paint(self, painter, option, widget) but option & widget are not being used
        painter.drawPicture(0, 0, self.patternPicture)
