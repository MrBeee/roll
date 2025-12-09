"""
This module provides the BinGrid Class to define binning area and binsize
"""
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QTransform
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toFloat, toInt


class RollBinGrid:
    # assign default values
    def __init__(self) -> None:
        # local grid
        self.fold: int = -1                                                     # -1.0 to catch errors
        self.binSize = QPointF(-1.0, -1.0)                                      # -1.0 to catch errors
        self.binShift = QPointF(-1.0, -1.0)                                     # -1.0 to catch errors
        self.stakeOrig = QPointF(-1.0, -1.0)                                    # -1.0 to catch errors
        self.stakeSize = QPointF(-1.0, -1.0)                                    # -1.0 to catch errors

        # global grid
        self.orig = QPointF(0.0, 0.0)
        self.scale = QPointF(1.0, 1.0)
        self.angle = 0.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        gridElem = doc.createElement('grid')

        # local grid parameters
        localElem = doc.createElement('local')

        localElem.setAttribute('fold', str(self.fold))

        localElem.setAttribute('x0', str(self.binShift.x()))
        localElem.setAttribute('y0', str(self.binShift.y()))

        localElem.setAttribute('dx', str(self.binSize.x()))
        localElem.setAttribute('dy', str(self.binSize.y()))

        localElem.setAttribute('s0', str(self.stakeOrig.x()))                   # s0 = stake number at grid origin
        localElem.setAttribute('l0', str(self.stakeOrig.y()))                   # l0 = line number at grid origin

        localElem.setAttribute('ds', str(self.stakeSize.x()))                   # ds = stake number interval [m]
        localElem.setAttribute('dl', str(self.stakeSize.y()))                   # dl = line number interval [m]

        # global grid parameters
        globalElem = doc.createElement('global')

        globalElem.setAttribute('x0', str(self.orig.x()))
        globalElem.setAttribute('y0', str(self.orig.y()))

        globalElem.setAttribute('azi', str(self.angle))

        globalElem.setAttribute('sy', str(self.scale.y()))
        globalElem.setAttribute('sx', str(self.scale.x()))

        t1 = QTransform()
        t1.translate(self.orig.x(), self.orig.y())
        t1.rotate(self.angle)
        t1.scale(self.scale.x(), self.scale.y())
        # inverted_transform, invertable = transform.inverted()
        t2, _ = t1.inverted()

        s1 = f'Forward transform: A0={t1.m31():.3f}, B0={t1.m32():.3f}, A1={t1.m11():.6f}, B1={t1.m12():.6f}, A2={t1.m21():.6f}, B2={t1.m22():.6f}'
        s2 = f'Inverse transform: A0={t2.m31():.3f}, B0={t2.m32():.3f}, A1={t2.m11():.6f}, B1={t2.m12():.6f}, A2={t2.m21():.6f}, B2={t2.m22():.6f}'
        s3 = 'See EPSG:9624 (https://epsg.io/9624-method) for the affine parametric transform definition'

        comment1 = doc.createComment(s1)
        comment2 = doc.createComment(s2)
        comment3 = doc.createComment(s3)

        gridElem.appendChild(localElem)
        gridElem.appendChild(globalElem)
        gridElem.appendChild(comment1)
        gridElem.appendChild(comment2)
        gridElem.appendChild(comment3)

        parent.appendChild(gridElem)

        return gridElem

    def readXml(self, parent: QDomNode):

        localElem = parent.namedItem('local').toElement()
        if localElem.isNull():
            return False

        self.fold = toInt(localElem.attribute('fold'))

        self.binSize.setX(toFloat(localElem.attribute('dx')))
        self.binSize.setY(toFloat(localElem.attribute('dy')))

        self.binShift.setX(toFloat(localElem.attribute('x0')))
        self.binShift.setY(toFloat(localElem.attribute('y0')))

        # default (stake, line) origin = (1000, 1000)
        self.stakeOrig.setX(toFloat(localElem.attribute('s0'), 1000.0))
        self.stakeOrig.setY(toFloat(localElem.attribute('l0'), 1000.0))

        # if no stake number intervals are given; default to bin interval
        self.stakeSize.setX(toFloat(localElem.attribute('ds'), self.binSize.x()))
        self.stakeSize.setY(toFloat(localElem.attribute('dl'), self.binSize.y()))

        globalElem = parent.namedItem('global').toElement()
        if globalElem.isNull():
            return False

        self.orig.setX(toFloat(globalElem.attribute('x0')))
        self.orig.setY(toFloat(globalElem.attribute('y0')))

        self.angle = toFloat(globalElem.attribute('azi'))

        self.scale.setX(toFloat(globalElem.attribute('sx')))
        self.scale.setY(toFloat(globalElem.attribute('sy')))

        return True
