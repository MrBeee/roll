"""
This module provides the main classes used in Roll
"""
import math
import os
from collections import defaultdict
from enum import Enum

import numpy as np
import pyqtgraph as pg
import wellpathpy as wp
from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsPointXY, QgsProject, QgsVector3D)
from qgis.PyQt.QtCore import (QFileInfo, QLineF, QMarginsF, QPointF, QRectF,
                              QThread, pyqtSignal)
from qgis.PyQt.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPicture,
                             QPolygonF, QTransform, QVector3D)
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtXml import QDomDocument, QDomElement, QDomNode

from . import config  # used to pass initial settings
from .functions import (clipLineF, clipRectF, containsPoint2D, containsPoint3D,
                        deviation, read_well_header, read_wws_header, toFloat,
                        toInt)
from .rdp import filterRdp
from .sps_io_and_qc import pntType1, relType2

# from numba import jit

# See: https://realpython.com/python-multiple-constructors/#instantiating-classes-in-python for multiple constructors
# See: https://stackoverflow.com/questions/39513191/python-operator-overloading-with-multiple-operands for operator overlaoding
# See: https://realpython.com/operator-function-overloading/#overloading-built-in-operators
# See: https://stackoverflow.com/questions/56762491/python-equivalent-to-c-line for showing line numbers
# See: https://www.programcreek.com/python/example/86794/PyQt5.QtCore.QPointF for a 2D point example, QPointF
# See: https://www.programcreek.com/python/example/83788/PyQt5.QtCore.QRectF for QRectF examples
# See: https://doc.qt.io/qtforpython-5/PySide2/QtCore/QPointF.html
# See: https://doc.qt.io/qtforpython-5/PySide2/QtCore/QRectF.html
# See: https://geekflare.com/multiply-matrices-in-python/ for matrix multiplication methods
# See: https://doc.qt.io/qt-6/examples-threadandconcurrent.html for using a worker thread

# in the end we need to plot these classes on a QtScene object managed through PyQtGraph.
# the base class in Qt for graphical objects is **QGraphicsItem** from which other classes can be derived.
# See for example: https://doc.qt.io/qtforpython-5/overviews/qtwidgets-graphicsview-dragdroprobot-example.html#drag-and-drop-robot-example

# In PyQtGraph we have an abstract class **GraphicsItem(object)**.
# See: D:\Source\Python\pyqtgraph\pyqtgraph\graphicsItems\GraphicsItem.py

# Derived from it we have a class that also inherits from Qt's QGraphicsObject:
# class **GraphicsObject(GraphicsItem, QtWidgets.QGraphicsObject)**

# GraphicsObject provides a base class for all graphics items that require signals, slots and properties
# The class extends a QGraphicsItem with QObject's signal/slot and property mechanisms.

# So in PyQtGraph, **GraphicsObject()** is the starting point for all other inherited graphical objects
# some example sub-classes are :
# class BarGraphItem(GraphicsObject)
# class ButtonItem(GraphicsObject)
# class CurvePoint(GraphicsObject)
# class ErrorBarItem(GraphicsObject)
# class GraphItem(GraphicsObject)
# class ImageItem(GraphicsObject)
# class InfiniteLine(GraphicsObject)
# class IsocurveItem(GraphicsObject)
# class ItemGroup(GraphicsObject)
# class LinearRegionItem(GraphicsObject)
# class NonUniformImage(GraphicsObject)
# class PColorMeshItem(GraphicsObject)
# class PlotCurveItem(GraphicsObject)
# class PlotDataItem(GraphicsObject)
# class ROI(GraphicsObject)
# class ScatterPlotItem(GraphicsObject)
# class TextItem(GraphicsObject)
# class UIGraphicsItem(GraphicsObject)
# class CandlestickItem(GraphicsObject) -> in the examples folder
# So where Roll end up painting something, the relevant class(es) need to be derived from PyQtGraph.GraphicsObject as well !!!
# As all classes here are a leaf in the tree derived from RollSurvey, it is this class that needs to be derived from GraphicsObject.
# That implies that the following two functions need to be implemented in RollSurvey:
#   >>def paint(self, p, *args)<<
#       the paint operation should paint all survey aspects (patterns, points, lines, blocks) dependent on the actual LOD
#   >>def boundingRect(self)<<
#       boundingRect _must_ indicate the entire area that will be drawn on or else we will get artifacts and possibly crashing.

# To give an xml-object a name, create a seperate <name> element as first xml entry (preferred over name attribute)
# the advantage of using element.text is that characters like ' and " don't cause issues in terminating a ""-string
# if len(self.name) > 0:
#     name_elem = ET.SubElement(seed_elem, 'name')
#     name_elem.text = self.name

# See: https://stackoverflow.com/questions/62196835/how-to-get-string-name-for-qevent-in-pyqt5
event_lookup = {
    '0': 'QEvent::None',
    '114': 'QEvent::ActionAdded',
    '113': 'QEvent::ActionChanged',
    '115': 'QEvent::ActionRemoved',
    '99': 'QEvent::ActivationChange',
    '121': 'QEvent::ApplicationActivate',
    '122': 'QEvent::ApplicationDeactivate',
    '36': 'QEvent::ApplicationFontChange',
    '37': 'QEvent::ApplicationLayoutDirectionChange',
    '38': 'QEvent::ApplicationPaletteChange',
    '214': 'QEvent::ApplicationStateChange',
    '35': 'QEvent::ApplicationWindowIconChange',
    '68': 'QEvent::ChildAdded',
    '69': 'QEvent::ChildPolished',
    '71': 'QEvent::ChildRemoved',
    '40': 'QEvent::Clipboard',
    '19': 'QEvent::Close',
    '200': 'QEvent::CloseSoftwareInputPanel',
    '178': 'QEvent::ContentsRectChange',
    '82': 'QEvent::ContextMenu',
    '183': 'QEvent::CursorChange',
    '52': 'QEvent::DeferredDelete',
    '60': 'QEvent::DragEnter',
    '62': 'QEvent::DragLeave',
    '61': 'QEvent::DragMove',
    '63': 'QEvent::Drop',
    '170': 'QEvent::DynamicPropertyChange',
    '98': 'QEvent::EnabledChange',
    '10': 'QEvent::Enter',
    '150': 'QEvent::EnterEditFocus',
    '124': 'QEvent::EnterWhatsThisMode',
    '206': 'QEvent::Expose',
    '116': 'QEvent::FileOpen',
    '8': 'QEvent::FocusIn',
    '9': 'QEvent::FocusOut',
    '23': 'QEvent::FocusAboutToChange',
    '97': 'QEvent::FontChange',
    '198': 'QEvent::Gesture',
    '202': 'QEvent::GestureOverride',
    '188': 'QEvent::GrabKeyboard',
    '186': 'QEvent::GrabMouse',
    '159': 'QEvent::GraphicsSceneContextMenu',
    '164': 'QEvent::GraphicsSceneDragEnter',
    '166': 'QEvent::GraphicsSceneDragLeave',
    '165': 'QEvent::GraphicsSceneDragMove',
    '167': 'QEvent::GraphicsSceneDrop',
    '163': 'QEvent::GraphicsSceneHelp',
    '160': 'QEvent::GraphicsSceneHoverEnter',
    '162': 'QEvent::GraphicsSceneHoverLeave',
    '161': 'QEvent::GraphicsSceneHoverMove',
    '158': 'QEvent::GraphicsSceneMouseDoubleClick',
    '155': 'QEvent::GraphicsSceneMouseMove',
    '156': 'QEvent::GraphicsSceneMousePress',
    '157': 'QEvent::GraphicsSceneMouseRelease',
    '182': 'QEvent::GraphicsSceneMove',
    '181': 'QEvent::GraphicsSceneResize',
    '168': 'QEvent::GraphicsSceneWheel',
    '18': 'QEvent::Hide',
    '27': 'QEvent::HideToParent',
    '127': 'QEvent::HoverEnter',
    '128': 'QEvent::HoverLeave',
    '129': 'QEvent::HoverMove',
    '96': 'QEvent::IconDrag',
    '101': 'QEvent::IconTextChange',
    '83': 'QEvent::InputMethod',
    '207': 'QEvent::InputMethodQuery',
    '169': 'QEvent::KeyboardLayoutChange',
    '6': 'QEvent::KeyPress',
    '7': 'QEvent::KeyRelease',
    '89': 'QEvent::LanguageChange',
    '90': 'QEvent::LayoutDirectionChange',
    '76': 'QEvent::LayoutRequest',
    '11': 'QEvent::Leave',
    '151': 'QEvent::LeaveEditFocus',
    '125': 'QEvent::LeaveWhatsThisMode',
    '88': 'QEvent::LocaleChange',
    '176': 'QEvent::NonClientAreaMouseButtonDblClick',
    '174': 'QEvent::NonClientAreaMouseButtonPress',
    '175': 'QEvent::NonClientAreaMouseButtonRelease',
    '173': 'QEvent::NonClientAreaMouseMove',
    '177': 'QEvent::MacSizeChange',
    '43': 'QEvent::MetaCall',
    '102': 'QEvent::ModifiedChange',
    '4': 'QEvent::MouseButtonDblClick',
    '2': 'QEvent::MouseButtonPress',
    '3': 'QEvent::MouseButtonRelease',
    '5': 'QEvent::MouseMove',
    '109': 'QEvent::MouseTrackingChange',
    '13': 'QEvent::Move',
    '197': 'QEvent::NativeGesture',
    '208': 'QEvent::OrientationChange',
    '12': 'QEvent::Paint',
    '39': 'QEvent::PaletteChange',
    '131': 'QEvent::ParentAboutToChange',
    '21': 'QEvent::ParentChange',
    '212': 'QEvent::PlatformPanel',
    '217': 'QEvent::PlatformSurface',
    '75': 'QEvent::Polish',
    '74': 'QEvent::PolishRequest',
    '123': 'QEvent::QueryWhatsThis',
    '106': 'QEvent::ReadOnlyChange',
    '199': 'QEvent::RequestSoftwareInputPanel',
    '14': 'QEvent::Resize',
    '204': 'QEvent::ScrollPrepare',
    '205': 'QEvent::Scroll',
    '117': 'QEvent::Shortcut',
    '51': 'QEvent::ShortcutOverride',
    '17': 'QEvent::Show',
    '26': 'QEvent::ShowToParent',
    '50': 'QEvent::SockAct',
    '192': 'QEvent::StateMachineSignal',
    '193': 'QEvent::StateMachineWrapped',
    '112': 'QEvent::StatusTip',
    '100': 'QEvent::StyleChange',
    '87': 'QEvent::TabletMove',
    '92': 'QEvent::TabletPress',
    '93': 'QEvent::TabletRelease',
    '171': 'QEvent::TabletEnterProximity',
    '172': 'QEvent::TabletLeaveProximity',
    '219': 'QEvent::TabletTrackingChange',
    '22': 'QEvent::ThreadChange',
    '1': 'QEvent::Timer',
    '120': 'QEvent::ToolBarChange',
    '110': 'QEvent::ToolTip',
    '184': 'QEvent::ToolTipChange',
    '194': 'QEvent::TouchBegin',
    '209': 'QEvent::TouchCancel',
    '196': 'QEvent::TouchEnd',
    '195': 'QEvent::TouchUpdate',
    '189': 'QEvent::UngrabKeyboard',
    '187': 'QEvent::UngrabMouse',
    '78': 'QEvent::UpdateLater',
    '77': 'QEvent::UpdateRequest',
    '111': 'QEvent::WhatsThis',
    '118': 'QEvent::WhatsThisClicked',
    '31': 'QEvent::Wheel',
    '132': 'QEvent::WinEventAct',
    '24': 'QEvent::WindowActivate',
    '103': 'QEvent::WindowBlocked',
    '25': 'QEvent::WindowDeactivate',
    '34': 'QEvent::WindowIconChange',
    '105': 'QEvent::WindowStateChange',
    '33': 'QEvent::WindowTitleChange',
    '104': 'QEvent::WindowUnblocked',
    '203': 'QEvent::WinIdChange',
    '126': 'QEvent::ZOrderChange',
}


class surveyType(Enum):
    Orthogonal = 0
    Parallel = 1
    Slanted = 2
    Brick = 3
    Zigzag = 4


# Note: we need to keep surveyType and surveyList in sync; maybe combine in a dictionary ?!
surveyList = [
    'Orthogonal - standard manner of acquiring land data',
    'Parallel - standard manner of acquiring OBN data',
    'Slanted - legacy variation on orthogonal, aiming to reduce LMOS',
    'Brick - legacy variation on orthogonal, aiming to reduce LMOS',
    'zigzag - legacy manner acquiring narrrow azimuth vibroseis data',
]


class BinningType(Enum):
    cmp = 0
    plane = 1
    sphere = 2


binningList = [
    'Cmp binning',
    'Dipping plane',
    'Buried sphere',
]


class paintMode(Enum):
    noTemplates = -1
    oneTemplate = 0
    allTemplates = 4


class seedType(Enum):
    grid = 0
    circle = 1
    spiral = 2
    well = 3


# CLASS ###############################################################################


class QVectorN3D:
    def __init__(self, count: int = 1, vector: QVector3D = QVector3D(0, 0, 0)) -> None:
        self._count = count
        self._vector = vector

    def count(self) -> int:
        return self._count

    def vector(self) -> QVector3D:
        return self._vector

    def setCount(self, count) -> int:
        count = max(1, count)
        self._count = count
        return self.count

    def setVector(self, vector) -> QVector3D:
        self._vector = vector
        return self._vector


# CLASS ###############################################################################


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


# CLASS ###############################################################################


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
        ray1 = (ptTo - self.origin).normalized()                              # ray from center to src
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
        ray1 = ptTo - npOrig                                                # ray from center to src
        ray2 = ptFrom - npOrig                                                # ray from center to rec
        len1 = np.linalg.norm(ray1, axis=0)                                     # get length of the vector
        len2 = np.linalg.norm(ray2, axis=0)                                     # get length of the vectors
        ray1 /= len1                                                             # normalize the vector
        ray2 /= len2                                                             # normalize the vectors

        # create the bisection ray
        ray3 = 0.5 * (ray1 + ray2)                                              # bisection ray to define a point on sphere
        ptRef = npOrig + ray3 * self.radius                                     # reflection point at the surface of sphere

        # now check AoI from point on sphere upwards
        ray4 = ptFrom - ptRef                                                 # ray from reflection to src
        len4 = np.linalg.norm(ray4, axis=0)                                     # get length of the vectors
        ray4 /= len4                                                             # normalize the vector

        cosAoI = np.inner(ray3, ray4)                                           # calculate the inner product
        aoi = np.arccos(cosAoI)                                              # go from cos to angle

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
        raySrc = ptSrc - npOrig                                               # ray from sphere center to src
        rayRec = ptRec - npOrig                                               # ray from sphere center to rec
        lenSrc = np.linalg.norm(raySrc, axis=0)                                 # get length of the src vector
        lenRec = np.linalg.norm(rayRec, axis=1)                                 # get length of the rec vectors
        raySrc = raySrc / lenSrc                                                # normalize the src vector
        rayRec = rayRec / lenRec[:, None]                                       # normalize the rec vectors

        # create the bisection ray
        # See: https://math.stackexchange.com/questions/2444193/equation-of-angle-bisector-of-two-3d-straight-lines
        rayMid = 0.5 * (raySrc + rayRec)                                        # bisection ray to define a point on sphere
        ptRef = npOrig + rayMid * self.radius                                   # reflection points at the surface of sphere

        # now check AoI from points-on-sphere upwards; redefine raySrc
        raySrc = ptSrc - ptRef                                                # rays from sphere surface to src
        lenSrc = np.linalg.norm(raySrc, axis=1)                                 # get length of the vectors
        raySrc = raySrc / lenSrc[:, None]                                       # normalize the src vectors

        # calculate the inner product of src- and bisection rays
        cosAoI = np.multiply(raySrc, rayMid)                                    # element wise multiplication      (N x 3) * (N x 3) -> (N x 3)
        cosAoI = np.sum(cosAoI, axis=1)                                       # sum per row, to get the wanted dot product (N x 3) -> (N x 1)
        aoi = np.arccos(cosAoI)                                              # go from cos to angle

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


# CLASS ###############################################################################

# Need to fully implement this class for symmetry with circles, spirals and wells !


class RollGrid:
    # by default no name
    def __init__(self, name: str = '') -> None:
        # input variables
        # Seed name
        self.name = name
        self.bRoll = True
        # list of (max 3) grow steps
        self.growList: list[RollTranslate] = []
        # calculated variables
        # draws line From FIRST to LAST point of FIRST grow step (quick draw)
        self.salvo = QLineF()
        # nr of points on grid
        self.points = 0

    def calcPointList(self, origin):
        while len(self.growList) < 3:
            # First, make sure there are three grow steps for every seed
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

    # we're in RollGrid here
    def calcBoundingRect(self, origin):
        # create QRectF by applying grow steps
        # declare new object to start iterating from
        pointIter = QVector3D(origin)
        for growStep in self.growList:                                          # iterate through all grow steps
            # we have to subtract 1 here' to get from deployments to roll steps
            for _ in range(growStep.steps - 1):
                # shift the iteration point with the appropriate amount
                pointIter += growStep.increment

        # create a rect from origin + shifted point
        boundingBox = QRectF(origin.toPointF(), pointIter.toPointF())
        return boundingBox

    def calcSalvoLine(self, origin):
        # The salvo is a line from first to last point in the last (lowest) growstep

        nPoints = 0
        if self.growList:                                                       # the list is not empty
            # use the last grow step; length is 1 shorter than nr of points
            nPoints = self.growList[-1].steps - 1

        if nPoints == 0:
            # avoid a null line; give it a minimum size
            lineLength = QVector3D(1.0e-6, 1.0e-6, 0.0)
        else:
            # calculate the line length
            lineLength = self.growList[-1].increment * nPoints

        # set the endPoint
        endPoint = origin + lineLength

        # this is the unshifted line
        self.salvo = QLineF(origin.toPointF(), endPoint.toPointF())
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


# CLASS ###############################################################################


class RollCircle:
    # by default no name
    def __init__(self, name: str = '') -> None:
        # input variables
        # Seed name
        self.name = name
        # circle radius
        self.radius = 1000.0
        # start angle
        self.azi0 = 0.0
        # point interval along the circle
        self.dist = 25.0
        # calculated variables
        # corresponding nr of points on circle
        self.points = 251

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


# CLASS ###############################################################################


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


# CLASS ###############################################################################


