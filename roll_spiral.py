"""
This module provides the Roll Spiral Seed
"""
import math

import numpy as np
from qgis.PyQt.QtCore import QPointF, QRectF
from qgis.PyQt.QtGui import QPainterPath, QTransform, QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat, toInt


class RollSpiral:
    # by default no name
    def __init__(self, name: str = '') -> None:
        # input variables
        # Seed name
        self.name = name
        self.radMin = 200.0
        self.radMax = 1000.0
        self.radInc = 200.0
        self.azi0 = 0.0
        self.dist = 50.0
        self.points = 302
        # calculated variables
        # spiral drawn when LOD is low
        self.path = QPainterPath()

    def derivative(self, dAngle, a):
        # Note :  Our spiral is defined by R = a x (theta - theta0) (theta in radians). Therefore:
        #    a = m_fDeltaR / twopi  (increase in radius over a full 360 degrees)
        # If we write "theta" as "p", the following formula gives the total arc length "s"
        #
        #    s  = 0.5 * a * [t * sqrt(1+t*t) + ln(t + sqrt(1+t*t))]
        #
        # See also: https://en.wikipedia.org/wiki/Archimedean_spiral
        # therefore ds / dt becomes
        #
        #    ds/dt = 0.5 * a * [sqrt(1+t*t) + t*t/sqrt(1+t*t) + (1+t/sqrt(1+t*t))/(t+sqrt(1+t*t))]

        rt = math.sqrt(1.0 + dAngle * dAngle)
        return 0.5 * a * (rt + dAngle * dAngle / rt + (1.0 + dAngle / rt) / (dAngle + rt))

    def angle(self, dArcLength, a):
        # provide initial estimate for phi
        # p stands for phi
        pEst = math.sqrt(2.0 * dArcLength / a)

        # max 4 iterations to improve phi
        for _ in range(4):
            sEst = self.arcLength(pEst, a)
            sErr = sEst - dArcLength

            if sErr < 0.05:
                # error is less than 5 cm, time to quit....
                break

            dSdP = self.derivative(pEst, a)
            pErr = sErr / dSdP
            # new estimate for phi
            pEst = pEst - pErr

        return pEst

    def arcLength(self, angle, a):
        rt = math.sqrt(1.0 + angle * angle)
        return 0.5 * a * (angle * rt + math.log(angle + rt))

    def calcNoPoints(self):
        r1 = self.radMin
        r2 = self.radMax
        dr = self.radInc
        d = abs(self.dist)

        n = 1
        if dr > 0:
            c = dr / (2 * math.pi)

            # get the angle for the minimum radius
            thetaMin = r1 / c
            # get the angle for the maximum radius
            thetaMax = r2 / c

            # get the arc length for minimum radius
            sMin = self.arcLength(thetaMin, c)
            # get the arc length for maximum radius
            sMax = self.arcLength(thetaMax, c)

            # get the total usable part of the arc
            sDif = sMax - sMin
            # get the nr. of shots that fit in it
            n = math.floor(sDif / d)
        self.points = n
        return n

    def calcPointList(self, origin):
        r1 = self.radMin
        dr = self.radInc
        # constant applied to radius
        c = dr / (2.0 * math.pi)
        p = self.azi0 * math.pi / 180.0
        d = self.dist
        # sign; create a [-1.0 or +1.0] value
        s = math.copysign(1.0, d)
        # continue with absolute value of step interval
        d = abs(d)
        n = self.points
        o = origin

        # get the angle for the minimum radius
        thetaMin = r1 / c
        # get the arc length for minimum radius
        sMin = self.arcLength(thetaMin, c)

        # points to derive cdp coverage from
        pointList = []
        for i in range(n):
            # current distance along spiral
            sCur = sMin + i * d
            # current corresponding angle
            pCur = self.angle(sCur, c)

            # the radius that belongs to this angle
            r = pCur * c
            # angle corrected for the start angle
            a = pCur + (p * s)

            x = math.cos(a) * r
            # applying a negative sign to the y-axis; we mirrow along this axis
            y = math.sin(a * s) * r
            # create a vector
            v = QVector3D(x, y, 0)
            # offset it by the origin
            v += o
            # append point to list
            pointList.append(v)

        return pointList

    # we're in a RollSpiral here
    def calcBoundingRect(self, origin):
        center = origin.toPointF()
        offset = QPointF(self.radMax, self.radMax)
        boundingBox = QRectF(center - offset, center + offset)
        return boundingBox

    def ZELineIntersection(self, m1, b1, m2, b2):
        # See: https://github.com/ZevEisenberg/ZESpiral and:
        # See: https://github.com/ZevEisenberg/ZESpiral/issues/1
        if m1 == m2:                                                            # lines are parallel
            return (False, 0, 0)

        X = (b2 - b1) / (m1 - m2)
        Y = m1 * X + b1
        return (True, X, Y)

    def createSpiralNew2(self, center, startRadius, spacePerLoop, startTheta, endTheta, thetaStep, clockWise=False):
        # See: https://github.com/ZevEisenberg/ZESpiral and:
        # See: https://github.com/ZevEisenberg/ZESpiral/issues/1

        # change relative to createSpiralNew: use QTransform to do the required translation and rotation

        # define sign for y-axis; needed for clockwise spirals
        s = -1 if clockWise is True else 1

        # transform to translate to center and rotate by startTheta
        t1 = QTransform()
        t1.translate(center.x(), center.y())
        t1.rotateRadians(startTheta)

        oldTheta = 0.0
        newTheta = 0.0

        oldR = startRadius
        newR = startRadius

        # max floating point value on a system
        oldSlope = np.finfo(np.float64).max
        newSlope = oldSlope

        self.path = QPainterPath()

        x = oldR * math.cos(oldTheta)
        # s has vertical mirror function
        y = s * oldR * math.sin(oldTheta)
        newPnt = QPointF(x, y)
        newPnt = t1.map(newPnt)
        self.path.moveTo(newPnt)

        firstSlope = True
        while oldTheta < endTheta - thetaStep:                                  # add another phase step
            # save old value
            oldTheta = newTheta
            # add new increment; prevent going beyond end value
            newTheta += min(thetaStep, endTheta - oldTheta)

            oldR = newR
            newR = startRadius + spacePerLoop * newTheta

            x = newR * math.cos(newTheta)
            y = s * newR * math.sin(newTheta)
            newPnt = QPointF(x, y)
            newPnt = t1.map(newPnt)

            # Slope calculation done with the formula:
            # (spacePerLoop * sinTheta + (startRadius + bTheta) * cosTheta) \
            #   / (spacePerLoop * cosTheta - (startRadius + bTheta) * sinTheta)

            aPlusBTheta = startRadius + spacePerLoop * newTheta

            if firstSlope:
                oldSlope = (spacePerLoop * math.sin(oldTheta) + aPlusBTheta * math.cos(oldTheta)) / (spacePerLoop * math.cos(oldTheta) - aPlusBTheta * math.sin(oldTheta))
                firstSlope = False
            else:
                oldSlope = newSlope

            newSlope = (spacePerLoop * math.sin(newTheta) + aPlusBTheta * math.cos(newTheta)) / (spacePerLoop * math.cos(newTheta) - aPlusBTheta * math.sin(newTheta))

            oldIntercept = -(oldSlope * oldR * math.cos(oldTheta) - oldR * math.sin(oldTheta))
            newIntercept = -(newSlope * newR * math.cos(newTheta) - newR * math.sin(newTheta))

            ok, outX, outY = self.ZELineIntersection(oldSlope, oldIntercept, newSlope, newIntercept)

            if ok:
                x = outX
                y = s * outY
                ctrlPnt = QPointF(x, y)
                ctrlPnt = t1.map(ctrlPnt)

                self.path.quadTo(ctrlPnt, newPnt)
            else:
                raise ValueError('These lines should never be parallel.')

    def createSpiralNew(self, center, startRadius, spacePerLoop, startTheta, endTheta, thetaStep, clockWise=False):
        # See: https://github.com/ZevEisenberg/ZESpiral and:
        # See: https://github.com/ZevEisenberg/ZESpiral/issues/1

        # define sign for y-axis; needed for clockwise spirals
        s = -1 if clockWise is True else 1
        cosT = math.cos(startTheta)
        sinT = math.sin(startTheta)

        oldTheta = 0.0
        newTheta = 0.0

        oldR = startRadius
        newR = startRadius

        # max floating point value on a system
        oldSlope = np.finfo(np.float64).max
        newSlope = oldSlope

        self.path = QPainterPath()

        x = oldR * math.cos(oldTheta)
        # s has vertical mirror function
        y = s * oldR * math.sin(oldTheta)
        # apply rotation by startTheta around center
        x1 = center.x() + cosT * x - sinT * y
        y1 = center.y() + sinT * x + cosT * y
        newPoint = QPointF(x1, y1)

        self.path.moveTo(newPoint)

        firstSlope = True
        while oldTheta < endTheta - thetaStep:                                  # add another phase step
            # save old value
            oldTheta = newTheta
            # add new increment; prevent going beyond end value
            newTheta += min(thetaStep, endTheta - oldTheta)

            oldR = newR
            newR = startRadius + spacePerLoop * newTheta

            x = newR * math.cos(newTheta)
            y = s * newR * math.sin(newTheta)
            # apply rotation by startTheta around center
            x1 = center.x() + cosT * x - sinT * y
            y1 = center.y() + sinT * x + cosT * y
            newPoint = QPointF(x1, y1)

            # Slope calculation done with the formula:
            # (spacePerLoop * sinTheta + (startRadius + bTheta) * cosTheta) \
            #   / (spacePerLoop * cosTheta - (startRadius + bTheta) * sinTheta)

            aPlusBTheta = startRadius + spacePerLoop * newTheta

            if firstSlope:
                oldSlope = (spacePerLoop * math.sin(oldTheta) + aPlusBTheta * math.cos(oldTheta)) / (spacePerLoop * math.cos(oldTheta) - aPlusBTheta * math.sin(oldTheta))
                firstSlope = False
            else:
                oldSlope = newSlope

            newSlope = (spacePerLoop * math.sin(newTheta) + aPlusBTheta * math.cos(newTheta)) / (spacePerLoop * math.cos(newTheta) - aPlusBTheta * math.sin(newTheta))

            oldIntercept = -(oldSlope * oldR * math.cos(oldTheta) - oldR * math.sin(oldTheta))
            newIntercept = -(newSlope * newR * math.cos(newTheta) - newR * math.sin(newTheta))

            ok, outX, outY = self.ZELineIntersection(oldSlope, oldIntercept, newSlope, newIntercept)

            if ok:
                x = outX
                y = s * outY
                # apply rotation by startTheta around center
                x1 = center.x() + cosT * x - sinT * y
                y1 = center.y() + sinT * x + cosT * y

                controlPoint = QPointF(x1, y1)
                self.path.quadTo(controlPoint, newPoint)
            else:
                raise ValueError('These lines should never be parallel.')

    def createSpiral(self, center, startRadius, spacePerLoop, startTheta, endTheta, thetaStep):
        # See: https://github.com/ZevEisenberg/ZESpiral and:
        # See: https://github.com/ZevEisenberg/ZESpiral/issues/1
        oldTheta = startTheta
        newTheta = startTheta
        oldR = startRadius + spacePerLoop * oldTheta
        newR = startRadius + spacePerLoop * newTheta
        # max floating point value on a system
        oldSlope = np.finfo(np.float64).max
        newSlope = oldSlope
        self.path = QPainterPath()

        newPoint = QPointF(center.x() + oldR * math.cos(oldTheta), center.y() + oldR * math.sin(oldTheta))
        self.path.moveTo(newPoint)

        firstSlope = True
        while oldTheta < endTheta - thetaStep:                                  # add another phase step
            # save old value
            oldTheta = newTheta
            # add new increment; prevent going beyond end value
            newTheta += min(thetaStep, endTheta - oldTheta)

            oldR = newR
            newR = startRadius + spacePerLoop * newTheta
            newPoint = QPointF(center.x() + newR * math.cos(newTheta), center.y() + newR * math.sin(newTheta))

            # Slope calculation done with the formula:
            # (spacePerLoop * sinTheta + (startRadius + bTheta) * cosTheta) \
            #   / (spacePerLoop * cosTheta - (startRadius + bTheta) * sinTheta)

            aPlusBTheta = startRadius + spacePerLoop * newTheta

            if firstSlope:
                oldSlope = (spacePerLoop * math.sin(oldTheta) + aPlusBTheta * math.cos(oldTheta)) / (spacePerLoop * math.cos(oldTheta) - aPlusBTheta * math.sin(oldTheta))
                firstSlope = False
            else:
                oldSlope = newSlope

            newSlope = (spacePerLoop * math.sin(newTheta) + aPlusBTheta * math.cos(newTheta)) / (spacePerLoop * math.cos(newTheta) - aPlusBTheta * math.sin(newTheta))

            oldIntercept = -(oldSlope * oldR * math.cos(oldTheta) - oldR * math.sin(oldTheta))
            newIntercept = -(newSlope * newR * math.cos(newTheta) - newR * math.sin(newTheta))

            ok, outX, outY = self.ZELineIntersection(oldSlope, oldIntercept, newSlope, newIntercept)

            if ok:
                controlPoint = QPointF(outX + center.x(), outY + center.y())
                self.path.quadTo(controlPoint, newPoint)
            else:
                raise ValueError('These lines should never be parallel.')

    def calcSpiralPath(self, origin):
        d = self.dist
        r1 = self.radMin
        r2 = self.radMax
        dr = self.radInc
        # constant applied to radius
        c = dr / (2.0 * math.pi)
        # start phase in radians
        p = self.azi0 * math.pi / 180.0
        # get the angle for the minimum radius
        thetaMin = r1 / c
        # get the angle for the maximum radius
        thetaMax = r2 / c
        # plot angle increment
        thetaStep = 0.125 * math.pi
        # define sign for y-axis
        clockWise = True if d < 0 else False

        # not completely clear why dr needs to be divided by 2Pi (dr --> c)
        #    createSpiral(QPointF center, qreal startRadius, qreal spacePerLoop, qreal startTheta, qreal endTheta, qreal thetaStep)
        self.createSpiralNew2(origin, r1, c, p, thetaMax - thetaMin, thetaStep, clockWise)
        # self.createSpiral(origin, 0, c, thetaMin, thetaMax, thetaStep)

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        wellElem = doc.createElement('spiral')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            wellElem.appendChild(nameElement)

        wellElem.setAttribute('radmin', str(self.radMin))
        wellElem.setAttribute('radmax', str(self.radMax))
        wellElem.setAttribute('radinc', str(self.radInc))
        wellElem.setAttribute('azi0', str(self.azi0))
        wellElem.setAttribute('dist', str(self.dist))
        wellElem.setAttribute('points', str(self.points))

        parent.appendChild(wellElem)
        return wellElem

    def readXml(self, parent: QDomNode):

        spiralElem = parent.namedItem('spiral').toElement()
        if spiralElem.isNull():
            return False

        nameElem = spiralElem.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.radMin = toFloat(spiralElem.attribute('radmin'))
        self.radMax = toFloat(spiralElem.attribute('radmax'))
        self.radInc = toFloat(spiralElem.attribute('radinc'))
        self.azi0 = toFloat(spiralElem.attribute('azi0'))
        self.dist = toFloat(spiralElem.attribute('dist'))
        self.points = toInt(spiralElem.attribute('points'))

        return True
