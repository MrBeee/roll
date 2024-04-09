"""
This module provides the main classes used in Roll
"""
import math
import os
from collections import defaultdict
from enum import Enum

import numpy as np
import pyqtgraph as pg
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QMarginsF, QPointF, QRectF, QThread, pyqtSignal
from qgis.PyQt.QtGui import QBrush, QColor, QPainter, QTransform, QVector3D
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from . import config  # used to pass initial settings
from .functions import clipLineF, containsPoint2D, containsPoint3D
from .roll_angles import RollAngles
from .roll_bingrid import RollBinGrid
from .roll_binning import BinningType, RollBinning
from .roll_block import RollBlock
from .roll_offset import RollOffset
from .roll_output import RollOutput
from .roll_pattern import RollPattern
from .roll_plane import RollPlane
from .roll_seed import RollSeed
from .roll_sphere import RollSphere
from .roll_template import RollTemplate
from .roll_translate import RollTranslate
from .roll_unique import RollUnique
from .sps_io_and_qc import pntType1, relType2

try:
    from numba import *  # pylint: disable=w0401,w0614 # I don't want to modify 3rd party code on en/disabling numba
except ImportError:
    from .nonumba import *  # pylint: disable=w0401,w0614 # I don't want to modify 3rd party code on en/disabling numba


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


class SurveyType(Enum):
    Orthogonal = 0
    Parallel = 1
    Slanted = 2
    Brick = 3
    Zigzag = 4


# Note: we need to keep SurveyType and SurveyList in sync; maybe combine in a dictionary ?!
SurveyList = [
    'Orthogonal - standard manner of acquiring land data',
    'Parallel - standard manner of acquiring OBN data',
    'Slanted - legacy variation on orthogonal, aiming to reduce LMOS',
    'Brick - legacy variation on orthogonal, aiming to reduce LMOS',
    'zigzag - legacy manner acquiring narrrow azimuth vibroseis data',
]


class PaintMode(Enum):
    noTemplates = -1
    oneTemplate = 0
    allTemplates = 4


