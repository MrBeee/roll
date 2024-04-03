"""
This module provides the Roll Plane Reflector
"""
import math

import numpy as np
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollPlane:
    def __init__(self, anchor: QVector3D = QVector3D(0, 0, -2000), azi: float = 0.0, dip: float = 0.0) -> None:  # assign default values
        # serialization hinges around anchor, azimuth and dip; from these parameters the plane equation is determined
        self.anchor = anchor                                                    # needed in xml-read & write
        self.azi = azi                                                       # needed in xml-read & write
        self.dip = dip                                                       # needed in xml-read & write

        self.dist = 0.0                                                       # calculated in calculateNormal()
        self.normal = QVector3D()                                               # calculated in calculateNormal()
        self.calculateNormal()                                                  # to initialise dist & normal

    @classmethod
    # See: https://realpython.com/python-multiple-constructors/#providing-multiple-constructors-with-classmethod-in-python
    def fromNormalAndDistance(cls, norm: QVector3D = QVector3D(0.0, 0.0, 1.0), dist: float = 0.0):
        dip = round(math.degrees(math.acos(QVector3D.dotProduct(norm, QVector3D(0.0, 0.0, 1.0)))), 4)
        azi = round(math.degrees(math.atan2(norm.y(), norm.x())) + 180.0, 4)
        anchor = QVector3D(0.0, 0.0, -dist / norm.z())
        return cls(anchor, azi, dip)

    @classmethod
    def fromAnchorAndNormal(cls, anchor: QVector3D = QVector3D(0, 0, -2000), norm: QVector3D = QVector3D(0.0, 0.0, 1.0)):
        dip = round(math.degrees(math.acos(QVector3D.dotProduct(norm, QVector3D(0.0, 0.0, 1.0)))), 4)
        azi = round(math.degrees(math.atan2(norm.y(), norm.x())) + 180.0, 4)
        return cls(anchor, azi, dip)

    def calculateDipAndAzimuth(self) -> None:
        self.dip = round(math.degrees(math.acos(QVector3D.dotProduct(self.normal, QVector3D(0.0, 0.0, 1.0)))), 4)
        self.azi = round(math.degrees(math.atan2(self.normal.y(), self.normal.x())) + 180.0, 4)

    def calculateNormal(self) -> None:
        # calculate normal and distance from origin
        self.normal.setX(math.sin(math.radians(-self.dip)) * math.cos(math.radians(self.azi)))
        self.normal.setY(math.sin(math.radians(-self.dip)) * math.sin(math.radians(self.azi)))
        self.normal.setZ(math.cos(math.radians(-self.dip)))
        self.dist = -QVector3D.dotProduct(self.normal, self.anchor)

    def depthAt(self, point2D: QPointF) -> float:
        if self.normal.z() == 0:
            return 0.0
        else:
            # make it a 3D point with z = 0
            point3D = QVector3D(point2D)
            return -(QVector3D.dotProduct(self.normal, point3D) + self.dist) / self.normal.z()

    def projectPoint(self, point3D: QVector3D) -> QVector3D:
        distance = self.distanceToPoint(point3D)
        return point3D - self.normal * distance

    def distanceToPoint(self, point3D: QVector3D) -> float:
        return QVector3D.dotProduct(self.normal, point3D) + self.dist

    # def foo(x: np.ndarray) -> np.ndarray:                                     # type checking with numpy
    def distanceToNpPoint(self, npPoint: np.ndarray) -> float:
        npNormal = np.array([self.normal.x(), self.normal.y(), self.normal.z()])  # turn normal vector into numpy array (=vector). Alas, QVector3D.toTuple() DOES NOT EXIST !
        return np.inner(npNormal, npPoint) + self.dist                          # calculate inner product + distance to origin

    def mirrorPoint3D(self, point3D: QVector3D) -> QVector3D:
        distance = self.distanceToPoint(point3D) * 2.0
        return point3D - self.normal * distance

    def mirrorPointNp(self, npPoint: np.ndarray) -> np.ndarray:
        distance = self.distanceToNpPoint(npPoint) * 2.0
        npNormal = np.array([self.normal.x(), self.normal.y(), self.normal.z()])  # turn normal vector into numpy array (=vector). Alas, QVector3D.toTuple() DOES NOT EXIST !
        return npPoint - npNormal * distance

    def IntersectLineAtPoint3D(self, ptFrom: QVector3D, ptTo: QVector3D, aoiMin: float = 0.0, aoiMax: float = 45.0) -> QVector3D:
        # See: https://stackoverflow.com/questions/7168484/3d-line-segment-and-plane-intersection

        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)

        # create the vector from src-mirror to rec
        ray = ptTo - ptFrom
        denominator = QVector3D.dotProduct(self.normal, ray)

        if denominator == 0.0:
            return None

        nominator = QVector3D.dotProduct(self.normal, ptTo) + self.dist
        U = nominator / denominator

        if U < 0 or U > 1:
            # rec and src-mirror are at the same side of plane
            return None
        else:
            cosAoI = denominator / ray.length()
            aoi = math.acos(cosAoI)

            if aoi > aoiMax or aoi < aoiMin:
                return None

            ptInt = ptTo - ray * U
            return ptInt

    def IntersectLineAtPointNp(self, ptFrom: np.ndarray, ptTo: np.ndarray, aoiMin: float = 0.0, aoiMax: float = 45.0) -> np.ndarray:
        # See: https://stackoverflow.com/questions/7168484/3d-line-segment-and-plane-intersection

        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)
        npNormal = np.array([self.normal.x(), self.normal.y(), self.normal.z()])  # turn normal vector into numpy array (=vector). Alas, QVector3D.toTuple() DOES NOT EXIST !

        # create the vector from src-mirror to rec
        ray = ptTo - ptFrom
        denominator = np.inner(npNormal, ray)

        if denominator == 0.0:
            return None

        nominator = np.inner(npNormal, ptTo) + self.dist
        U = nominator / denominator

        if U < 0 or U > 1:
            # rec and src-mirror are at the same side of plane
            return None
        else:
            cosAoI = denominator / np.sqrt(ray.dot(ray))                        # np.sqrt(ray.dot(ray)) to calculate the length of the ray
            aoi = math.acos(cosAoI)

            if aoi > aoiMax or aoi < aoiMin:                                    # check if AoI is in range
                return None

            ptInt = ptTo - ray * U
            return ptInt

    def IntersectLinesAtPointNp(self, ptFrom: np.ndarray, ptTo: np.ndarray, aoiMin: float = 0.0, aoiMax: float = 45.0) -> np.ndarray:
        # See: https://stackoverflow.com/questions/7168484/3d-line-segment-and-plane-intersection

        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)
        npNormal = np.array([self.normal.x(), self.normal.y(), self.normal.z()])  # turn normal vector into numpy array (=vector). Alas, QVector3D.toTuple() DOES NOT EXIST !

        # create the vector from src-mirror to rec
        ray = ptTo - ptFrom
        denominator = np.inner(npNormal, ray)

        I = denominator[:] != 0.0
        if np.count_nonzero(I) == 0:
            return (None, None)                                                 # no valid distances > 0.0 found

        denominator = denominator[I]                                            # filter the denominator array
        ptTo = ptTo[I]                                                   # filter the end points too
        ray = ray[I]                                                    # filter the rays too

        nominator = np.inner(npNormal, ptTo) + self.dist                        # setup the nominator array
        nominator = nominator[I]                                                # filter the nominator array as well

        U = nominator / denominator                                             # setup the ratio array

        I = (U[:] >= 0.0) & (U[:] <= 1.0)                                      # only use these ratios

        if np.count_nonzero(I) == 0:
            return (None, None)                                                 # no valid ratios found

        denominator = denominator[I]                                            # filter the denominator array
        ptTo = ptTo[I]                                                   # filter the end points too
        ray = ray[I]                                                    # filter the rays too
        U = U[I]                                                      # filter the ratio array

        # length = np.apply_along_axis(np.linalg.norm, 1, ray)                    # calculate the length of each row in the array
        length = np.linalg.norm(ray, axis=1)
        # See: https://stackoverflow.com/questions/7741878/how-to-apply-numpy-linalg-norm-to-each-row-of-a-matrix/19794741#19794741

        cosAoI = denominator / length                                           # normalize to 0.0 - 1.0 cos() range
        aoi = np.arccos(cosAoI)                                              # go from cos to angle

        I = (aoi[:] >= aoiMin) & (aoi[:] <= aoiMax)                             # only use these angles

        if np.count_nonzero(I) == 0:
            return (None, None)                                                 # no valid angles found

        U = U[I]                                                             # filter the ratio array
        ptTo = ptTo[I]                                                          # filter the end points too
        ray = ray[I]                                                           # filter the rays too
        rayU = ray * U[:, None]                                                 # get rays (x, y, z) multiplied per row by U(n)
        # See: https://stackoverflow.com/questions/68245372/how-to-multiply-each-row-in-matrix-by-its-scalar-in-numpy

        ptIntercept = ptTo - rayU                                               # interception points at the plane's surface
        return (ptIntercept, ptTo)                                              # return interception points (=cmp's) and pruned receiver points

    # def angleOfIncidenceOld(self, point3D: QVector3D) -> float:
    #     phi = 0.0
    #     dist2 = math.sqrt(point3D * point3D)

    #     if dist2 > 0.0:
    #         phi = math.acos(point3D * self.normal / dist2)
    #         phi = math.degrees(phi)
    #     return phi

    def angleOfIncidence(self, point3D: QVector3D) -> float:
        phi = 0.0
        length = point3D.lenght()

        if length > 0.0:
            phi = math.acos(point3D * self.normal / length)
            phi = math.degrees(phi)
        return phi

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        planeElem = doc.createElement('plane')
        planeElem.setAttribute('x0', str(self.anchor.x()))
        planeElem.setAttribute('y0', str(self.anchor.y()))
        planeElem.setAttribute('z0', str(self.anchor.z()))
        planeElem.setAttribute('azi', str(self.azi))
        planeElem.setAttribute('dip', str(self.dip))
        parent.appendChild(planeElem)

        s1 = f'Plane equation: {self.normal.x():.6f}·x + {self.normal.y():.6f}·y + {self.normal.z():.6f}·z + {self.dist:.6f} = 0  '
        s2 = 'Plane is defined in global coordinates. Subsurface corresponds with negative z-values'
        comment1 = doc.createComment(s1)
        comment2 = doc.createComment(s2)
        parent.appendChild(comment1)
        parent.appendChild(comment2)

        return planeElem

    def readXml(self, parent: QDomNode):

        planeElem = parent.namedItem('plane').toElement()
        if planeElem.isNull():
            return False

        self.anchor.setX(toFloat(planeElem.attribute('x0')))
        self.anchor.setY(toFloat(planeElem.attribute('y0')))
        self.anchor.setZ(toFloat(planeElem.attribute('z0')))

        self.azi = toFloat(planeElem.attribute('azi'))
        self.dip = toFloat(planeElem.attribute('dip'))

        # to complete initialisation of plane
        self.calculateNormal()

        # dip = round(math.degrees(math.acos(QVector3D.dotProduct(self.normal, QVector3D(0.0, 0.0, 1.0)))), 4)
        # azi = round(math.degrees(math.atan2(self.normal.y(), self.normal.x())) + 180.0, 4)

        return True