class RollWell:
    # assign default name
    def __init__(self, name: str = '') -> None:
        # input variables
        self.name = name                                                        # path to well file
        self.errorText = None                                                   # text explaining which error occurred

        if config.surveyCrs is not None and config.surveyCrs.isValid():         # copy crs from project
            self.crs = config.surveyCrs
        else:
            self.crs = QgsCoordinateReferenceSystem('EPSG:23095')               # ED50 / TM 5 NE (arbitrarily)

        self.ahd0 = 1000.0                                                      # first (along hole) depth
        self.dAhd = 15.0                                                        # along hole depth increment
        self.nAhd = 12                                                          # nr of along hole stations

        # variables, calculated and serialized
        self.ahdMax = -999.0                                                    # ahd max, used to set limits for ahd0 and nAhd
        self.origW = QVector3D(-999.0, -999.0, -999.0)                          # wellhead location in original well coordinates
        self.origG = QPointF(-999.0, -999.0)                                    # wellhead location in global project coordinates
        self.origL = QPointF(-999.0, -999.0)                                    # wellhead location in local project coordinates

        # variables, calculated but not serialized
        self.polygon = None                                                     # polygon in survey coordinates, to draw well trajectory
        self.pntList2D = []                                                     # points in survey coordinates, to draw well trajectory

        # please note the seed's origin isn't shown in the property editor, when using a well-based seed
        # instead, the well's origin is shown in 3 different CRSes; (a) well (b) global (c) local

        # for self.lod0 See: https://python.hotexamples.com/examples/PyQt5.QtGui/QPainter/drawPolyline/python-qpainter-drawpolyline-method-examples.html

    def readHeader(self, surveyCrs, glbTransform):
        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}
        self.errorText = None                                                   # text explaining which error occurred

        f = self.name
        if f is None or not os.path.exists(f):                                  # check filename first
            self.errorText = 'No valid well file selected'
            return False

        if not self.crs.isValid():                                              # then check CRS
            self.errorText = 'An invalid CRS has been selected'
            return False

        if self.crs.isGeographic():
            self.errorText = 'geographic CRS selected (using lat/lon angles)'
            return False

        ext = QFileInfo(f).suffix()

        try:
            if ext == 'wws':                                                        # read the well survey file
                md, _, _ = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')   # inc, azi unused and replaced by _, _
                self.ahdMax = md[-1]                                                # maximum along-hole-depth

                # where is the well located ? First see if there's a header file, to pull information from.
                hdrFile = os.path.splitext(f)[0]
                hdrFile = hdrFile + '.hdr'
                # open the header file
                if os.path.exists(hdrFile):
                    # read header in json format
                    header = wp.read_header_json(hdrFile)
                else:
                    # get header information from wws-file itself
                    header = read_wws_header(f)

            elif ext == 'well':
                header, index = read_well_header(f)

                # read the 4 column ascii data; skip header rows
                pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')

                # transpose array to 4 rows, and read these rows
                _, _, depth, md = pos2D.T

                # determine maximum along-hole-depth
                self.ahdMax = md[-1]

                # the self-contained 'well' file does not require a separate header file;
                hdrFile = os.path.splitext(f)[0]

                # but a header file could be used to override the included header data
                hdrFile = hdrFile + '.hdr'
                if os.path.exists(hdrFile):
                    # read header in json format, as described in header dict above
                    header = wp.read_header_json(hdrFile)

                # no separate header file has been provided
                if header['elevation'] is None:
                    header['elevation'] = md[0] - depth[0]
            else:
                self.errorText = f'unsupported file extension: {ext}'
                return False

        except BaseException as e:
            self.errorText = str(e)
            return False

        if header['surface_easting'] is None or header['surface_northing'] is None or header['elevation'] is None:
            self.errorText = 'invalid or missing file header'
            return False

        self.origW = QVector3D(header['surface_easting'], header['surface_northing'], header['elevation'])

        # note: if survey's crs and well's crs are the same, the wellToGlobalTransform has no effect
        wellToGlobalTransform = QgsCoordinateTransform(surveyCrs, self.crs, QgsProject.instance())

        if not wellToGlobalTransform.isValid():                                 # no valid transform found
            self.errorText = 'invalid coordinate transform'
            return False

        # now create the origin in global survey coordinates (well-crs -> project-crs)
        x0, y0 = wellToGlobalTransform.transform(header['surface_easting'], header['surface_northing'])

        x0 = round(x0, 2)
        y0 = round(y0, 2)
        self.origG = QPointF(x0, y0)

        # create transform from global- to survey coordinates
        toLocalTransform, _ = glbTransform.inverted()

        # convert orig from global- to local coordinates
        self.origL = toLocalTransform.map(self.origG)
        self.origL.setX(round(self.origL.x(), 2))
        self.origL.setY(round(self.origL.y(), 2))

        return True

    def calcPointList(self, surveyCrs, glbTransform):
        # See: https://stackoverflow.com/questions/49322017/merging-1d-arrays-into-a-2d-array
        # See: https://www.appsloveworld.com/numpy/100/17/how-can-i-efficiently-transfer-data-from-a-numpy-array-to-a-qpolygonf-when-using
        # See: https://stackoverflow.com/questions/5081875/ctypes-beginner for working with ctypes

        success = self.readHeader(surveyCrs, glbTransform)
        if not success:
            return [], QVector3D(-999.0, -999.0, -999.0)

        f = self.name
        a = self.ahd0
        s = self.dAhd
        n = self.nAhd
        td = a + (n - 1) * s

        # note: if survey's crs and well's crs are the same, the wellToGlobalTransform has no effect
        wellToGlobalTransform = QgsCoordinateTransform(surveyCrs, self.crs, QgsProject.instance())

        # create transform from global- to local coordinates
        toLocalTransform, _ = glbTransform.inverted()

        # create list of available ahd-depth-levels that show source/sensor positions
        ahdList = list(np.linspace(a, td, num=n))

        ext = QFileInfo(f).suffix()

        try:
            if ext == 'wws':                                                        # read contents well survey file
                md, inc, azi = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')

                # get an approximate deviation survey from the position log
                dev = wp.deviation(md=md, inc=inc, azi=azi)
            elif ext == 'well':
                _, index = read_well_header(f)                                      # need index to get to the data

                # read the 4 column ascii data; skip header rows
                pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')

                north, east, depth, md = pos2D.T                                    # transpose array to 4 rows, and read these rows
                self.ahdMax = md[-1]                                                # maximum along-hole-depth

                # for next line; see position_log.py line 409 and further in imported module wellpathpy
                # from here, things are the same as for the wws solution
                dev = deviation(north, east, depth)
            else:
                raise ValueError(f'unsupported file extension: {ext}')

        except BaseException as e:
            self.errorText = str(e)
            return [], QVector3D(-999.0, -999.0, -999.0)

        # this is the key routine that resamples a well trajectory into (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=ahdList)
        pos_wellhead = pos.to_wellhead(surface_northing=self.origW.y(), surface_easting=self.origW.x())
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=self.origW.z())

        x = pos_tvdss.easting
        y = pos_tvdss.northing
        z = pos_tvdss.depth
        n = len(x)

        # first create the list of 3D points in survey coordinates (well-crs -> project-crs -> survey grid)

        pointList = []                                                          # points to derive cdp coverage from
        for i in range(n):                                                      # iterate over all points
            # use 3D values; survey points reside below surface in a well
            vector = QgsVector3D(x[i], y[i], z[i])

            # wellToGlobalTransform may affect elevation
            vector = wellToGlobalTransform.transform(vector)

            # z-value not used in toLocalTransform
            pnt2D = QPointF(vector.x(), vector.y())

            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)

            # create 3D point to be added to list after survey transform
            pnt3D = QVector3D(pnt2D.x(), pnt2D.y(), vector.z())

            # points to derive cdp coverage from
            pointList.append(pnt3D)

        # now display the well trajectory; use 2D points in local coordinates (well-crs -> project-crs -> local grid)
        steps = 50                                                              # start with 50 points along trajectory
        displayList = list(range(0, int(dev.md[-1]) + 1, steps))                # range only likes int values

        # this is the key routine that resamples to (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=displayList)              # use minimum curvature interpolation
        pos_wellhead = pos.to_wellhead(surface_northing=self.origW.y(), surface_easting=self.origW.x())
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=self.origW.z())

        data = list(zip(pos_tvdss.easting, pos_tvdss.northing))                 # create list with (x, y) pairs

        # create mask point list with 2.5 m accuracy
        mask = filterRdp(data, threshold=2.5)                                   # create a numpy mask

        # apply the mask and reduce mumber of points
        data = np.array(data)[mask]                                             # apply the mask

        # the (reduced) data points are still in well-crs coordinates
        self.pntList2D = []                                                     # points to display on map

        # create polygon to draw well trajectory
        self.polygon = QPolygonF()
        for p in data:                                                          # using point iterator
            # wellToGlobalTransform may affect elevation
            pnt2D = wellToGlobalTransform.transform(QgsPointXY(*p)).toQPointF()

            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)

            # points to display on map
            self.pntList2D.append(pnt2D)

            # add points to polygon
            self.polygon.append(pnt2D)

        # return list and well origin in local coordinates; borrow z from well coords
        return pointList, QVector3D(self.origL.x(), self.origL.y(), self.origW.z())

    def calcPointListOld(self, surveyCrs, glbTransform):
        # See: https://stackoverflow.com/questions/49322017/merging-1d-arrays-into-a-2d-array
        # See: https://www.appsloveworld.com/numpy/100/17/how-can-i-efficiently-transfer-data-from-a-numpy-array-to-a-qpolygonf-when-using
        # See: https://stackoverflow.com/questions/5081875/ctypes-beginner for working with ctypes
        f = self.name
        a = self.ahd0
        s = self.dAhd
        n = self.nAhd
        td = a + (n - 1) * s
        header = {'datum': 'dfe', 'elevation_units': 'm', 'elevation': None, 'surface_coordinates_units': 'm', 'surface_easting': None, 'surface_northing': None}

        # note: if survey's crs and well's crs are the same, the wellToGlobalTransform has no effect
        wellToGlobalTransform = QgsCoordinateTransform(surveyCrs, self.crs, QgsProject.instance())

        # create transform from global- to local coordinates
        toLocalTransform, _ = glbTransform.inverted()

        # create list of available ahd-depth-levels
        depths = list(np.linspace(a, td, num=n))

        ext = QFileInfo(f).suffix()
        if ext == 'wws':                                                        # read the well survey file
            # where is the well located ? First see if there's a header file, to pull information from.
            hdrFile = os.path.splitext(f)[0]
            hdrFile = hdrFile + '.hdr'
            # open the header file
            if os.path.exists(hdrFile):
                # read header in json format
                header = wp.read_header_json(hdrFile)
            else:
                # get header information from wws-file itself
                header = read_wws_header(f)

            md, inc, azi = wp.read_csv(f, delimiter=None, skiprows=0, comments='#')  # read well survey file
            # get an approximate deviation survey from the position log
            dev = wp.deviation(md=md, inc=inc, azi=azi)

        elif ext == 'well':
            header, index = read_well_header(f)
            # read the 4 column ascii data; skip header rows
            pos2D = np.loadtxt(f, delimiter=None, skiprows=index, comments='!')
            # transpose array to 4 rows, and read these rows
            north, east, depth, md = pos2D.T

            # the self-contained 'well' file does not require a separate header file;
            hdrFile = os.path.splitext(f)[0]
            # but a header file could be used to override the included header data
            hdrFile = hdrFile + '.hdr'
            # open the header file
            if os.path.exists(hdrFile):
                # read header in json format, as described in header dict above
                header = wp.read_header_json(hdrFile)

            # maximum along-hole-depth
            self.ahdMax = md[-1]
            # no separate header file has been provided
            if header['elevation'] is None:
                header['elevation'] = md[0] - depth[0]

            # for next line; see position_log.py line 409 and further in imported module wellpathpy
            # from here, things are the same as for the wws solution
            dev = deviation(north, east, depth)

        else:
            raise ValueError(f'unsupported file extension: {ext}')

        # this is the key routine that resamples well trajectory to (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=depths)
        pos_wellhead = pos.to_wellhead(surface_northing=header['surface_northing'], surface_easting=header['surface_easting'])
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=header['elevation'])

        x = pos_tvdss.easting
        y = pos_tvdss.northing
        z = pos_tvdss.depth
        n = len(x)

        # first create the list of 3D points in survey coordinates (well-crs -> project-crs -> survey grid)
        # points to derive cdp coverage from
        pointList = []
        # iterate over all points
        for i in range(n):
            # use 3D values; survey points reside in well
            vector = QgsVector3D(x[i], y[i], z[i])

            # wellToGlobalTransform may affect elevation
            vector = wellToGlobalTransform.transform(vector)

            # z-value not used in toLocalTransform
            pnt2D = QPointF(vector.x(), vector.y())

            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)

            # create 3D point to be added to list after survey transform
            pnt3D = QVector3D(pnt2D.x(), pnt2D.y(), vector.z())

            # points to derive cdp coverage from
            pointList.append(pnt3D)

        # now create the well trajectory; 2D points in survey coordinates (well-crs -> project-crs -> survey grid); start with origin
        x0, y0 = wellToGlobalTransform.transform(header['surface_easting'], header['surface_northing'])

        x0 = round(x0, 2)
        y0 = round(y0, 2)

        # convert from global- to survey coordinates; unpack tuple to create a QVector3D
        x0, y0 = toLocalTransform.map(x0, y0)
        x0 = round(x0, 2)
        y0 = round(y0, 2)
        z0 = round(header['elevation'], 2)
        seedOrigin = QVector3D(x0, y0, z0)

        # create a well trajectory to be displayed; start with 50 points along trajectory
        steps = 50
        depths = list(range(0, int(dev.md[-1]) + 1, steps))

        # this is the key routine that resamples to (x, y, z) values
        pos = dev.minimum_curvature().resample(depths=depths)
        pos_wellhead = pos.to_wellhead(surface_northing=header['surface_northing'], surface_easting=header['surface_easting'])
        pos_tvdss = pos_wellhead.to_tvdss(datum_elevation=header['elevation'])
        data = list(zip(pos_tvdss.easting, pos_tvdss.northing))

        # create mask point list with 2.5 m accuracy
        mask = filterRdp(data, threshold=2.5)
        # apply the mask and reduce mumber of points
        data = np.array(data)[mask]

        # the (reduced) data points are still in well-crs coordinates
        # points to display on map
        self.pntList2D = []
        # create polygon to draw well trajectory
        self.polygon = QPolygonF()
        for p in data:                                                          # create point iterator
            # wellToGlobalTransform may affect elevation
            pnt2D = wellToGlobalTransform.transform(QgsPointXY(*p)).toQPointF()
            # convert 2D point from global coordinates to survey coordinates
            pnt2D = toLocalTransform.map(pnt2D)
            # points to display on map
            self.pntList2D.append(pnt2D)
            # add points to polygon
            self.polygon.append(pnt2D)

        # return list and well origin in local coordinates
        return pointList, seedOrigin

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        wellElem = doc.createElement('well')

        if self.name is None or self.name == '':
            self.name = 'None'

        # if not self.name is None and len(self.name) > 0:
        nameElement = doc.createElement('name')
        text = doc.createTextNode(self.name)
        nameElement.appendChild(text)
        wellElem.appendChild(nameElement)

        wellElem.setAttribute('ds', str(self.dAhd))
        wellElem.setAttribute('ns', str(self.nAhd))
        wellElem.setAttribute('s0', str(self.ahd0))
        wellElem.setAttribute('smax', str(self.ahdMax))

        wellElem.setAttribute('wx', str(round(self.origW.x(), 2)))
        wellElem.setAttribute('wy', str(round(self.origW.y(), 2)))
        wellElem.setAttribute('wz', str(round(self.origW.z(), 2)))

        wellElem.setAttribute('gx', str(round(self.origG.x(), 2)))
        wellElem.setAttribute('gy', str(round(self.origG.y(), 2)))

        wellElem.setAttribute('lx', str(round(self.origL.x(), 2)))
        wellElem.setAttribute('ly', str(round(self.origL.y(), 2)))

        wellCrs = doc.createElement('wellCrs')
        wellElem.appendChild(wellCrs)
        if self.crs is not None:                                                # check if we have a valid crs
            # write xml-string to parent element (=surveyCrs)
            self.crs.writeXml(wellCrs, doc)

        parent.appendChild(wellElem)
        return wellElem

    def readXml(self, parent: QDomNode):
        wellElem = parent.namedItem('well').toElement()
        if wellElem.isNull():
            return False

        nameElem = wellElem.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        self.dAhd = toFloat(wellElem.attribute('ds'))
        self.nAhd = toInt(wellElem.attribute('ns'))
        self.ahd0 = toFloat(wellElem.attribute('s0'))
        self.ahdMax = toFloat(wellElem.attribute('smax'), -999.0)

        x0 = toFloat(wellElem.attribute('x0'), -999.0)                          # 'old' xml-attribute
        y0 = toFloat(wellElem.attribute('y0'), -999.0)                          # 'old' xml-attribute
        z0 = toFloat(wellElem.attribute('z0'), -999.0)                          # 'old' xml-attribute

        self.origW.setX(toFloat(wellElem.attribute('wx'), x0))                  # these parameters need to be calculated
        self.origW.setY(toFloat(wellElem.attribute('wy'), y0))                  # using input from a 'well file'
        self.origW.setZ(toFloat(wellElem.attribute('wz'), z0))

        self.origG.setX(toFloat(wellElem.attribute('gx'), -999.0))              # well coordinates converted to 'global' survey crs
        self.origG.setY(toFloat(wellElem.attribute('gy'), -999.0))

        hx = toFloat(wellElem.attribute('hx'), -999.0)
        hy = toFloat(wellElem.attribute('hy'), -999.0)

        self.origL.setX(toFloat(wellElem.attribute('lx'), hx))                  # 'global' well coordinates converted to local survey grid
        self.origL.setY(toFloat(wellElem.attribute('ly'), hy))

        crsElem = wellElem.namedItem('wellCrs').toElement()
        if not crsElem.isNull():
            self.crs.readXml(crsElem)

        return True


# CLASS ###############################################################################


class RollSeed:
    # assign default name value
    def __init__(self, name: str = 'seed-1') -> None:
        # input variables
        self.name = name                                                        # Seed name
        self.origin = QVector3D()                                               # Seed origin
        self.bSource = False                                                    # 'True' if this is a source point seed (receiver = 'False')
        self.bAzimuth = False                                                   # 'True' if this seed has a pattern in direction of line direction
        self.patternNo = -1                                                     # Pattern index serialized in survey file (-1 if name not found)
        self.color = QColor()                                                   # color of seed to discriminate different sources / receivers
        # seed subtypes
        self.type = 0                                                           # Seed type 0 = rolling, 1 = fixed, 2 = circle, 3 = spiral, 4 = well,
        self.grid = RollGrid()
        self.circle = RollCircle()
        self.spiral = RollSpiral()
        self.well = RollWell()
        # calculated variables
        self.boundingBox = QRectF()                                             # Constructs a null rectangle.size of the seed after all grow steps have been done
        # self.salvo = QLineF()                                                   # draws line From FIRST to LAST point of FIRST grow step (quick draw)
        self.pointList = []                                                     # point list to derive cdp coverage from
        self.pointArray = None                                                  # numpy array to derive cdp coverage from
        self.blockBorder = QRectF()                                             # inherited from seed -> template -> block's srcBorder / recBorder depending on seed type
        self.pointPicture = QPicture()                                          # pre-computing a QPicture object allows paint() to run much more quickly
        self.patternPicture = QPicture()                                        # pre-computing a QPicture object allows paint() to run much more quickly
        self.rendered = False                                                   # prevent painting stationary seeds multiple times due to roll-along of other seeds

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
        seedElem.setAttribute('typno', str(self.type))
        seedElem.setAttribute('argb', str(self.color.name(QColor.HexArgb)))

        if self.type < 2:
            self.grid.writeXml(seedElem, doc)
        elif self.type == 2:
            self.circle.writeXml(seedElem, doc)
        elif self.type == 3:
            self.spiral.writeXml(seedElem, doc)
        elif self.type == 4:
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
        self.type = int(parent.attribute('typno'))

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

        if self.type < 2:
            self.grid.readXml(parent)
        elif self.type == 2:
            self.circle.readXml(parent)
        elif self.type == 3:
            self.spiral.readXml(parent)
        elif self.type == 4:
            self.well.readXml(parent)

    def resetBoundingRect(self):
        # Constructs a null rectangle.size of the seed
        self.boundingBox = QRectF()

    # we're in a RollSeed here
    def calcBoundingRect(self):
        if self.type < 2:
            self.boundingBox = self.grid.calcBoundingRect(self.origin)          # grid

        elif self.type == 2:                                                    # circle
            self.boundingBox = self.circle.calcBoundingRect(self.origin)

        elif self.type == 3:                                                    # spiral
            self.boundingBox = self.spiral.calcBoundingRect(self.origin)

        elif self.type == 4:                                                    # well
            self.boundingBox = self.well.polygon.boundingRect()
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
        length = len(self.pointList)
        assert length > 0, 'need 1 or more points in a seed'

        # start with empty array of the right size and type
        self.pointArray = np.empty(shape=(length, 3), dtype=np.float32)

        for count, item in enumerate(self.pointList):
            self.pointArray[count, 0] = item.x()
            self.pointArray[count, 1] = item.y()
            self.pointArray[count, 2] = item.z()

    def calcPointPicture(self):
        # create painter object to draw against
        painter = QPainter(self.pointPicture)
        painter.setPen(pg.mkPen('k'))
        painter.setBrush(self.color)
        painter.drawRect(QRectF(-5, -5, 10, 10))
        painter.end()


# CLASS ###############################################################################


class RollOffset:
    def __init__(self) -> None:  # assign default values
        self.rctOffsets = QRectF()
        self.radOffsets = QPointF()

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        offsetElem = doc.createElement('offset')
        offsetElem.setAttribute('xmin', str(self.rctOffsets.left()))
        offsetElem.setAttribute('xmax', str(self.rctOffsets.right()))
        offsetElem.setAttribute('ymin', str(self.rctOffsets.top()))
        offsetElem.setAttribute('ymax', str(self.rctOffsets.bottom()))

        offsetElem.setAttribute('rmin', str(self.radOffsets.x()))
        offsetElem.setAttribute('rmax', str(self.radOffsets.y()))
        parent.appendChild(offsetElem)

        return offsetElem

    def readXml(self, parent: QDomNode):

        offsetElem = parent.namedItem('offset').toElement()
        if offsetElem.isNull():
            return False

        xmin = toFloat(offsetElem.attribute('xmin'))
        xmax = toFloat(offsetElem.attribute('xmax'))
        self.rctOffsets.setLeft(min(xmin, xmax))
        self.rctOffsets.setRight(max(xmin, xmax))

        ymin = toFloat(offsetElem.attribute('ymin'))
        ymax = toFloat(offsetElem.attribute('ymax'))
        self.rctOffsets.setTop(min(ymin, ymax))
        self.rctOffsets.setBottom(max(ymin, ymax))

        rmin = toFloat(offsetElem.attribute('rmin'))
        rmax = toFloat(offsetElem.attribute('rmax'))
        self.radOffsets.setX(min(rmin, rmax))
        self.radOffsets.setY(max(rmin, rmax))

        return True


# CLASS ###############################################################################


class RollAngles:
    def __init__(self, reflection: QPointF = QPointF(0, 45), azimuthal: QPointF = QPointF(0, 360)) -> None:  # assign default values
        self.reflection = reflection
        self.azimuthal = azimuthal

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        anglesElem = doc.createElement('angles')
        anglesElem.setAttribute('azimin', str(self.azimuthal.x()))
        anglesElem.setAttribute('azimax', str(self.azimuthal.y()))
        anglesElem.setAttribute('refmin', str(self.reflection.x()))
        anglesElem.setAttribute('refmax', str(self.reflection.y()))
        parent.appendChild(anglesElem)

        return anglesElem

    def readXml(self, parent: QDomNode):

        anglesElem = parent.namedItem('angles').toElement()
        if anglesElem.isNull():
            return False

        azimin = toFloat(anglesElem.attribute('azimin'))
        azimax = toFloat(anglesElem.attribute('azimax'))
        self.azimuthal.setX(min(azimin, azimax))
        self.azimuthal.setY(max(azimin, azimax))

        refmin = toFloat(anglesElem.attribute('refmin'))
        refmax = toFloat(anglesElem.attribute('refmax'))
        self.reflection.setX(min(refmin, refmax))
        self.reflection.setY(max(refmin, refmax))

        return True


# CLASS ###############################################################################


class RollOutput:
    # assign default values
    def __init__(self) -> None:
        # size and local position of analysis area
        self.rctOutput = QRectF()

        # numpy array with foldmap
        self.binOutput = None
        # numpy array with minimum offset
        self.minOffset = None
        # numpy array with maximum offset
        self.maxOffset = None
        # memory mapped numpy trace record array
        self.anaOutput = None

        # numpy array with list of receiver locations
        self.recGeom = None
        # numpy array with list of source locations
        self.srcGeom = None
        # numpy array with list of relation records
        self.relGeom = None

        # See: https://stackoverflow.com/questions/17915117/nested-dictionary-comprehension-python
        # See: https://stackoverflow.com/questions/20446526/how-to-construct-nested-dictionary-comprehension-in-python-with-correct-ordering
        # See: https://stackoverflow.com/questions/68305584/nested-dictionary-comprehension-2-level
        # See: https://treyhunner.com/2015/12/python-list-comprehensions-now-in-color/
        # See: https://rowannicholls.github.io/python/advanced/dictionaries.html
        # nested dictionary to access rec positions
        self.recDict = None
        # nested dictionary to access src positions
        self.srcDict = None

        # self.anaType = np.dtype([('SrcX', np.float32), ('SrcY', np.float32),    # Src (x, y)
        #                          ('RecX', np.float32), ('RecY', np.float32),    # Rec (x, y)
        #                          ('CmpX', np.float32), ('CmpY', np.float32),    # Cmp (x, y); needed for spider plot when binning against dipping plane
        #                          ('SrcL', np.int32  ), ('SrcP', np.int32  ),    # SrcLine, SrcPoint
        #                          ('RecL', np.int32  ), ('RecP', np.int32  )])   # RecLine, RecPoint

        # 0 in case no fold is okay
        self.minimumFold: int = 0
        self.maximumFold: int = 0

        self.minMinOffset = 0.0
        self.maxMinOffset = 0.0

        self.minMaxOffset = 0.0
        self.maxMaxOffset = 0.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        outputElem = doc.createElement('output')
        outputElem.setAttribute('xmin', str(self.rctOutput.left()))
        outputElem.setAttribute('xmax', str(self.rctOutput.right()))
        outputElem.setAttribute('ymin', str(self.rctOutput.top()))
        outputElem.setAttribute('ymax', str(self.rctOutput.bottom()))
        parent.appendChild(outputElem)

        return outputElem

    def readXml(self, parent: QDomNode):

        outputElem = parent.namedItem('output').toElement()
        if outputElem.isNull():
            return False

        xmin = toFloat(outputElem.attribute('xmin'))
        xmax = toFloat(outputElem.attribute('xmax'))
        self.rctOutput.setLeft(min(xmin, xmax))
        self.rctOutput.setRight(max(xmin, xmax))

        ymin = toFloat(outputElem.attribute('ymin'))
        ymax = toFloat(outputElem.attribute('ymax'))
        self.rctOutput.setTop(min(ymin, ymax))
        self.rctOutput.setBottom(max(ymin, ymax))

        return True


# CLASS ###############################################################################


class RollBinning:
    def __init__(self, method=BinningType.cmp, vint=2000.0) -> None:  # assign default values
        self.method = method
        self.vint = vint

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        binningElem = doc.createElement('binning')

        binningElem.setAttribute('method', str(self.method.name))
        binningElem.setAttribute('vint', str(self.vint))

        parent.appendChild(binningElem)

        return binningElem

    def readXml(self, parent: QDomNode):

        binningElem = parent.namedItem('binning').toElement()
        if binningElem.isNull():
            return False

        self.method = BinningType[(binningElem.attribute('method'))]
        self.vint = toFloat(binningElem.attribute('vint'), 2000.0)

        return True


# CLASS ###############################################################################


class RollUnique:
    # assign default values
    def __init__(self) -> None:
        self.apply = False
        self.dOffset = 200.0
        self.dAzimuth = 180.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        uniqueElem = doc.createElement('unique')
        uniqueElem.setAttribute('apply', str(self.apply))
        uniqueElem.setAttribute('deltaoff', str(self.dOffset))
        uniqueElem.setAttribute('deltaazi', str(self.dAzimuth))
        parent.appendChild(uniqueElem)

        return uniqueElem

    def readXml(self, parent: QDomNode):

        uniqueElem = parent.namedItem('unique').toElement()
        if uniqueElem.isNull():
            return False

        self.apply = uniqueElem.attribute('apply') == 'True'
        self.dOffset = toFloat(uniqueElem.attribute('deltaoff'))
        self.dAzimuth = toFloat(uniqueElem.attribute('deltaazi'))

        return True


# CLASS ###############################################################################


class RollBinGrid:
    # assign default values
    def __init__(self) -> None:
        # local grid
        self.fold: int = -1                                                     # -1 to catch errors
        self.binSize = QPointF(-1.0, -1.0)                                      # -1 to catch errors
        self.binShift = QPointF(-1.0, -1.0)                                     # -1 to catch errors
        self.stakeOrig = QPointF(-1.0, -1.0)                                    # -1 to catch errors
        self.stakeSize = QPointF(-1.0, -1.0)                                    # -1 to catch errors

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


# CLASS ###############################################################################


class BlockBorders:
    # assign default values; all zeros implies invalid QRectF; so no truncation applied
    def __init__(self, src=QRectF(), rec=QRectF()) -> None:
        # creates new object instead of creating a reference to existing border
        self.srcBorder = QRectF(src)
        self.recBorder = QRectF(rec)

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        bordersElem = doc.createElement('borders')

        srcElem = doc.createElement('src_border')
        bordersElem.appendChild(srcElem)

        # do top & left first; this *anchors* the QRectF
        srcElem.setAttribute('ymin', str(self.srcBorder.top()))
        srcElem.setAttribute('xmin', str(self.srcBorder.left()))
        # do bottom & right next; this defines width & height of the QRectF
        srcElem.setAttribute('ymax', str(self.srcBorder.bottom()))
        srcElem.setAttribute('xmax', str(self.srcBorder.right()))

        recElem = doc.createElement('rec_border')
        bordersElem.appendChild(recElem)

        # do top & left first; this *anchors* the QRectF
        recElem.setAttribute('ymin', str(self.recBorder.top()))
        recElem.setAttribute('xmin', str(self.recBorder.left()))
        # do bottom & right next; this defines width & height of the QRectF
        recElem.setAttribute('ymax', str(self.recBorder.bottom()))
        recElem.setAttribute('xmax', str(self.recBorder.right()))

        parent.appendChild(bordersElem)

        return bordersElem

    def readXml(self, parent: QDomNode):

        bordersElem = parent.namedItem('borders').toElement()

        srcElem = bordersElem.namedItem('src_border').toElement()
        if srcElem.isNull():
            return False

        xmin = toFloat(srcElem.attribute('xmin'))
        xmax = toFloat(srcElem.attribute('xmax'))
        self.srcBorder.setLeft(min(xmin, xmax))
        self.srcBorder.setRight(max(xmin, xmax))

        ymin = toFloat(srcElem.attribute('ymin'))
        ymax = toFloat(srcElem.attribute('ymax'))
        self.srcBorder.setTop(min(ymin, ymax))
        self.srcBorder.setBottom(max(ymin, ymax))

        recElem = bordersElem.namedItem('rec_border').toElement()
        if recElem.isNull():
            return False

        xmin = toFloat(recElem.attribute('xmin'))
        xmax = toFloat(recElem.attribute('xmax'))

        self.recBorder.setLeft(min(xmin, xmax))
        self.recBorder.setRight(max(xmin, xmax))

        ymin = toFloat(recElem.attribute('ymin'))
        ymax = toFloat(recElem.attribute('ymax'))
        self.recBorder.setTop(min(ymin, ymax))
        self.recBorder.setBottom(max(ymin, ymax))

        return True


# CLASS ###############################################################################


class RollBlock:
    def __init__(self, name: str = 'block-1') -> None:  # assign default name value
        self.name: str = name

        # block spatial extent
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

        self.borders = BlockBorders()
        self.templateList: list[RollTemplate] = []

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        blockElem = doc.createElement('block')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            blockElem.appendChild(nameElement)

        self.borders.writeXml(blockElem, doc)

        templatesElem = doc.createElement('template_list')
        blockElem.appendChild(templatesElem)

        for template in self.templateList:
            template.writeXml(templatesElem, doc)

        parent.appendChild(blockElem)

        return blockElem

    def readXml(self, parent: QDomNode):

        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        templatesElem = parent.namedItem('template_list').toElement()

        t = templatesElem.firstChildElement('template')

        if t.isNull():
            return False  # We need at least one template in a block

        while not t.isNull():
            template = RollTemplate()
            template.readXml(t)
            self.templateList.append(template)
            t = t.nextSiblingElement('template')

        if not self.borders.readXml(parent):
            return False

    def resetBoundingRect(self):

        for template in self.templateList:
            template.resetBoundingRect()

        self.srcBoundingRect = QRectF()  # reset it
        self.recBoundingRect = QRectF()  # reset it
        self.cmpBoundingRect = QRectF()  # reset it
        self.boundingBox = QRectF()  # reset it

        # return all 3 as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)

    # We are in RollBlock here
    def calcBoundingRect(self, roll=True):
        for template in self.templateList:
            srcBounds, recBounds, cmpBounds = template.calcBoundingRect(self.borders.srcBorder, self.borders.recBorder, roll)
            self.srcBoundingRect |= srcBounds  # add it
            self.recBoundingRect |= recBounds  # add it
            self.cmpBoundingRect |= cmpBounds  # add it

        self.boundingBox = self.srcBoundingRect | self.recBoundingRect
        # return all 3 as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)


# CLASS ###############################################################################


class RollTranslate:
    # assign default name value
    def __init__(self, name: str = '') -> None:
        self.name = name
        # Minimum (default) value
        self.steps = 1
        self.increment = QVector3D()
        self.azimuth = 0.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        translateElem = doc.createElement('translate')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            translateElem.appendChild(nameElement)

        translateElem.setAttribute('n', str(self.steps))
        translateElem.setAttribute('dx', str(self.increment.x()))
        translateElem.setAttribute('dy', str(self.increment.y()))
        translateElem.setAttribute('dz', str(self.increment.z()))

        parent.appendChild(translateElem)

        return translateElem

    def readXml(self, parent: QDomNode):

        # The parent node has translate as tagname, so no need to find it first
        if parent.isNull():
            return False

        self.steps = int(parent.attribute('n'))
        self.increment.setX(toFloat(parent.attribute('dx')))
        self.increment.setY(toFloat(parent.attribute('dy')))
        self.increment.setZ(toFloat(parent.attribute('dyz')))

        return True


# CLASS ###############################################################################


class RollTemplate:
    # assign default name value
    def __init__(self, name: str = 'template-1') -> None:
        self.name: str = name
        self.nSrcSeeds = 0
        self.nRecSeeds = 0

        self.rollList: list[RollTranslate] = []
        self.seedList: list[RollSeed] = []

        # spatial extent of this template formed by the contributing seeds
        self.srcTemplateRect = QRectF()
        self.recTemplateRect = QRectF()
        self.cmpTemplateRect = QRectF()
        self.templateBox = QRectF()

        # spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        templateElem = doc.createElement('template')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            templateElem.appendChild(nameElement)

        rollsElem = doc.createElement('roll_list')
        templateElem.appendChild(rollsElem)

        for roll in self.rollList:
            # if roll.steps > 1:
            roll.writeXml(rollsElem, doc)

        seedsElem = doc.createElement('seed_list')
        templateElem.appendChild(seedsElem)

        for seed in self.seedList:
            seed.writeXml(seedsElem, doc)

        parent.appendChild(templateElem)

        return templateElem

    def readXml(self, parent: QDomNode):

        nameElem = parent.namedItem('name').toElement()                         # get the name first
        if not nameElem.isNull():
            self.name = nameElem.text()

        rollsElem = parent.namedItem('roll_list').toElement()                   # get the roll steps next
        r = rollsElem.firstChildElement('translate')

        while not r.isNull():
            translate = RollTranslate()
            translate.readXml(r)  # the REAL parent is actually the roll_list
            self.rollList.append(translate)
            r = r.nextSiblingElement('translate')

        while len(self.rollList) < 3:                                           # Make sure there are 3 roll steps in the list
            self.rollList.insert(0, RollTranslate())

        seedsElem = parent.namedItem('seed_list').toElement()                   # finally, get the seeds
        s = seedsElem.firstChildElement('seed')

        if s.isNull():
            raise AttributeError('We need at least TWO SEEDS in a template (src & rec')

        while not s.isNull():
            seed = RollSeed()
            seed.readXml(s)
            self.seedList.append(seed)
            s = s.nextSiblingElement('seed')

        return True

    def resetBoundingRect(self):
        for seed in self.seedList:
            seed.resetBoundingRect()

        # reset spatial extent of this template formed by the contributing seeds
        self.srcTemplateRect = QRectF()
        self.recTemplateRect = QRectF()
        self.cmpTemplateRect = QRectF()
        self.templateBox = QRectF()

        # reset spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

    def rollSeed(self, seed):
        # get the pre-calculated seed's boundingbox
        seedBoundingBox = seed.boundingBox
        # start here, with a rect before rolling it
        rolledBoundingRect = QRectF(seedBoundingBox)

        for rollStep in self.rollList:                                          # iterate through all roll steps
            # create a copy to roll around
            seedIter = QRectF(seedBoundingBox)

            # if we get a 0 here, there's no additional rolling occurring
            for _ in range(rollStep.steps - 1):
                # apply a roll step on the seed area
                seedIter.translate(rollStep.increment.toPointF())
                # increase the area with new seed position
                rolledBoundingRect |= seedIter

        return rolledBoundingRect

    # we're in RollTemplate here
    def calcBoundingRect(self, srcBorder=QRectF(), recBorder=QRectF(), roll=True):
        for seed in self.seedList:
            # get the seed's boundingbox
            seedBounds = seed.calcBoundingRect()

            if seed.type == 0 and roll is True:                                 # rolling grid of seeds
                if seed.bSource:                                                # it's a source seed
                    # take note of it; handy for QC
                    self.nSrcSeeds += 1
                    # add it taking roll along into account
                    self.srcTemplateRect |= self.rollSeed(seed)
                    # seed's extent limited by Block's src border; needed when painting
                    seed.blockBorder = srcBorder
                else:
                    # take note of it; handy for QC
                    self.nRecSeeds += 1
                    # add it taking roll along into account
                    self.recTemplateRect |= self.rollSeed(seed)
                    # seed's extent limited by Block's rec border; needed when painting
                    seed.blockBorder = recBorder
            else:
                if seed.bSource:                                                # it's a source seed
                    # take note of it; handy for QC
                    self.nSrcSeeds += 1
                    # add it; no roll along
                    self.srcTemplateRect |= seedBounds
                    # seed's extent limited by Block's src border; needed when painting
                    seed.blockBorder = srcBorder
                else:
                    # take note of it; handy for QC
                    self.nRecSeeds += 1
                    # add it; no roll along
                    self.recTemplateRect |= seedBounds
                    # seed's extent limited by Block's rec border; needed when painting
                    seed.blockBorder = recBorder

        # get the normalized position of all 'grown' seeds in a template
        self.srcTemplateRect = self.srcTemplateRect.normalized()
        # the next step is to 'roll' these templates in the 'roll steps'
        self.recTemplateRect = self.recTemplateRect.normalized()

        # traces are generated WITHIN a template, and a cmp area results between the sources and the receives
        TL = (self.srcTemplateRect.topLeft() + self.recTemplateRect.topLeft()) / 2.0
        BR = (self.srcTemplateRect.bottomRight() + self.recTemplateRect.bottomRight()) / 2.0
        # the cmp area sits in the middle between source and receiver area
        self.cmpTemplateRect = QRectF(TL, BR)

        # overall size of a template
        self.templateBox = self.srcTemplateRect | self.recTemplateRect

        # deal with the block border(s) that has been handed down from block to template
        # create copy that may be truncated
        srcAdd = QRectF(self.srcTemplateRect)
        # check rect against block's src/rec border, if the border is valid
        srcAdd = clipRectF(srcAdd, srcBorder)

        # create copy that may be truncated
        recAdd = QRectF(self.recTemplateRect)
        # check rect against block's src/rec border, if the border is valid
        recAdd = clipRectF(recAdd, recBorder)

        # Recalc the cmp area as it is affected too
        if srcBorder.isValid() or recBorder.isValid():
            # if src or rec fall outside borders; no cmps will be valid
            if srcAdd.isValid() and recAdd.isValid():
                TL = (srcAdd.topLeft() + recAdd.topLeft()) / 2.0
                BR = (srcAdd.bottomRight() + recAdd.bottomRight()) / 2.0
                # the cmp area sits in the middle between source and receiver area
                cmpAdd = QRectF(TL, BR)
            else:
                # nothing to add, really; so use an empty rect
                cmpAdd = QRectF()
        else:
            # use the original value
            cmpAdd = QRectF(self.cmpTemplateRect)

        # Increase the src area with new template position
        self.srcBoundingRect = srcAdd
        # Increase the rec area with new template position
        self.recBoundingRect = recAdd
        # Increase the rec area with new template position
        self.cmpBoundingRect = cmpAdd
        # define 'own' boundingBox
        self.boundingBox = self.srcBoundingRect | self.recBoundingRect

        # print(f"SRC = x1:{self.srcBoundingRect.left():11.2f} y1:{self.srcBoundingRect.top():11.2f}, x2:{self.srcBoundingRect.right():11.2f} y2:{self.srcBoundingRect.bottom():11.2f}")
        # print(f"REC = x1:{self.recBoundingRect.left():11.2f} y1:{self.recBoundingRect.top():11.2f}, x2:{self.recBoundingRect.right():11.2f} y2:{self.recBoundingRect.bottom():11.2f}")
        # print(f"CMP = x1:{self.cmpBoundingRect.left():11.2f} y1:{self.cmpBoundingRect.top():11.2f}, x2:{self.cmpBoundingRect.right():11.2f} y2:{self.cmpBoundingRect.bottom():11.2f}")

        # return all 3 as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)


# CLASS ###############################################################################