class SeedType(Enum):
    grid = 0
    circle = 1
    spiral = 2
    well = 3


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
        self.typ_ = SurveyType.Orthogonal
        self.name: str = name

        # survey painting mode
        self.PaintMode = PaintMode.allTemplates

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

        self.output.binOutput = np.zeros(shape=(nx, ny), dtype=np.uint32)       # start with empty array of the right size and type
        self.output.minOffset = np.zeros(shape=(nx, ny), dtype=np.float32)      # start with empty array of the right size and type
        self.output.maxOffset = np.zeros(shape=(nx, ny), dtype=np.float32)      # start with empty array of the right size and type
        self.output.minOffset.fill(np.Inf)                                      # start min offset with +inf (use np.full instead)
        self.output.maxOffset.fill(np.NINF)                                     # start max offset with -inf (use np.full instead)

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
        """iterate over all seeds in a template; make sure we start wih *source* seeds
        iterate using the three levels in the growList (slow approach)"""
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
        """use numpy arrays instead of iterating over the growList
        this provides a much faster approach then using the growlist"""

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
            self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0

            success = self.binFromGeometry4(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromGeometry4(False)

    def binFromGeometry4(self, fullAnalysis) -> bool:
        """
        all binning methods implemented, using numpy arrays, rather than a for-loop

        On 09/04/2024 the earlier implementations of binTemplate v1 to v5 have been removed.
        They are still available in the roll-2024-08-04 folder in classes.py
        """
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
                        recArray = np.concatenate((recPoints, recLine))         # need to supply arrays to be concatenated as a tuple !
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

                size = recPoints.shape[0]
                offArray = np.zeros(shape=(size, 3), dtype=np.float32)          # allocate the offset array according to rec array
                offArray = recPoints - src                                      # define the offset array

                l = self.offset.rctOffsets.left()
                r = self.offset.rctOffsets.right()
                t = self.offset.rctOffsets.top()
                b = self.offset.rctOffsets.bottom()
                I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                if np.count_nonzero(I) == 0:
                    continue

                offArray = offArray[I, :]                                       # filter the offset-array
                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array too, as we still need this
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this

                size = recPoints.shape[0]
                hypArray = np.zeros(shape=(size, 1), dtype=np.float32)          # allocate the radius array according to rec array
                hypArray = np.hypot(offArray[:, 0], offArray[:, 1])             # calculate radial offset size
                aziArray = np.arctan2(offArray[:, 0], offArray[:, 1])           # calculate offset angles
                aziArray = np.rad2deg(aziArray)                                 # get angles in degrees instead of radians

                r1 = self.offset.radOffsets.x()                                 # r1 = minimum radius
                r2 = self.offset.radOffsets.y()                                 # r2 = maximum radius
                if r2 > 0:                                                      # we need to apply the radial offset selection criteria
                    I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                    if np.count_nonzero(I) == 0:
                        continue                                                # continue with next recSeed
                    # print(I)
                    hypArray = hypArray[I]                                      # filter the radial offset-array
                    aziArray = aziArray[I]                                      # filter the offset-angle array too
                    offArray = offArray[I, :]                                   # filter the off-array too, as we still need this
                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                # now work on the TWT aspect of the src, cmp & rec positions
                if self.binning.method == BinningType.cmp:
                    upDnArray = recPoints - src                                 # straigth rays; total length of both legs
                    totalTime = np.linalg.norm(upDnArray, axis=1)               # get length of the rays
                else:
                    downArray = cmpPoints - src                                 # 1st leg of the rays
                    up__Array = cmpPoints - recPoints                           # 2nd leg of the rays
                    downTime = np.linalg.norm(downArray, axis=1)                # get length of the 1st leg
                    up__Time = np.linalg.norm(up__Array, axis=1)                # get length of the 2nd leg
                    totalTime = downTime + up__Time                             # total length of both legs

                totalTime *= self.binning.slowness                              # convert distance into travel time

                #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                for count, cmp in enumerate(cmpPoints):                         # process all traces
                    try:
                        cmpX = cmp[0]
                        cmpY = cmp[1]

                        x, y = self.binTransform.map(cmpX, cmpY)                # local position in bin area
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
                                self.output.anaOutput[nx][ny][fold][9] = totalTime[count]
                                self.output.anaOutput[nx][ny][fold][10] = hypArray[count]
                                self.output.anaOutput[nx][ny][fold][11] = aziArray[count]
                                self.output.anaOutput[nx][ny][fold][12] = 1

                        # all selection criteria have been fullfilled; use the trace
                        self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                        self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                        self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

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
        """this routine is used for working from templates only"""

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        if fullAnalysis:
            self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0
            success = self.binFromTemplates(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromTemplates(False)

    # See: https://github.com/pyqtgraph/pyqtgraph/issues/1253, how to use numba with PyQtGraph
    # See: https://numba.readthedocs.io/en/stable/user/jit.html for preferred way of using @jit
    # See: https://stackoverflow.com/questions/57774497/how-do-i-make-a-dummy-do-nothing-jit-decorator

    @jit  # pylint: disable=used-before-assignment # undefined variable in case of using nonumba (suppressing E601 does not work !)
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

        # implement code to handle unique offsets
        if self.unique.apply:                                               # slot offsets and azimuths and prune data
            slottedOffset = self.output.anaOutput[:, :, :, 10]              # grab every 10th element of 4th dimension
            slot = 200.0
            scalar = 1.0 / slot
            slottedOffset = slottedOffset * scalar
            slottedOffset = np.round(slottedOffset)
            slottedOffset = slottedOffset * slot
            self.output.anaOutput[:, :, :, 10] = slottedOffset

            slottedAzimuth = self.output.anaOutput[:, :, :, 11]              # grab every 10th element of 4th dimension
            slot = 10.0
            scalar = 1.0 / slot
            slottedAzimuth = slottedAzimuth * scalar
            slottedAzimuth = np.round(slottedAzimuth)
            slottedAzimuth = slottedAzimuth * slot
            self.output.anaOutput[:, :, :, 11] = slottedAzimuth

            # Now we need to find unique rows in terms of line, stake, offset and azimuth values
            # See:  https://stackoverflow.com/questions/16970982/find-unique-rows-in-numpy-array
            # See:  https://www.geeksforgeeks.org/find-unique-rows-in-a-numpy-array/

            # testUnique = self.output.anaOutput[:, :, :, [0, 1, 10, 11]]     # extract stake, line, offset and azimuth
            # unique, indices = np.unique(testUnique, return_index=True)
            # self.output.anaOutput[:, :, :, 12] = indices.astype(int)        # write unique offsets back into analysis array

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

    @jit  # pylint: disable=e0602 # undefined variable in case of using nonumba
    def binTemplate6(self, block, template, templateOffset, fullAnalysis):
        """
        using *pointArray* for a significant speed up,
        introduced *vectorized* binning methods, removed need for a for loop

        On 25/03/2024 the earlier implementations of binTemplate v1 to v5 have been removed.
        They are still available in the roll-2024-03-04 folder in classes.py
        """

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

                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                    size = recPoints.shape[0]
                    offArray = np.zeros(shape=(size, 3), dtype=np.float32)      # allocate the offset array according to rec array
                    offArray = recPoints - src                                  # fill the offset array with  (x,y,z) values

                    l = self.offset.rctOffsets.left()
                    r = self.offset.rctOffsets.right()
                    t = self.offset.rctOffsets.top()
                    b = self.offset.rctOffsets.bottom()
                    I = (offArray[:, 0] >= l) & (offArray[:, 0] <= r) & (offArray[:, 1] >= t) & (offArray[:, 1] <= b)
                    if np.count_nonzero(I) == 0:
                        continue

                    offArray = offArray[I, :]                                   # filter the off-array
                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                    size = recPoints.shape[0]
                    hypArray = np.zeros(shape=(size, 1), dtype=np.float32)      # allocate the radius array according to rec array
                    hypArray = np.hypot(offArray[:, 0], offArray[:, 1])         # calculate radial offset per row
                    aziArray = np.arctan2(offArray[:, 0], offArray[:, 1])       # calculate offset angles
                    aziArray = np.rad2deg(aziArray)                             # get angles in degrees instead of radians

                    r1 = self.offset.radOffsets.x()                             # r1 = minimum radius
                    r2 = self.offset.radOffsets.y()                             # r2 = maximum radius
                    if r2 > 0:                                                  # we need to apply the radial offset selection criteria
                        I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                        if np.count_nonzero(I) == 0:
                            continue                                            # continue with next recSeed

                        hypArray = hypArray[I]                                  # filter the radial offset-array
                        aziArray = aziArray[I]                                  # filter the offset-angle array
                        offArray = offArray[I, :]                               # filter the off-array too, as we still need this
                        cmpPoints = cmpPoints[I, :]                             # filter the cmp-array too, as we still need this
                        recPoints = recPoints[I, :]                             # filter the rec-array too, as we still need this

                    # now work on the TWT aspect of the src, cmp & rec positions
                    if self.binning.method == BinningType.cmp:
                        upDnArray = recPoints - src                             # straigth rays; total length of both legs
                        totalTime = np.linalg.norm(upDnArray, axis=1)           # get length of the rays
                    else:
                        downArray = cmpPoints - src                             # 1st leg of the rays
                        up__Array = cmpPoints - recPoints                       # 2nd leg of the rays
                        downTime = np.linalg.norm(downArray, axis=1)            # get length of the 1st leg
                        up__Time = np.linalg.norm(up__Array, axis=1)            # get length of the 2nd leg
                        totalTime = downTime + up__Time                         # total length of both legs

                    totalTime *= self.binning.slowness                          # convert distance into travel time

                    #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
                    for count, cmp in enumerate(cmpPoints):                     # process all traces
                        try:                                                    # protect against potential index errors
                            cmpX = cmp[0]                                       # decompose (x, y, z) cmp into x, y components
                            cmpY = cmp[1]

                            x, y = self.binTransform.map(cmpX, cmpY)            # get local position in bin area
                            nx = int(x)                                         # truncate into integer indices
                            ny = int(y)                                         # truncate into integer indices

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
                                    self.output.anaOutput[nx][ny][fold][9] = totalTime[count]
                                    self.output.anaOutput[nx][ny][fold][10] = hypArray[count]
                                    self.output.anaOutput[nx][ny][fold][11] = aziArray[count]
                                    self.output.anaOutput[nx][ny][fold][12] = 1

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
                    if seed.typ_ == 4:                                          # well site; check for errors
                        f = seed.well.name                                      # check if well-file exists
                        if f is None or not os.path.exists(f):
                            QMessageBox.warning(None, e, f'A well-seed should point to an existing well-file\nRemove seed or adjust name in well-seed "{seed.name}"')
                            return False

                        if seed.well.errorText is not None:
                            QMessageBox.warning(None, e, f'{seed.well.errorText} in well file:\n{f}\nRemove seed or correct error in well-seed "{seed.name}"')
                            return False

                        c = seed.well.crs                                       # check if crs is valid; not really needed already checked in RollWell
                        if not c.isValid():
                            QMessageBox.warning(None, e, f'Invalid CRS in well-seed\nPlease change CRS in well-seed "{seed.name}"')
                            return False

                        if c.isGeographic():                                   # check if crs is projected; not really needed already checked in RollWell
                            QMessageBox.warning(None, e, f'{c.description()}. Invalid CRS (using lat/lon values) in well-seed\nPlease change CRS in well-seed "{seed.name}"')
                            return False

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
                    if seed.typ_ < 2:                                           # grid
                        seed.pointList = seed.grid.calcPointList(seed.origin)   # calculate the point list for this seed type
                        seed.grid.calcSalvoLine(seed.origin)                    # calc line to be drawn in low LOD values

                    elif seed.typ_ == 2:                                        # circle
                        seed.pointList = seed.circle.calcPointList(seed.origin)   # calculate the point list for this seed type

                    elif seed.typ_ == 3:                                        # spiral
                        seed.pointList = seed.spiral.calcPointList(seed.origin)   # calculate the point list for this seed type
                        seed.spiral.calcSpiralPath(seed.origin)                 # calc spiral path to be drawn
                    elif seed.typ_ == 4:                                        # well site
                        seed.pointList, seed.origin = seed.well.calcPointList(self.crs, self.glbTransform)  # calculate the well's point list

                    # at this point; convert the point-lists to numpy-arrays for more efficient processing
                    seed.calcPointArray()                                       # setup the numpy arrays

    def createBasicSkeleton(self, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=2):

        block = RollBlock('block-1')                                            # create a block
        self.blockList.append(block)                                            # add block to survey object

        for template in range(nTemplates):
            templateName = f'template-{template + 1}'                           # get suitable template name
            template = RollTemplate(templateName)                               # create template
            block.templateList.append(template)                                 # add template to block object

            roll1 = RollTranslate()                                             # create the 'first' roll object
            template.rollList.append(roll1)                                     # add roll object to template's rollList

            roll2 = RollTranslate()                                             # create a 'second' roll object
            template.rollList.append(roll2)                                     # add roll object to template's rollList

            for srcSeed in range(nSrcSeeds):
                seedName = f'src-{srcSeed + 1}'                                 # create a source seed object
                seedSrc = RollSeed(seedName)
                seedSrc.bSource = True
                seedSrc.color = QColor('#77FF8989')
                template.seedList.append(seedSrc)                               # add seed object to template

                growR1 = RollTranslate()                                        # create a 'lines' grow object
                seedSrc.grid.growList.append(growR1)                            # add grow object to seed
                growR2 = RollTranslate()                                        # create a 'points' grow object
                seedSrc.grid.growList.append(growR2)                            # add grow object to seed

            for recSeed in range(nRecSeeds):
                seedName = f'rec-{recSeed + 1}'                                 # create a receiver seed object
                seedRec = RollSeed(seedName)
                seedRec.bSource = False
                seedRec.color = QColor('#7787A4D9')
                template.seedList.append(seedRec)                               # add seed object to template

                growR1 = RollTranslate()                                        # create a 'lines' grow object
                seedRec.grid.growList.append(growR1)                            # add grow object to seed's growlist
                growR2 = RollTranslate()                                        # create a 'points' grow object
                seedRec.grid.growList.append(growR2)                            # add grow object to seed

        for pattern in range(nPatterns):
            patternName = f'pattern-{pattern + 1}'                              # create suitable pattern name
            pattern = RollPattern(patternName)                                  # create the pattern

            grow1 = RollTranslate()                                             # create a 'vertical' grow object
            pattern.growList.append(grow1)                                      # add grow object to pattern's growList
            grow2 = RollTranslate()                                             # create a 'horizontal' grow object
            pattern.growList.append(grow2)                                      # add grow object to pattern's growList
            self.patternList.append(pattern)                                    # add block to survey object

    def writeXml(self, doc: QDomDocument):
        doc.clear()

        instruction = doc.createProcessingInstruction('xml', 'version="1.0" encoding="UTF-8"')
        doc.appendChild(instruction)

        # root is created within the survey object; other elements are appended to root
        root = doc.createElement('survey')
        root.setAttribute('version', '1.0')
        doc.appendChild(root)

        pathElement = doc.createElement('type')

        text = doc.createTextNode(self.typ_.name)
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
                    self.typ_ = SurveyType[e.text()]

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
                    if seed.typ_ < 2 and seed.patternNo > -1 and seed.patternNo < len(self.patternList):
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
                        length = min(length, self.PaintMode.value)

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

            if seed.typ_ < 2 and seed.rendered is False:                        # grid based seed
                if seed.typ_ == 1:                                              # no rolling along; fixed grid
                    templateOffset = QVector3D()
                    seed.rendered = True

                length = len(seed.grid.growList)                                # how deep is the grow list ?
                if length == 0:
                    offset = QVector3D(0.0, 0.0, 0.0)                           # always start at (0, 0, 0)
                    offset += templateOffset                                    # start here
                    salvo = seed.grid.salvo.translated(offset.toPointF())       # move the line into place
                    salvo = clipLineF(salvo, seed.blockBorder)                  # check line against block's src/rec border
                    salvo = clipLineF(salvo, viewbox)                           # check line against viewbox

                    if not salvo.isNull():
                        if lod < config.lod2 or self.mouseGrabbed:              # just draw lines
                            painter.drawLine(salvo)
                        else:
                            seedOrigin = offset + seed.origin                   # start at templateOffset and add seed's origin
                            if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                    painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)   # paint seed picture
                                    if lod > config.lod3 and seed.patternPicture is not None:       # paint pattern picture
                                        painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 1:
                    offset = QVector3D(0.0, 0.0, 0.0)                           # always start at (0, 0, 0)
                    offset += templateOffset                                    # start here
                    salvo = seed.salvo.grid.translated(offset.toPointF())       # move the line into place
                    salvo = clipLineF(salvo, seed.blockBorder)                  # check line against block's src/rec border
                    salvo = clipLineF(salvo, viewbox)                           # check line against viewbox

                    if not salvo.isNull():
                        if lod < config.lod2 or self.mouseGrabbed:              # just draw lines
                            painter.drawLine(salvo)
                        else:
                            for i in range(seed.grid.growList[0].steps):        # iterate over 1st step
                                seedOrigin = offset + seed.origin               # start at templateOffset and add seed's origin
                                seedOrigin += seed.grid.growList[0].increment * i   # we now have the correct location
                                if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                    if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                        painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)  # paint seed picture
                                        if lod > config.lod3 and seed.patternPicture is not None:   # paint pattern picture
                                            painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)
                elif length == 2:
                    for i in range(seed.grid.growList[0].steps):                # iterate over 1st step
                        offset = QVector3D(0.0, 0.0, 0.0)                       # always start at (0, 0, 0)
                        offset += templateOffset                                # start here
                        offset += seed.grid.growList[0].increment * i           # we now have the correct location
                        salvo = seed.grid.salvo.translated(offset.toPointF())   # move the line into place
                        salvo = clipLineF(salvo, seed.blockBorder)              # check line against block's src/rec border
                        salvo = clipLineF(salvo, viewbox)                       # check line against viewbox
                        if not salvo.isNull():
                            if lod < config.lod2 or self.mouseGrabbed:          # just draw lines
                                painter.drawLine(salvo)
                            else:
                                for j in range(seed.grid.growList[1].steps):
                                    seedOrigin = offset + seed.origin           # start at templateOffset and add seed's origin
                                    seedOrigin += seed.grid.growList[1].increment * j   # we now have the correct location
                                    if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                        if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                            painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)   # paint seed picture
                                            if lod > config.lod3 and seed.patternPicture is not None:
                                                painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)   # paint pattern picture

                elif length == 3:
                    for i in range(seed.grid.growList[0].steps):
                        for j in range(seed.grid.growList[1].steps):
                            offset = QVector3D(0.0, 0.0, 0.0)                   # always start at (0, 0)
                            offset += templateOffset                            # start here
                            offset += seed.grid.growList[0].increment * i       # we now have the correct location
                            offset += seed.grid.growList[1].increment * j       # we now have the correct location
                            salvo = seed.grid.salvo.translated(offset.toPointF())   # move the line into place
                            salvo = clipLineF(salvo, seed.blockBorder)          # check line against block's src/rec border
                            salvo = clipLineF(salvo, viewbox)                   # check line against viewbox
                            if not salvo.isNull():
                                if lod < config.lod2 or self.mouseGrabbed:      # just draw lines
                                    painter.drawLine(salvo)
                                else:
                                    for k in range(seed.grid.growList[2].steps):
                                        seedOrigin = offset + seed.origin       # start at templateOffset and add seed's origin
                                        seedOrigin += seed.grid.growList[2].increment * k   # we now have the correct location
                                        if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                            if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                                painter.drawPicture(seedOrigin.toPointF(), seed.pointPicture)   # paint seed picture
                                                if lod > config.lod3 and seed.patternPicture is not None:
                                                    painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)   # paint pattern picture
                else:
                    # do something recursively; not  implemented yet
                    raise NotImplementedError('More than three grow steps currently not allowed.')

            if seed.typ_ == 2 and seed.rendered is False:                       # circle seed
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

            if seed.typ_ == 3 and seed.rendered is False:                       # spiral seed
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
                        painter.drawPicture(p, seed.pointPicture)               # paint seed picture

            if seed.typ_ == 4 and seed.rendered is False:                       # well seed
                seed.rendered = True
                painter.drawPolyline(seed.well.polygon)                         # draw well trajectory as part of this template; move this up to paint()
                painter.drawEllipse(seed.well.origL, 5.0, 5.0)                  # draw small circle where well surfaces

                if lod > config.lod2 and not self.mouseGrabbed:                 # need the in-well points as well...
                    length = len(seed.pointList)
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        painter.drawPicture(p, seed.pointPicture)               # paint seed picture

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy