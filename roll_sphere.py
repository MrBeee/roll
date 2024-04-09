"""
This module provides the Roll Sphere Reflector
"""
import math

import numpy as np
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollSphere:
    def __init__(self, origin: QVector3D = QVector3D(0, 0, -4000), radius: float = 2000.0) -> None:  # assign default values
        self.origin = origin
        self.radius = radius

    def depthAt(self, point2D: QPointF) -> float:
        point3D = QVector3D(point2D.x(), point2D.y(), self.origin.z())
        vector = point3D - self.origin
        length = vector.length()
        if length > self.radius:
            return float('inf')
        else:
            r = self.radius
            l = length
            z = math.sqrt(r * r - l * l)
            return self.origin.z() + z

    def ReflectSphereAtPoint3D(self, ptFrom: QVector3D, ptTo: QVector3D, aoiMin: float = 0.0, aoiMax: float = 45.0) -> QVector3D:
        """calculate relection point for a single src, and rec QVector3D combination"""
        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)

        # create two normalized rays starting from the center of the sphere
        ray1 = (ptTo - self.origin).normalized()                                # ray from center to src
        ray2 = (ptFrom - self.origin).normalized()                              # ray from center to rec

        # create the bisection ray
        ray3 = 0.5 * (ray1 + ray2)                                              # bisection ray

        ptInt = self.origin + self.radius * ray3                                # reflection point at surface of sphere

        # now check AoI from point on sphere upwards
        ray4 = (ptFrom - ptInt).normalized()                                    # ray from reflection to src

        cosAoI = QVector3D.dotProduct(ray3, ray4)                               # AoI factor from inner product
        aoi = math.acos(cosAoI)                                                 # angle from cos factor

        if aoi > aoiMax or aoi < aoiMin:
            return None
        else:
            return ptInt

    def ReflectSphereAtPointNp(self, ptFrom: np.ndarray, ptTo: np.ndarray, aoiMin: float = 0.0, aoiMax: float = 45.0) -> np.ndarray:
        """calculate relection point for a single src, and rec QVector3D combination"""
        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)
        npOrig = np.array([self.origin.x(), self.origin.y(), self.origin.z()], dtype=np.float32)

        # create two normalized rays starting from the center of the sphere
        ray1 = ptTo - npOrig                                                    # ray from center to src
        ray2 = ptFrom - npOrig                                                  # ray from center to rec
        len1 = np.linalg.norm(ray1, axis=0)                                     # get length of the vector
        len2 = np.linalg.norm(ray2, axis=0)                                     # get length of the vectors
        ray1 /= len1                                                            # normalize the vector
        ray2 /= len2                                                            # normalize the vectors

        # create the bisection ray
        ray3 = 0.5 * (ray1 + ray2)                                              # bisection ray to define a point on sphere
        ptRef = npOrig + ray3 * self.radius                                     # reflection point at the surface of sphere

        # now check AoI from point on sphere upwards
        ray4 = ptFrom - ptRef                                                   # ray from reflection to src
        len4 = np.linalg.norm(ray4, axis=0)                                     # get length of the vectors
        ray4 /= len4                                                            # normalize the vector

        cosAoI = np.inner(ray3, ray4)                                           # calculate the inner product
        aoi = np.arccos(cosAoI)                                                 # go from cos to angle

        if aoi > aoiMax or aoi < aoiMin:
            return None                                                         # AoI out of range
        else:
            return ptRef                                                        # AoI in valid range

    def ReflectSphereAtPointsNp(self, ptSrc: np.ndarray, ptRec: np.ndarray, aoiMin: float = 0.0, aoiMax: float = 45.0) -> np.ndarray:
        """calculate relection point for a single src, and rec QVector3D combination"""
        aoiMin = math.radians(aoiMin)
        aoiMax = math.radians(aoiMax)
        npOrig = np.array([self.origin.x(), self.origin.y(), self.origin.z()], dtype=np.float32)

        # create two normalized rays starting from the center of the sphere
        raySrc = ptSrc - npOrig                                                 # ray from sphere center to src
        rayRec = ptRec - npOrig                                                 # ray from sphere center to rec
        lenSrc = np.linalg.norm(raySrc, axis=0)                                 # get length of the src vector
        lenRec = np.linalg.norm(rayRec, axis=1)                                 # get length of the rec vectors
        raySrc = raySrc / lenSrc                                                # normalize the src vector
        rayRec = rayRec / lenRec[:, None]                                       # normalize the rec vectors

        # create the bisection ray
        # See: https://math.stackexchange.com/questions/2444193/equation-of-angle-bisector-of-two-3d-straight-lines
        rayMid = 0.5 * (raySrc + rayRec)                                        # bisection ray to define a point on sphere
        ptRef = npOrig + rayMid * self.radius                                   # reflection points at the surface of sphere

        # now check AoI from points-on-sphere upwards; redefine raySrc
        raySrc = ptSrc - ptRef                                                  # rays from sphere surface to src
        lenSrc = np.linalg.norm(raySrc, axis=1)                                 # get length of the vectors
        raySrc = raySrc / lenSrc[:, None]                                       # normalize the src vectors

        # calculate the inner product of src- and bisection rays
        cosAoI = np.multiply(raySrc, rayMid)                                    # element wise multiplication      (N x 3) * (N x 3) -> (N x 3)
        cosAoI = np.sum(cosAoI, axis=1)                                         # sum per row, to get the wanted dot product (N x 3) -> (N x 1)
        aoi = np.arccos(cosAoI)                                                 # go from cos to angle

        I = (aoi[:] >= aoiMin) & (aoi[:] <= aoiMax)                             # only use these angles

        if np.count_nonzero(I) == 0:
            return (None, None)                                                 # no valid angles found

        ptRef = ptRef[I]                                                        # filter the reflection array
        ptRec = ptRec[I]                                                        # filter the end points too
        return (ptRef, ptRec)                                                   # return reflection points (=cmp's) and pruned receiver points

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        sphereElem = doc.createElement('sphere')
        sphereElem.setAttribute('x0', str(self.origin.x()))
        sphereElem.setAttribute('y0', str(self.origin.y()))
        sphereElem.setAttribute('z0', str(self.origin.z()))
        sphereElem.setAttribute('radius', str(self.radius))
        parent.appendChild(sphereElem)

        s1 = 'Sphere is defined in global coordinates. Subsurface corresponds with negative z-values'
        comment1 = doc.createComment(s1)
        parent.appendChild(comment1)

        return sphereElem

    def readXml(self, parent: QDomNode):

        sphereElem = parent.namedItem('sphere').toElement()
        if sphereElem.isNull():
            return False

        self.origin.setX(toFloat(sphereElem.attribute('x0')))
        self.origin.setY(toFloat(sphereElem.attribute('y0')))
        self.origin.setZ(toFloat(sphereElem.attribute('z0'), 4000.0))
        self.radius = toFloat(sphereElem.attribute('radius'), 2000.0)
        return True