class RollSurvey(pg.GraphicsObject):
    progress = pyqtSignal(int)                                                  # signal to keep track of worker thread progress

    # See: https://github.com/pyqtgraph/pyqtgraph/blob/develop/examples/CustomGraphItem.py
    # This example gives insight in the mouse drag event

    # assign default name value
    def __init__(self, name: str = 'Untitled') -> None:

        pg.GraphicsObject.__init__(self)
        self.mouseGrabbed = False                                               # needed to speed up drawing, whilst dragging

        self.nShotPoint = 0                                                     # managed in worker thread
        self.nShotPoints = -1                                                   # set at -1 to initialize calculations
        self.nRelRecord = -1                                                    # set at -1 to initialize calculations
        self.nRecRecord = -1                                                    # set at -1 to initialize calculations
        self.nLastRecLine = -9999                                               # to set up the first rec-point in a rel-record
        self.nNextRecLine = 0                                                   # to control moving along with rel-records

        self.threadProgress = 0                                                 # progress percentage
        self.errorText = None                                                   # text explaining which error occurred

        self.binTransform = None                                                # binning transform
        self.cmpTransform = None                                                # plotting transform local <--> global CRS
        self.glbTransform = None                                                # transform to display binning results
        self.stkTransform = None                                                # transform to *show* line & stake numbers from Orig(0.0, 0.0) = (1000, 1000)
        self.st2Transform = None                                                # transform to *calc* line & stake numbers from Orig(0.0, 0.0) = (1000, 1000)

        # self.installEventFilter(self)                                         # captures events through an event filter
        # self.setAcceptDrops(True)                                             # needed to capture these events (Nrs 186, 186). See: https://groups.google.com/g/pyqtgraph/c/OKY-Y_rSlL4

        # # See: https://doc.qt.io/qt-6/qgraphicsitem.html
        # self.setFlags(QGraphicsItem.ItemIsMovable)
        # note: the consequence of using QGraphicsItem.ItemIsMovable
        # is that the item becomes DETACHED from the X-axis and Y-axis !!! DO NOT USE !

        # self.setFlags(QGraphicsItem.ItemIsSelectable)
        # note: the consequence of using QGraphicsItem.ItemIsSelectable
        # is that the moving the chart is significantly delayed !!! DO NOT USE !

        # survey spatial extent
        self.srcBoundingRect = QRectF()                                         # source extent
        self.recBoundingRect = QRectF()                                         # receiver extent
        self.cmpBoundingRect = QRectF()                                         # cmp extent
        self.boundingBox = QRectF()                                             # src|rec extent

        # survey configuration
        self.crs = QgsCoordinateReferenceSystem()                               # create invalid crs object
        self.type = surveyType.Orthogonal
        self.name: str = name

        # survey painting mode
        self.paintMode = paintMode.allTemplates

        # survey limits
        self.binning = RollBinning()
        self.offset = RollOffset()
        self.output = RollOutput()
        self.angles = RollAngles()
        self.unique = RollUnique()

        # survey grid
        self.grid = RollBinGrid()

        # reflector types
        self.globalPlane = RollPlane()
        self.localPlane = None
        self.globalSphere = RollSphere()
        self.localSphere = None

        # survey block list
        self.blockList: list[RollBlock] = []

        # pattern list
        self.patternList: list[RollPattern] = []

        # seed list; list of seeds, created seperately for quick painting of non-rolling seeds
        self.seedList: list[RollSeed] = []

    def calcTransforms(self):
        x = self.grid.orig.x()
        y = self.grid.orig.y()
        p = self.grid.angle
        q = self.grid.scale.x()
        r = self.grid.scale.y()

        self.glbTransform = QTransform()
        self.glbTransform.translate(x, y)
        self.glbTransform.rotate(p)
        self.glbTransform.scale(q, r)

        config.glbTransform = self.glbTransform                              # for global access to this transform

        # set up a QMatrix4x4 using the three transform steps (translate, rotate, scale)
        # glbMatrix1 = QMatrix4x4()
        # glbMatrix1.translate(QVector3D(x, y, 0))
        # glbMatrix1.rotate(p, 0.0, 0.0, 1.0)
        # glbMatrix1.scale(q, r)
        # set up a QMatrix4x4 using a QTransform
        # glbMatrix2 = QMatrix4x4(self.glbTransform)
        # both matrices are the same, so using a QMatrix4x4 from QTransform is working fine
        # next, a not working attempt to transform the plane itself directly from global to local coordinates:
        # M0    = QMatrix4x4(self.glbTransform)                                 # create 4D matrix from transform
        # M1, _ = M0.inverted()                                                 # invert the matrix
        # # M2  = M1.transposed()                                               # transpose the matrix
        # n     = M1.mapVector(self.globalPlane.normal)                         # transform the normal
        # l     = n1.length()                                                   # find out that l != 1.0 (not always)

        # transform the global reflection plane to local coordinates
        # See: https://stackoverflow.com/questions/7685495/transforming-a-3d-plane-using-a-4x4-matrix
        # See: https://math.stackexchange.com/questions/2502857/transform-plane-to-another-coordinate-system
        # See: https://math.stackexchange.com/questions/3123130/transforming-a-plane
        # See: https://www.cs.brandeis.edu/~cs155/Lecture_07_6.pdf
        # See: https://cseweb.ucsd.edu/classes/wi18/cse167-a/lec3.pdf
        # See: http://www.songho.ca/opengl/gl_normaltransform.html
        # admittedly; the transform proved to be tricky when scaling (s != 1.0) is allowed.
        # the great escape was to set up the plane using three points in the global space
        # by building up the local plane from 3 transformed points, the correct normal was found
        # the plane's anchor is simply one of the three points that were used for the transform

        toLocalTransform, _ = self.glbTransform.inverted()                      # get inverse transform

        o0 = self.globalPlane.anchor                                            # get the plane's anchor
        o1 = toLocalTransform.map(o0.toPointF())                                # transform the 2D point
        o2 = QVector3D(o1.x(), o1.y(), o0.z())                                  # 3D point in local coordinates

        p0 = o0 + QVector3D(1000.0, 0.0, 0.0)                                   # shift the anchor in x-direction
        p1 = toLocalTransform.map(p0.toPointF())                                # transform the shifted 2D point
        p2 = QVector3D(p1.x(), p1.y(), self.globalPlane.depthAt(p0.toPointF()))   # 3D point in local coordinates

        q0 = o0 + QVector3D(0.0, 1000.0, 0.0)                                   # shift the anchor in y-direction
        q1 = toLocalTransform.map(q0.toPointF())                                # transform the shifted 2D point
        q2 = QVector3D(q1.x(), q1.y(), self.globalPlane.depthAt(q0.toPointF()))   # 3D point in local coordinates

        n = QVector3D.normal(o2, p2, q2)                                        # Get the normalized normal vector of a plane defined by p2 - o2 and q2 - o2
        self.localPlane = RollPlane.fromAnchorAndNormal(o2, n)                  # pylint: disable=E1101

        # now define the localSphere, based on the globalSphere
        assert q == r, 'x- and y-scales need to be identical, preferrably 1.0'

        r0 = self.globalSphere.radius
        r1 = r0 * q
        o0 = self.globalSphere.origin
        s1 = toLocalTransform.map(o0.toPointF())                                  # transform the 2D point to local coordinates
        s2 = QVector3D(s1.x(), s1.y(), o0.z() * q)                              # 3D point in local coordinates, with z axis scaled as well
        self.localSphere = RollSphere(s2, r1)                                   # initiate the local sphere

        w = self.output.rctOutput.width()
        h = self.output.rctOutput.height()
        x0 = self.output.rctOutput.left()
        y0 = self.output.rctOutput.top()

        dx = self.grid.binSize.x()
        dy = self.grid.binSize.y()
        ox = self.grid.binShift.x()
        oy = self.grid.binShift.y()

        s0 = self.grid.stakeOrig.x()
        l0 = self.grid.stakeOrig.y()
        ds = self.grid.stakeSize.x()
        dl = self.grid.stakeSize.y()

        nx = math.ceil(w / dx)
        ny = math.ceil(h / dy)

        sx = w / nx
        sy = h / ny

        # it is fine to have 'zeroes' where there is no fold
        self.output.binOutput = np.zeros(shape=(nx, ny), dtype=np.uint32)
        # start with empty array of the right size and type
        self.output.minOffset = np.empty(shape=(nx, ny), dtype=np.float32)
        # start with empty array of the right size and type
        self.output.maxOffset = np.empty(shape=(nx, ny), dtype=np.float32)
        # start min offset with +inf
        self.output.minOffset.fill(np.Inf)
        # start max offset with -inf
        self.output.maxOffset.fill(np.NINF)

        self.binTransform = QTransform()
        self.binTransform.translate(x0, y0)
        self.binTransform.scale(dx, dy)
        self.binTransform, _ = self.binTransform.inverted()

        self.cmpTransform = QTransform()
        self.cmpTransform.translate(x0, y0)
        self.cmpTransform.scale(sx, sy)

        self.stkTransform = QTransform()
        self.stkTransform.translate(-ox, -oy)                                   # first shift origin by small offset (usually 1/2 bin size)
        self.stkTransform.scale(ds, dl)                                         # then scale it according to the stake / line intervals
        self.stkTransform.translate(-s0, -l0)                                   # then shift origin to the (stake, line) origin
        self.stkTransform, _ = self.stkTransform.inverted()                     # invert the transform before applying

        self.st2Transform = QTransform()
        self.st2Transform.scale(ds, dl)                                         # scale it according to the stake / line intervals
        self.st2Transform.translate(-s0, -l0)                                   # then shift origin to (stake, line) origin
        self.st2Transform, _ = self.st2Transform.inverted()                     # invert the transform before applying

    def noShotPoints(self):
        if self.nShotPoints == -1:
            return self.calcNoShotPoints()
        else:
            return self.nShotPoints

    def calcNoShotPoints(self) -> int:
        self.nShotPoints = 0
        for block in self.blockList:
            nBlockShots = 0
            for template in block.templateList:
                nTemplateShots = 0

                for seed in template.seedList:
                    nSeedShots = 0
                    if seed.bSource:                                            # Source seed
                        nSeedShots = 1                                          # at least one SP
                        for growStep in seed.grid.growList:                     # iterate through all grow steps
                            nSeedShots *= growStep.steps                        # multiply seed's shots at each level
                        nTemplateShots += nSeedShots                            # add to template's SPs

                for roll in template.rollList:
                    # template is rolled a number of times
                    nTemplateShots *= roll.steps

                nBlockShots += nTemplateShots
            self.nShotPoints += nBlockShots
        return self.nShotPoints

    def setupGeometryFromTemplates(self) -> bool:

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        try:
            # the numpy array with the list of source locations simply follows from self.nShotPoints
            self.output.srcGeom = np.zeros(shape=(self.nShotPoints), dtype=pntType1)

            # the numpy array with the list of relation records follows from the nr of shot points x max number of rec lines
            self.output.relGeom = np.zeros(shape=(self.nShotPoints), dtype=relType2)

            # The array with the list of receiver locations is the most difficult to determine.
            # It can be calculated using one of two different approaches :
            #   a) define a large (line, stake) grid and populate this for each line stake number that we come across
            #   b) just append 'new' receivers and remove duplicates, of which there will be many
            # the difficulty of a) is that you need to be sure of grid increments and start/end points
            # the easy part is that at the end the non-zero records can be gathered (filtered out)
            # the difficulty of b) is that the recGeom array will overflow, unless you remove duplicates at timely intervals
            # the easy part is that you don't have to setup a large grid with offset counters, which can be error prone
            # overall, approach b) seems more 'failsafe' and easier to implement.

            # for starters; assume there are 100 x as many receivers as shots in the survey
            self.output.recGeom = np.zeros(shape=(self.nShotPoints * 100), dtype=pntType1)
            success = self.geometryFromTemplates()
        except BaseException as e:
            self.errorText = str(e)
            success = False

        return success

    def geometryFromTemplates(self) -> bool:
        try:
            # get all blocks
            for nBlock, block in enumerate(self.blockList):
                for template in block.templateList:                             # get all templates
                    # how deep is the list ?
                    length = len(template.rollList)
                    if length == 0:
                        off0 = QVector3D(0.0, 0.0, 0.0)                         # always start at (0, 0, 0)
                        self.geomTemplate2(nBlock, block, template, off0)

                    elif length == 1:
                        # get the template boundaries
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D(0.0, 0.0, 0.0)                     # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            self.geomTemplate2(nBlock, block, template, off0)

                    elif length == 2:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D(0.0, 0.0, 0.0)                     # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j
                                self.geomTemplate2(nBlock, block, template, off1)

                    elif length == 3:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D(0.0, 0.0, 0.0)                     # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i

                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j

                                for k in range(template.rollList[2].steps):
                                    off2 = off1 + template.rollList[2].increment * k

                                    self.geomTemplate2(nBlock, block, template, off2)
                    else:
                        # do something recursively; not  implemented yet
                        raise NotImplementedError('More than three roll steps currently not allowed.')

        except StopIteration:
            self.errorText = 'geometry creation canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        #  first remove all remaining receiver duplicates
        self.output.recGeom = np.unique(self.output.recGeom)

        # trim rel & rec arrays removing any zeros, using the 'Uniq' == 1 condition.
        self.output.relGeom = self.output.relGeom[self.output.relGeom['Uniq'] == 1]
        self.output.recGeom = self.output.recGeom[self.output.recGeom['Uniq'] == 1]

        # set all values in one go at the end
        self.output.srcGeom['Uniq'] = 1
        self.output.srcGeom['InXps'] = 1
        self.output.srcGeom['Code'] = 'E1'

        self.output.recGeom['Uniq'] = 1
        self.output.recGeom['InXps'] = 1
        self.output.recGeom['Code'] = 'G1'

        self.output.relGeom['InSps'] = 1
        self.output.relGeom['InRps'] = 1

        # sort the three geometry arrays
        self.output.srcGeom.sort(order=['Index', 'Point', 'Line'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        return True

    def geomTemplate(self, nBlock, block, template, templateOffset):

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        # iterate over all seeds in a template, using the growList
        for srcSeed in template.seedList:
            while len(srcSeed.grid.growList) < 3:
                # First, make sure there are 3 grow steps for every srcSeed
                srcSeed.grid.growList.insert(0, RollTranslate())

            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            for i in range(srcSeed.grid.growList[0].steps):
                # start with a new PointF object
                srcOff0 = QVector3D(templateOffset)
                srcOff0 += srcSeed.grid.growList[0].increment * i

                for j in range(srcSeed.grid.growList[1].steps):
                    srcOff1 = srcOff0 + srcSeed.grid.growList[1].increment * j

                    for k in range(srcSeed.grid.growList[2].steps):
                        # we now have the correct offset
                        srcOff2 = srcOff1 + srcSeed.grid.growList[2].increment * k
                        # we now have the correct source location
                        srcLoc = srcOff2 + srcSeed.origin

                        if QThread.currentThread().isInterruptionRequested():   # maybe stop at each shot...
                            raise StopIteration

                        # do this now, some shots may fall out of the areal limits later
                        self.nShotPoint += 1
                        # a new shotpoint always starts with new relation records
                        self.nLastRecLine = -9999
                        # apply integer divide
                        threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                        if threadProgress > self.threadProgress:
                            self.threadProgress = threadProgress
                            # print("progress % = ", threadProgress)
                            self.progress.emit(threadProgress + 1)

                        # is src within block limits (or is the border empty) ?
                        if containsPoint3D(block.borders.srcBorder, srcLoc):

                            # useful source point; update the source geometry list here
                            # need to step back by one to arrive at start of array
                            nSrc = self.nShotPoint - 1
                            # line & stake nrs for source point
                            srcStake = self.st2Transform.map(srcLoc.toPointF())
                            srcGlob = self.glbTransform.map(srcLoc.toPointF())  # we need global positions

                            self.output.srcGeom[nSrc]['Line'] = int(srcStake.y())
                            self.output.srcGeom[nSrc]['Point'] = int(srcStake.x())
                            self.output.srcGeom[nSrc]['Index'] = nBlock % 10 + 1
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'           # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0            # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()     # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()     # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()     # z-component of 3D-location

                            # now iterate over all seeds to find the receivers
                            for recSeed in template.seedList:                   # iterate over all seeds in a template
                                while len(recSeed.grid.growList) < 3:
                                    # First, make sure there are 3 grow steps for every recSeed
                                    recSeed.grid.growList.insert(0, RollTranslate())

                                if recSeed.bSource:                             # work with receiver seeds here
                                    continue

                                # patches increase here
                                for l in range(recSeed.grid.growList[0].steps):
                                    # start with a new QVector3D object
                                    recOff0 = QVector3D(templateOffset)
                                    recOff0 += recSeed.grid.growList[0].increment * l

                                    # lines increase here
                                    for m in range(recSeed.grid.growList[1].steps):
                                        recOff1 = recOff0 + recSeed.grid.growList[1].increment * m

                                        # points increase here
                                        for n in range(recSeed.grid.growList[2].steps):
                                            recOff2 = recOff1 + recSeed.grid.growList[2].increment * n

                                            recLoc = QVector3D(recOff2)
                                            # we now have the correct receiver location
                                            recLoc += recSeed.origin

                                            # print("recLoc: ", recLoc.x(), recLoc.y(), recLoc.z() )

                                            # is it within block limits (or is the border empty) ?
                                            if containsPoint3D(block.borders.recBorder, recLoc):

                                                # now we have a valid src-point and rec-point
                                                # time to work with the relation records

                                                # line & stake nrs for receiver point
                                                recStake = self.st2Transform.map(recLoc.toPointF())
                                                # we need global positions for all points
                                                recGlob = self.glbTransform.map(recLoc.toPointF())

                                                self.nNextRecLine = int(recStake.y())
                                                # we're on a 'new' receiver line and need a new rel-record
                                                if self.nNextRecLine != self.nLastRecLine:
                                                    self.nLastRecLine = self.nNextRecLine

                                                    self.nRelRecord += 1                            # we have a new relation record

                                                    recMin = int(recStake.x())
                                                    recMax = int(recStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNo'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    recMin = min(int(recStake.x()), self.output.relGeom[self.nRelRecord]['RecMin'])
                                                    recMax = max(int(recStake.x()), self.output.relGeom[self.nRelRecord]['RecMax'])
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    # append 1000 more records
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)

                                                # we have a new receiver record
                                                self.nRecRecord += 1

                                                self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'                # can do this in one go at the end
                                                # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0                 # not needed; zero when initialized
                                                self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()          # x-component of 3D-location
                                                self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()          # y-component of 3D-location
                                                self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()          # z-component of 3D-location
                                                # we want to remove empty records at the end
                                                self.output.recGeom[self.nRecRecord]['Uniq'] = 1

                                                # apply self.output.recGeom.resize(N) when more memory is needed
                                                arraySize = self.output.recGeom.shape[0]
                                                if self.nRecRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    # first remove all duplicates
                                                    self.output.recGeom = np.unique(self.output.recGeom)
                                                    # get array size (again)
                                                    arraySize = self.output.recGeom.shape[0]
                                                    # adjust nRecRecord to the next available spot
                                                    self.nRecRecord = arraySize
                                                    # append 1000 more receiver records
                                                    self.output.recGeom.resize(arraySize + 1000, refcheck=False)

    def geomTemplate2(self, nBlock, block, template, templateOffset):
        """use numpy arrays instead of iterating over the growList"""

        # convert the template offset to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            # deal with block's source  border if it isn't null()
            if not block.borders.srcBorder.isNull():
                l = block.borders.srcBorder.left()
                r = block.borders.srcBorder.right()
                t = block.borders.srcBorder.top()
                b = block.borders.srcBorder.bottom()
                I = (srcArray[:, 0] >= l) & (srcArray[:, 0] <= r) & (srcArray[:, 1] >= t) & (srcArray[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue                                                    # if nothing succeeds; pick next seed
                srcArray = srcArray[I, :]                                       # filter the source array

            for src in srcArray:                                                # iterate over all sources

                self.nShotPoint += 1
                self.nLastRecLine = -9999                                       # a new shotpoint always starts with new relation records

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # useful source point; update the source geometry list here
                nSrc = self.nShotPoint - 1                                      # need to step back by one to arrive at start of array

                # determine line & stake nrs for source point
                srcX = src[0]
                srcY = src[1]
                srcZ = src[2]

                srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)            # get line and point indices
                srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)            # we need global positions

                self.output.srcGeom[nSrc]['Line'] = int(srcStkY)
                self.output.srcGeom[nSrc]['Point'] = int(srcStkX)
                self.output.srcGeom[nSrc]['Index'] = nBlock % 10 + 1
                # self.output.srcGeom[nSrc]['Code' ] = 'E1'                       # can do this in one go at the end
                # self.output.srcGeom[nSrc]['Depth'] = 0.0                        # not needed; zero when initialized
                self.output.srcGeom[nSrc]['East'] = srcLocX
                self.output.srcGeom[nSrc]['North'] = srcLocY
                self.output.srcGeom[nSrc]['LocX'] = srcX                       # x-component of 3D-location
                self.output.srcGeom[nSrc]['LocY'] = srcY                       # y-component of 3D-location
                self.output.srcGeom[nSrc]['Elev'] = srcZ                       # z-value not affected by transform

                # now iterate over all seeds to find the receivers
                for recSeed in template.seedList:                               # iterate over all rec seeds in a template
                    if recSeed.bSource:                                         # work with receiver seeds here
                        continue

                    # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                    recPoints = recSeed.pointArray + npTemplateOffset

                    # deal with block's receiver border if it isn't null()
                    if not block.borders.recBorder.isNull():
                        l = block.borders.recBorder.left()
                        r = block.borders.recBorder.right()
                        t = block.borders.recBorder.top()
                        b = block.borders.recBorder.bottom()
                        I = (recPoints[:, 0] >= l) & (recPoints[:, 0] <= r) & (recPoints[:, 1] >= t) & (recPoints[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue
                        recPoints = recPoints[I, :]

                    for rec in recPoints:                                       # iterate over all receivers

                        # determine line & stake nrs for source point
                        recX = rec[0]
                        recY = rec[1]
                        recZ = rec[2]

                        recStkX, recStkY = self.st2Transform.map(recX, recY)    # get line and point indices
                        recLocX, recLocY = self.glbTransform.map(recX, recY)    # we need global positions

                        # we have a new receiver record
                        self.nRecRecord += 1

                        self.output.recGeom[self.nRecRecord]['Line'] = int(recStkY)
                        self.output.recGeom[self.nRecRecord]['Point'] = int(recStkX)
                        self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                        # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'                # can do this in one go at the end
                        # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0                 # not needed; zero when initialized
                        self.output.recGeom[self.nRecRecord]['East'] = recLocX
                        self.output.recGeom[self.nRecRecord]['North'] = recLocY
                        self.output.recGeom[self.nRecRecord]['LocX'] = recX                # x-component of 3D-location
                        self.output.recGeom[self.nRecRecord]['LocY'] = recY                # y-component of 3D-location
                        self.output.recGeom[self.nRecRecord]['Elev'] = recZ                # z-value not affected by transform
                        self.output.recGeom[self.nRecRecord]['Uniq'] = 1                   # we want to remove empty records at the end

                        # apply self.output.recGeom.resize(N) when more memory is needed, after cleaning duplicates
                        arraySize = self.output.recGeom.shape[0]
                        if self.nRecRecord + 100 > arraySize:                               # room for less than 100 left ?
                            self.output.recGeom = np.unique(self.output.recGeom)            # first remove all duplicates
                            arraySize = self.output.recGeom.shape[0]                        # get array size (again)
                            self.nRecRecord = arraySize                                     # adjust nRecRecord to the next available spot
                            self.output.recGeom.resize(arraySize + 10000, refcheck=False)   # append 10000 more records

                        # time to work with the relation records, now we have both a valid src-point and rec-point;
                        self.nNextRecLine = int(recStkY)
                        if self.nNextRecLine != self.nLastRecLine:              # we're on a 'new' receiver line and need a new rel-record
                            self.nLastRecLine = self.nNextRecLine

                            self.nRelRecord += 1                                # new relation record; fill it in completely
                            self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStkY)
                            self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStkX)
                            self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                            self.output.relGeom[self.nRelRecord]['RecNo'] = self.nShotPoint
                            self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStkY)
                            self.output.relGeom[self.nRelRecord]['RecMin'] = int(recStkX)
                            self.output.relGeom[self.nRelRecord]['RecMax'] = int(recStkX)
                            self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                            self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                        else:                                                   # existing relation record; update min/max rec stake numbers
                            recMin = min(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMin'])
                            recMax = max(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMax'])
                            self.output.relGeom[self.nRelRecord]['RecMin'] = recMin
                            self.output.relGeom[self.nRelRecord]['RecMax'] = recMax

                        # apply self.output.relGeom.resize(N) when more memory is needed
                        arraySize = self.output.relGeom.shape[0]
                        if self.nRelRecord + 100 > arraySize:                   # room for less than 100 left ?
                            # append 1000 more records
                            self.output.relGeom.resize(arraySize + 1000, refcheck=False)

    def setupBinFromGeometry(self, fullAnalysis) -> bool:
        """this routine is used for both geometry files and SPS files"""

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        # Now do the binning
        if fullAnalysis:
            success = self.binFromGeometry4(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromGeometry4(False)

    def binFromGeometry(self, fullAnalysis) -> bool:
        """only cmp binning implemented here, using a nested dictionary to access the src position"""

        self.threadProgress = 0                                                 # always start at zero

        # as we access the srcGeom and relGeom from relGem, we need to create some quick lookup tables
        # nested dictionary to access src positions
        self.output.srcDict = defaultdict(dict)
        for record in self.output.srcGeom:
            point = QPointF(record['East'], record['North'])
            self.output.srcDict[int(record['Line'])][int(record['Point'])] = point

        # nested dictionary to access rec positions
        self.output.recDict = defaultdict(dict)
        for record in self.output.recGeom:
            point = QPointF(record['East'], record['North'])
            self.output.recDict[int(record['Line'])][int(record['Point'])] = point

        toLocalTransform = QTransform()                                         # setup empty (unit) transform
        toLocalTransform, _ = self.glbTransform.inverted()

        # we iterate from RecMin to RecMax in the relation records
        # so we need to find out what the incremental station value is
        recPoints = self.output.recGeom['Point']
        uniquePoints = np.unique(recPoints)
        nPoints = uniquePoints.shape[0]
        nMax = uniquePoints[-1]
        nMin = uniquePoints[0]
        delta = (nMax - nMin) / (nPoints - 1)
        delta = int(round(delta))

        nRelRecords = self.output.relGeom.shape[0]

        try:
            for index, relRecord in enumerate(self.output.relGeom):

                # maybe stop at each record...
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                threadProgress = (100 * index) // nRelRecords
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                try:
                    srcGlob = self.output.srcDict[relRecord['SrcLin']][relRecord['SrcPnt']]
                except KeyError:
                    continue

                recMin = int(round(relRecord['RecMin']))
                recMax = int(round(relRecord['RecMax']))
                # recNum = (recMax - recMin) / delta + 1

                for j in range(recMin, recMax + delta, delta):

                    try:
                        recGlob = self.output.recDict[relRecord['RecLin']][j]
                    except KeyError:
                        continue

                    cmpLoc = QPointF()

                    cmpBinning = True
                    if cmpBinning:
                        cmpGlob = 0.5 * (srcGlob + recGlob)

                    cmpLoc = toLocalTransform.map(cmpGlob)

                    if containsPoint2D(self.output.rctOutput, cmpLoc):
                        # now we need to process a valid trace
                        # local position in bin area
                        loc = self.binTransform.map(cmpLoc)
                        nx = int(loc.x())
                        ny = int(loc.y())

                        try:                                                    # index nx, ny might be wrong
                            # need local positions for inline/crossline offset criteria
                            srcLoc = QPointF()
                            recLoc = QPointF()
                            srcLoc = toLocalTransform.map(srcGlob)
                            recLoc = toLocalTransform.map(recGlob)

                            # determine offset vector on the *local* grid
                            rctOffset = recLoc - srcLoc

                            # first check if offset falls within offset analysis rectangle
                            if containsPoint2D(self.offset.rctOffsets, rctOffset):

                                # now do the 'expensive' sqrt operation
                                radOffset = math.hypot(rctOffset.x(), rctOffset.y())

                                # now check radial offset range. Only do this test if max offset > 0.0
                                if self.offset.radOffsets.y() == 0.0 or (radOffset < self.offset.radOffsets.y() and radOffset >= self.offset.radOffsets.x()):

                                    if fullAnalysis:
                                        # ('SrcX', np.float32), ('SrcY', np.float32),    # Src (x, y)
                                        # ('RecX', np.float32), ('RecY', np.float32),    # Rec (x, y)
                                        # ('CmpX', np.float32), ('CmpY', np.float32),    # Cmp (x, y); needed for spider plot when binning against dipping plane
                                        # ('SrcL', np.int32  ), ('SrcP', np.int32  ),    # SrcLine, SrcPoint
                                        # ('RecL', np.int32  ), ('RecP', np.int32  )])   # RecLine, RecPoint

                                        fold = self.output.binOutput[nx, ny]
                                        if fold < self.grid.fold:                   # prevent overwriting next bin
                                            # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(),
                                            #                                         recLoc.x(), recLoc.y(),
                                            #                                         cmpLoc.x(), cmpLoc.y(),
                                            #                                         0, 0, 0, 0)
                                            # line & stake nrs for reporting in extended np-array
                                            stkLoc = self.st2Transform.map(cmpLoc)
                                            self.output.anaOutput[nx][ny][fold][0] = int(stkLoc.x())        # pylint: disable=E1136
                                            self.output.anaOutput[nx][ny][fold][1] = int(stkLoc.y())
                                            self.output.anaOutput[nx][ny][fold][2] = fold + 1               # to make fold run from 1 to N
                                            self.output.anaOutput[nx][ny][fold][3] = round(srcLoc.x(), 1)   # round to overcome transform inaccuracies
                                            self.output.anaOutput[nx][ny][fold][4] = round(srcLoc.y(), 1)
                                            self.output.anaOutput[nx][ny][fold][5] = round(recLoc.x(), 1)
                                            self.output.anaOutput[nx][ny][fold][6] = round(recLoc.y(), 1)
                                            self.output.anaOutput[nx][ny][fold][7] = round(cmpLoc.x(), 1)
                                            self.output.anaOutput[nx][ny][fold][8] = round(cmpLoc.y(), 1)
                                        # self.output.anaOutput[nx][ny][fold][9]

                                        # print (self.output.anaOutput[nx, ny, fold])

                                    # all offset criteria have been fullfilled; use the trace
                                    self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                                    self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], radOffset)
                                    self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], radOffset)
                                # print (cmpLoc.x(), cmpLoc.y(), loc.x(), loc.y(), stk.x(), stk.y(), self.output.binOutput[nx, ny])

                        except IndexError:
                            continue

        except StopIteration:
            self.errorText = 'binning from geometry canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        # min/max fold is straightforward
        self.output.maximumFold = self.output.binOutput.max()
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.output.minMinOffset = self.output.minOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF
        # calc max values against (-inf) minimum
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.output.maxMaxOffset = self.output.maxOffset.max()
        # replace (-inf) by (inf) for min values
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf
        # calc min offset against min (inf) values
        self.output.minMaxOffset = self.output.maxOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        return True

    def binFromGeometry2(self, fullAnalysis) -> bool:
        """only cmp binning implemented, working from the shot points rather than the relation records"""

        self.threadProgress = 0                                                 # always start at zero

        toLocalTransform = QTransform()                                         # setup empty (unit) transform
        toLocalTransform, _ = self.glbTransform.inverted()                      # transform to local survey coordinates

        # if needed, fill the source and receiver arrays with local coordinates
        minLocX = np.min(self.output.srcGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.srcGeom['LocY'])                           # determine if there's any data there...
        if minLocX == maxLocX == 0.0:                                           # comparisons can be chained
            # See: https://stackoverflow.com/questions/6304509/are-there-sideeffects-in-python-using-if-a-b-c-pass
            # See: https://docs.python.org/3/library/stdtypes.html
            for record in self.output.srcGeom:
                srcX = record['East']
                srcY = record['North']
                x, y = toLocalTransform.map(srcX, srcY)
                record['LocX'] = x
                record['LocY'] = y

        minLocX = np.min(self.output.recGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.recGeom['LocY'])                           # determine if there's any data there...
        if minLocX == maxLocX == 0.0:                                           # comparisons can be chained
            for record in self.output.recGeom:
                recX = record['East']
                recY = record['North']
                x, y = toLocalTransform.map(recX, recY)
                record['LocX'] = x
                record['LocY'] = y

        # relType2= np.dtype([('SrcLin', 'f4'),   # F10.2
        #                     ('SrcPnt', 'f4'),   # F10.2
        #                     ('SrcInd', 'i4'),   # I1
        #                     ('RecNo',  'i4'),   # I8
        #                     ('RecLin', 'f4'),   # F10.2
        #                     ('RecMin', 'f4'),   # F10.2
        #                     ('RecMax', 'f4'),   # F10.2
        #                     ('RecInd', 'i4'),   # I1
        #                     ('Uniq',   'i4'),   # check if record is unique
        #                     ('InSps',  'i4'),   # check if record is orphan
        #                     ('InRps',  'i4') ]) # check if record is orphan

        # pntType1= np.dtype([('Line',   'f4'),   # F10.2
        #                     ('Point',  'f4'),   # F10.2
        #                     ('Index',  'i4'),   # I1
        #                     ('Code',   'U2'),   # A2
        #                     ('Depth',  'f4'),   # I4
        #                     ('East',   'f4'),   # F9.1
        #                     ('North',  'f4'),   # F10.1
        #                     ('Elev',   'f4'),   # F6.1
        #                     ('Uniq',   'i4'),   # check if record is unique
        #                     ('InXps',  'i4'),   # check if record is orphan
        #                     ('LocX',   'f4'),   # F9.1
        #                     ('LocY',   'f4') ]) # F10.1

        # pntType2= np.dtype([('Line',   'f4'),   # F10.2
        #                     ('Point',  'f4'),   # F10.2
        #                     ('Index',  'i4'),   # I1
        #                     ('Code',   'U2'),   # A2
        #                     ('Depth',  'f4'),   # I4
        #                     ('East',   'f4'),   # F9.1
        #                     ('North',  'f4'),   # F10.1
        #                     ('Elev',   'f4'),   # F6.1
        #                     ('Uniq',   'i4'),   # check if record is unique
        #                     ('InXps',  'i4') ]) # check if record is orphan

        # Find out where shots start and stop in the relation file
        # Therefore create reference to relation file.

        # The 1st element is the first entry into the rel file for a shot number
        # The 2nd element is the last  entry into the rel file for a shot number
        relFileIndices = np.zeros(shape=(self.output.srcGeom.shape[0], 2), dtype=np.int32)

        # now iterate over srcGeom to check where shots are referenced
        # the next for loop assumes that:
        # 1. any duplicate records have been removed
        # 2. any orphans (missing corresponding src/rel records) have been removed
        # 2. source records are ordered (sorted) on shotindex / shotline / shotpoint
        # 3. relation records are sorted on shotindex / shotline / shotpoint followed by recindex / recline / recpoint

        assert self.output.relGeom[0]['SrcLin'] == self.output.srcGeom[0]['Line'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcPnt'] == self.output.srcGeom[0]['Point'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcInd'] == self.output.srcGeom[0]['Index'], 'error in geometry files'

        # to be sure; sort the three geometry arrays in order: index; line; point
        self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        marker = 0
        for index, srcRecord in enumerate(self.output.srcGeom):                 # find the relevant relation records for each shot point

            relFileIndices[index][0] = marker
            for j in range(marker, self.output.relGeom.shape[0]):

                if self.output.relGeom[j]['SrcPnt'] == srcRecord['Point'] and self.output.relGeom[j]['SrcLin'] == srcRecord['Line'] and self.output.relGeom[j]['SrcInd'] == srcRecord['Index']:
                    relFileIndices[index][1] = j + 1                            # last number will stay out of scope for range: 0 - n
                else:
                    marker = j
                    break

        # now iterate over the shot points and select the range of applicable receivers
        # assume the receivers have been sorted index/line/point

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        try:
            for index, srcRecord in enumerate(self.output.srcGeom):
                # convert the source record to an [x, y, z] value
                srcPoints = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                minRecord = relFileIndices[index][0]                            # range of relevant relation records
                maxRecord = relFileIndices[index][1]

                if maxRecord == minRecord:                                      # no receivers found; move to next shot !
                    continue

                relSlice = self.output.relGeom[minRecord:maxRecord]             # create a slice out of the relation file

                recIndex = relSlice[0]['RecInd']
                minLine = np.min(relSlice['RecLin'])
                maxLine = np.max(relSlice['RecLin'])
                minMinPoint = np.min(relSlice['RecMin'])                        # determine if it is a purely square block
                maxMinPoint = np.max(relSlice['RecMin'])
                minMaxPoint = np.min(relSlice['RecMax'])
                maxMaxPoint = np.max(relSlice['RecMax'])

                if minMinPoint == maxMinPoint and minMaxPoint == maxMaxPoint:
                    # if it is a square block, make a simple single square selection in receiver array. See binTemplate4()
                    I = (
                        (self.output.recGeom['Index'] == recIndex)
                        & (self.output.recGeom['Line'] >= minLine)
                        & (self.output.recGeom['Line'] <= maxLine)
                        & (self.output.recGeom['Point'] >= minMinPoint)
                        & (self.output.recGeom['Point'] <= maxMaxPoint)
                    )
                    if np.count_nonzero(I) == 0:
                        continue                                                # no receivers found; move to next shot !
                    recPoints = self.output.recGeom[I]                           # select the filtered receivers

                else:
                    # there are different min/max rec points on different rec lines.
                    # we need to determine the recPoints line by line; per relation record

                    recPoints = np.zeros(shape=(0), dtype=pntType1)              # setup empty numpy array
                    for relRecord in relSlice:
                        recInd = relRecord['RecInd']
                        recLin = relRecord['RecLin']
                        recMin = relRecord['RecMin']
                        recMax = relRecord['RecMax']

                        # select appropriate receivers on a receiver line
                        I = (self.output.recGeom['Index'] == recInd) & (self.output.recGeom['Line'] == recLin) & (self.output.recGeom['Point'] >= recMin) & (self.output.recGeom['Point'] <= recMax)

                        recLine = self.output.recGeom[I]                        # select the filtered receivers
                        recPoints = np.concatenate((recPoints, recLine))          # need to supply arrays to be concatenated as a tuple !
                        # See: https://stackoverflow.com/questions/50997928/typeerror-only-integer-scalar-arrays-can-be-converted-to-a-scalar-index-with-1d

                # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
                # we combine recPoints with source point to create cmp array, define offsets, etc...

                # we are not dealing with the block's src border; should have been done while generating geometry
                # we are not dealing with the block's rec border; should have been done while generating geometry
                # it is essential that any orphans & duplicates in recPoints have been removed at this stage
                # for cmp and offset calcuations, we need numpy arrays in the form of local (x, y, z) coordinates

                recPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                recPoints[:, 0] = recPoints['LocX']
                recPoints[:, 1] = recPoints['LocY']
                recPoints[:, 2] = recPoints['Elev']

                # setup a cmp array with the same size as recPoints
                cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

                # create all cmp-locations for this shot point
                cmpPoints = (recPoints + srcPoints) * 0.5

                l = self.output.rctOutput.left()
                r = self.output.rctOutput.right()
                t = self.output.rctOutput.top()
                b = self.output.rctOutput.bottom()
                I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                cmpPoints = cmpPoints[I, :]                                           # filter the cmp-array
                recPoints = recPoints[I, :]                                           # filter the rec-array too, as we still need this for offsets

                ofVectors = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                ofVectors = recPoints - srcPoints                                    # define the offset array

                l = self.offset.rctOffsets.left()
                r = self.offset.rctOffsets.right()
                t = self.offset.rctOffsets.top()
                b = self.offset.rctOffsets.bottom()
                I = (ofVectors[:, 0] >= l) & (ofVectors[:, 0] <= r) & (ofVectors[:, 1] >= t) & (ofVectors[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                ofVectors = ofVectors[I, :]                                       # filter the offset-array
                cmpPoints = cmpPoints[I, :]                                       # filter the cmp-array too, as we still need this
                recPoints = recPoints[I, :]                                       # filter the rec-array too, as we still need this

                hypRRR = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                # calculate per row
                hypRRR = np.hypot(ofVectors[:, 0], ofVectors[:, 1])

                r1 = self.offset.radOffsets.x()                             # minimum radius
                r2 = self.offset.radOffsets.y()                             # maximum radius
                if r2 > 0:                                                  # we need to apply the radial offset selection criteria
                    I = (hypRRR[:] >= r1) & (hypRRR[:] <= r2)
                    if np.count_nonzero(I) == 0:
                        continue                                            # continue with next recSeed
                    # print(I)
                    hypRRR = hypRRR[I]                                      # filter the radial offset-array
                    ofVectors = ofVectors[I, :]                                   # filter the off-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]                                   # filter the cmp-array too, as we still need this
                    recPoints = recPoints[I, :]                                   # filter the rec-array too, as we still need this

                #  we have applied all filters now; time to save the traces that 'pass' all selection criteria

                # process all traces
                for count, cmp in enumerate(cmpPoints):
                    try:
                        cmpX = cmp[0]
                        cmpY = cmp[1]
                        # local position in bin area
                        x, y = self.binTransform.map(cmpX, cmpY)
                        nx = int(x)
                        ny = int(y)

                        if fullAnalysis:
                            fold = self.output.binOutput[nx, ny]
                            if fold < self.grid.fold:                   # prevent overwriting next bin
                                # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                # line & stake nrs for reporting in extended np-array
                                stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                self.output.anaOutput[nx][ny][fold][2] = fold + 1       # to make fold run from 1 to N
                                self.output.anaOutput[nx][ny][fold][3] = srcPoints[0]
                                self.output.anaOutput[nx][ny][fold][4] = srcPoints[1]
                                self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                            # self.output.anaOutput[nx][ny][fold][9]

                        # all selection criteria have been fullfilled; use the trace
                        self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                        self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypRRR[count])
                        self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypRRR[count])

                    # rather than checking nx, ny & fold, use exception handling to deal with index errors
                    except IndexError:
                        continue

        except StopIteration:
            self.errorText = 'binning from geometry canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        # min/max fold is straightforward
        self.output.maximumFold = self.output.binOutput.max()
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.output.minMinOffset = self.output.minOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF
        # calc max values against (-inf) minimum
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.output.maxMaxOffset = self.output.maxOffset.max()
        # replace (-inf) by (inf) for min values
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf
        # calc min offset against min (inf) values
        self.output.minMaxOffset = self.output.maxOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        return True

    def binFromGeometry3(self, fullAnalysis) -> bool:
        """all binning methods implemented, working from the shot points rather than the relation records"""

        self.threadProgress = 0                                                 # always start at zero

        toLocalTransform = QTransform()                                         # setup empty (unit) transform
        toLocalTransform, _ = self.glbTransform.inverted()                      # transform to local survey coordinates

        # if needed, fill the source and receiver arrays with local coordinates
        minLocX = np.min(self.output.srcGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.srcGeom['LocY'])                           # determine if there's any data there...
        if minLocX == 0.0 and maxLocX == 0.0:
            for record in self.output.srcGeom:
                srcX = record['East']
                srcY = record['North']
                x, y = toLocalTransform.map(srcX, srcY)
                record['LocX'] = x
                record['LocY'] = y

        minLocX = np.min(self.output.recGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.recGeom['LocY'])                           # determine if there's any data there...
        if minLocX == 0.0 and maxLocX == 0.0:
            for record in self.output.recGeom:
                recX = record['East']
                recY = record['North']
                x, y = toLocalTransform.map(recX, recY)
                record['LocX'] = x
                record['LocY'] = y

        # Find out where shots start and stop in the relation file
        # Therefore create reference to relation file.

        # The 1st element is the first entry into the rel file for a shot number
        # The 2nd element is the last  entry into the rel file for a shot number
        relFileIndices = np.zeros(shape=(self.output.srcGeom.shape[0], 2), dtype=np.int32)

        # now iterate over srcGeom to check where shots are referenced
        # the next for loop assumes that:
        # 1. any duplicate records have been removed
        # 2. any orphans (missing corresponding src/rel records) have been removed
        # 2. source records are ordered (sorted) on shotindex / shotline / shotpoint
        # 3. relation records are sorted on shotindex / shotline / shotpoint followed by recindex / recline / recpoint

        assert self.output.relGeom[0]['SrcLin'] == self.output.srcGeom[0]['Line'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcPnt'] == self.output.srcGeom[0]['Point'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcInd'] == self.output.srcGeom[0]['Index'], 'error in geometry files'

        # to be sure; sort the three geometry arrays in order: index; line; point
        self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        marker = 0
        for index, srcRecord in enumerate(self.output.srcGeom):                 # find the relevant relation records for each shot point

            relFileIndices[index][0] = marker
            for j in range(marker, self.output.relGeom.shape[0]):

                if self.output.relGeom[j]['SrcPnt'] == srcRecord['Point'] and self.output.relGeom[j]['SrcLin'] == srcRecord['Line'] and self.output.relGeom[j]['SrcInd'] == srcRecord['Index']:
                    relFileIndices[index][1] = j + 1                            # last number will stay out of scope for range: 0 - n
                else:
                    marker = j
                    break

        # now iterate over the shot points and select the range of applicable receivers
        # assume the receivers have been sorted based on index/line/point

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        try:
            for index, srcRecord in enumerate(self.output.srcGeom):
                # convert the source record to a single [x, y, z] value
                src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                minRecord = relFileIndices[index][0]                            # range of relevant relation records
                maxRecord = relFileIndices[index][1]

                if maxRecord == minRecord:                                      # no receivers found; move to next shot !
                    continue

                relSlice = self.output.relGeom[minRecord:maxRecord]             # create a slice out of the relation file

                recIndex = relSlice[0]['RecInd']
                minLine = np.min(relSlice['RecLin'])
                maxLine = np.max(relSlice['RecLin'])
                minMinPoint = np.min(relSlice['RecMin'])                        # determine if it is a purely square block
                maxMinPoint = np.max(relSlice['RecMin'])
                minMaxPoint = np.min(relSlice['RecMax'])
                maxMaxPoint = np.max(relSlice['RecMax'])

                if minMinPoint == maxMinPoint and minMaxPoint == maxMaxPoint:
                    # if it is a square block, make a simple single square selection in receiver array. See binTemplate4()
                    I = (
                        (self.output.recGeom['Index'] == recIndex)
                        & (self.output.recGeom['Line'] >= minLine)
                        & (self.output.recGeom['Line'] <= maxLine)
                        & (self.output.recGeom['Point'] >= minMinPoint)
                        & (self.output.recGeom['Point'] <= maxMaxPoint)
                    )
                    if np.count_nonzero(I) == 0:
                        continue                                                # no receivers found; move to next shot !
                    recArray = self.output.recGeom[I]                           # select the filtered receivers

                else:
                    # there are different min/max rec points on different rec lines.
                    # we need to determine the recPoints line by line; per relation record
                    recArray = np.zeros(shape=(0), dtype=pntType1)             # setup empty numpy array
                    for relRecord in relSlice:
                        recInd = relRecord['RecInd']
                        recLin = relRecord['RecLin']
                        recMin = relRecord['RecMin']
                        recMax = relRecord['RecMax']

                        # select appropriate receivers on a receiver line
                        I = (self.output.recGeom['Index'] == recInd) & (self.output.recGeom['Line'] == recLin) & (self.output.recGeom['Point'] >= recMin) & (self.output.recGeom['Point'] <= recMax)

                        recLine = self.output.recGeom[I]                        # select the filtered receivers
                        recArray = np.concatenate((recPoints, recLine))          # need to supply arrays to be concatenated as a tuple !
                        # See: https://stackoverflow.com/questions/50997928/typeerror-only-integer-scalar-arrays-can-be-converted-to-a-scalar-index-with-1d

                # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
                # we combine recPoints with source point to create cmp array, define offsets, etc...

                # we are not dealing with the block's src border; should have been done while generating geometry
                # we are not dealing with the block's rec border; should have been done while generating geometry
                # it is essential that any orphans & duplicates in recPoints have been removed at this stage
                # for cmp and offset calcuations, we need numpy arrays in the form of local (x, y, z) coordinates

                recPoints = np.zeros(shape=(recArray.shape[0], 3), dtype=np.float32)
                recPoints[:, 0] = recArray['LocX']
                recPoints[:, 1] = recArray['LocY']
                recPoints[:, 2] = recArray['Elev']

                # setup a cmp array with the same size as recPoints
                cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

                if self.binning.method == BinningType.cmp:
                    # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
                    cmpPoints = (recPoints + src) * 0.5
                elif self.binning.method == BinningType.plane:
                    # create all cmp-locations using the following steps:
                    # 1. mirror the source location against the plane
                    # 2. find out where/if the lines defined by the source-mirror to the receivers cut through the plane
                    # 3. these locations are the cmp locations for binning against a dipping plane
                    srcMirror3D = self.localPlane.mirrorPoint3D(QVector3D(*src))

                    # now iterate over recPoints to find all intersection points with the dipping plane
                    # in a second revision, the for loop should be replaced by a 'native numpy' routine
                    for nR, rec in enumerate(recPoints):                           # iterate over all receivers
                        recPoint3D = QVector3D(*rec)
                        cmpPoint3D = self.localPlane.IntersectLineAtPoint3D(srcMirror3D, recPoint3D, self.angles.reflection.x(), self.angles.reflection.y())

                        if cmpPoint3D is not None:
                            cmpPoints[nR][0] = cmpPoint3D.x()
                            cmpPoints[nR][1] = cmpPoint3D.y()
                            cmpPoints[nR][2] = cmpPoint3D.z()
                        else:
                            cmpPoints[nR][0] = None                             # don't bother with y or z; later only test on x

                    # check which cmp values are valid (i.e. not None)
                    I = cmpPoints[:, 0] != None                               # pylint: disable=C0121 # we need to do a per-element comparison, can't use "is not None"
                    if np.count_nonzero(I) == 0:
                        continue

                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this for offsets
                elif self.binning.method == BinningType.sphere:
                    srcPoint3D = QVector3D(*src)                                # source point used in iteration over receivers; *src is same as src[0], src[1], src[2]

                    for nR, rec in enumerate(recPoints):                        # iterate over all receivers
                        recPoint3D = QVector3D(*rec)                            # *rec is same as rec[0], rec[1], rec[2]
                        cmpPoint3D = self.localSphere.ReflectSphereAtPoint3D(srcPoint3D, recPoint3D, self.angles.reflection.x(), self.angles.reflection.y())

                        if cmpPoint3D is not None:
                            cmpPoints[nR][0] = cmpPoint3D.x()
                            cmpPoints[nR][1] = cmpPoint3D.y()
                            cmpPoints[nR][2] = cmpPoint3D.z()
                        else:
                            cmpPoints[nR][0] = None                             # don't bother with y or z; later only test on x

                    # check which cmp values are valid (i.e. not None)
                    I = cmpPoints[:, 0] != None                               # pylint: disable=C0121 # we need to do a per-element comparison, can't use "is not None"
                    if np.count_nonzero(I) == 0:
                        continue

                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this for offsets

                # find the cmp locations that contribute to the output area
                l = self.output.rctOutput.left()
                r = self.output.rctOutput.right()
                t = self.output.rctOutput.top()
                b = self.output.rctOutput.bottom()
                I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this for offsets

                ofVectors = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                ofVectors = recPoints - src                                     # define the offset array

                l = self.offset.rctOffsets.left()
                r = self.offset.rctOffsets.right()
                t = self.offset.rctOffsets.top()
                b = self.offset.rctOffsets.bottom()
                I = (ofVectors[:, 0] >= l) & (ofVectors[:, 0] <= r) & (ofVectors[:, 1] >= t) & (ofVectors[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                ofVectors = ofVectors[I, :]                                     # filter the offset-array
                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array too, as we still need this
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this

                hypRRR = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                # calculate per row
                hypRRR = np.hypot(ofVectors[:, 0], ofVectors[:, 1])

                r1 = self.offset.radOffsets.x()                                 # minimum radius
                r2 = self.offset.radOffsets.y()                                 # maximum radius
                if r2 > 0:                                                      # we need to apply the radial offset selection criteria
                    I = (hypRRR[:] >= r1) & (hypRRR[:] <= r2)
                    if np.count_nonzero(I) == 0:
                        continue                                                # continue with next recSeed
                    # print(I)
                    hypRRR = hypRRR[I]                                          # filter the radial offset-array
                    ofVectors = ofVectors[I, :]                                 # filter the off-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                #  we have applied all filters now; time to save the traces that 'pass' all selection criteria

                # process all traces
                for count, cmp in enumerate(cmpPoints):
                    try:
                        cmpX = cmp[0]
                        cmpY = cmp[1]
                        # local position in bin area
                        x, y = self.binTransform.map(cmpX, cmpY)
                        nx = int(x)
                        ny = int(y)

                        if fullAnalysis:
                            fold = self.output.binOutput[nx, ny]
                            if fold < self.grid.fold:                           # prevent overwriting next bin
                                # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                # line & stake nrs for reporting in extended np-array
                                stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                self.output.anaOutput[nx][ny][fold][2] = fold + 1       # to make fold run from 1 to N
                                self.output.anaOutput[nx][ny][fold][3] = src[0]
                                self.output.anaOutput[nx][ny][fold][4] = src[1]
                                self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                            # self.output.anaOutput[nx, ny, fold, 9]

                        # all selection criteria have been fullfilled; use the trace
                        self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                        self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypRRR[count])
                        self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypRRR[count])

                    # rather than checking nx, ny & fold, use exception handling to deal with index errors
                    except IndexError:
                        continue

        except StopIteration:
            self.errorText = 'binning from geometry canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        # min/max fold is straightforward
        self.output.maximumFold = self.output.binOutput.max()
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.output.minMinOffset = self.output.minOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF
        # calc max values against (-inf) minimum
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.output.maxMaxOffset = self.output.maxOffset.max()
        # replace (-inf) by (inf) for min values
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf
        # calc min offset against min (inf) values
        self.output.minMaxOffset = self.output.maxOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        return True

    def binFromGeometry4(self, fullAnalysis) -> bool:
        """all binning methods implemented, using numpy arrays, rather than a for-loop"""

        self.threadProgress = 0                                                 # always start at zero

        toLocalTransform = QTransform()                                         # setup empty (unit) transform
        toLocalTransform, _ = self.glbTransform.inverted()                      # transform to local survey coordinates

        # if needed, fill the source and receiver arrays with local coordinates
        minLocX = np.min(self.output.srcGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.srcGeom['LocY'])                           # determine if there's any data there...
        if minLocX == 0.0 and maxLocX == 0.0:
            for record in self.output.srcGeom:
                srcX = record['East']
                srcY = record['North']
                x, y = toLocalTransform.map(srcX, srcY)
                record['LocX'] = x
                record['LocY'] = y

        minLocX = np.min(self.output.recGeom['LocX'])                           # determine if there's any data there...
        maxLocX = np.max(self.output.recGeom['LocY'])                           # determine if there's any data there...
        if minLocX == 0.0 and maxLocX == 0.0:
            for record in self.output.recGeom:
                recX = record['East']
                recY = record['North']
                x, y = toLocalTransform.map(recX, recY)
                record['LocX'] = x
                record['LocY'] = y

        # Find out where shots start and stop in the relation file
        # Therefore create reference to relation file.

        # The 1st element is the first entry into the rel file for a shot number
        # The 2nd element is the last  entry into the rel file for a shot number
        relFileIndices = np.zeros(shape=(self.output.srcGeom.shape[0], 2), dtype=np.int32)

        # now iterate over srcGeom to check where shots are referenced
        # the next for loop assumes that:
        # 1. any duplicate records have been removed
        # 2. any orphans (missing corresponding src/rel records) have been removed
        # 2. source records are ordered (sorted) on shotindex / shotline / shotpoint
        # 3. relation records are sorted on shotindex / shotline / shotpoint followed by recindex / recline / recpoint

        assert self.output.relGeom[0]['SrcLin'] == self.output.srcGeom[0]['Line'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcPnt'] == self.output.srcGeom[0]['Point'], 'error in geometry files'
        assert self.output.relGeom[0]['SrcInd'] == self.output.srcGeom[0]['Index'], 'error in geometry files'

        # to be sure; sort the three geometry arrays in order: index; line; point
        self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        marker = 0
        for index, srcRecord in enumerate(self.output.srcGeom):                 # find the relevant relation records for each shot point

            relFileIndices[index][0] = marker
            for j in range(marker, self.output.relGeom.shape[0]):

                if self.output.relGeom[j]['SrcPnt'] == srcRecord['Point'] and self.output.relGeom[j]['SrcLin'] == srcRecord['Line'] and self.output.relGeom[j]['SrcInd'] == srcRecord['Index']:
                    relFileIndices[index][1] = j + 1                            # last number will stay out of scope for range: 0 - n
                else:
                    marker = j
                    break

        # now iterate over the shot points and select the range of applicable receivers
        # assume the receivers have been sorted based on index/line/point

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        try:
            for index, srcRecord in enumerate(self.output.srcGeom):
                # convert the source record to a single [x, y, z] value
                src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                minRecord = relFileIndices[index][0]                            # range of relevant relation records
                maxRecord = relFileIndices[index][1]

                if maxRecord == minRecord:                                      # no receivers found; move to next shot !
                    continue

                relSlice = self.output.relGeom[minRecord:maxRecord]             # create a slice out of the relation file

                recIndex = relSlice[0]['RecInd']
                minLine = np.min(relSlice['RecLin'])
                maxLine = np.max(relSlice['RecLin'])
                minMinPoint = np.min(relSlice['RecMin'])                        # determine if it is a purely square block
                maxMinPoint = np.max(relSlice['RecMin'])
                minMaxPoint = np.min(relSlice['RecMax'])
                maxMaxPoint = np.max(relSlice['RecMax'])

                if minMinPoint == maxMinPoint and minMaxPoint == maxMaxPoint:
                    # if it is a square block, make a simple single square selection in receiver array. See binTemplate4()
                    I = (
                        (self.output.recGeom['Index'] == recIndex)
                        & (self.output.recGeom['Line'] >= minLine)
                        & (self.output.recGeom['Line'] <= maxLine)
                        & (self.output.recGeom['Point'] >= minMinPoint)
                        & (self.output.recGeom['Point'] <= maxMaxPoint)
                    )
                    if np.count_nonzero(I) == 0:
                        continue                                                # no receivers found; move to next shot !
                    recArray = self.output.recGeom[I]                           # select the filtered receivers

                else:
                    # there are different min/max rec points on different rec lines.
                    # we need to determine the recPoints line by line; per relation record
                    recArray = np.zeros(shape=(0), dtype=pntType1)             # setup empty numpy array
                    for relRecord in relSlice:
                        recInd = relRecord['RecInd']
                        recLin = relRecord['RecLin']
                        recMin = relRecord['RecMin']
                        recMax = relRecord['RecMax']

                        # select appropriate receivers on a receiver line
                        I = (self.output.recGeom['Index'] == recInd) & (self.output.recGeom['Line'] == recLin) & (self.output.recGeom['Point'] >= recMin) & (self.output.recGeom['Point'] <= recMax)

                        recLine = self.output.recGeom[I]                        # select the filtered receivers
                        recArray = np.concatenate((recPoints, recLine))          # need to supply arrays to be concatenated as a tuple !
                        # See: https://stackoverflow.com/questions/50997928/typeerror-only-integer-scalar-arrays-can-be-converted-to-a-scalar-index-with-1d

                # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
                # we combine recPoints with source point to create cmp array, define offsets, etc...

                # we are not dealing with the block's src border; should have been done while generating geometry
                # we are not dealing with the block's rec border; should have been done while generating geometry
                # it is essential that any orphans & duplicates in recPoints have been removed at this stage
                # for cmp and offset calcuations, we need numpy arrays in the form of local (x, y, z) coordinates

                recPoints = np.zeros(shape=(recArray.shape[0], 3), dtype=np.float32)
                recPoints[:, 0] = recArray['LocX']
                recPoints[:, 1] = recArray['LocY']
                recPoints[:, 2] = recArray['Elev']

                # setup a cmp array with the same size as recPoints
                cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

                if self.binning.method == BinningType.cmp:
                    # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
                    cmpPoints = (recPoints + src) * 0.5
                elif self.binning.method == BinningType.plane:
                    # create all cmp-locations using the following steps:
                    # 1. mirror the source location against the plane
                    # 2. find out where/if the lines defined by the source-mirror to the receivers cut through the plane
                    # 3. these locations are the cmp locations for binning against a dipping plane
                    srcMirrorNp = self.localPlane.mirrorPointNp(src)

                    # now find all intersection points with the dipping plane, and prune any non-contributing receivers
                    cmpPoints, recPoints = self.localPlane.IntersectLinesAtPointNp(srcMirrorNp, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

                    if cmpPoints is None:
                        continue
                elif self.binning.method == BinningType.sphere:

                    # now find all intersection points with the sphere, and prune any non-contributing receivers
                    cmpPoints, recPoints = self.localSphere.ReflectSphereAtPointsNp(src, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

                    if cmpPoints is None:
                        continue

                # find the cmp locations that contribute to the output area
                l = self.output.rctOutput.left()
                r = self.output.rctOutput.right()
                t = self.output.rctOutput.top()
                b = self.output.rctOutput.bottom()
                I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this for offsets

                ofVectors = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                ofVectors = recPoints - src                                     # define the offset array

                l = self.offset.rctOffsets.left()
                r = self.offset.rctOffsets.right()
                t = self.offset.rctOffsets.top()
                b = self.offset.rctOffsets.bottom()
                I = (ofVectors[:, 0] >= l) & (ofVectors[:, 0] <= r) & (ofVectors[:, 1] >= t) & (ofVectors[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                ofVectors = ofVectors[I, :]                                     # filter the offset-array
                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array too, as we still need this
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this

                hypRRR = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                hypRRR = np.hypot(ofVectors[:, 0], ofVectors[:, 1])             # calculate radial offset size

                r1 = self.offset.radOffsets.x()                                 # minimum radius
                r2 = self.offset.radOffsets.y()                                 # maximum radius
                if r2 > 0:                                                      # we need to apply the radial offset selection criteria
                    I = (hypRRR[:] >= r1) & (hypRRR[:] <= r2)
                    if np.count_nonzero(I) == 0:
                        continue                                                # continue with next recSeed
                    # print(I)
                    hypRRR = hypRRR[I]                                          # filter the radial offset-array
                    ofVectors = ofVectors[I, :]                                 # filter the off-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                #  we have applied all filters now; time to save the traces that 'pass' all selection criteria

                # process all traces
                for count, cmp in enumerate(cmpPoints):
                    try:
                        cmpX = cmp[0]
                        cmpY = cmp[1]
                        # local position in bin area
                        x, y = self.binTransform.map(cmpX, cmpY)
                        nx = int(x)
                        ny = int(y)

                        if fullAnalysis:
                            fold = self.output.binOutput[nx, ny]
                            if fold < self.grid.fold:                           # prevent overwriting next bin
                                # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                # line & stake nrs for reporting in extended np-array
                                stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                self.output.anaOutput[nx][ny][fold][2] = fold + 1       # to make fold run from 1 to N
                                self.output.anaOutput[nx][ny][fold][3] = src[0]
                                self.output.anaOutput[nx][ny][fold][4] = src[1]
                                self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                                # self.output.anaOutput[nx, ny, fold, 9]

                        # all selection criteria have been fullfilled; use the trace
                        self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                        self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypRRR[count])
                        self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypRRR[count])

                    # rather than checking nx, ny & fold, use exception handling to deal with index errors
                    except IndexError:
                        continue

        except StopIteration:
            self.errorText = 'binning from geometry canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        # min/max fold is straightforward
        self.output.maximumFold = self.output.binOutput.max()
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.output.minMinOffset = self.output.minOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF
        # calc max values against (-inf) minimum
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.output.maxMaxOffset = self.output.maxOffset.max()
        # replace (-inf) by (inf) for min values
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf
        # calc min offset against min (inf) values
        self.output.minMaxOffset = self.output.maxOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        return True

    def setupBinFromTemplates(self, fullAnalysis) -> bool:

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        if fullAnalysis:
            success = self.binFromTemplates(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromTemplates(False)

    # https://github.com/pyqtgraph/pyqtgraph/issues/1253
    # the above link shows how to use numba with PyQtGraph
    # @jit(nopython=True)
    # @jit
    def binFromTemplates(self, fullAnalysis) -> bool:
        try:
            for block in self.blockList:                                        # get all blocks
                for template in block.templateList:                             # get all templates
                    # how deep is the list ?
                    length = len(template.rollList)
                    if length == 0:
                        # always start at (0, 0, 0)
                        off0 = QVector3D(0.0, 0.0, 0.0)
                        self.binTemplate6(block, template, off0, fullAnalysis)

                    elif length == 1:
                        # get the template boundaries
                        for i in range(template.rollList[0].steps):
                            # always start at (0, 0, 0)
                            off0 = QVector3D(0.0, 0.0, 0.0)
                            off0 += template.rollList[0].increment * i
                            self.binTemplate6(block, template, off0, fullAnalysis)

                    elif length == 2:
                        for i in range(template.rollList[0].steps):
                            # always start at (0, 0, 0)
                            off0 = QVector3D(0.0, 0.0, 0.0)
                            off0 += template.rollList[0].increment * i
                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j
                                self.binTemplate6(block, template, off1, fullAnalysis)
                                # print("length = 2. Template offset: ", off1.x(), off1.y() )

                    elif length == 3:
                        for i in range(template.rollList[0].steps):
                            # always start at (0, 0, 0)
                            off0 = QVector3D(0.0, 0.0, 0.0)
                            off0 += template.rollList[0].increment * i

                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j

                                for k in range(template.rollList[2].steps):
                                    off2 = off1 + template.rollList[2].increment * k

                                    self.binTemplate6(block, template, off2, fullAnalysis)
                    else:
                        # do something recursively; not  implemented yet
                        raise NotImplementedError('More than three roll steps currently not allowed.')

        except StopIteration:
            self.errorText = 'binning from templates canceled by user'
            return False
        except BaseException as e:
            self.errorText = str(e)
            return False

        # min/max fold is straightforward
        self.output.maximumFold = self.output.binOutput.max()
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.output.minMinOffset = self.output.minOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF
        # calc max values against (-inf) minimum
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.output.maxMaxOffset = self.output.maxOffset.max()
        # replace (-inf) by (inf) for min values
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf
        # calc min offset against min (inf) values
        self.output.minMaxOffset = self.output.maxOffset.min()
        # replace (inf) by (-inf) for max values
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        return True

    # @jit(nopython=True)
    # @jit
    def binTemplate(self, block, template, templateOffset, fullAnalysis):
        """iterate over all seeds in a template; make sure we start wih *source* seeds"""

        # iterate over all seeds in a template
        for srcSeed in template.seedList:
            while len(srcSeed.grid.growList) < 3:
                # First, make sure there are 3 grow steps for every srcSeed
                srcSeed.grid.growList.insert(0, RollTranslate())

            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            for i in range(srcSeed.grid.growList[0].steps):
                # start with a new QVector3D object
                srcOff0 = QVector3D(templateOffset)
                srcOff0 += srcSeed.grid.growList[0].increment * i

                for j in range(srcSeed.grid.growList[1].steps):
                    srcOff1 = srcOff0 + srcSeed.grid.growList[1].increment * j

                    for k in range(srcSeed.grid.growList[2].steps):
                        # we now have the correct offset
                        srcOff2 = srcOff1 + srcSeed.grid.growList[2].increment * k
                        # we now have the correct location
                        srcLoc = srcOff2 + srcSeed.origin

                        if QThread.currentThread().isInterruptionRequested():   # maybe stop at each shot...
                            raise StopIteration

                        self.nShotPoint += 1
                        # apply integer divide
                        threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                        if threadProgress > self.threadProgress:
                            self.threadProgress = threadProgress
                            # print("progress % = ", threadProgress)
                            self.progress.emit(threadProgress + 1)

                        # is it within block limits (or is the border empty) ?
                        if containsPoint3D(block.borders.srcBorder, srcLoc):

                            # now iterate over all seeds to find the receivers
                            for recSeed in template.seedList:                   # iterate over all seeds in a template
                                while len(recSeed.grid.growList) < 3:
                                    # First, make sure there are 3 grow steps for every recSeed
                                    recSeed.grid.growList.insert(0, RollTranslate())

                                if recSeed.bSource:                             # work with receiver seeds here
                                    continue

                                for l in range(recSeed.grid.growList[0].steps):
                                    # start with a new QVector3D object
                                    recOff0 = QVector3D(templateOffset)
                                    recOff0 += recSeed.grid.growList[0].increment * l

                                    for m in range(recSeed.grid.growList[1].steps):
                                        recOff1 = recOff0 + recSeed.grid.growList[1].increment * m

                                        for n in range(recSeed.grid.growList[2].steps):
                                            recOff2 = recOff1 + recSeed.grid.growList[2].increment * n

                                            recLoc = QVector3D(recOff2)
                                            recLoc += recSeed.origin            # we now have the correct location

                                            # print("recLoc: ", recLoc.x(), recLoc.y() )

                                            # is it within block limits (or is the border empty) ?
                                            if containsPoint3D(block.borders.recBorder, recLoc):

                                                # now we have a valid src-point and rec-point
                                                cmpLoc = QPointF()

                                                cmpBinning = True
                                                if cmpBinning:
                                                    cmpLoc = 0.5 * (srcLoc.toPointF() + recLoc.toPointF())

                                                if containsPoint2D(self.output.rctOutput, cmpLoc):
                                                    # now we need to process a valid trace

                                                    # local position in bin area
                                                    loc = self.binTransform.map(cmpLoc)
                                                    nx = int(loc.x())
                                                    ny = int(loc.y())

                                                    vecOffset = recLoc - srcLoc             # determine offset vector
                                                    rctOffset = vecOffset.toPointF()        # loose the z-component

                                                    # first check if offset falls within offset analysis rectangle
                                                    if containsPoint2D(self.offset.rctOffsets, rctOffset):

                                                        # now do the 'expensive' sqrt operation
                                                        radOffset = math.hypot(rctOffset.x(), rctOffset.y())

                                                        # now check radial offset range. Only do this test if max offset > 0.0
                                                        if self.offset.radOffsets.y() == 0.0 or (radOffset < self.offset.radOffsets.y() and radOffset >= self.offset.radOffsets.x()):

                                                            if fullAnalysis:
                                                                # ('SrcX', np.float32), ('SrcY', np.float32),    # Src (x, y)
                                                                # ('RecX', np.float32), ('RecY', np.float32),    # Rec (x, y)
                                                                # ('CmpX', np.float32), ('CmpY', np.float32),    # Cmp (x, y); needed for spider plot when binning against dipping plane
                                                                # ('SrcL', np.int32  ), ('SrcP', np.int32  ),    # SrcLine, SrcPoint
                                                                # ('RecL', np.int32  ), ('RecP', np.int32  )])   # RecLine, RecPoint

                                                                fold = self.output.binOutput[nx, ny]
                                                                if fold < self.grid.fold:                       # prevent overwriting next bin
                                                                    # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(),
                                                                    #                                         recLoc.x(), recLoc.y(),
                                                                    #                                         cmpLoc.x(), cmpLoc.y(),
                                                                    #                                         0, 0, 0, 0)
                                                                    # line & stake nrs for reporting in extended np-array
                                                                    stkLoc = self.st2Transform.map(cmpLoc)
                                                                    self.output.anaOutput[nx][ny][fold][0] = int(stkLoc.x())
                                                                    self.output.anaOutput[nx][ny][fold][1] = int(stkLoc.y())
                                                                    self.output.anaOutput[nx][ny][fold][2] = fold + 1        # to make fold run from 1 to N
                                                                    self.output.anaOutput[nx][ny][fold][3] = srcLoc.x()
                                                                    self.output.anaOutput[nx][ny][fold][4] = srcLoc.y()
                                                                    self.output.anaOutput[nx][ny][fold][5] = recLoc.x()
                                                                    self.output.anaOutput[nx][ny][fold][6] = recLoc.y()
                                                                    self.output.anaOutput[nx][ny][fold][7] = cmpLoc.x()
                                                                    self.output.anaOutput[nx][ny][fold][8] = cmpLoc.y()
                                                                # self.output.anaOutput[nx][ny][fold][9]

                                                            # all selection criteria have been fullfilled; use the trace
                                                            self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                                                            self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], radOffset)
                                                            self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], radOffset)
                                                            # print (cmpLoc.x(), cmpLoc.y(), loc.x(), loc.y(), stk.x(), stk.y(), self.output.binOutput[nx, ny])

    def binTemplate2(self, block, template, templateOffset, fullAnalysis):
        """forget about the seed's *growList*; make use of the seed's *pointList*"""

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            for src in srcSeed.pointList:
                srcLoc = src + templateOffset

                # begin thread progress code
                # maybe stop at each shot...
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                # apply integer divide
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # is it within block limits (or is the border empty) ?
                if containsPoint3D(block.borders.srcBorder, srcLoc):

                    # now iterate over all seeds to find the receivers
                    for recSeed in template.seedList:                           # iterate over all seeds in a template
                        if recSeed.bSource:                                     # work with receiver seeds here
                            continue

                        for rec in recSeed.pointList:
                            recLoc = rec + templateOffset

                            # is it within block limits (or is the border empty) ?
                            if containsPoint3D(block.borders.recBorder, recLoc):

                                # now we have a valid src-point and rec-point
                                cmpLoc = QPointF()

                                cmpBinning = True
                                if cmpBinning:
                                    cmpLoc = 0.5 * (srcLoc.toPointF() + recLoc.toPointF())

                                    if containsPoint2D(self.output.rctOutput, cmpLoc):
                                        # now we need to process a valid trace

                                        # local position in bin area
                                        loc = self.binTransform.map(cmpLoc)
                                        nx = int(loc.x())
                                        ny = int(loc.y())

                                        rctOffset = recLoc - srcLoc             # determine offset vector

                                        # first check if offset falls within offset analysis rectangle

                                        if containsPoint3D(self.offset.rctOffsets, rctOffset):

                                            # now do the 'expensive' sqrt operation
                                            radOffset = math.hypot(rctOffset.x(), rctOffset.y())

                                            # now check radial offset range. Only do this test if max offset > 0.0
                                            if self.offset.radOffsets.y() == 0.0 or (radOffset < self.offset.radOffsets.y() and radOffset >= self.offset.radOffsets.x()):

                                                if fullAnalysis:
                                                    # ('SrcX', np.float32), ('SrcY', np.float32),    # Src (x, y)
                                                    # ('RecX', np.float32), ('RecY', np.float32),    # Rec (x, y)
                                                    # ('CmpX', np.float32), ('CmpY', np.float32),    # Cmp (x, y); needed for spider plot when binning against dipping plane
                                                    # ('SrcL', np.int32  ), ('SrcP', np.int32  ),    # SrcLine, SrcPoint
                                                    # ('RecL', np.int32  ), ('RecP', np.int32  )])   # RecLine, RecPoint

                                                    fold = self.output.binOutput[nx, ny]
                                                    if fold < self.grid.fold:                       # prevent overwriting next bin
                                                        # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(),
                                                        #                                         recLoc.x(), recLoc.y(),
                                                        #                                         cmpLoc.x(), cmpLoc.y(),
                                                        #                                         0, 0, 0, 0)
                                                        # line & stake nrs for reporting in extended np-array
                                                        stkLoc = self.st2Transform.map(cmpLoc)
                                                        self.output.anaOutput[nx][ny][fold][0] = int(stkLoc.x())
                                                        self.output.anaOutput[nx][ny][fold][1] = int(stkLoc.y())
                                                        self.output.anaOutput[nx][ny][fold][2] = fold + 1            # to make fold run from 1 to N
                                                        self.output.anaOutput[nx][ny][fold][3] = srcLoc.x()
                                                        self.output.anaOutput[nx][ny][fold][4] = srcLoc.y()
                                                        self.output.anaOutput[nx][ny][fold][5] = recLoc.x()
                                                        self.output.anaOutput[nx][ny][fold][6] = recLoc.y()
                                                        self.output.anaOutput[nx][ny][fold][7] = cmpLoc.x()
                                                        self.output.anaOutput[nx][ny][fold][8] = cmpLoc.y()
                                                    # self.output.anaOutput[nx][ny][fold][9]

                                                    # print (self.output.anaOutput[nx, ny, fold])
                                                    # print(cmpLoc.x(), cmpLoc.y(), loc.x(), loc.y(), stkLoc.x(), stkLoc.y(), self.output.binOutput[nx, ny])

                                                # all selection criteria have been fullfilled; use the trace
                                                self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                                                self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], radOffset)
                                                self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], radOffset)
                                                print(cmpLoc.x(), cmpLoc.y(), loc.x(), loc.y(), self.output.binOutput[nx, ny])

    def binTemplate3(self, block, template, templateOffset, fullAnalysis):
        """move away from the seed's *pointList*, start using *pointArray* for a significant speed up"""

        # convert the template offset to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            for src in srcSeed.pointList:
                srcLoc = src + templateOffset

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                # apply integer divide
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # is it within block limits (or is the border empty) ?
                if containsPoint3D(block.borders.srcBorder, srcLoc):

                    # now iterate over all seeds to find the receivers
                    for recSeed in template.seedList:                           # iterate over all seeds in a template
                        if recSeed.bSource:                                     # work with receiver seeds here
                            continue

                        # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                        recPoints = recSeed.pointArray + npTemplateOffset

                        # deal with block's receiver border if it isn't null()
                        if not block.borders.recBorder.isNull():
                            l = block.borders.recBorder.left()
                            r = block.borders.recBorder.right()
                            t = block.borders.recBorder.top()
                            b = block.borders.recBorder.bottom()
                            I = (recPoints[:, 0] >= l) & (recPoints[:, 0] <= r) & (recPoints[:, 1] >= t) & (recPoints[:, 1] <= b)
                            if np.count_nonzero(I) == 0:
                                continue
                            recPoints = recPoints[I, :]

                        srcArray = np.array([srcLoc.x(), srcLoc.y(), srcLoc.z()], dtype=np.float32)
                        cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                        # create all cmp-locations for this shot point
                        cmpPoints = (recPoints + srcArray) * 0.5

                        l = self.output.rctOutput.left()
                        r = self.output.rctOutput.right()
                        t = self.output.rctOutput.top()
                        b = self.output.rctOutput.bottom()
                        I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue

                        # filter the cmp-array
                        cmpPoints = cmpPoints[I, :]
                        # filter the rec-array too, as we still need this
                        recPoints = recPoints[I, :]

                        cmpBinning = True
                        if cmpBinning:
                            offArray = np.zeros(shape=(recPoints.shape[0], 2), dtype=np.float32)
                            offArray = recPoints - srcArray                      # define the offset array

                            l = self.offset.rctOffsets.left()
                            r = self.offset.rctOffsets.right()
                            t = self.offset.rctOffsets.top()
                            b = self.offset.rctOffsets.bottom()
                            I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                            if np.count_nonzero(I) == 0:
                                continue

                            # print(I)
                            # filter the off-array
                            offArray = offArray[I, :]
                            # filter the cmp-array too, as we still need this
                            cmpPoints = cmpPoints[I, :]
                            # filter the rec-array too, as we still need this
                            recPoints = recPoints[I, :]

                            hypArray = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                            # calculate per row
                            hypArray = np.hypot(offArray[:, 0], offArray[:, 1])

                            r1 = self.offset.radOffsets.x()
                            r2 = self.offset.radOffsets.y()
                            if r2 > 0:                                          # we need to apply radial offset crieria
                                I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                                if np.count_nonzero(I) == 0:
                                    continue
                                # print(I)
                                # filter the radial offset-array
                                hypArray = hypArray[I]
                                # filter the off-array too, as we still need this
                                offArray = offArray[I, :]
                                # filter the cmp-array too, as we still need this
                                cmpPoints = cmpPoints[I, :]
                                # filter the rec-array too, as we still need this
                                recPoints = recPoints[I, :]

                            #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                            # process all traces
                            for count, item in enumerate(cmpPoints):
                                cmpX = item[0]
                                cmpY = item[1]
                                # local position in bin area
                                x, y = self.binTransform.map(cmpX, cmpY)
                                nx = int(x)
                                ny = int(y)

                                if fullAnalysis:

                                    fold = self.output.binOutput[nx, ny]
                                    if fold < self.grid.fold:                   # prevent overwriting next bin
                                        # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                        # line & stake nrs for reporting in extended np-array
                                        stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                        self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                        self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                        self.output.anaOutput[nx][ny][fold][2] = fold + 1           # to make fold run from 1 to N
                                        self.output.anaOutput[nx][ny][fold][3] = srcArray[0]
                                        self.output.anaOutput[nx][ny][fold][4] = srcArray[1]
                                        self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                        self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                        self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                        self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                                    # self.output.anaOutput[nx][ny][fold][9]

                                # all selection criteria have been fullfilled; use the trace
                                self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                                self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                                self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

    def binTemplate4(self, block, template, templateOffset, fullAnalysis):
        """further move away from the seed's *pointList*, start using *pointArray* for a significant speed up"""

        # convert the template offset to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work only with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            # deal with block's source  border if it isn't null()
            if not block.borders.srcBorder.isNull():
                l = block.borders.srcBorder.left()
                r = block.borders.srcBorder.right()
                t = block.borders.srcBorder.top()
                b = block.borders.srcBorder.bottom()
                I = (srcArray[:, 0] >= l) & (srcArray[:, 0] <= r) & (srcArray[:, 1] >= t) & (srcArray[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue                                                    # if nothing succeeds; pick next seed
                srcArray = srcArray[I, :]                                       # filter the source array

            for src in srcArray:                                                # iterate over all sources

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # now iterate over all seeds to find the receivers
                for recSeed in template.seedList:                               # iterate over all rec seeds in a template
                    if recSeed.bSource:                                         # work with receiver seeds here
                        continue

                    # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                    recPoints = recSeed.pointArray + npTemplateOffset

                    # deal with block's receiver border if it isn't null()
                    if not block.borders.recBorder.isNull():
                        l = block.borders.recBorder.left()
                        r = block.borders.recBorder.right()
                        t = block.borders.recBorder.top()
                        b = block.borders.recBorder.bottom()
                        I = (recPoints[:, 0] >= l) & (recPoints[:, 0] <= r) & (recPoints[:, 1] >= t) & (recPoints[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue
                        recPoints = recPoints[I, :]

                    cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)
                    # create all cmp-locations for this shot point
                    cmpPoints = (recPoints + src) * 0.5

                    l = self.output.rctOutput.left()
                    r = self.output.rctOutput.right()
                    t = self.output.rctOutput.top()
                    b = self.output.rctOutput.bottom()
                    I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    # filter the cmp-array
                    cmpPoints = cmpPoints[I, :]
                    # filter the rec-array too, as we still need this
                    recPoints = recPoints[I, :]

                    cmpBinning = True
                    if cmpBinning:
                        offArray = np.zeros(shape=(recPoints.shape[0], 2), dtype=np.float32)
                        offArray = recPoints - src                       # define the offset array

                        l = self.offset.rctOffsets.left()
                        r = self.offset.rctOffsets.right()
                        t = self.offset.rctOffsets.top()
                        b = self.offset.rctOffsets.bottom()
                        I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue

                        # filter the off-array
                        offArray = offArray[I, :]
                        # filter the cmp-array too, as we still need this
                        cmpPoints = cmpPoints[I, :]
                        # filter the rec-array too, as we still need this
                        recPoints = recPoints[I, :]

                        hypArray = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                        # calculate per row
                        hypArray = np.hypot(offArray[:, 0], offArray[:, 1])

                        r1 = self.offset.radOffsets.x()                         # minimum radius
                        r2 = self.offset.radOffsets.y()                         # maximum radius
                        if r2 > 0:                                              # we need to apply the radial offset selection criteria
                            I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                            if np.count_nonzero(I) == 0:
                                continue                                        # continue with next recSeed

                            # filter the radial offset-array
                            hypArray = hypArray[I]
                            # filter the off-array too, as we still need this
                            offArray = offArray[I, :]
                            # filter the cmp-array too, as we still need this
                            cmpPoints = cmpPoints[I, :]
                            # filter the rec-array too, as we still need this
                            recPoints = recPoints[I, :]

                        #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                        # process all traces
                        for count, cmp in enumerate(cmpPoints):
                            try:                                                # protect against potential index errors
                                cmpX = cmp[0]
                                cmpY = cmp[1]
                                # local position in bin area
                                x, y = self.binTransform.map(cmpX, cmpY)
                                nx = int(x)
                                ny = int(y)

                                if fullAnalysis:
                                    fold = self.output.binOutput[nx, ny]
                                    if fold < self.grid.fold:                   # prevent overwriting next bin
                                        # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                        # line & stake nrs for reporting in extended np-array
                                        stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                        self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                        self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                        self.output.anaOutput[nx][ny][fold][2] = fold + 1           # to make fold run from 1 to N
                                        self.output.anaOutput[nx][ny][fold][3] = src[0]
                                        self.output.anaOutput[nx][ny][fold][4] = src[1]
                                        self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                        self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                        self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                        self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                                    # self.output.anaOutput[nx][ny][fold][9]

                                # all selection criteria have been fullfilled; use the trace
                                self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                                self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                                self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

                            # rather than checking nx, ny & fold, use exception handling to deal with index errors
                            # note: the other exceptions are handled in binFromTemplates()
                            except IndexError:
                                continue

    def binTemplate5(self, block, template, templateOffset, fullAnalysis):
        """using *pointArray* for a significant speed up, introduce different binning methods"""

        # convert the template offset (a QVector3D) to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work only with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            # deal with block's source  border if it isn't null()
            if not block.borders.srcBorder.isNull():
                l = block.borders.srcBorder.left()
                r = block.borders.srcBorder.right()
                t = block.borders.srcBorder.top()
                b = block.borders.srcBorder.bottom()
                I = (srcArray[:, 0] >= l) & (srcArray[:, 0] <= r) & (srcArray[:, 1] >= t) & (srcArray[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue                                                    # if nothing succeeds; pick next seed
                srcArray = srcArray[I, :]                                       # filter the source array

            for src in srcArray:                                                # iterate over all sources

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # now iterate over all seeds to find the receivers
                for recSeed in template.seedList:                           # iterate over all rec seeds in a template
                    if recSeed.bSource:                                     # work with receiver seeds here
                        continue

                    # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                    recPoints = recSeed.pointArray + npTemplateOffset

                    # deal with block's receiver border if it isn't null()
                    if not block.borders.recBorder.isNull():
                        l = block.borders.recBorder.left()
                        r = block.borders.recBorder.right()
                        t = block.borders.recBorder.top()
                        b = block.borders.recBorder.bottom()
                        I = (recPoints[:, 0] >= l) & (recPoints[:, 0] <= r) & (recPoints[:, 1] >= t) & (recPoints[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue
                        recPoints = recPoints[I, :]

                    cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

                    if self.binning.method == BinningType.cmp:
                        # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
                        cmpPoints = (recPoints + src) * 0.5
                    elif self.binning.method == BinningType.plane:
                        # create all cmp-locations using the following steps:
                        # 1. mirror the source location against the plane
                        # 2. find out where/if the lines defined by the source-mirror with the receivers cuts through the plane
                        # 3. these locations are the cmp locations for binning against a dipping plane
                        srcMirror3D = self.localPlane.mirrorPoint3D(QVector3D(*src))

                        # now iterate over recPoints to find all intersection points with the dipping plane
                        # in a second revision, the for loop should be replaced by a 'native numpy' routine
                        for nR, rec in enumerate(recPoints):                     # iterate over all receivers
                            recPoint3D = QVector3D(*rec)
                            cmpPoint3D = self.localPlane.IntersectLineAtPoint3D(srcMirror3D, recPoint3D, self.angles.reflection.x(), self.angles.reflection.y())

                            if cmpPoint3D is not None:
                                cmpPoints[nR][0] = cmpPoint3D.x()
                                cmpPoints[nR][1] = cmpPoint3D.y()
                                cmpPoints[nR][2] = cmpPoint3D.z()
                            else:
                                cmpPoints[nR][0] = None                         # don't bother with y or z; later only test on x

                        # check which cmp values are valid (i.e. not None)
                        I = cmpPoints[:, 0] != None                           # pylint: disable=C0121 # we need to do a per-element comparison, can't use "is not None"
                        if np.count_nonzero(I) == 0:
                            continue

                        cmpPoints = cmpPoints[I, :]                             # filter the cmp-array
                        recPoints = recPoints[I, :]                             # filter the rec-array
                    elif self.binning.method == BinningType.sphere:
                        for nR, rec in enumerate(recPoints):                        # iterate over all receivers
                            cmpPoint = self.localSphere.ReflectSphereAtPointNp(src, rec, self.angles.reflection.x(), self.angles.reflection.y())

                            if cmpPoint is not None:
                                cmpPoints[nR] = cmpPoint
                            else:
                                cmpPoints[nR][0] = None                         # don't bother with y or z; later only test on x

                        # check which cmp values are valid (i.e. not None)
                        I = cmpPoints[:, 0] != None                           # pylint: disable=C0121 # we need to do a per-element comparison, can't use "is not None"
                        if np.count_nonzero(I) == 0:
                            continue

                        cmpPoints = cmpPoints[I, :]                             # filter the cmp-array
                        recPoints = recPoints[I, :]                             # filter the rec-array too, as we still need this for offsets

                    # find the cmp locations that contribute to the output area
                    l = self.output.rctOutput.left()
                    r = self.output.rctOutput.right()
                    t = self.output.rctOutput.top()
                    b = self.output.rctOutput.bottom()

                    I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    # filter the cmp-array
                    cmpPoints = cmpPoints[I, :]
                    # filter the rec-array too, as we still need this
                    recPoints = recPoints[I, :]

                    offArray = np.zeros(shape=(recPoints.shape[0], 2), dtype=np.float32)
                    offArray = recPoints - src                       # define the offset array

                    l = self.offset.rctOffsets.left()
                    r = self.offset.rctOffsets.right()
                    t = self.offset.rctOffsets.top()
                    b = self.offset.rctOffsets.bottom()
                    I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    # filter the off-array
                    offArray = offArray[I, :]
                    # filter the cmp-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]
                    # filter the rec-array too, as we still need this
                    recPoints = recPoints[I, :]

                    hypArray = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                    # calculate per row
                    hypArray = np.hypot(offArray[:, 0], offArray[:, 1])

                    r1 = self.offset.radOffsets.x()                         # minimum radius
                    r2 = self.offset.radOffsets.y()                         # maximum radius
                    if r2 > 0:                                              # we need to apply the radial offset selection criteria
                        I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                        if np.count_nonzero(I) == 0:
                            continue                                        # continue with next recSeed

                        # filter the radial offset-array
                        hypArray = hypArray[I]
                        # filter the off-array too, as we still need this
                        offArray = offArray[I, :]
                        # filter the cmp-array too, as we still need this
                        cmpPoints = cmpPoints[I, :]
                        # filter the rec-array too, as we still need this
                        recPoints = recPoints[I, :]

                    #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                    # process all traces
                    for count, cmp in enumerate(cmpPoints):
                        try:                                                # protect against potential index errors
                            cmpX = cmp[0]
                            cmpY = cmp[1]
                            # local position in bin area
                            x, y = self.binTransform.map(cmpX, cmpY)
                            nx = int(x)
                            ny = int(y)

                            if fullAnalysis:
                                fold = self.output.binOutput[nx, ny]
                                if fold < self.grid.fold:                   # prevent overwriting next bin
                                    # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                    # line & stake nrs for reporting in extended np-array
                                    stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                    self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                    self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                    self.output.anaOutput[nx][ny][fold][2] = fold + 1           # to make fold run from 1 to N
                                    self.output.anaOutput[nx][ny][fold][3] = src[0]
                                    self.output.anaOutput[nx][ny][fold][4] = src[1]
                                    self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                    self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                    self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                    self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                                # self.output.anaOutput[nx][ny][fold][9]

                            # all selection criteria have been fullfilled; use the trace
                            self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                            self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                            self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

                        # rather than checking nx, ny & fold, use exception handling to deal with index errors
                        # note: the other exceptions are handled in binFromTemplates()
                        except IndexError:
                            continue

    def binTemplate6(self, block, template, templateOffset, fullAnalysis):
        """using *pointArray* for a significant speed up, introduce *vectorized* binning methods, removing for loop"""

        # convert the template offset (a QVector3D) to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:

            if not srcSeed.bSource:                                             # work only with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            # deal with block's source  border if it isn't null()
            if not block.borders.srcBorder.isNull():
                l = block.borders.srcBorder.left()
                r = block.borders.srcBorder.right()
                t = block.borders.srcBorder.top()
                b = block.borders.srcBorder.bottom()
                I = (srcArray[:, 0] >= l) & (srcArray[:, 0] <= r) & (srcArray[:, 1] >= t) & (srcArray[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue                                                    # if nothing succeeds; pick next seed
                srcArray = srcArray[I, :]                                       # filter the source array

            for src in srcArray:                                                # iterate over all sources

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # now iterate over all seeds to find the receivers
                for recSeed in template.seedList:                               # iterate over all rec seeds in a template
                    if recSeed.bSource:                                         # work with receiver seeds here
                        continue

                    # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                    recPoints = recSeed.pointArray + npTemplateOffset

                    # deal with block's receiver border if it isn't null()
                    if not block.borders.recBorder.isNull():
                        l = block.borders.recBorder.left()
                        r = block.borders.recBorder.right()
                        t = block.borders.recBorder.top()
                        b = block.borders.recBorder.bottom()
                        I = (recPoints[:, 0] >= l) & (recPoints[:, 0] <= r) & (recPoints[:, 1] >= t) & (recPoints[:, 1] <= b)
                        if np.count_nonzero(I) == 0:
                            continue
                        recPoints = recPoints[I, :]

                    cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

                    if self.binning.method == BinningType.cmp:
                        # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
                        cmpPoints = (recPoints + src) * 0.5
                    elif self.binning.method == BinningType.plane:
                        # create all cmp-locations using the following steps:
                        # 1. mirror the source location against the plane
                        # 2. find out where/if the lines defined by the source-mirror with the receivers cuts through the plane
                        # 3. these locations are the cmp locations for binnenig against a dipping plane
                        srcMirrorNp = self.localPlane.mirrorPointNp(src)

                        # now find all intersection points with the dipping plane, and prune any non-contributing receivers
                        cmpPoints, recPoints = self.localPlane.IntersectLinesAtPointNp(srcMirrorNp, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

                        if cmpPoints is None:
                            continue
                    elif self.binning.method == BinningType.sphere:

                        # now find all intersection points with the sphere, and prune any non-contributing receivers
                        cmpPoints, recPoints = self.localSphere.ReflectSphereAtPointsNp(src, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

                        if cmpPoints is None:
                            continue

                    # find the cmp locations that contribute to the output area
                    l = self.output.rctOutput.left()
                    r = self.output.rctOutput.right()
                    t = self.output.rctOutput.top()
                    b = self.output.rctOutput.bottom()

                    I = (cmpPoints[:, 0] >= l) & (cmpPoints[:, 0] <= r) & (cmpPoints[:, 1] >= t) & (cmpPoints[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    # filter the cmp-array
                    cmpPoints = cmpPoints[I, :]
                    # filter the rec-array too, as we still need this
                    recPoints = recPoints[I, :]

                    offArray = np.zeros(shape=(recPoints.shape[0], 2), dtype=np.float32)
                    offArray = recPoints - src                       # define the offset array

                    l = self.offset.rctOffsets.left()
                    r = self.offset.rctOffsets.right()
                    t = self.offset.rctOffsets.top()
                    b = self.offset.rctOffsets.bottom()
                    I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    # filter the off-array
                    offArray = offArray[I, :]
                    # filter the cmp-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]
                    # filter the rec-array too, as we still need this
                    recPoints = recPoints[I, :]

                    hypArray = np.zeros(shape=(recPoints.shape[0], 1), dtype=np.float32)
                    # calculate per row
                    hypArray = np.hypot(offArray[:, 0], offArray[:, 1])

                    r1 = self.offset.radOffsets.x()                         # minimum radius
                    r2 = self.offset.radOffsets.y()                         # maximum radius
                    if r2 > 0:                                              # we need to apply the radial offset selection criteria
                        I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                        if np.count_nonzero(I) == 0:
                            continue                                        # continue with next recSeed

                        # filter the radial offset-array
                        hypArray = hypArray[I]
                        # filter the off-array too, as we still need this
                        offArray = offArray[I, :]
                        # filter the cmp-array too, as we still need this
                        cmpPoints = cmpPoints[I, :]
                        # filter the rec-array too, as we still need this
                        recPoints = recPoints[I, :]

                    #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                    # process all traces
                    for count, cmp in enumerate(cmpPoints):
                        try:                                                # protect against potential index errors
                            cmpX = cmp[0]
                            cmpY = cmp[1]
                            # local position in bin area
                            x, y = self.binTransform.map(cmpX, cmpY)
                            nx = int(x)
                            ny = int(y)

                            if fullAnalysis:
                                fold = self.output.binOutput[nx, ny]
                                if fold < self.grid.fold:                   # prevent overwriting next bin
                                    # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

                                    # line & stake nrs for reporting in extended np-array
                                    stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                    self.output.anaOutput[nx][ny][fold][0] = int(stkX)
                                    self.output.anaOutput[nx][ny][fold][1] = int(stkY)
                                    self.output.anaOutput[nx][ny][fold][2] = fold + 1           # to make fold run from 1 to N
                                    self.output.anaOutput[nx][ny][fold][3] = src[0]
                                    self.output.anaOutput[nx][ny][fold][4] = src[1]
                                    self.output.anaOutput[nx][ny][fold][5] = recPoints[count, 0]
                                    self.output.anaOutput[nx][ny][fold][6] = recPoints[count, 1]
                                    self.output.anaOutput[nx][ny][fold][7] = cmpPoints[count, 0]
                                    self.output.anaOutput[nx][ny][fold][8] = cmpPoints[count, 1]
                                # self.output.anaOutput[nx][ny][fold][9]

                            # all selection criteria have been fullfilled; use the trace
                            self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                            self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                            self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

                        # rather than checking nx, ny & fold, use exception handling to deal with index errors
                        # note: the other exceptions are handled in binFromTemplates()
                        except IndexError:
                            continue

    def toXmlString(self, indent=4) -> str:
        # build the xml-tree by creating a QDomDocument and populating it
        doc = QDomDocument()
        self.writeXml(doc)
        # plain text representation of xml content
        plainText = doc.toString(indent)
        return plainText

    def fromXmlString(self, xmlString) -> bool:
        # first get a QDomDocument to work with
        doc = QDomDocument()
        # errorMsg, errorLine, errorColumn not being used
        success = doc.setContent(xmlString)

        # parsing went ok, start with a new survey object
        if success:
            # build the RollSurvey object tree
            self.readXml(doc)
            # calculate transforms to plot items at the right location
            self.calcTransforms()
            # needed for circles, spirals & well-seeds; may affect bounding box
            self.calcSeedData()
            # (re)calculate the boundingBox as part of parsing the data
            self.calcBoundingRect()

        return success

    def deepcopy(self):
        # regular deepcopy() does not work for the compound 'RollSurvey' object.
        # reason; pickle doesn't like the following objects:
        # ".crs (Type 'QgsCoordinateReferenceSystem' caused: cannot pickle 'QgsCoordinateReferenceSystem' object)",
        # ".blockList[0].templateList[0].seedList[0].pointPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".blockList[0].templateList[0].seedList[0].patternPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".patternList[0].pointPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".patternList[0].patternPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)"
        #
        # tested using: **get_unpicklable(instance, exception=None, string='', first_only=False)**. See functions.py
        # applied fix: copy via: object --> xml --> object

        plainText = self.toXmlString()
        surveyCopy = RollSurvey()
        succes = surveyCopy.fromXmlString(plainText)

        if succes:
            return surveyCopy
        else:
            return None

    def checkIntegrity(self):
        """this routine checks survey integrity, after edits have been made"""

        e = 'Survey format error'
        if len(self.blockList) == 0:
            QMessageBox.warning(None, e, 'A survey needs at least one block')
            return False

        for block in self.blockList:
            if len(block.templateList) == 0:
                QMessageBox.warning(None, e, 'Each block needs at least one template')
                return False

        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type == 4:                                          # well site; check for errors
                        f = seed.well.name                                      # check if well-file exists
                        if f is None or not os.path.exists(f):
                            QMessageBox.warning(None, e, 'A well-seed should point to an existing well-file')
                            return False

                        if seed.well.errorText is not None:
                            QMessageBox.warning(None, e, f'{seed.well.errorText} in well file:\n{f}')
                            return False

                        c = seed.well.crs                                       # check if crs is valid
                        if not c.isValid():
                            QMessageBox.warning(None, e, 'Invalid CRS.   \nPlease change CRS in well-seed')
                            return False

                        if c.isGeographic():                                   # check if crs is projected
                            QMessageBox.warning(None, e, f'{c.description()}. Invalid CRS (using lat/lon values).   \nPlease change CRS in well-seed')
                            return False

                            # the next check is too much hassle to implement, as we'll need to update the parameter tree too, to reflect changes in well CRS
                            # reply = QMessageBox.question(None, e, f'{c.description()}. Invalid CRS (using lat/lon values).  \nUse project CRS instead ?', QMessageBox.Ok, QMessageBox.Cancel)
                            # if reply == QMessageBox.Cancel:
                            #     return False
                            # c = self.crs                                        # use project CRS as proposed
                nSrc = 0
                nRec = 0
                for seed in template.seedList:
                    if seed.bSource:
                        nSrc += 1
                    else:
                        nRec += 1

                if nSrc == 0:
                    QMessageBox.warning(None, e, 'Each template needs at least one source seed')
                    return False

                if nRec == 0:
                    QMessageBox.warning(None, e, 'Each template needs at least one receiver seed')
                    return False
        return True

    def calcSeedData(self):
        # this routine relies on self.checkIntegrity() to spot any errors
        # reset seedList
        self.seedList = []
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    # avoid rendering stationary seed multiple times
                    seed.rendered = False
                    # add to seedList for quick access
                    self.seedList.append(seed)
                    # do this as well in the seed's preparation phase
                    seed.calcPointPicture()
                    if seed.type < 2:                                           # grid
                        seed.pointList = seed.grid.calcPointList(seed.origin)   # calculate the point list for this seed type
                        seed.grid.calcSalvoLine(seed.origin)                    # calc line to be drawn in low LOD values

                    elif seed.type == 2:                                        # circle
                        seed.pointList = seed.circle.calcPointList(seed.origin)   # calculate the point list for this seed type

                    elif seed.type == 3:                                        # spiral
                        seed.pointList = seed.spiral.calcPointList(seed.origin)   # calculate the point list for this seed type
                        seed.spiral.calcSpiralPath(seed.origin)                 # calc spiral path to be drawn
                    elif seed.type == 4:                                        # well site
                        seed.pointList, seed.origin = seed.well.calcPointList(self.crs, self.glbTransform)  # calculate the well's point list

                    # at this point; convert the point-lists to numpy-arrays for more efficient processing
                    seed.calcPointArray()                                       # setup the numpy arrays

    def createBasicSkeleton(self, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=2):

        # create a block
        block = RollBlock('block-1')

        # add block to survey object
        self.blockList.append(block)

        for template in range(nTemplates):

            # create a template
            templateName = f'template-{template + 1}'
            template = RollTemplate(templateName)

            # add template to block object
            block.templateList.append(template)

            # create a 'vertical' roll object
            roll1 = RollTranslate()

            # add roll object to template's rollList
            template.rollList.append(roll1)

            # create a 'horizontal' roll object
            roll2 = RollTranslate()

            # add roll object to template's rollList
            template.rollList.append(roll2)

            for srcSeed in range(nSrcSeeds):

                # create a source seed object
                seedName = f'src-{srcSeed + 1}'
                seedSrc = RollSeed(seedName)
                seedSrc.bSource = True
                seedSrc.color = QColor('#77FF8989')

                # add seed object to template
                template.seedList.append(seedSrc)

                # create a 'lines' grow object
                growR1 = RollTranslate()

                # add grow object to seed's growlist
                seedSrc.grid.growList.append(growR1)

                # create a 'points' grow object
                growR2 = RollTranslate()

                # add grow object to seed
                seedSrc.grid.growList.append(growR2)

            for recSeed in range(nRecSeeds):

                # create a receiver seed object
                seedName = f'rec-{recSeed + 1}'
                seedRec = RollSeed(seedName)
                seedRec.bSource = False
                seedRec.color = QColor('#7787A4D9')

                # add seed object to template
                template.seedList.append(seedRec)

                # create a 'lines' grow object
                growR1 = RollTranslate()

                # add grow object to seed's growlist
                seedRec.grid.growList.append(growR1)

                # create a 'points' grow object
                growR2 = RollTranslate()

                # add grow object to seed
                seedRec.grid.growList.append(growR2)

        for pattern in range(nPatterns):
            patternName = f'pattern-{pattern + 1}'

            # first create a pattern
            pattern = RollPattern(patternName)

            # create a 'vertical' grow object
            grow1 = RollTranslate()

            # add grow object to pattern's growList
            pattern.growList.append(grow1)

            # create a 'horizontal' grow object
            grow2 = RollTranslate()

            # add grow object to pattern's growList
            pattern.growList.append(grow2)

            # add block to survey object
            self.patternList.append(pattern)

    # the root element is created within the survey object
    def writeXml(self, doc: QDomDocument):

        doc.clear()

        instruction = doc.createProcessingInstruction('xml', 'version="1.0" encoding="UTF-8"')
        doc.appendChild(instruction)

        root = doc.createElement('survey')
        root.setAttribute('version', '1.0')
        doc.appendChild(root)

        pathElement = doc.createElement('type')

        text = doc.createTextNode(self.type.name)
        pathElement.appendChild(text)
        root.appendChild(pathElement)

        nameElement = doc.createElement('name')
        text = doc.createTextNode(self.name)
        nameElement.appendChild(text)
        root.appendChild(nameElement)

        surveyCrs = doc.createElement('surveyCrs')
        root.appendChild(surveyCrs)
        if self.crs is not None:                                                # check if we have a valid crs
            self.crs.writeXml(surveyCrs, doc)                                   # write xml-string to parent element (=surveyCrs)

        limitsElement = doc.createElement('limits')
        root.appendChild(limitsElement)
        self.output.writeXml(limitsElement, doc)
        self.angles.writeXml(limitsElement, doc)
        self.offset.writeXml(limitsElement, doc)
        self.unique.writeXml(limitsElement, doc)
        self.binning.writeXml(limitsElement, doc)

        reflectorElement = doc.createElement('reflectors')
        root.appendChild(reflectorElement)
        self.globalPlane.writeXml(reflectorElement, doc)
        self.globalSphere.writeXml(reflectorElement, doc)

        self.grid.writeXml(root, doc)

        blockListElement = doc.createElement('block_list')
        root.appendChild(blockListElement)

        for block in self.blockList:
            block.writeXml(blockListElement, doc)

        patternListElement = doc.createElement('pattern_list')
        root.appendChild(patternListElement)

        for pattern in self.patternList:
            pattern.writeXml(patternListElement, doc)

        return root

    def readXml(self, doc: QDomDocument):

        root = doc.documentElement()
        version = QDomElement.attribute(root, 'version')

        if root.tagName() != 'survey' or version != '1.0':
            QMessageBox.information(None, 'Read error', 'Format and/or version of this survey file is incorrect')
            return False

        n = root.firstChild()
        while not n.isNull():
            # try to convert the node to an element.
            e = n.toElement()
            if not e.isNull():
                # the node really is an element.
                tagName = e.tagName()

                # print(tagName + "---->")

                if tagName == 'type':
                    self.type = surveyType[e.text()]

                if tagName == 'name':
                    self.name = e.text()

                if tagName == 'surveyCrs':
                    self.crs.readXml(e)
                    # print( self.crs.authid())
                    # print( self.crs.srsid())
                    # print( self.crs.isGeographic())

                if tagName == 'limits':
                    self.output.readXml(e)
                    self.angles.readXml(e)
                    self.offset.readXml(e)
                    self.unique.readXml(e)
                    self.binning.readXml(e)

                if tagName == 'grid':
                    self.grid.readXml(e)

                if tagName == 'reflectors':
                    self.globalPlane.readXml(e)
                    self.globalSphere.readXml(e)

                if tagName == 'block_list':
                    # b = e.namedItem('block')

                    b = e.firstChildElement('block')
                    while not b.isNull():
                        block = RollBlock()
                        block.readXml(b)
                        self.blockList.append(block)
                        b = b.nextSiblingElement('block')

                if tagName == 'pattern_list':
                    p = e.firstChildElement('pattern')
                    while not p.isNull():
                        pattern = RollPattern()
                        pattern.readXml(p)
                        self.patternList.append(pattern)
                        p = p.nextSiblingElement('pattern')
            n = n.nextSibling()

    # RollSurvey boundaries
    def resetBoundingRect(self):

        for block in self.blockList:
            block.resetBoundingRect()

        # reset survey spatial extent
        # source extent
        self.srcBoundingRect = QRectF()
        # receiver extent
        self.recBoundingRect = QRectF()
        # cmp extent
        self.cmpBoundingRect = QRectF()
        # src|rec extent
        self.boundingBox = QRectF()

    # RollSurvey boundaries
    def calcBoundingRect(self, roll=True):
        # initialise pattern figures
        for pattern in self.patternList:
            pattern.calcPatternPicture()

        # we also need to update the template-seeds giving them the right pattern type
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type < 2 and seed.patternNo > -1 and seed.patternNo < len(self.patternList):
                        translate = seed.grid.growList[-1]
                        if translate and seed.bAzimuth:                         # need to reorient the pattern
                            # get the slant angle (deviation from orthogonal
                            angle = math.degrees(math.atan2(translate.increment.x(), translate.increment.y()))
                            # create painter object to draw against
                            painter = QPainter(seed.patternPicture)
                            # rotate painter in opposite direction before drawing
                            painter.rotate(-angle)
                            painter.drawPicture(0, 0, self.patternList[seed.patternNo].patternPicture)
                            painter.end()
                        else:
                            seed.patternPicture = self.patternList[seed.patternNo].patternPicture
                    else:
                        seed.patternPicture = None

        # do the real work here...
        for block in self.blockList:
            srcBounds, recBounds, cmpBounds = block.calcBoundingRect(roll)
            self.srcBoundingRect |= srcBounds                                   # add it
            self.recBoundingRect |= recBounds                                   # add it
            self.cmpBoundingRect |= cmpBounds                                   # add it

        self.boundingBox = self.srcBoundingRect | self.recBoundingRect
        # stretch it to capture overflowing patterns
        self.boundingBox += QMarginsF(50, 50, 50, 50)

        return self.boundingBox

    # required for painting a pg.GraphicsObject
    def boundingRect(self):
        if self.boundingBox.isEmpty():
            return self.calcBoundingRect()
        else:
            # earlier derived result, from blocks -> templates -> seeds
            return self.boundingBox

    def paint(self, painter, option, _):
        # the paint function actually is: paint(self, painter, option, widget) but widget is not being used
        with pg.BusyCursor():
            # See: https://doc.qt.io/qt-6/qgraphicsitem.html#paint and for QGraphicsItem::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget = nullptr)
            # See: https://doc.qt.io/qt-6/qstyleoptiongraphicsitem.html for LOD painting using QStyleOptionGraphicsItem
            # the 'option' can be used to access LOD directly by using:
            # lod = option.levelOfDetailFromTransform(painter.worldTransform())

            # vb = self.getViewBox().viewRect()
            # print("\n\n\nVB  = " + "x0:{:.2f} y0:{:.2f}, xmax:{:.2f} ymax:{:.2f}".format(vb.left(), vb.top(), vb.left()+vb.width(), vb.top()+vb.height()))
            # # print ("Painting - Mouse grabbed: " + str(self.mouseGrabbed))

            # vb = self.getViewBox().itemBoundingRect(self)
            # print("VB1 = " + "x0:{:.2f} y0:{:.2f}, xmax:{:.2f} ymax:{:.2f}".format(vb.left(), vb.top(), vb.left()+vb.width(), vb.top()+vb.height()))

            vb = self.viewRect()
            # print(f"VB2 = x0:{vb.left():.2f} y0:{vb.top():.2f}, xmax:{vb.left()+vb.width():.2f} ymax:{vb.top()+vb.height():.2f}")

            lod = option.levelOfDetailFromTransform(painter.worldTransform())
            # print("LOD = " + str(lod))

            if lod < config.lod0:                                               # so small; just paint the survey outline
                # use a black pen for borders
                painter.setPen(pg.mkPen('k'))
                # dark grey solid brush
                painter.setBrush(pg.mkBrush((64, 64, 64, 255)))
                # that's all that needs to be painted
                painter.drawRect(self.boundingRect())
                return

            # use a black pen for borders
            painter.setPen(pg.mkPen('k'))
            # grey & semi-transparent, use for all templates
            painter.setBrush(pg.mkBrush((192, 192, 192, 7)))

            length = len(self.seedList)
            for i in range(length):
                s = self.seedList[i]
                s.rendered = False

            # for seed in self.seedList
            #     seed.rendered = False                                           # avoid rendering stationary seed multiple times

            for block in self.blockList:                                        # get all blocks
                if block.boundingBox.intersects(vb):                            # is block within viewbox ?

                    for template in block.templateList:                         # get all templates
                        # how deep is the list ?
                        length = len(template.rollList)
                        # possibly restrict nr templates being drawn (all, one, none)
                        length = min(length, self.paintMode.value)

                        if length < 0:                                          # don't paint any templates
                            pass
                        elif length == 0:
                            # always start at (0, 0, 0)
                            offset = QVector3D(0.0, 0.0, 0.0)
                            templt = template.templateBox                       # no translation required
                            if not templt.intersects(vb):
                                continue                                        # outside viewbox; skip it

                            if lod < config.lod1:                               # so small; just paint the template outline
                                templt &= self.boundingBox                      # we need to restrict it
                                # draw template rectangle
                                painter.drawRect(templt)
                            else:
                                self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 1:
                            # get the template boundaries
                            for i in range(template.rollList[0].steps):
                                # always start at (0, 0, 0)
                                offset = QVector3D(0.0, 0.0, 0.0)
                                offset += template.rollList[0].increment * i
                                templt = template.templateBox.translated(offset.toPointF())  # we now have the correct location
                                if not templt.intersects(vb):
                                    continue                                    # outside viewbox; skip it

                                if lod < config.lod1:                           # so small; just paint the template outline
                                    templt &= self.boundingBox                  # we need to restrict it
                                    # draw template rectangle
                                    painter.drawRect(templt)
                                else:
                                    self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 2:
                            for i in range(template.rollList[0].steps):
                                for j in range(template.rollList[1].steps):
                                    # always start at (0, 0, 0)
                                    offset = QVector3D(0.0, 0.0, 0.0)
                                    offset += template.rollList[0].increment * i
                                    offset += template.rollList[1].increment * j
                                    templt = template.templateBox.translated(offset.toPointF())  # we now have the correct location
                                    if not templt.intersects(vb):
                                        continue                                # outside viewbox; skip it

                                    # print("TPL = " + "x0:{:.2f} y0:{:.2f}, xmax:{:.2f} ymax:{:.2f}"
                                    # .format(templt.left(), templt.top(), templt.left()+templt.width(), templt.top()+templt.height()))

                                    if lod < config.lod1:                       # so small; just paint the template outline
                                        templt &= self.boundingBox              # we need to restrict it
                                        # draw template rectangle
                                        painter.drawRect(templt)
                                    else:
                                        self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 3:
                            for i in range(template.rollList[0].steps):
                                for j in range(template.rollList[1].steps):
                                    for k in range(template.rollList[2].steps):
                                        # always start at (0, 0, 0)
                                        offset = QVector3D(0.0, 0.0, 0.0)
                                        offset += template.rollList[0].increment * i
                                        offset += template.rollList[1].increment * j
                                        offset += template.rollList[2].increment * k
                                        templt = template.templateBox.translated(offset.toPointF())  # we now have the correct location
                                        if not templt.intersects(vb):
                                            continue                            # outside viewbox; skip it

                                        if lod < config.lod1:                   # so small; just paint the template outline
                                            templt &= self.boundingBox          # we need to restrict it
                                            # draw template rectangle
                                            painter.drawRect(templt)
                                        else:
                                            self.paintTemplate(painter, vb, lod, template, offset)
                        else:
                            # do something recursively; not  implemented yet
                            raise NotImplementedError('More than three roll steps currently not allowed.')

                    # a survey may have more than one block; do this for each block

                    # painter.setPen(pg.mkPen("r", style=Qt.DashLine))          # use a dashed red line for the border
                    # use a dashed red line for the border
                    painter.setPen(config.srcAreaPen)
                    # painter.setBrush(pg.mkBrush((255, 0, 0, 8)))              # red & semi-transparent; mkBrush uses RGBA instead of ARGB
                    # red & semi-transparent
                    painter.setBrush(QBrush(QColor(config.srcAreaColor)))
                    painter.drawRect(block.srcBoundingRect)

                    # painter.setPen(pg.mkPen("b", style=Qt.DashLine))          # use a dashed blue line for the border
                    # use a dashed blue line for the border
                    painter.setPen(config.recAreaPen)
                    # painter.setBrush(pg.mkBrush((0, 0, 255, 8)))              # blue & semi-transparent; mkBrush uses RGBA instead of ARGB
                    # blue & semi-transparent
                    painter.setBrush(QBrush(QColor(config.recAreaColor)))
                    painter.drawRect(block.recBoundingRect)

                    # painter.setPen(pg.mkPen("g", style=Qt.DashLine))          # use a dashed green line for the border
                    # use a dashed green line for the border
                    painter.setPen(config.cmpAreaPen)
                    # painter.setBrush(pg.mkBrush((0, 255, 0, 8)))              # green & semi-transparent; mkBrush uses RGBA instead of ARGB
                    # green & semi-transparent
                    painter.setBrush(QBrush(QColor(config.cmpAreaColor)))
                    painter.drawRect(block.cmpBoundingRect)

            # a survey has only one binning output area; show this in black
            if self.output.rctOutput.isValid():
                # painter.setPen(pg.mkPen("k", style=Qt.DashLine))              # use a dashed black line for the border
                # use a dashed black line for the border
                painter.setPen(config.binAreaPen)
                # painter.setBrush(pg.mkBrush((0, 0, 0, 32)))                     # black & semi-transparent
                # red & semi-transparent
                painter.setBrush(QBrush(QColor(config.binAreaColor)))
                painter.drawRect(self.output.rctOutput)

            # done painting; next time maybe more details required
            self.mouseGrabbed = False

    def paintTemplate(self, painter, viewbox, lod, template, templateOffset):

        # iterate over all seeds in a template
        for seed in template.seedList:
            # use a solid pen, 2 pixels wide
            painter.setPen(pg.mkPen(seed.color, width=2))

            if seed.type < 2 and seed.rendered is False:                       # grid based seed
                if seed.type == 1:
                    # no rolling along; fixed grid
                    templateOffset = QVector3D()
                    seed.rendered = True

                # how deep is the grow list ?
                length = len(seed.grid.growList)

                if length == 0:
                    # always start at (0, 0, 0)
                    offset = QVector3D(0.0, 0.0, 0.0)
                    offset += templateOffset                                    # start here
                    # move the line into place
                    salvo = seed.grid.salvo.translated(offset.toPointF())
                    # check line against block's src/rec border
                    salvo = clipLineF(salvo, seed.blockBorder)
                    # check line against viewbox
                    salvo = clipLineF(salvo, viewbox)

                    if not salvo.isNull():
                        if lod < config.lod2 or self.mouseGrabbed:              # just draw lines
                            painter.drawLine(salvo)
                        else:
                            # start at templateOffset and add seed's origin
                            seedOrigin = offset + seed.origin
                            # is it within block limits ?
                            if containsPoint3D(seed.blockBorder, seedOrigin):
                                # is it within the viewbox ?
                                if containsPoint3D(viewbox, seedOrigin):
                                    # paint seed picture
                                    painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)
                                    if lod > config.lod3 and seed.patternPicture is not None:
                                        # paint pattern picture
                                        painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 1:
                    # always start at (0, 0, 0)
                    offset = QVector3D(0.0, 0.0, 0.0)
                    offset += templateOffset                                    # start here
                    # move the line into place
                    salvo = seed.salvo.grid.translated(offset.toPointF())
                    # check line against block's src/rec border
                    salvo = clipLineF(salvo, seed.blockBorder)
                    # check line against viewbox
                    salvo = clipLineF(salvo, viewbox)

                    if not salvo.isNull():
                        if lod < config.lod2 or self.mouseGrabbed:              # just draw lines
                            painter.drawLine(salvo)
                        else:
                            # iterate over 1st step
                            for i in range(seed.grid.growList[0].steps):
                                # start at templateOffset and add seed's origin
                                seedOrigin = offset + seed.origin
                                # we now have the correct location
                                seedOrigin += seed.grid.growList[0].increment * i
                                # is it within block limits ?
                                if containsPoint3D(seed.blockBorder, seedOrigin):
                                    # is it within the viewbox ?
                                    if containsPoint3D(viewbox, seedOrigin):
                                        # paint seed picture
                                        painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)
                                        if lod > config.lod3 and seed.patternPicture is not None:
                                            # paint pattern picture
                                            painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 2:
                    # iterate over 1st step
                    for i in range(seed.grid.growList[0].steps):
                        # always start at (0, 0, 0)
                        offset = QVector3D(0.0, 0.0, 0.0)
                        offset += templateOffset                                # start here
                        # we now have the correct location
                        offset += seed.grid.growList[0].increment * i
                        # move the line into place
                        salvo = seed.grid.salvo.translated(offset.toPointF())
                        # check line against block's src/rec border
                        salvo = clipLineF(salvo, seed.blockBorder)
                        # check line against viewbox
                        salvo = clipLineF(salvo, viewbox)
                        if not salvo.isNull():
                            if lod < config.lod2 or self.mouseGrabbed:          # just draw lines
                                painter.drawLine(salvo)
                            else:
                                for j in range(seed.grid.growList[1].steps):
                                    # start at templateOffset and add seed's origin
                                    seedOrigin = offset + seed.origin
                                    # we now have the correct location
                                    seedOrigin += seed.grid.growList[1].increment * j
                                    # is it within block limits ?
                                    if containsPoint3D(seed.blockBorder, seedOrigin):
                                        # is it within the viewbox ?
                                        if containsPoint3D(viewbox, seedOrigin):
                                            # paint seed picture
                                            painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)
                                            if lod > config.lod3 and seed.patternPicture is not None:
                                                # paint pattern picture
                                                painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 3:
                    for i in range(seed.grid.growList[0].steps):
                        for j in range(seed.grid.growList[1].steps):
                            # always start at (0, 0)
                            offset = QVector3D(0.0, 0.0, 0.0)
                            offset += templateOffset                            # start here
                            # we now have the correct location
                            offset += seed.grid.growList[0].increment * i
                            # we now have the correct location
                            offset += seed.grid.growList[1].increment * j
                            # move the line into place
                            salvo = seed.grid.salvo.translated(offset.toPointF())
                            # check line against block's src/rec border
                            salvo = clipLineF(salvo, seed.blockBorder)
                            # check line against viewbox
                            salvo = clipLineF(salvo, viewbox)
                            if not salvo.isNull():
                                if lod < config.lod2 or self.mouseGrabbed:      # just draw lines
                                    painter.drawLine(salvo)
                                else:
                                    for k in range(seed.grid.growList[2].steps):
                                        # start at templateOffset and add seed's origin
                                        seedOrigin = offset + seed.origin
                                        # we now have the correct location
                                        seedOrigin += seed.grid.growList[2].increment * k
                                        # is it within block limits ?
                                        if containsPoint3D(seed.blockBorder, seedOrigin):
                                            # is it within the viewbox ?
                                            if containsPoint3D(viewbox, seedOrigin):
                                                # paint seed picture
                                                painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)
                                                if lod > config.lod3 and seed.patternPicture is not None:
                                                    # paint pattern picture
                                                    painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)
                else:
                    # do something recursively; not  implemented yet
                    raise NotImplementedError('More than three grow steps currently not allowed.')

            if seed.type == 2 and seed.rendered is False:                       # circle seed
                seed.rendered = True
                if lod < config.lod2 or self.mouseGrabbed:                      # just draw a circle

                    # empty brush
                    painter.setBrush(QBrush())
                    r = seed.circle.radius
                    o = seed.origin.toPointF()
                    painter.drawEllipse(o, r, r)
                else:
                    length = len(seed.pointList)
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        # paint seed picture
                        painter.drawPicture(p, seed.pointPicture)

            if seed.type == 3 and seed.rendered is False:                       # spiral seed
                seed.rendered = True
                if lod < config.lod2 or self.mouseGrabbed:                      # just draw two circles

                    # empty brush
                    painter.setBrush(QBrush())
                    # r1 = seed.spiral.radMin
                    # r2 = seed.spiral.radMax
                    # o = seed.origin.toPointF()
                    # painter.drawEllipse(o, r1, r1)
                    # painter.drawEllipse(o, r2, r2)
                    # draw spiral shape
                    painter.drawPath(seed.spiral.path)
                else:
                    # empty brush
                    painter.setBrush(QBrush())
                    # r1 = seed.spiral.radMin
                    # r2 = seed.spiral.radMax
                    # o = seed.origin.toPointF()
                    # painter.drawEllipse(o, r1, r1)
                    # painter.drawEllipse(o, r2, r2)
                    # draw spiral shape
                    painter.drawPath(seed.spiral.path)
                    length = len(seed.pointList)

                    # for p in seed.pointList                                   # this for loop causes a crash ???
                    #     painter.drawPicture(p.toPointF(), seed.pointPicture)  # paint seed picture; causes problems when list is empty
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        # paint seed picture
                        painter.drawPicture(p, seed.pointPicture)

            if seed.type == 4 and seed.rendered is False:                       # well seed
                seed.rendered = True
                # draw well trajectory as part of this template; move this up to paint()
                painter.drawPolyline(seed.well.polygon)
                # draw small circle where well surfaces
                painter.drawEllipse(seed.well.origL, 5.0, 5.0)

                # need the in-well points as well...
                if lod > config.lod2 and not self.mouseGrabbed:
                    length = len(seed.pointList)
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        # paint seed picture
                        painter.drawPicture(p, seed.pointPicture)


# CLASS ###############################################################################


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
