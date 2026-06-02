"""
This module provides the main classes used in Roll
"""
import math
import os
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

import numpy as np
import pyqtgraph as pg
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QMarginsF, QRectF, QThread, pyqtSignal
from qgis.PyQt.QtGui import (QBrush, QColor, QGuiApplication, QImage, QPainter,
                             QPicture, QTransform, QVector3D)
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from . import aux_functions_numba as fnb
from . import config
from .app_settings import getActiveAppSettings
from .aux_functions import containsPoint3D
from .enums_and_int_flags import PaintDetails, PaintMode, SeedType, SurveyType
from .roll_angles import RollAngles
from .roll_bingrid import RollBinGrid
from .roll_binning import BinningType, RollBinning
from .roll_block import RollBlock
from .roll_offset import RollOffset
from .roll_output import RollOutput
from .roll_pattern import RollPattern
from .roll_pattern_seed import RollPatternSeed
from .roll_plane import RollPlane
from .roll_seed import RollSeed
from .roll_sphere import RollSphere
from .roll_template import RollTemplate
from .roll_unique import RollUnique
from .roll_well import RollWellError
from .sps_io_and_qc import pntType1, relType2


@dataclass(frozen=True)
class GeometryRelationBinningLookup:
    relLeft: np.ndarray
    relRight: np.ndarray
    recIndex: np.ndarray
    recLineI: np.ndarray
    recPointI: np.ndarray
    relRecIndI: np.ndarray
    relRecLinI: np.ndarray
    relRecMinI: np.ndarray
    relRecMaxI: np.ndarray

# from .aux_functions_numba import (clipLineF, numbaFixRelationRecord,
#                                   numbaSetPointRecord, numbaSetRelationRecord,
#                                   numbaSliceStats, pointsInRect)
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

# to use different symbol size / color iun a graph; use scatterplot :
# See: https://www.geeksforgeeks.org/pyqtgraph-different-colored-spots-on-scatter-plot-graph/
# See: https://www.geeksforgeeks.org/pyqtgraph-getting-rotation-of-spots-in-scatter-plot-graph/


# To give an xml-object a name, create a seperate <name> element as first xml entry (preferred over name attribute)
# the advantage of using element.text is that characters like ' and " don't cause issues in terminating a ""-string
# if len(self.name) > 0:
#     nameElem = ET.SubElement(seed_elem, 'name')
#     nameElem.text = self.name

# The survey object contains several "lower" objects such as blocks, templates and patterns, all defined in separate modules
# When these need their parent "survey" object in a function, there's a chance of getting circular references
# See: https://www.mend.io/blog/closing-the-loop-on-python-circular-import-issue/


# See: https://docs.python.org/3/howto/enum.html
# See: https://realpython.com/python-enum/#creating-integer-flags-intflag-and-flag
# class Show(IntFlag):
#     NONE = 0
#     LOD0 = 1
#     LOD1 = 2
#     LOD2 = 4
#     LOD3 = 8
#     LOD = LOD0 | LOD1 | LOD2 | LOD3
#     LIM0 = 16
#     LIM1 = 32
#     LIM2 = 64
#     LIM3 = 128
#     LIM = LIM0 | LIM1 | LIM2 | LIM3
#     SUR = 256
#     BLK = 512
#     TPL = 1024
#     LIN = 2048
#     PNT = 4096
#     PAT = 8192
#     ROL = 16384
#     ALL = SUR | BLK | TPL | LIN | PNT | PAT | ROL
#     TOP = SUR | BLK


class RollSurvey(pg.GraphicsObject):
    progress = pyqtSignal(int)                                                  # signal to keep track of worker thread progress
    message = pyqtSignal(str)                                                   # signal to update statusbar progresss text
    logMessage = pyqtSignal(str)                                                # signal to append a persistent line to the log dock

    # See: https://github.com/pyqtgraph/pyqtgraph/blob/develop/examples/CustomGraphItem.py
    # This example gives insight in the mouse drag event

    # assign default name value
    def __init__(self, name: str = 'Untitled') -> None:

        pg.GraphicsObject.__init__(self)

        self.nShotPoint = 0                                                     # managed in worker thread
        self.nShotPoints = -1                                                   # set at -1 to initialize calculations
        self.nTemplate = 0                                                      # managed in worker thread
        self.nTemplates = -1                                                    # set at -1 to initialize calculations
        self.nRecRecord = -1                                                    # set at -1 to initialize calculations
        self.nRelRecord = -1                                                    # set at -1 to initialize calculations
        self.nOldRecLine = -999999                                              # to set up the first rec-point in a rel-record
        self.nNewRecLine = -1                                                   # to control moving along with rel-records
        self.recMin = 0                                                         # to set up the highest rec number on a line
        self.recMax = 0                                                         # to set up the highest rec number on a line

        self.threadProgress = 0                                                 # progress percentage
        self.cfpTemplateContributionCount = 0                                   # managed in CFP template scan worker
        self.cfpApertureRadius = 0.0                                            # managed in CFP template scan worker
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
        self.type = SurveyType.Orthogonal                                      # survey type as defined in class SurveyType()
        self.name: str = name

        # note: type() is a builtin Python function, so it is recommended NOT to use it as a variable name
        # as in that case you'll overwrite a built-in function, which can have undesired side effects
        # so using "self.type = xxx" is fine, but "type = xxx" is NOT fine

        # survey painting mode
        self.paintMode = PaintMode.all                                          # paints down to patterns
        self.paintDetails = PaintDetails.all                                    # template details to be painted
        self.lodScale = 1.0                                                     # force Level of Detail (LOD) to a higher value (for small Wizard plots)

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

        # timings for time critical functions, allowing for 20 steps
        # this needs to be cleaned up; and put in separate profiler class
        self.timerTmin = [float('Inf') for _ in range(20)]
        self.timerTmax = [0.0 for _ in range(20)]
        self.timerTtot = [0.0 for _ in range(20)]
        self.timerFreq = [0 for _ in range(20)]

        # framebuffers for progressive rendering
        self._cancelPaint = False       # to cancel painting in progress
        self._fbBase = None             # QImage with bin/src/rec/cmp areas
        self._fbProg = None             # QImage accumulating progressive details
        self._fbKey = None              # tuple key (size, transform, lod, flags, epoch)
        self._ps = None                 # progressive state (indices)
        self._paintBudgetMs = 20.0      # time budget per paint pass (tune as you like)
        self._paintEpoch = 0            # bump when data/flags change
        self._paintStart = None         # to track when painting started

    def bindSeedsToSurvey(self):
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    seed.setSurvey(self)
        # patterns are separate objects (not part of a RollSeed), so nothing to bind there

    def getPattern(self, index: int):
        if 0 <= index < len(self.patternList):
            return self.patternList[index]
        return None

    def setPatternList(self, newList):
        self.patternList = list(newList)
        # clamp invalid indices
        maxIdx = len(self.patternList) - 1
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.patternNo > maxIdx:
                        seed.patternNo = -1
        self.invalidatePaintCache()

    def deepcopy(self):
        # regular deepcopy() does not work for the compound 'RollSurvey' object.
        # reason; pickle doesn't like the following objects:
        # ".crs (Type 'QgsCoordinateReferenceSystem' caused: cannot pickle 'QgsCoordinateReferenceSystem' object)",
        # ".blockList[0].templateList[0].seedList[0].pointPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".blockList[0].templateList[0].seedList[0].patternPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".patternList[0].pointPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)",
        # ".patternList[0].patternPicture (Type 'QPicture' caused: cannot pickle 'QPicture' object)"
        #
        # tested using: **getUnpicklable(instance, exception=None, string='', firstOnly=False)**. See functions.py
        # applied fix: copy via: object --> xml --> object

        plainText = self.toXmlString()
        surveyCopy = RollSurvey()
        succes = surveyCopy.fromXmlString(plainText)

        if succes:
            surveyCopy.bindSeedsToSurvey()                                      # bind seeds to survey after creating copy. This restores weakrefs
            return surveyCopy
        return None

    def calcSeedData(self):
        # this routine relies on self.checkIntegrity() to spot any errors
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:

                    if seed.type == SeedType.rollingGrid:                       # rolling grid
                        seed.grid.calcSalvoLine(seed.origin)                    # calc line to be drawn in low LOD values

                    elif seed.type == SeedType.fixedGrid:                       # stationary grid
                        seed.grid.calcSalvoLine(seed.origin)                    # calc line to be drawn in low LOD values

                    elif seed.type == SeedType.circle:                          # circle
                        seed.pointList = seed.circle.calcPointList(seed.origin)   # calculate the point list for this seed type

                    elif seed.type == SeedType.spiral:                          # spiral
                        seed.pointList = seed.spiral.calcPointList(seed.origin)   # calculate the point list for this seed type
                        seed.spiral.calcSpiralPath(seed.origin)                 # calc spiral path to be drawn

                    elif seed.type == SeedType.well:                            # well site
                        seed.pointList, seed.origin = seed.well.calcPointList(self.crs, self.glbTransform)  # calculate the well's point list

    def ensureGeometrySeedData(self):
        # Geometry generation consumes pointArray for non-grid seeds. Backfill
        # pointList only when it has not been prepared yet, so we do not
        # overwrite tests or call sites that intentionally seeded custom points.
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type == SeedType.circle and len(seed.pointList) == 0:
                        seed.pointList = seed.circle.calcPointList(seed.origin)
                    elif seed.type == SeedType.spiral and len(seed.pointList) == 0:
                        seed.pointList = seed.spiral.calcPointList(seed.origin)
                    elif seed.type == SeedType.well and len(seed.pointList) == 0:
                        seed.pointList, seed.origin = seed.well.calcPointList(self.crs, self.glbTransform)

    def createBasicSkeleton(self, nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=2):

        # Constructor invariant for generated skeletons.
        assert nBlocks > 0, 'Need at least 1 block'  # nosec B101
        # Constructor invariant for generated skeletons.
        assert nTemplates > 0, 'Need at least 1 template'  # nosec B101
        # Constructor invariant for generated skeletons.
        assert nSrcSeeds > 0, 'Need at least 1 source seed'  # nosec B101
        # Constructor invariant for generated skeletons.
        assert nRecSeeds > 0, 'Need at least 1 receiver seed'  # nosec B101
        # nPatterns may be zero

        self.blockList = []                                                     # make sure, we start with an empty list

        for nBlock in range(nBlocks):
            blockName = f'block-{nBlock + 1}'                                   # get suitable block name
            block = RollBlock(blockName)                                        # create block
            self.blockList.append(block)                                        # add block to survey object

            for nTemplate in range(nTemplates):
                templateName = f'template-{nTemplate + 1}'                      # get suitable template name
                template = RollTemplate(templateName)                           # create template

                block.templateList.append(template)                             # add template to block object

                for nSrcSeed in range(nSrcSeeds):
                    seedName = f'src-{nSrcSeed + 1}'                            # create a source seed object
                    seedSrc = RollSeed(seedName)
                    seedSrc.bSource = True
                    seedSrc.color = QColor('#77FF8989')

                    template.seedList.append(seedSrc)                           # add seed object to template

                for nRecSeed in range(nRecSeeds):
                    seedName = f'rec-{nRecSeed + 1}'                            # create a receiver seed object
                    seedRec = RollSeed(seedName)
                    seedRec.bSource = False
                    seedRec.color = QColor('#7787A4D9')

                    template.seedList.append(seedRec)                           # add seed object to template

        self.patternList = []                                                   # make sure, we start with an empty list
        for nPattern in range(nPatterns):
            patternName = f'pattern-{nPattern + 1}'                             # create suitable pattern name
            pattern = RollPattern(patternName)                                  # create the pattern
            self.patternList.append(pattern)                                    # add pattern to patternList

            seed = RollPatternSeed()                                            # create a new seed (we need just one)
            pattern.seedList.append(seed)                                       # add this seed to pattern's seedList

        self.bindSeedsToSurvey()                                                # bind seeds to survey after creating skeleton

    def calcTransforms(self, createArrays=False):
        """(re)calculate the transforms being used, and optionally initialize fold & offset arrays"""
        x = self.grid.orig.x()
        y = self.grid.orig.y()
        p = self.grid.angle
        q = self.grid.scale.x()
        r = self.grid.scale.y()

        self.glbTransform = QTransform()
        self.glbTransform.translate(x, y)
        self.glbTransform.rotate(p)
        self.glbTransform.scale(q, r)

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
        # Current transform model assumes uniform XY scale.
        assert q == r, 'x- and y-scales need to be identical, preferrably 1.0'  # nosec B101

        r0 = self.globalSphere.radius
        r1 = r0 * q
        o0 = self.globalSphere.origin
        s1 = toLocalTransform.map(o0.toPointF())                                # transform the 2D point to local coordinates
        s2 = QVector3D(s1.x(), s1.y(), o0.z() * q)                              # 3D point in local coordinates, with z axis scaled as well
        self.localSphere = RollSphere(s2, r1)                                   # initiate the local sphere

        w = self.output.rctOutput.width()
        h = self.output.rctOutput.height()
        x0 = self.output.rctOutput.left()
        y0 = self.output.rctOutput.top()

        dx = self.grid.binSize.x()
        dy = self.grid.binSize.y()
        # ox = self.grid.binShift.x()
        # oy = self.grid.binShift.y()

        s0 = self.grid.stakeOrig.x()
        l0 = self.grid.stakeOrig.y()
        ds = self.grid.stakeSize.x()
        dl = self.grid.stakeSize.y()

        nx = math.ceil(w / dx)
        ny = math.ceil(h / dy)

        sx = w / nx
        sy = h / ny

        if createArrays:
            self.output.binOutput = np.zeros(shape=(nx, ny), dtype=np.uint32)   # start with empty array of the right size and type
            self.output.minOffset = np.zeros(shape=(nx, ny), dtype=np.float32)  # start with empty array of the right size and type
            self.output.maxOffset = np.zeros(shape=(nx, ny), dtype=np.float32)  # start with empty array of the right size and type
            self.output.minOffset.fill(np.inf)                                  # start min offset with +inf (use np.full instead)
            self.output.maxOffset.fill(-np.inf)                                 # start max offset with -inf (use np.full instead)

        self.binTransform = QTransform()
        self.binTransform.translate(x0, y0)
        self.binTransform.scale(dx, dy)
        self.binTransform, _ = self.binTransform.inverted()

        self.cmpTransform = QTransform()
        self.cmpTransform.translate(x0, y0)
        self.cmpTransform.scale(sx, sy)

        self.stkTransform = QTransform()
        self.stkTransform.translate(-ds / 2.0, -dl / 2.0)                           # first shift origin by an offset equal to half the stake/line increments
        self.stkTransform.scale(ds, dl)                                         # then scale it according to the stake / line intervals
        self.stkTransform.translate(-s0, -l0)                                   # then shift origin to the (stake, line) origin
        self.stkTransform, _ = self.stkTransform.inverted()                     # invert the transform before applying

        self.st2Transform = QTransform()                                        # no minor shift (for rounding purpose) applied in this case
        self.st2Transform.scale(ds, dl)                                         # scale it according to the stake / line intervals
        self.st2Transform.translate(-s0, -l0)                                   # then shift origin to (stake, line) origin
        self.st2Transform, _ = self.st2Transform.inverted()                     # invert the transform before applying

    def noShotPoints(self):
        if self.nShotPoints == -1:
            return self.calcNoShotPoints()
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
                        if seed.type < SeedType.circle:                         # grid-based source seed (rolling/fixed grid)
                            nSeedShots = 1                                      # at least one SP
                            for growStep in seed.grid.growList:                 # iterate through all grow steps
                                nSeedShots *= growStep.steps                    # multiply seed's shots at each level
                        else:                                                   # circle / spiral / well source seed
                            nSeedShots = max(len(seed.pointList), 1)            # mirror calcPointArray's sizing
                        nTemplateShots += nSeedShots                            # add to template's SPs

                for roll in template.rollList:
                    nTemplateShots *= roll.steps                                # template is rolled a number of times

                nBlockShots += nTemplateShots
            self.nShotPoints += nBlockShots
        return self.nShotPoints

    def calcNoTemplates(self) -> int:
        self.nTemplates = 0
        for block in self.blockList:
            nTemplates = 0                                                      # reset for each block in case there no templates in a block
            for template in block.templateList:
                nTemplateRolls = 1
                for roll in template.rollList:
                    nTemplateRolls *= roll.steps                                # template is rolled a number of times
                nTemplates += nTemplateRolls
            self.nTemplates += nTemplates
        return self.nTemplates

    def iterTemplateRollOffsets(self, template):
        length = len(template.rollList)
        # Normalized template invariant.
        assert length == 3, 'there must always be 3 roll steps / grow steps'  # nosec B101

        for i in range(template.rollList[0].steps):
            off0 = QVector3D()
            off0 += template.rollList[0].increment * i

            for j in range(template.rollList[1].steps):
                off1 = off0 + template.rollList[1].increment * j

                for k in range(template.rollList[2].steps):
                    yield off1 + template.rollList[2].increment * k

    def iterSeedGrowOffsets(self, seed, templateOffset):
        length = len(seed.grid.growList)
        # Normalized seed invariant.
        assert length == 3, 'there must always be 3 grow steps / roll steps'  # nosec B101

        for i in range(seed.grid.growList[0].steps):
            off0 = QVector3D(templateOffset)
            off0 += seed.grid.growList[0].increment * i

            for j in range(seed.grid.growList[1].steps):
                off1 = off0 + seed.grid.growList[1].increment * j

                for k in range(seed.grid.growList[2].steps):
                    yield off1 + seed.grid.growList[2].increment * k

    @staticmethod
    def _seedUsesTemplateRoll(seed) -> bool:
        return seed.type == SeedType.rollingGrid

    @staticmethod
    def _receiverSeedUsesTemplateRoll(seed) -> bool:
        return RollSurvey._seedUsesTemplateRoll(seed)

    def _seedTemplateOffset(self, seed, npTemplateOffset):
        if self._seedUsesTemplateRoll(seed):
            return npTemplateOffset
        return 0.0

    def _receiverSeedTemplateOffset(self, seed, npTemplateOffset):
        return self._seedTemplateOffset(seed, npTemplateOffset)

    def _shouldAppendReceiverSeedGeometry(self, seed) -> bool:
        if self._receiverSeedUsesTemplateRoll(seed):
            return True

        emittedSeedIds = getattr(self.output, 'invariantReceiverSeedIds', None)
        if emittedSeedIds is None:
            emittedSeedIds = set()
            self.output.invariantReceiverSeedIds = emittedSeedIds

        seedId = id(seed)
        if seedId in emittedSeedIds:
            return False

        emittedSeedIds.add(seedId)
        return True

    def _recordInnermostExceptionLocation(self, e: BaseException) -> None:
        """Set self.errorText to point at the innermost frame of the active
        exception, not the catch site. Without walking to tb_next-end, the
        reported line number is whatever caught the exception, which makes
        worker-thread bug reports useless. Used by all worker entry points
        (geometryFromTemplates, setupGeometryFromTemplates, binFromGeometry*,
        binFromGeometryNoRel*, etc.).
        """
        tb = sys.exc_info()[2]
        if tb is None:
            self.errorText = f'error: {str(e)}'
            return
        while tb.tb_next is not None:
            tb = tb.tb_next
        fileName = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        funcName = tb.tb_frame.f_code.co_name
        lineNo = str(tb.tb_lineno)
        self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'

    def setupGeometryFromTemplates(self) -> bool:

        try:
            # The array with the list of receiver locations is the most difficult to determine.
            # It can be calculated using one of several approaches :
            #   a) define a large (line, stake) grid and populate this for each line stake number that we come across
            #   b) just append 'new' receivers to the numpy array and later remove duplicates, of which there will be many
            # the difficulty of a) is that you need to be sure of grid increments and start/end points
            # the easy part is that at the end the non-zero records can be gathered (filtered out)
            # the difficulty of b) is that the recGeom array will overflow, unless you remove duplicates at timely intervals
            # the easy part is that you don't have to setup a large grid with offset counters, which can be error prone
            # overall, approach b) seems more 'failsafe' and easier to implement.
            #   c) lastly; use a nested dictionary to check rec positions before adding them to the numpy array
            # if a receiver is found at recDict[line][point], there is no need to add it to the numpy array

            # gc.collect()                                                        # get the garbage collector going
            self.calcNoTemplates()                                              # need to know nr templates, to track progress
            self.nTemplate = 0                                                  # zero based counter

            # GPT-5.2 Codex fix proposed to initiate empty nested dictionary here. Original code shown first
            # self.output.recDict = defaultdict(dict)                             # nested dictionary to access rec positions
            self.output.recDict = defaultdict(lambda: defaultdict(dict))        # nested dictionary to access rec positions
            self.output.recSeenSet = set()                                      # flat dedup set used by geomTemplate5; reset per run

            self.nRecRecord = 0                                                 # zero based array index
            self.nRelRecord = 0                                                 # zero based array index; previously left at -1 from __init__
            self.nShotPoint = 0                                                 # zero based array index
            if self.nShotPoints == -1:                                          # calcNoShotPoints has been skipped ?!?
                self.calcNoShotPoints()

            # the numpy array with the list of source locations simply follows from self.nShotPoints
            self.output.srcGeom = np.zeros(shape=(self.nShotPoints), dtype=pntType1)

            # the numpy array with the list of relation records follows from the nr of shot points x number of rec lines (assume 20)
            self.output.relGeom = np.zeros(shape=(self.nShotPoints * 20), dtype=relType2)
            self.output.relTemp = np.zeros(shape=(100), dtype=relType2)         # holds 100 rec lines/template will be increased if needed

            # for starters; assume there are 40,000 receivers in a survey, will be extended in steps of 10,000
            self.output.recGeom = np.zeros(shape=(40000), dtype=pntType1)

            success = self.geometryFromTemplates()                              # here the work is being done

        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            success = False

        return success

    @staticmethod
    def _pointsInsideRect(pointArray: np.ndarray, rect: QRectF) -> np.ndarray:
        if pointArray is None or pointArray.shape[0] == 0:
            return pointArray

        rect = QRectF(rect).normalized()
        included = (
            (pointArray[:, 0] >= rect.left()) &
            (pointArray[:, 0] <= rect.right()) &
            (pointArray[:, 1] >= rect.top()) &
            (pointArray[:, 1] <= rect.bottom())
        )
        return pointArray[included, :]

    def _updateTemplateScanProgress(self, progressStart: int = 0, progressEnd: int = 100) -> None:
        if QThread.currentThread().isInterruptionRequested():
            raise StopIteration

        self.nTemplate += 1
        if self.nTemplates <= 0:
            return

        progressSpan = max(progressEnd - progressStart, 0)
        threadProgress = progressStart + ((progressSpan * self.nTemplate) // self.nTemplates)
        if threadProgress > self.threadProgress:
            self.threadProgress = threadProgress
            self.progress.emit(threadProgress)

    def _seedBoundingRectForTemplateOffset(self, seed, block, templateOffset: QVector3D) -> QRectF:
        seedRect = QRectF(seed.boundingBox)
        if seed.bSource:
            if self._seedUsesTemplateRoll(seed):
                seedRect.translate(templateOffset.x(), templateOffset.y())
            border = block.borders.srcBorder
        else:
            if self._receiverSeedUsesTemplateRoll(seed):
                seedRect.translate(templateOffset.x(), templateOffset.y())
            border = block.borders.recBorder

        if border.isValid():
            seedRect = seedRect.intersected(border)

        return seedRect.normalized()

    def _seedPointsForTemplateOffset(self, seed, block, npTemplateOffset: np.ndarray) -> np.ndarray:
        if seed.bSource:
            pointArray = seed.pointArray + self._seedTemplateOffset(seed, npTemplateOffset)
            border = block.borders.srcBorder
        else:
            pointArray = seed.pointArray + self._receiverSeedTemplateOffset(seed, npTemplateOffset)
            border = block.borders.recBorder

        if border.isValid():
            pointArray = self._pointsInsideRect(pointArray, border)

        return pointArray

    def _filterPointsByCfpRadius(self, pointArray: np.ndarray, focalX: float, focalY: float, radiusSquared: float) -> np.ndarray:
        if pointArray is None or pointArray.shape[0] == 0:
            return pointArray

        dx = pointArray[:, 0] - focalX
        dy = pointArray[:, 1] - focalY
        return pointArray[dx * dx + dy * dy <= radiusSquared]

    @staticmethod
    def _filterPointsForCfp(pointArray: np.ndarray, apertureRect: QRectF, focalX: float, focalY: float, radiusSquared: float) -> np.ndarray:
        if pointArray is None or pointArray.shape[0] == 0:
            return pointArray

        included = (
            (pointArray[:, 0] >= apertureRect.left()) &
            (pointArray[:, 0] <= apertureRect.right()) &
            (pointArray[:, 1] >= apertureRect.top()) &
            (pointArray[:, 1] <= apertureRect.bottom())
        )
        if not np.any(included):
            return pointArray[:0]

        dx = pointArray[:, 0] - focalX
        dy = pointArray[:, 1] - focalY
        included &= (dx * dx + dy * dy <= radiusSquared)
        return pointArray[included, :]

    def _collectTemplatePointsForCfp(
        self,
        block,
        template,
        templateOffset: QVector3D,
        apertureRect: QRectF,
        focalX: float,
        focalY: float,
        radiusSquared: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        emptyPoints = np.empty((0, 3), dtype=np.float32)
        templateRect = QRectF()
        for seed in template.seedList:
            seedRect = self._seedBoundingRectForTemplateOffset(seed, block, templateOffset)
            if seedRect.isNull() or not seedRect.isValid():
                continue
            templateRect |= seedRect

        if templateRect.isNull() or not templateRect.intersects(apertureRect):
            return emptyPoints, emptyPoints

        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)
        sourcePointArrays = []
        receiverPointArrays = []

        for seed in template.seedList:
            pointArray = self._seedPointsForTemplateOffset(seed, block, npTemplateOffset)
            if pointArray is None or pointArray.shape[0] == 0:
                continue

            pointArray = self._filterPointsForCfp(pointArray, apertureRect, focalX, focalY, radiusSquared)
            if pointArray.shape[0] == 0:
                continue

            if seed.bSource:
                sourcePointArrays.append(pointArray)
            else:
                receiverPointArrays.append(pointArray)

        if not sourcePointArrays or not receiverPointArrays:
            return emptyPoints, emptyPoints

        sourcePoints = sourcePointArrays[0] if len(sourcePointArrays) == 1 else np.concatenate(sourcePointArrays, axis=0)
        receiverPoints = receiverPointArrays[0] if len(receiverPointArrays) == 1 else np.concatenate(receiverPointArrays, axis=0)
        return sourcePoints, receiverPoints

    def _templateContributesToCfp(self, block, template, templateOffset: QVector3D, apertureRect: QRectF, focalX: float, focalY: float, radiusSquared: float) -> bool:
        sourcePoints, receiverPoints = self._collectTemplatePointsForCfp(block, template, templateOffset, apertureRect, focalX, focalY, radiusSquared)
        return sourcePoints.shape[0] > 0 and receiverPoints.shape[0] > 0

    def scanCfpTemplates(
        self,
        focalX: float,
        focalY: float,
        focalZ: float,
        maxDipDegrees: float,
        vint: float,
        contributionHandler: Callable[[np.ndarray, np.ndarray], None] | None = None,
        weightedContributionHandler: Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], None] | None = None,
        progressStart: int = 0,
        progressEnd: int = 100,
    ) -> bool:
        try:
            self.calcNoTemplates()
            self.calcBoundingRect()
            self.calcPointArrays()
            self.nTemplate = 0
            self.threadProgress = 0
            self.cfpTemplateContributionCount = 0
            self.cfpApertureRadius = abs(focalZ) * math.tan(math.radians(maxDipDegrees))

            apertureRect = QRectF(
                focalX - self.cfpApertureRadius,
                focalY - self.cfpApertureRadius,
                self.cfpApertureRadius * 2.0,
                self.cfpApertureRadius * 2.0,
            ).normalized()
            radiusSquared = self.cfpApertureRadius * self.cfpApertureRadius

            self.message.emit('CFP template scan - evaluating rolling templates')
            self.logMessage.emit(
                f'CFP: local target=({focalX:.2f}, {focalY:.2f}, {focalZ:.2f}), aperture={maxDipDegrees:.1f}deg, radius={self.cfpApertureRadius:.2f}m, Vint={vint:.1f}m/s'
            )

            for block in self.blockList:
                for template in block.templateList:
                    for templateOffset in self.iterTemplateRollOffsets(template):
                        self._updateTemplateScanProgress(progressStart, progressEnd)
                        sourcePoints, receiverPoints = self._collectTemplatePointsForCfp(
                            block,
                            template,
                            templateOffset,
                            apertureRect,
                            focalX,
                            focalY,
                            radiusSquared,
                        )
                        if sourcePoints.shape[0] == 0 or receiverPoints.shape[0] == 0:
                            continue

                        nSrc = sourcePoints.shape[0]
                        nRec = receiverPoints.shape[0]

                        self.cfpTemplateContributionCount += 1
                        if weightedContributionHandler is not None:
                            sourceWeights = np.full(nSrc, nRec, dtype=np.float64)
                            receiverWeights = np.full(nRec, nSrc, dtype=np.float64)
                            weightedContributionHandler(sourcePoints, receiverPoints, sourceWeights, receiverWeights)
                        elif contributionHandler is not None:
                            sourceExp = np.repeat(sourcePoints, nRec, axis=0)
                            receiverExp = np.tile(receiverPoints, (nSrc, 1))
                            contributionHandler(sourceExp, receiverExp)

            self.progress.emit(progressEnd)
            return True

        except StopIteration:
            self.errorText = 'CFP template scan cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

    def setupCfpFromTemplates(self, focalX: float, focalY: float, focalZ: float, maxDipDegrees: float, vint: float) -> bool:
        return self.scanCfpTemplates(focalX, focalY, focalZ, maxDipDegrees, vint)

    def geometryFromTemplates(self) -> bool:
        try:
            appSettings = getActiveAppSettings()
            chosenRoutineName = 'geomTemplate5' if appSettings.useExperimental else 'geomTemplate4'
            self.logMessage.emit(f'Method : useExperimental={appSettings.useExperimental} -> {chosenRoutineName}')
            self.calcPointArrays()                                              # first set up all point arrays
            # get all blocks
            for nBlock, block in enumerate(self.blockList):
                for template in block.templateList:                             # get all templates
                    self.appendTemplateGeometryFromRolls(nBlock, block, template)

        except StopIteration:
            self.errorText = 'geometry creation cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        # early completion emit removed
        # self.progress.emit(100)                                                 # make sure we stop at 100
        self.finalizeGeometryArrays()

        # --- DEBUG: validate rel coverage per shot ---
        # build counts of rel records per (SrcInd, SrcLin, SrcPnt)
        # srcKey = np.core.records.fromarrays(
        #     [
        #         self.output.srcGeom['Index'].astype(np.int32),
        #         np.rint(self.output.srcGeom['Line']).astype(np.int32),
        #         np.rint(self.output.srcGeom['Point']).astype(np.int32),
        #     ],
        #     names='Ind,Lin,Pnt',
        # )

        # relKey = np.core.records.fromarrays(
        #     [
        #         self.output.relGeom['SrcInd'].astype(np.int32),
        #         np.rint(self.output.relGeom['SrcLin']).astype(np.int32),
        #         np.rint(self.output.relGeom['SrcPnt']).astype(np.int32),
        #     ],
        #     names='Ind,Lin,Pnt',
        # )

        # # sort once for search
        # relKeySorted = np.sort(relKey)
        # left = np.searchsorted(relKeySorted, srcKey, side='left')
        # right = np.searchsorted(relKeySorted, srcKey, side='right')
        # relCounts = right - left

        # # any shot with zero rel records?
        # missing = np.where(relCounts == 0)[0]
        # if missing.size > 0:
        #     self.errorText = f'geometryFromTemplates(): {missing.size} shots without rel records. Example index {missing[0]}'
        #     print(self.errorText)
        #     return False

        # --- END DEBUG: validate rel coverage per shot ---

        return True

    def appendTemplateGeometryFromRolls(self, nBlock, block, template):
        appSettings = getActiveAppSettings()
        templateGeometryRoutine = self.geomTemplate5 if appSettings.useExperimental else self.geomTemplate4

        for templateOffset in self.iterTemplateRollOffsets(template):
            templateGeometryRoutine(nBlock, block, template, templateOffset)

    def geomTemplate4(self, nBlock, block, template, templateOffset):
        """
        Like geomTemplate3, but fixes receiver de-dup keying by including block index (RecInd).
        This prevents RecInd/Index mismatches across block boundaries.
        """

        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        if QThread.currentThread().isInterruptionRequested():
            raise StopIteration

        self.nTemplate += 1
        threadProgress = (100 * self.nTemplate) // self.nTemplates
        if threadProgress > self.threadProgress:
            self.threadProgress = threadProgress
            self.progress.emit(threadProgress + 1)

        nShotPoint = self.nShotPoint

        self.appendTemplateSourceRecords(nBlock, block, template, npTemplateOffset)

        nRelRecord = self.populateTemplateReceiversInRelTemp(nBlock, block, template, npTemplateOffset)

        if nRelRecord < 0:
            self.errorText = 'geomTemplate4(): no relTemp records created for this template'
            raise StopIteration

        self.appendTemplateRelationsFromRelTemp(nShotPoint, nRelRecord)

    def geomTemplate5(self, nBlock, block, template, templateOffset):
        """
        Vectorized equivalent of geomTemplate4. Same parameters, same end-result.

        Performance differences (purely faster, identical outputs):
          * Receiver de-dup uses a flat int64-keyed Python ``set`` keyed by
            ``(Index, Line, Point)`` packed as one int64, instead of the
            nested ``defaultdict(lambda: defaultdict(dict))`` + try/except
            KeyError pattern in geomTemplate4 (three dict lookups per point
            collapse to one set lookup).
          * Source-record creation is a single bulk numpy assignment into a
            slice of ``srcGeom`` (Line/Point/Index/East/North/LocX/LocY/
            Elev/Uniq/InUse/InXps), replacing the Python per-point
            ``QTransform.map()`` + ``numbaSetPointRecord()`` loop.
          * Receiver-record creation is the same: vectorized stake+global
            mapping, dedup mask, then one bulk slice assignment to
            ``recGeom``.
          * relTemp records are built in one numpy pass: concatenate all
            non-source seed point arrays in seed order, then find runs of
            equal ``RecLin`` via ``np.diff`` and compute per-run
            (RecMin, RecMax) via ``np.minimum.reduceat`` /
            ``np.maximum.reduceat``.
          * Relation emission is one ``np.repeat`` / ``np.tile`` slice
            write into ``relGeom`` for the full nShots * nRelTempRuns
            block, replacing the nested ``for i: for j:`` loop with
            ``numbaSetRelationRecord`` per call.

        Side-effect note: this routine maintains its own flat dedup set
        on ``self.output.recSeenSet`` (created lazily). It does not write
        to ``self.output.recDict`` -- that nested dict is only used by
        geomTemplate4. If both functions are mixed in the same run, the
        dedup state will diverge; pick one path.
        """
        npTemplateOffset = np.array(
            [templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32
        )

        if QThread.currentThread().isInterruptionRequested():
            raise StopIteration

        self.nTemplate += 1
        threadProgress = (100 * self.nTemplate) // self.nTemplates
        if threadProgress > self.threadProgress:
            self.threadProgress = threadProgress
            self.progress.emit(threadProgress + 1)

        nShotPointStart = self.nShotPoint
        recInd = nBlock % 10 + 1                                                # matches numbaSetPointRecord (block % 10 + 1)

        # Lazily init the flat-set replacement for the nested recDict.
        if not hasattr(self.output, 'recSeenSet') or self.output.recSeenSet is None:
            self.output.recSeenSet = set()
        seenSet = self.output.recSeenSet

        # Pre-extract QTransform coefficients once (st2: local -> stake/line,
        # glb: local -> East/North).
        s = self.st2Transform
        s11, s21, s31 = s.m11(), s.m21(), s.m31()
        s12, s22, s32 = s.m12(), s.m22(), s.m32()
        g = self.glbTransform
        g11, g21, g31 = g.m11(), g.m21(), g.m31()
        g12, g22, g32 = g.m12(), g.m22(), g.m32()

        # =====================================================================
        # 1. SOURCES -- bulk-write all source records for this template.
        # =====================================================================
        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue

            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)
            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    continue
                srcArray = srcArray[included, :]
            n = srcArray.shape[0]
            if n == 0:
                continue

            sx = srcArray[:, 0]
            sy = srcArray[:, 1]
            sz = srcArray[:, 2]

            srcStkX = s11 * sx + s21 * sy + s31
            srcStkY = s12 * sx + s22 * sy + s32
            srcLocX = g11 * sx + g21 * sy + g31
            srcLocY = g12 * sx + g22 * sy + g32

            # numbaSetPointRecord stores Line = float(int(stkY)), Point = float(int(stkX)).
            # int() truncates toward zero, so use astype(int32) (same semantics).
            srcLineF = srcStkY.astype(np.int32).astype(np.float32)
            srcPointF = srcStkX.astype(np.int32).astype(np.float32)

            end = self.nShotPoint + n
            # Defensive: grow srcGeom if calcNoShotPoints undercounted (e.g. for
            # non-grid source seeds, or any other unexpected mismatch). Without
            # this, the field-slice assignments below would silently clip to a
            # (0,) destination and raise the cryptic numpy broadcast error
            # "could not broadcast input array from shape (n,) into shape (0,)".
            if end > self.output.srcGeom.shape[0]:
                self.output.srcGeom.resize(
                    end + max(1000, n), refcheck=False
                )
            sg = self.output.srcGeom
            sg['Line'][self.nShotPoint:end] = srcLineF
            sg['Point'][self.nShotPoint:end] = srcPointF
            sg['Index'][self.nShotPoint:end] = recInd
            sg['East'][self.nShotPoint:end] = srcLocX
            sg['North'][self.nShotPoint:end] = srcLocY
            sg['LocX'][self.nShotPoint:end] = sx
            sg['LocY'][self.nShotPoint:end] = sy
            # Elevation = height relative to a datum (e.g. mean sea level). As we
            # have no datum information available, leave Elev at 0.0 per SPS convention.
            sg['Elev'][self.nShotPoint:end] = 0.0
            # Depth = burial depth below surface (positive for sub-surface points).
            # Convention: z < 0 below surface (e.g. well TVDss).
            sg['Depth'][self.nShotPoint:end] = np.maximum(-sz, 0.0)
            sg['Uniq'][self.nShotPoint:end] = 1
            sg['InUse'][self.nShotPoint:end] = 1
            sg['InXps'][self.nShotPoint:end] = 1
            self.nShotPoint = end

        # =====================================================================
        # 2. RECEIVERS -- collect across all rec-seeds (preserving seed order),
        #    map vectorized, dedup, build relTemp, append unique to recGeom.
        # =====================================================================
        recArrays = []
        recIsWell = []                                                          # per-seed boolean: True for well seeds (skip dedup)
        recAppendGeom = []                                                      # per-seed boolean: append physical receiver geometry this rollout
        for recSeed in template.seedList:
            if recSeed.bSource:
                continue
            rPts = recSeed.pointArray + self._receiverSeedTemplateOffset(recSeed, npTemplateOffset)
            if not block.borders.recBorder.isNull():
                included = fnb.pointsInRect(rPts, block.borders.recBorder)
                if included.shape[0] == 0:
                    continue
                rPts = rPts[included, :]
            if rPts.shape[0] > 0:
                recArrays.append(rPts)
                recIsWell.append(np.full(rPts.shape[0], recSeed.type == SeedType.well, dtype=bool))
                recAppendGeom.append(np.full(rPts.shape[0], self._shouldAppendReceiverSeedGeometry(recSeed), dtype=bool))

        if not recArrays:
            self.errorText = 'geomTemplate5(): no relTemp records created for this template'
            raise StopIteration

        rPts = np.concatenate(recArrays, axis=0)
        isWellMask = np.concatenate(recIsWell, axis=0)
        appendGeomMask = np.concatenate(recAppendGeom, axis=0)
        rx = rPts[:, 0]
        ry = rPts[:, 1]
        rz = rPts[:, 2]

        recStkXf = s11 * rx + s21 * ry + s31
        recStkYf = s12 * rx + s22 * ry + s32
        recLocX = g11 * rx + g21 * ry + g31
        recLocY = g12 * rx + g22 * ry + g32

        recPointI = recStkXf.astype(np.int32)                                   # truncate toward zero, like int()
        recLineI = recStkYf.astype(np.int32)
        nRec = rPts.shape[0]

        # --- 2a. relTemp: one record per run of equal RecLin in concat order. ---
        if nRec == 1:
            runStart = np.array([0], dtype=np.int64)
        else:
            runStart = np.concatenate(([0], np.where(np.diff(recLineI) != 0)[0] + 1)).astype(np.int64)
        nRuns = runStart.shape[0]
        nRelRecord = nRuns - 1                                                  # 0-based last index, matches geomTemplate4

        runRecLin = recLineI[runStart]
        runRecMin = np.minimum.reduceat(recPointI, runStart)
        runRecMax = np.maximum.reduceat(recPointI, runStart)

        if np.any(runRecMin > runRecMax):
            self.errorText = 'geomTemplate5(): RecMin > RecMax detected'
            raise StopIteration

        if nRuns + 10 > self.output.relTemp.shape[0]:
            self.output.relTemp.resize(nRuns + 100, refcheck=False)
        rt = self.output.relTemp
        rt['RecLin'][:nRuns] = runRecLin.astype(np.float32)
        rt['RecMin'][:nRuns] = runRecMin.astype(np.float32)
        rt['RecMax'][:nRuns] = runRecMax.astype(np.float32)
        rt['RecInd'][:nRuns] = recInd

        # --- 2b. Dedup against survey-level flat set, append unique to recGeom. ---
        # Key = packed int64 of (recInd, qz, line, point) to vectorize the
        # within-template dedup via ``np.unique`` and keep the cross-template
        # ``seenSet`` membership test cheap (one int per row).
        # Bit layout (LSB -> MSB), sized for realistic survey ranges:
        #   point + POINT_OFF : POINT_BITS = 20  (range -524_288 .. +524_287;
        #                                          actual line/point are 1..10_000)
        #   line  + LINE_OFF  : LINE_BITS  = 20
        #   qz    + QZ_OFF    : QZ_BITS    =  8  (1 m bucket; range -128 .. +127,
        #                                          covers grid/circle/spiral z spread)
        #   recInd            : IND_BITS   =  8  (0 .. 255; matches nBlock%10 + 1,
        #                                          plenty of headroom for marine blocks)
        # Total = 56 bits, well within int64. Including quantized z prevents
        # grid-seed receivers at the same (Line, Point) cell but different
        # elevations from being collapsed.
        # Wells: well receivers are intrinsically unique by trajectory
        # construction (near-vertical wells produce many points sharing the
        # same Line/Point bin and even the same qz bucket). They bypass dedup
        # entirely and are NOT added to ``seenSet``.
        POINT_BITS = np.int64(20)
        LINE_BITS = np.int64(20)
        QZ_BITS = np.int64(8)
        POINT_OFF = np.int64(1) << (POINT_BITS - np.int64(1))
        LINE_OFF = np.int64(1) << (LINE_BITS - np.int64(1))
        QZ_OFF = np.int64(1) << (QZ_BITS - np.int64(1))
        SHIFT_LINE = POINT_BITS
        SHIFT_QZ = POINT_BITS + LINE_BITS
        SHIFT_IND = POINT_BITS + LINE_BITS + QZ_BITS

        qz = np.rint(rz).astype(np.int64)                                       # 1-metre quantized z
        keys = (
            (np.int64(recInd) << SHIFT_IND) |                                   # noqa: W504
            ((qz + QZ_OFF) << SHIFT_QZ) |                                       # noqa: W504
            ((recLineI.astype(np.int64) + LINE_OFF) << SHIFT_LINE) |            # noqa: W504
            (recPointI.astype(np.int64) + POINT_OFF)                            # noqa: W504
        )

        nonWellIdx = np.where((~isWellMask) & appendGeomMask)[0]
        wellIdx = np.where(isWellMask & appendGeomMask)[0]

        if nonWellIdx.size > 0:
            # First-occurrence-within-template via stable np.unique.
            _, firstLocal = np.unique(keys[nonWellIdx], return_index=True)
            firstLocal.sort()
            candIdx = nonWellIdx[firstLocal]
            candKeys = keys[candIdx]
            # Filter against the survey-wide seenSet (Python int membership).
            keepMask = np.fromiter(
                (k not in seenSet for k in candKeys.tolist()),
                dtype=bool,
                count=candKeys.shape[0],
            )
            keepNonWell = candIdx[keepMask]
        else:
            keepNonWell = np.empty(0, dtype=np.int64)

        # Wells: keep every row, no seenSet filtering.
        keepIdx = np.concatenate([keepNonWell, wellIdx]).astype(np.int64)

        if keepIdx.shape[0] > 0:
            nNew = keepIdx.shape[0]
            if self.nRecRecord + nNew + 1000 > self.output.recGeom.shape[0]:
                self.output.recGeom.resize(
                    self.output.recGeom.shape[0] + max(10000, nNew + 1000), refcheck=False
                )
            end = self.nRecRecord + nNew
            rg = self.output.recGeom
            rg['Line'][self.nRecRecord:end] = recLineI[keepIdx].astype(np.float32)
            rg['Point'][self.nRecRecord:end] = recPointI[keepIdx].astype(np.float32)
            rg['Index'][self.nRecRecord:end] = recInd
            rg['East'][self.nRecRecord:end] = recLocX[keepIdx]
            rg['North'][self.nRecRecord:end] = recLocY[keepIdx]
            rg['LocX'][self.nRecRecord:end] = rx[keepIdx]
            rg['LocY'][self.nRecRecord:end] = ry[keepIdx]
            # Elevation = height relative to a datum (e.g. mean sea level). As we
            # have no datum information available, leave Elev at 0.0 per SPS convention.
            rg['Elev'][self.nRecRecord:end] = 0.0
            # Depth = burial depth below surface (positive number for sub-surface
            # points such as well receivers); zero for points at/above surface.
            rg['Depth'][self.nRecRecord:end] = np.maximum(-rz[keepIdx], 0.0)
            rg['Uniq'][self.nRecRecord:end] = 1
            rg['InUse'][self.nRecRecord:end] = 1
            rg['InXps'][self.nRecRecord:end] = 1
            self.nRecRecord = end
            # Register non-well keys in the survey-wide seenSet so subsequent
            # templates dedup against them. Wells are intrinsically unique
            # and therefore not added.
            if keepNonWell.size > 0:
                seenSet.update(keys[keepNonWell].tolist())

        # =====================================================================
        # 3. RELATIONS -- emit (nShots * nRuns) records in one slice write.
        # =====================================================================
        nShotsThis = self.nShotPoint - nShotPointStart
        if nShotsThis == 0 or nRelRecord < 0:
            return

        nRel = nShotsThis * nRuns
        if self.nRelRecord + nRel + 1000 > self.output.relGeom.shape[0]:
            self.output.relGeom.resize(
                self.output.relGeom.shape[0] + max(10000, nRel + 1000), refcheck=False
            )

        sg = self.output.srcGeom
        rg = self.output.relGeom
        rt = self.output.relTemp

        # Outer = shot, inner = relTemp run -- matches geomTemplate4's nesting.
        srcLinR = np.repeat(sg['Line'][nShotPointStart:self.nShotPoint], nRuns)
        srcPntR = np.repeat(sg['Point'][nShotPointStart:self.nShotPoint], nRuns)
        srcIndR = np.repeat(sg['Index'][nShotPointStart:self.nShotPoint], nRuns)
        # shtRec = i + 1 (1-based shot record number) in the original.
        shtRecR = np.repeat(
            np.arange(nShotPointStart + 1, self.nShotPoint + 1, dtype=np.int32), nRuns
        )

        recLinT = np.tile(rt['RecLin'][:nRuns], nShotsThis)
        recMinT = np.tile(rt['RecMin'][:nRuns], nShotsThis)
        recMaxT = np.tile(rt['RecMax'][:nRuns], nShotsThis)

        end = self.nRelRecord + nRel
        sl = slice(self.nRelRecord, end)
        rg['SrcLin'][sl] = srcLinR
        rg['SrcPnt'][sl] = srcPntR
        rg['SrcInd'][sl] = srcIndR
        rg['RecNum'][sl] = shtRecR
        rg['RecLin'][sl] = recLinT
        rg['RecMin'][sl] = recMinT
        rg['RecMax'][sl] = recMaxT
        rg['RecInd'][sl] = srcIndR                                              # original sets RecInd = srcInd
        rg['Uniq'][sl] = 1
        self.nRelRecord = end

    def finalizeGeometryArrays(self) -> None:
        #  first remove all remaining receiver duplicates
        self.message.emit('Post processing step 1/4 - remove receiver duplicates')
        self.progress.emit(20)
        self.compactGeometryArrays()

        # set all values in one go at the end
        self.message.emit('Post processing step 3/4 - set source geometry flags')
        self.progress.emit(60)
        self.applyGeometryRecordFlags()

        # sort the three geometry arrays
        self.message.emit('Post processing step 4/4 - sort geometry arrays')
        self.progress.emit(80)
        self.sortGeometryArrays()
        self.progress.emit(100)

    def compactGeometryArrays(self) -> None:
        self.output.recGeom = np.unique(self.output.recGeom)

        # no longer needed, because we keep track of 'self.nRelRecord'
        # there's no need to shrink the array based on the 'Uniq' == 1 condition.
        # need to change the code; resize the relGeom array based on self.nRelRecord
        # trim rel & rec arrays removing any zeros, using the 'Uniq' == 1 condition.

        self.message.emit('Post processing step 2/4 - remove zeros in relation & receiver arrays')
        self.progress.emit(40)
        self.output.relGeom = self.output.relGeom[self.output.relGeom['Uniq'] == 1]
        self.output.recGeom = self.output.recGeom[self.output.recGeom['Uniq'] == 1]

    def applyGeometryRecordFlags(self) -> None:
        self.output.srcGeom['Uniq'] = 1
        self.output.srcGeom['InXps'] = 1
        self.output.srcGeom['Code'] = 'E1'

        self.output.recGeom['Uniq'] = 1
        self.output.recGeom['InXps'] = 1
        self.output.recGeom['Code'] = 'G1'

        self.output.relGeom['InSps'] = 1
        self.output.relGeom['InRps'] = 1

    def sortGeometryArrays(self) -> None:
        self.output.srcGeom.sort(order=['Index', 'Point', 'Line'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        return perf_counter()  # call again; to ignore any time spent in this funtion

    def appendTemplateSourceRecords(self, nBlock, block, template, npTemplateOffset):
        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue

            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)

            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    continue
                srcArray = srcArray[included, :]

            for src in srcArray:
                srcX = src[0]
                srcY = src[1]

                srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)
                srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)

                fnb.numbaSetPointRecord(self.output.srcGeom, self.nShotPoint, srcStkY, srcStkX, nBlock, srcLocX, srcLocY, src)
                self.nShotPoint += 1

    def populateTemplateReceiversInRelTemp(self, nBlock, block, template, npTemplateOffset):
        nRelRecord = -1
        nOldRecLine = -999999

        # -- Receiver points & relTemp --
        for recSeed in template.seedList:
            if recSeed.bSource:
                continue

            recPoints = recSeed.pointArray + self._receiverSeedTemplateOffset(recSeed, npTemplateOffset)
            appendGeometry = self._shouldAppendReceiverSeedGeometry(recSeed)

            if not block.borders.recBorder.isNull():
                included = fnb.pointsInRect(recPoints, block.borders.recBorder)
                if included.shape[0] == 0:
                    continue
                recPoints = recPoints[included, :]

            isWellSeed = (recSeed.type == SeedType.well)

            for rec in recPoints:
                recX = rec[0]
                recY = rec[1]
                recZ = rec[2]

                recStkX, recStkY = self.st2Transform.map(recX, recY)
                recLocX, recLocY = self.glbTransform.map(recX, recY)

                recPoint = int(recStkX)
                recLine = int(recStkY)

                # block-aware receiver index
                recInd = nBlock % 10 + 1

                # De-dup receivers by (block, line, point, quantized-z). Including
                # quantized z (1 m bucket) prevents grid-seed receivers at the same
                # (Line, Point) cell but different elevations from being collapsed.
                # Well seeds skip dedup entirely: well receivers are intrinsically
                # unique by trajectory construction, and near-vertical wells
                # produce many points sharing the same (Line, Point) cell that
                # must NOT be deduped.
                if isWellSeed:
                    isNew = True
                else:
                    qz = int(round(float(recZ)))
                    # nested-dict lookup keyed by [recInd][recLine][recPoint][qz]
                    inner = self.output.recDict[recInd][recLine].setdefault(recPoint, {})
                    if not isinstance(inner, dict):
                        # Backward-compat: legacy entries stored an int directly.
                        # Promote to a dict keyed by qz so the new logic can
                        # discriminate elevations.
                        prev = inner
                        inner = {0: prev}
                        self.output.recDict[recInd][recLine][recPoint] = inner
                    isNew = qz not in inner
                    if isNew:
                        inner[qz] = self.nRecRecord

                if isNew and appendGeometry:
                    fnb.numbaSetPointRecord(self.output.recGeom, self.nRecRecord, recStkY, recStkX, nBlock, recLocX, recLocY, rec)
                    # fnb.numbaSetPointRecord uses nBlock -> Index consistent with recInd
                    self.nRecRecord += 1

                    arraySize = self.output.recGeom.shape[0]
                    if self.nRecRecord + 1000 > arraySize:
                        self.output.recGeom.resize(arraySize + 10000, refcheck=False)

                if recLine != nOldRecLine:
                    nOldRecLine = recLine
                    nRelRecord += 1

                    self.output.relTemp[nRelRecord]['RecLin'] = recStkY
                    self.output.relTemp[nRelRecord]['RecMin'] = recStkX
                    self.output.relTemp[nRelRecord]['RecMax'] = recStkX
                    self.output.relTemp[nRelRecord]['RecInd'] = recInd

                    if self.output.relTemp[nRelRecord]['RecMin'] > self.output.relTemp[nRelRecord]['RecMax']:
                        self.errorText = 'geomTemplate4(): RecMin > RecMax detected'
                        raise StopIteration

                    arraySize = self.output.relTemp.shape[0]
                    if nRelRecord + 10 > arraySize:
                        self.output.relTemp.resize(arraySize + 100, refcheck=False)
                else:
                    self.output.relTemp[nRelRecord]['RecMin'] = min(recStkX, self.output.relTemp[nRelRecord]['RecMin'])
                    self.output.relTemp[nRelRecord]['RecMax'] = max(recStkX, self.output.relTemp[nRelRecord]['RecMax'])

        return nRelRecord

    def appendTemplateRelationsFromRelTemp(self, firstShotPoint, nRelRecord):
        for i in range(firstShotPoint, self.nShotPoint):
            arraySize = self.output.relGeom.shape[0]
            if self.nRelRecord + 1000 > arraySize:
                self.output.relGeom.resize(arraySize + 10000, refcheck=False)

            srcLin = self.output.srcGeom[i]['Line']
            srcPnt = self.output.srcGeom[i]['Point']
            srcInd = self.output.srcGeom[i]['Index']

            for j in range(nRelRecord + 1):
                recLin = self.output.relTemp[j]['RecLin']
                recMin = self.output.relTemp[j]['RecMin']
                recMax = self.output.relTemp[j]['RecMax']

                fnb.numbaSetRelationRecord(self.output.relGeom, self.nRelRecord, srcLin, srcPnt, srcInd, i + 1, recLin, recMin, recMax)
                self.nRelRecord += 1

    def updateBinOutputsForValidCmpPoints(self, src, cmpPoints, recPoints, hypArray, aziArray, writeAnalysis, totalTime=None, profileBaseIndex=None):
        if profileBaseIndex is not None:
            timer = perf_counter()
        mapped = np.array([self.binTransform.map(float(p[0]), float(p[1])) for p in cmpPoints], dtype=np.float32)
        nx = mapped[:, 0].astype(int)
        ny = mapped[:, 1].astype(int)

        valid = (
            (nx >= 0) & (ny >= 0) &                     # noqa: W504
            (nx < self.output.binOutput.shape[0]) &     # noqa: W504
            (ny < self.output.binOutput.shape[1])       # noqa: W504
        )
        if np.all(~valid):
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex)
            return False

        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex)

        nx = nx[valid]
        ny = ny[valid]
        cmpPoints = cmpPoints[valid]
        recPoints = recPoints[valid]
        hypArray = hypArray[valid]
        aziArray = aziArray[valid]
        if totalTime is not None:
            totalTime = totalTime[valid]

        # ------------------------------------------------------------------
        # BUG FIX (2026-04-28):
        # The previous implementation incremented binOutput in bulk via
        # np.add.at(...) BEFORE the analysis loop, then read
        #     fold = binOutput[x, y] - 1
        # inside the loop. That meant every one of the N traces landing in
        # the same bin saw the SAME post-increment count and wrote into
        # slot N-1 of anaOutput, overwriting traces 0..N-2. As a result,
        # the relation/template binning paths silently lost all but the
        # last trace per over-folded bin in anaOutput, while binOutput
        # still showed the correct fold count -- so downstream calc helpers
        # that index anaOutput[x, y, :fold, ...] were reading mostly zeros.
        #
        # The no-rel fast path (_applyBinUpdatesVectorized) reads `fold`
        # BEFORE incrementing, which is correct: trace k lands in slot k.
        # We now mirror that pattern here. The min/max offset scatters are
        # also folded into the per-trace loop in the analysis branch so
        # they stay in lock-step with the bin increment.
        # ------------------------------------------------------------------

        if writeAnalysis:
            if profileBaseIndex is not None:
                timer = perf_counter()
            maxFold = self.grid.fold
            for idx, (x, y) in enumerate(zip(nx, ny)):
                fold = int(self.output.binOutput[x, y])                 # read BEFORE increment
                if fold < maxFold:
                    stkX, stkY = self.st2Transform.map(cmpPoints[idx, 0], cmpPoints[idx, 1])
                    self.output.anaOutput[x, y, fold, 0] = int(stkX)
                    self.output.anaOutput[x, y, fold, 1] = int(stkY)
                    self.output.anaOutput[x, y, fold, 2] = fold + 1
                    self.output.anaOutput[x, y, fold, 3] = src[0]
                    self.output.anaOutput[x, y, fold, 4] = src[1]
                    self.output.anaOutput[x, y, fold, 5] = src[2]
                    self.output.anaOutput[x, y, fold, 6] = recPoints[idx, 0]
                    self.output.anaOutput[x, y, fold, 7] = recPoints[idx, 1]
                    self.output.anaOutput[x, y, fold, 8] = recPoints[idx, 2]
                    self.output.anaOutput[x, y, fold, 9] = cmpPoints[idx, 0]
                    self.output.anaOutput[x, y, fold, 10] = cmpPoints[idx, 1]
                    self.output.anaOutput[x, y, fold, 11] = cmpPoints[idx, 2]
                    self.output.anaOutput[x, y, fold, 12] = totalTime[idx] if totalTime is not None else 0.0
                    self.output.anaOutput[x, y, fold, 13] = hypArray[idx]
                    self.output.anaOutput[x, y, fold, 14] = aziArray[idx]
                # increment AFTER the analysis read so the next trace in
                # this bin lands in the next fold slot.
                self.output.binOutput[x, y] += 1
                if hypArray[idx] < self.output.minOffset[x, y]:
                    self.output.minOffset[x, y] = hypArray[idx]
                if hypArray[idx] > self.output.maxOffset[x, y]:
                    self.output.maxOffset[x, y] = hypArray[idx]
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex + 1)
            return True

        # No-analysis fast path: vectorized scatter is fine because there
        # is no per-trace dependency on fold ordering.
        if profileBaseIndex is not None:
            timer = perf_counter()
        np.add.at(self.output.binOutput, (nx, ny), 1)
        np.minimum.at(self.output.minOffset, (nx, ny), hypArray)
        np.maximum.at(self.output.maxOffset, (nx, ny), hypArray)
        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex + 2)
        return True

    def buildBinningArraysFromSelectedReceivers(self, src, recPoints):
        if self.binning.method == BinningType.cmp:
            cmpPoints = (recPoints + src) * 0.5
            offArray = recPoints - src
        elif self.binning.method == BinningType.plane:
            srcMirrorNp = self.localPlane.mirrorPointNp(src)
            cmpPoints, recPoints = self.localPlane.IntersectLinesAtPointNp(
                srcMirrorNp, recPoints, self.angles.reflection.x(), self.angles.reflection.y()
            )
            if cmpPoints is None:
                return None
            offArray = recPoints - src
        elif self.binning.method == BinningType.sphere:
            cmpPoints, recPoints = self.localSphere.ReflectSphereAtPointsNp(
                src, recPoints, self.angles.reflection.x(), self.angles.reflection.y()
            )
            if cmpPoints is None:
                return None
            offArray = recPoints - src
        else:
            return None

        included = fnb.pointsInRect(cmpPoints, self.output.rctOutput)
        if np.all(~included):
            return None

        cmpPoints = cmpPoints[included]
        recPoints = recPoints[included]
        offArray = offArray[included]

        included = fnb.pointsInRect(offArray, self.offset.rctOffsets)
        if np.all(~included):
            return None

        cmpPoints = cmpPoints[included]
        recPoints = recPoints[included]
        offArray = offArray[included]

        hypArray = np.hypot(offArray[:, 0], offArray[:, 1])
        aziArray = np.rad2deg(np.arctan2(offArray[:, 0], offArray[:, 1]))
        aziArray = (aziArray + 360.0) % 360.0

        r1 = self.offset.radOffsets.x()
        r2 = self.offset.radOffsets.y()
        if r2 > 0:
            included = (hypArray >= r1) & (hypArray <= r2)
            if np.all(~included):
                return None
            cmpPoints = cmpPoints[included]
            recPoints = recPoints[included]
            hypArray = hypArray[included]
            aziArray = aziArray[included]

        return cmpPoints, recPoints, hypArray, aziArray

    def ensurePointArrayLocalCoordinates(self, pointArray, toLocalTransform) -> None:
        if pointArray is None or pointArray.shape[0] == 0:
            return

        if np.all(pointArray['LocX'] == 0.0) and np.all(pointArray['LocY'] == 0.0):
            mapped = np.array(
                [toLocalTransform.map(float(x), float(y)) for x, y in zip(pointArray['East'], pointArray['North'])],
                dtype=np.float32,
            )
            pointArray['LocX'] = mapped[:, 0]
            pointArray['LocY'] = mapped[:, 1]

    def ensureGeometryLocalCoordinates(self) -> None:
        toLocalTransform, _ = self.glbTransform.inverted()
        self.ensurePointArrayLocalCoordinates(self.output.srcGeom, toLocalTransform)
        self.ensurePointArrayLocalCoordinates(self.output.recGeom, toLocalTransform)

    def finalizeLiveBinningOutputs(self, fullAnalysis) -> None:
        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcOffsetGapValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None

    def prepareGeometryRelationBinningLookup(self):
        self.ensureGeometryLocalCoordinates()

        if self.output.srcGeom is not None:
            self.output.srcGeom.sort(order=['Index', 'Point', 'Line'])
        if self.output.recGeom is not None:
            self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        if self.output.relGeom is not None:
            self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        if self.output.srcGeom is None or self.output.recGeom is None or self.output.relGeom is None:
            return None

        srcIndI = self.output.srcGeom['Index'].astype(np.int32)
        srcLinI = np.rint(self.output.srcGeom['Line']).astype(np.int32)
        srcPntI = np.rint(self.output.srcGeom['Point']).astype(np.int32)

        relSrcIndI = self.output.relGeom['SrcInd'].astype(np.int32)
        relSrcLinI = np.rint(self.output.relGeom['SrcLin']).astype(np.int32)
        relSrcPntI = np.rint(self.output.relGeom['SrcPnt']).astype(np.int32)

        relKey = np.rec.fromarrays([relSrcIndI, relSrcLinI, relSrcPntI], names='Ind,Lin,Pnt')
        srcKey = np.rec.fromarrays([srcIndI, srcLinI, srcPntI], names='Ind,Lin,Pnt')

        return GeometryRelationBinningLookup(
            relLeft=np.searchsorted(relKey, srcKey, side='left'),
            relRight=np.searchsorted(relKey, srcKey, side='right'),
            recIndex=self.output.recGeom['Index'],
            recLineI=np.rint(self.output.recGeom['Line']).astype(np.int32),
            recPointI=np.rint(self.output.recGeom['Point']).astype(np.int32),
            relRecIndI=self.output.relGeom['RecInd'].astype(np.int32),
            relRecLinI=np.rint(self.output.relGeom['RecLin']).astype(np.int32),
            relRecMinI=np.rint(self.output.relGeom['RecMin']).astype(np.int32),
            relRecMaxI=np.rint(self.output.relGeom['RecMax']).astype(np.int32),
        )

    def selectReceiversForSourceRelationSlice(self, sourceIndex, lookup):
        minRecord = lookup.relLeft[sourceIndex]
        maxRecord = lookup.relRight[sourceIndex]
        if maxRecord <= minRecord:
            return None

        recMask = np.zeros(self.output.recGeom.shape[0], dtype=bool)
        for relationIndex in range(minRecord, maxRecord):
            recMask |= (
                (lookup.recIndex == lookup.relRecIndI[relationIndex]) &     # noqa: W504
                (lookup.recLineI == lookup.relRecLinI[relationIndex]) &     # noqa: W504
                (lookup.recPointI >= lookup.relRecMinI[relationIndex]) &    # noqa: W504
                (lookup.recPointI <= lookup.relRecMaxI[relationIndex])      # noqa: W504
            )

        recArray = self.output.recGeom[recMask]
        recArray = recArray[recArray['InUse'] > 0]
        if recArray.shape[0] == 0:
            return None

        # Real receiver z = Elev - Depth (Elev=0 for SPS surface convention,
        # Depth>0 for well/TVDss receivers); keeps geometry binning numerically
        # identical to template binning, which uses each seed's true 3D z.
        return np.vstack((recArray['LocX'], recArray['LocY'], recArray['Elev'] - recArray['Depth'])).T

    def setupBinFromGeometry(self, fullAnalysis) -> bool:
        """this routine is used for both geometry files and SPS files"""

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0
        appSettings = getActiveAppSettings()

        if appSettings.useExperimental:
            relBinningRoutine = self.binFromGeometry10
            noRelBinningRoutine = self.binFromGeometryNoRel2
        else:
            relBinningRoutine = self.binFromGeometry8
            noRelBinningRoutine = self.binFromGeometryNoRel

        # Announce which routine is actually being dispatched so we can
        # confirm at runtime that the useExperimental flag flowed through.
        hasRel = self.output.relGeom is not None
        chosen = relBinningRoutine if hasRel else noRelBinningRoutine
        self.logMessage.emit(
            f'Method : useExperimental={appSettings.useExperimental}, hasRel={hasRel} -> {chosen.__name__}, fullAnalysis={fullAnalysis}'
        )

        # Now do the binning; check if we haave a relation file or not
        if self.output.relGeom is not None:                                     # we have a relation file
            if fullAnalysis:
                success = relBinningRoutine(True)
                if isinstance(self.output.anaOutput, np.memmap):
                    np.memmap.flush(self.output.anaOutput)                      # flush results to hard disk when using memmap
                return success

            return relBinningRoutine(False)
        if fullAnalysis:                                                        # no relation file available
            success = noRelBinningRoutine(True)
            if isinstance(self.output.anaOutput, np.memmap):
                np.memmap.flush(self.output.anaOutput)                          # flush results to hard disk when using memmap
            return success
        return noRelBinningRoutine(False)

    def binFromGeometryNoRel(self, fullAnalysis) -> bool:
        """
        all binning methods (cmp, plane, sphere) implemented, using numpy arrays, rather than a for-loop.
        On 09/04/2024 the earlier implementations of binFromGeometry v1 to v3 have been removed.
        They are still available in the roll-2024-08-04 folder in classes.py
        """
        self.threadProgress = 0                                                 # always start at zero

        self.ensureGeometryLocalCoordinates()

        # There is no relation file in this binning approach; iterate over all shots and find receivers based on proximity

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        recGeom = self.output.recGeom
        recMask = recGeom['InUse'] > 0
        if not np.any(recMask):
            return True  # nothing to bin

        # it is ESSENTIAL that any orphans & duplicates in recPoints have been removed at this stage
        baseRecArray = recGeom[recMask]

        # for cmp and offset calcuations, we need numpy arrays in the form of local (x, y, z) coordinates
        # Real receiver z = Elev - Depth (see selectReceiversForSourceRelationSlice).
        baseRecPoints = np.column_stack((baseRecArray['LocX'], baseRecArray['LocY'], baseRecArray['Elev'] - baseRecArray['Depth'])).astype(np.float32)

        # we are NOT DEALING with the block's src border; this should have been done while generating geometry
        # we are NOT DEALING with the block's rec border; this should have been done while generating geometry
        # but we are dealing with the "InUse" attribute, that allows for killing a point in QGIS

        try:
            for srcRecord in self.output.srcGeom:

                if srcRecord['InUse'] == 0:                                     # this record has been disabled
                    continue

                # convert the source record to a single [x, y, z] value
                # Real source z = Elev - Depth (mirrors receiver convention).
                src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev'] - srcRecord['Depth']], dtype=np.float32)

                # begin thread progress code
                if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end thread progress code

                # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
                # we combine recPoints with a source point to create cmp array, define offsets, etc...
                recPoints = baseRecPoints

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

                included = fnb.pointsInRect(cmpPoints, self.output.rctOutput)   # find the cmp locations that contribute to the output area
                if included.shape[0] == 0:
                    continue

                cmpPoints = cmpPoints[included, :]                              # filter the cmp-array
                recPoints = recPoints[included, :]                              # filter the rec-array too, as we still need this for offsets

                size = recPoints.shape[0]
                offArray = np.zeros(shape=(size, 3), dtype=np.float32)          # allocate the offset array according to rec array
                offArray = recPoints - src                                      # define the offset array

                included = fnb.pointsInRect(offArray, self.offset.rctOffsets)
                if included.shape[0] == 0:
                    continue

                offArray = offArray[included, :]                                # filter the offset-array
                cmpPoints = cmpPoints[included, :]                              # filter the cmp-array too, as we still need this
                recPoints = recPoints[included, :]                              # filter the rec-array too, as we still need this

                size = recPoints.shape[0]
                hypArray = np.zeros(shape=(size, 1), dtype=np.float32)          # allocate the radius array according to rec array
                hypArray = np.hypot(offArray[:, 0], offArray[:, 1])             # calculate radial offset size
                aziArray = np.arctan2(offArray[:, 0], offArray[:, 1])           # calculate offset angles
                aziArray = np.rad2deg(aziArray)                                 # get angles in degrees instead of radians
                aziArray = (aziArray + 360.0) % 360.0                           # convert angles to 0-360 range

                r1 = self.offset.radOffsets.x()                                 # r1 = minimum radius
                r2 = self.offset.radOffsets.y()                                 # r2 = maximum radius
                if r2 > 0:                                                      # we need to apply the radial offset selection criteria
                    included = (hypArray[:] >= r1) & (hypArray[:] <= r2)
                    if np.count_nonzero(included) == 0:
                        continue                                                # continue with next recSeed
                    # print(included)
                    hypArray = hypArray[included]                               # filter the radial offset-array
                    aziArray = aziArray[included]                               # filter the offset-angle array too
                    offArray = offArray[included, :]                            # filter the off-array too, as we still need this
                    cmpPoints = cmpPoints[included, :]                          # filter the cmp-array too, as we still need this
                    recPoints = recPoints[included, :]                          # filter the rec-array too, as we still need this

                # now work on the TWT aspect of the src, cmp & rec positions
                if self.binning.method == BinningType.cmp:
                    upDnArray = recPoints - src                                 # straigth rays; total length of both legs
                    totalTime = np.linalg.norm(upDnArray, axis=1)               # get length of the rays
                else:
                    dnArray = cmpPoints - src                                   # 1st leg of the rays
                    upArray = cmpPoints - recPoints                             # 2nd leg of the rays
                    dnTime = np.linalg.norm(dnArray, axis=1)                    # get length of the 1st leg
                    upTime = np.linalg.norm(upArray, axis=1)                    # get length of the 2nd leg
                    totalTime = dnTime + upTime                                 # total length of both legs

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
                                self.output.anaOutput[nx, ny, fold, 0] = int(stkX)
                                self.output.anaOutput[nx, ny, fold, 1] = int(stkY)
                                self.output.anaOutput[nx, ny, fold, 2] = fold + 1       # to make fold run from 1 to N
                                self.output.anaOutput[nx, ny, fold, 3] = src[0]
                                self.output.anaOutput[nx, ny, fold, 4] = src[1]
                                self.output.anaOutput[nx, ny, fold, 5] = src[2]
                                self.output.anaOutput[nx, ny, fold, 6] = recPoints[count, 0]
                                self.output.anaOutput[nx, ny, fold, 7] = recPoints[count, 1]
                                self.output.anaOutput[nx, ny, fold, 8] = recPoints[count, 2]
                                self.output.anaOutput[nx, ny, fold, 9] = cmpPoints[count, 0]
                                self.output.anaOutput[nx, ny, fold, 10] = cmpPoints[count, 1]
                                self.output.anaOutput[nx, ny, fold, 11] = cmpPoints[count, 2]
                                self.output.anaOutput[nx, ny, fold, 12] = totalTime[count]
                                self.output.anaOutput[nx, ny, fold, 13] = hypArray[count]
                                self.output.anaOutput[nx, ny, fold, 14] = aziArray[count]
                                # self.output.anaOutput[nx, ny, fold, 15] = -1

                        # all selection criteria have been fullfilled; use the trace
                        self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                        self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                        self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

                    # rather than checking nx, ny & fold, use exception handling to deal with index errors
                    except IndexError:
                        continue

        except StopIteration:
            self.errorText = 'binning from geometry cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.finalizeLiveBinningOutputs(fullAnalysis)

        return True

    def binFromGeometryNoRel2(self, fullAnalysis) -> bool:
        """
        Optimized variant of binFromGeometryNoRel with identical semantics.

        Aligned with binFromGeometry10:
          * Reuses buildBinningArraysFromSelectedReceivers() for CMP / plane
            / sphere binning + rctOutput + rctOffsets + radOffsets filtering
            (binFromGeometryNoRel inlines all of this).
          * Reuses the shared bin-update helpers for the bin/stake transform
            and scatter writes, replacing the Python per-point
            QTransform.map() loop.

        Differences vs binFromGeometry10 (intentional, no-rel path only):
          * No relation lookup; every live source sees the same shared
            baseRecPoints array (one np.column_stack done once outside the
            shot loop).
          * Travel time (totalTime = ||src->cmp|| + ||cmp->rec||) * slowness
            is computed per shot and forwarded to the selected write helper so
            anaOutput[..., 12] keeps the value binFromGeometryNoRel writes
            there. With useNumba enabled in full-analysis mode, the per-trace
            analysis writes go through _applyBinUpdatesNumba().
        """
        self.threadProgress = 0
        appSettings = getActiveAppSettings()
        profile = appSettings.debug
        writeRoutine = self._applyBinUpdatesNumba if fullAnalysis and appSettings.useNumba else self._applyBinUpdatesVectorized

        self.ensureGeometryLocalCoordinates()

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        recGeom = self.output.recGeom
        recMask = recGeom['InUse'] > 0
        if not np.any(recMask):
            self.finalizeLiveBinningOutputs(fullAnalysis)
            return True

        baseRecArray = recGeom[recMask]
        baseRecPoints = np.column_stack(
            (baseRecArray['LocX'], baseRecArray['LocY'], baseRecArray['Elev'] - baseRecArray['Depth'])
        ).astype(np.float32, copy=False)

        T = self.binTransform
        binMat = np.array(
            [[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()]], dtype=np.float64
        )
        S = self.st2Transform
        st2Mat = np.array(
            [[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()]], dtype=np.float64
        )

        slowness = self.binning.slowness
        cmpMethod = self.binning.method == BinningType.cmp

        try:
            for srcRecord in self.output.srcGeom:
                if srcRecord['InUse'] == 0:
                    continue

                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                src = np.array(
                    [srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev'] - srcRecord['Depth']], dtype=np.float32
                )

                if profile:
                    timer = perf_counter()
                traceArrays = self.buildBinningArraysFromSelectedReceivers(src, baseRecPoints)
                if profile:
                    self.elapsedTime(timer, 1)
                if traceArrays is None:
                    continue
                cmpPoints, recPoints, hypArray, aziArray = traceArrays

                if profile:
                    timer = perf_counter()
                if cmpMethod:
                    totalTime = np.linalg.norm(recPoints - src, axis=1)
                else:
                    dnTime = np.linalg.norm(cmpPoints - src, axis=1)
                    upTime = np.linalg.norm(cmpPoints - recPoints, axis=1)
                    totalTime = dnTime + upTime
                totalTime = totalTime * slowness
                if profile:
                    self.elapsedTime(timer, 2)

                if profile:
                    timer = perf_counter()
                writeRoutine(src, cmpPoints, recPoints, hypArray, aziArray, binMat, st2Mat, fullAnalysis, totalTime)
                if profile:
                    self.elapsedTime(timer, 3)

        except StopIteration:
            self.errorText = 'binning from geometry cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.finalizeLiveBinningOutputs(fullAnalysis)
        return True

    def binFromGeometry8(self, fullAnalysis) -> bool:
        """
        Optimized binning with integer-normalized relation indexing to avoid gaps.
        """
        self.threadProgress = 0
        lookup = self.prepareGeometryRelationBinningLookup()

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        try:
            for i, srcRecord in enumerate(self.output.srcGeom):
                if srcRecord['InUse'] == 0:
                    continue

                src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev'] - srcRecord['Depth']], dtype=np.float32)

                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                recPoints = self.selectReceiversForSourceRelationSlice(i, lookup)
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration
                if recPoints is None:
                    continue

                traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration
                if traceArrays is None:
                    continue
                cmpPoints, recPoints, hypArray, aziArray = traceArrays

                # Compute travel time so anaOutput[..., 12] gets populated for
                # the relation path too (Option A: matches binFromGeometryNoRel).
                if self.binning.method == BinningType.cmp:
                    totalTime = np.linalg.norm(recPoints - src, axis=1)
                else:
                    totalTime = np.linalg.norm(cmpPoints - src, axis=1) + np.linalg.norm(cmpPoints - recPoints, axis=1)
                totalTime = totalTime * self.binning.slowness

                if not self.updateBinOutputsForValidCmpPoints(src, cmpPoints, recPoints, hypArray, aziArray, fullAnalysis, totalTime):
                    continue
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

        except StopIteration:
            self.errorText = 'binning from geometry cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcOffsetGapValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None

        return True

    def binFromGeometry9(self, fullAnalysis) -> bool:
        """
        Optimized binning with integer-normalized relation indexing to avoid gaps.
        """
        self.threadProgress = 0
        lookup = self.prepareGeometryRelationBinningLookup()

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        # Pre-extract data for Numba (cannot pass 'self')
        srcLocs = np.column_stack((self.output.srcGeom['LocX'], self.output.srcGeom['LocY'], self.output.srcGeom['Elev'] - self.output.srcGeom['Depth'], self.output.srcGeom['Line'], self.output.srcGeom['Point']))  # noqa: E501 # pylint: disable=C0301
        relFileIndices = np.column_stack((lookup.relLeft, lookup.relRight))
        recLocs = np.column_stack((self.output.recGeom['LocX'], self.output.recGeom['LocY'], self.output.recGeom['Elev'] - self.output.recGeom['Depth']))

        # Extract Transform Matrix as raw array
        T = self.binTransform
        binMat = np.array([[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()], [0, 0, 1]], dtype=np.float32)
        S = self.st2Transform
        st2Mat = np.array([[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()], [0, 0, 1]], dtype=np.float32)

        # PRE-CALCULATE RECEIVER LINE BOUNDARIES
        # Create unique keys for (Index, Line) combinations
        recKeys = self.output.recGeom['Index'].astype(np.int64) * 1000000 + np.rint(self.output.recGeom['Line']).astype(np.int64)
        relKeys = lookup.relRecIndI.astype(np.int64) * 1000000 + lookup.relRecLinI.astype(np.int64)

        # Find start and end of every line in the receiver array
        relRecStartI = np.searchsorted(recKeys, relKeys, side='left').astype(np.int32)
        relRecEndI = np.searchsorted(recKeys, relKeys, side='right').astype(np.int32)

        maxFold = self.grid.fold if self.grid.fold > 0 else 1000

        try:
            batchSize = 500  # Larger batch size for better throughput
            for i in range(0, self.nShotPoints, batchSize):
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                end = min(i + batchSize, self.nShotPoints)

                # Call the Parallel Kernel for this batch
                fnb.numbaBinBatchParallel(
                    srcLocs[i:end],                                             # Pass srcLocs as a slice
                    relFileIndices[i:end],
                    recLocs,
                    self.output.recGeom['InUse'],
                    lookup.recPointI,
                    lookup.relRecMinI,
                    lookup.relRecMaxI,
                    relRecStartI,
                    relRecEndI,
                    self.output.binOutput,
                    self.output.minOffset,
                    self.output.maxOffset,
                    self.output.anaOutput,
                    binMat,
                    st2Mat,
                    fullAnalysis,
                    maxFold
                )

                self.nShotPoint = end
                self.progress.emit(int(100 * end / self.nShotPoints))

        except StopIteration:
            self.errorText = 'binning from geometry cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcOffsetGapValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None

        return True

    def binFromGeometry10(self, fullAnalysis) -> bool:
        """
        Optimized variant of binFromGeometry8 with identical semantics.

        Differences from binFromGeometry8 (purely performance):
          * Receiver selection per source uses contiguous slice access into
            the (Index, Line, Point)-sorted recGeom via a per-relation
            [start, end) lookup, instead of OR-masking the full recGeom on
            every relation. This drops a major hot loop from
            O(N_relations_per_shot * N_recGeom) to roughly
            O(N_relations_per_shot * log N_recGeom + N_selected).
          * The bin-transform application is a 2x3 matrix multiply over the
            full cmpPoints array instead of a Python per-point
            QTransform.map() call.

        Differences from binFromGeometry9 (Gemini draft):
          * Preserves binFromGeometry8 semantics exactly: full CMP / plane
            / sphere binning support, output-rect filtering, rectangular
            offset filtering, radial offset filtering, source InUse gating,
            azimuth + travel-time placeholders in anaOutput.
          * With useNumba enabled in full-analysis mode, the shared write
            helper routes per-trace analysis writes through
            _applyBinUpdatesNumba().
        """
        self.threadProgress = 0
        appSettings = getActiveAppSettings()
        profile = appSettings.debug
        writeRoutine = self._applyBinUpdatesNumba if fullAnalysis and appSettings.useNumba else self._applyBinUpdatesVectorized
        lookup = self.prepareGeometryRelationBinningLookup()
        relRecLineStart, relRecLineEnd = self._buildRelationReceiverSliceLookup(lookup)

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        recCoords = np.column_stack(
            (self.output.recGeom['LocX'], self.output.recGeom['LocY'], self.output.recGeom['Elev'] - self.output.recGeom['Depth'])
        ).astype(np.float32, copy=False)
        recInUse = self.output.recGeom['InUse']

        T = self.binTransform
        binMat = np.array(
            [[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()]], dtype=np.float64
        )
        S = self.st2Transform
        st2Mat = np.array(
            [[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()]], dtype=np.float64
        )

        try:
            for i, srcRecord in enumerate(self.output.srcGeom):
                if srcRecord['InUse'] == 0:
                    continue

                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                src = np.array(
                    [srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev'] - srcRecord['Depth']], dtype=np.float32
                )

                if profile:
                    timer = perf_counter()
                recPoints = self._gatherReceiversForSource(
                    i, lookup, relRecLineStart, relRecLineEnd, recCoords, recInUse
                )
                if profile:
                    self.elapsedTime(timer, 0)
                if recPoints is None:
                    continue

                if profile:
                    timer = perf_counter()
                traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
                if profile:
                    self.elapsedTime(timer, 1)
                if traceArrays is None:
                    continue
                cmpPoints, recPoints, hypArray, aziArray = traceArrays

                if profile:
                    timer = perf_counter()
                if self.binning.method == BinningType.cmp:
                    totalTime = np.linalg.norm(recPoints - src, axis=1)
                else:
                    totalTime = np.linalg.norm(cmpPoints - src, axis=1) + np.linalg.norm(cmpPoints - recPoints, axis=1)
                totalTime = totalTime * self.binning.slowness
                if profile:
                    self.elapsedTime(timer, 2)

                if profile:
                    timer = perf_counter()
                writeRoutine(src, cmpPoints, recPoints, hypArray, aziArray, binMat, st2Mat, fullAnalysis, totalTime)
                if profile:
                    self.elapsedTime(timer, 3)

        except StopIteration:
            self.errorText = 'binning from geometry cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcOffsetGapValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None

        return True

    def _buildRelationReceiverSliceLookup(self, lookup):
        """
        Compute, for every relation record, the contiguous half-open slice
        [start, end) into the (Index, Line, Point)-sorted recGeom that holds
        every receiver on the same (RecInd, RecLin) line as the relation.
        This avoids the per-shot boolean OR-scan of the full recGeom done by
        selectReceiversForSourceRelationSlice() in binFromGeometry8().
        """
        # Composite key: Index * BIG + Line. Same construction for both
        # arrays so np.searchsorted is consistent. recGeom is already sorted
        # by (Index, Line, Point) by sortGeometryArrays(), so recKeys is
        # non-decreasing, which is required for searchsorted.
        BIG = np.int64(1_000_000)
        recKeys = lookup.recIndex.astype(np.int64) * BIG + lookup.recLineI.astype(np.int64)
        relKeys = lookup.relRecIndI.astype(np.int64) * BIG + lookup.relRecLinI.astype(np.int64)
        relRecLineStart = np.searchsorted(recKeys, relKeys, side='left').astype(np.int32)
        relRecLineEnd = np.searchsorted(recKeys, relKeys, side='right').astype(np.int32)
        return relRecLineStart, relRecLineEnd

    def _gatherReceiversForSource(self, sourceIndex, lookup, relRecLineStart, relRecLineEnd, recCoords, recInUse):
        """
        Equivalent of selectReceiversForSourceRelationSlice() but uses direct
        slice access driven by per-relation (start, end) bounds instead of
        scanning the entire recGeom array per relation.
        Returns the same (N, 3) np.float32 array of (LocX, LocY, Elev) the
        slow path returns, or None if there are no live receivers for this
        source.
        """
        minRec = lookup.relLeft[sourceIndex]
        maxRec = lookup.relRight[sourceIndex]
        if maxRec <= minRec:
            return None

        # Two-pass collection: first total length so we can allocate once.
        totalLen = 0
        spans = []
        for relIdx in range(minRec, maxRec):
            start = relRecLineStart[relIdx]
            end = relRecLineEnd[relIdx]
            if end <= start:
                continue
            # Receivers within this (Index, Line) slice are sorted by Point,
            # so we can binary-search the [RecMin, RecMax] window.
            rMin = lookup.relRecMinI[relIdx]
            rMax = lookup.relRecMaxI[relIdx]
            sliceI = lookup.recPointI[start:end]
            lo = start + int(np.searchsorted(sliceI, rMin, side='left'))
            hi = start + int(np.searchsorted(sliceI, rMax, side='right'))
            if hi > lo:
                spans.append((lo, hi))
                totalLen += hi - lo

        if totalLen == 0:
            return None

        # Allocate once, copy each contiguous span. This preserves the slow
        # path's filtering semantics exactly (same set of receivers, possibly
        # with duplicates if relations overlap on the same line, which the
        # boolean OR collapses; we collapse here via np.unique on indices).
        idxBuf = np.empty(totalLen, dtype=np.int64)
        offset = 0
        for lo, hi in spans:
            n = hi - lo
            idxBuf[offset:offset + n] = np.arange(lo, hi, dtype=np.int64)
            offset += n

        # Collapse duplicates (matches the boolean OR behavior of the slow
        # path) and apply the InUse > 0 filter.
        idxBuf = np.unique(idxBuf)
        liveMask = recInUse[idxBuf] > 0
        idxBuf = idxBuf[liveMask]
        if idxBuf.shape[0] == 0:
            return None

        return recCoords[idxBuf]

    def _applyBinUpdatesVectorized(self, src, cmpPoints, recPoints, hypArray, aziArray, binMat, st2Mat, writeAnalysis, totalTime=None, profileBaseIndex=None):
        """
        Vectorized counterpart of updateBinOutputsForValidCmpPoints():
        applies the bin and stake transforms with a 2x3 matrix multiply
        instead of a Python per-point QTransform.map() loop. Semantics are
        otherwise identical (same fold cap, same anaOutput layout, same
        np.add.at / np.minimum.at / np.maximum.at scatter writes).

        If ``totalTime`` is provided (1-D array aligned with cmpPoints), it
        is written to anaOutput[..., 12]; otherwise that column is left at
        0.0 to match updateBinOutputsForValidCmpPoints() / binFromGeometry8.
        """
        if profileBaseIndex is not None:
            timer = perf_counter()

        # bin transform: nx, ny = binMat @ (cmpX, cmpY, 1)
        nx = (binMat[0, 0] * cmpPoints[:, 0] + binMat[0, 1] * cmpPoints[:, 1] + binMat[0, 2]).astype(np.int64)
        ny = (binMat[1, 0] * cmpPoints[:, 0] + binMat[1, 1] * cmpPoints[:, 1] + binMat[1, 2]).astype(np.int64)

        valid = (
            (nx >= 0) & (ny >= 0) &                     # noqa: W504
            (nx < self.output.binOutput.shape[0]) &     # noqa: W504
            (ny < self.output.binOutput.shape[1])       # noqa: W504
        )
        if not valid.any():
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex)
            return False

        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex)

        nx = nx[valid]
        ny = ny[valid]
        cmpPoints = cmpPoints[valid]
        recPoints = recPoints[valid]
        hypArray = hypArray[valid]
        aziArray = aziArray[valid]
        if totalTime is not None:
            totalTime = totalTime[valid]

        if writeAnalysis:
            if profileBaseIndex is not None:
                timer = perf_counter()
            # Compute fold *before* the scatter increment, just like
            # updateBinOutputsForValidCmpPoints() does (it reads
            # binOutput[x, y] - 1 *after* the scatter, which is equivalent).
            stkX = (st2Mat[0, 0] * cmpPoints[:, 0] + st2Mat[0, 1] * cmpPoints[:, 1] + st2Mat[0, 2]).astype(np.int32)
            stkY = (st2Mat[1, 0] * cmpPoints[:, 0] + st2Mat[1, 1] * cmpPoints[:, 1] + st2Mat[1, 2]).astype(np.int32)

            maxFold = self.grid.fold
            for k in range(nx.shape[0]):
                x = int(nx[k])
                y = int(ny[k])
                fold = int(self.output.binOutput[x, y])
                if fold < maxFold:
                    self.output.anaOutput[x, y, fold, 0] = stkX[k]
                    self.output.anaOutput[x, y, fold, 1] = stkY[k]
                    self.output.anaOutput[x, y, fold, 2] = fold + 1
                    self.output.anaOutput[x, y, fold, 3] = src[0]
                    self.output.anaOutput[x, y, fold, 4] = src[1]
                    self.output.anaOutput[x, y, fold, 5] = src[2]
                    self.output.anaOutput[x, y, fold, 6] = recPoints[k, 0]
                    self.output.anaOutput[x, y, fold, 7] = recPoints[k, 1]
                    self.output.anaOutput[x, y, fold, 8] = recPoints[k, 2]
                    self.output.anaOutput[x, y, fold, 9] = cmpPoints[k, 0]
                    self.output.anaOutput[x, y, fold, 10] = cmpPoints[k, 1]
                    self.output.anaOutput[x, y, fold, 11] = cmpPoints[k, 2]
                    self.output.anaOutput[x, y, fold, 12] = totalTime[k] if totalTime is not None else 0.0
                    self.output.anaOutput[x, y, fold, 13] = hypArray[k]
                    self.output.anaOutput[x, y, fold, 14] = aziArray[k]
                # increment after analysis read so the next trace lands in
                # the next fold slot, matching the slow path's behavior.
                self.output.binOutput[x, y] += 1
                if hypArray[k] < self.output.minOffset[x, y]:
                    self.output.minOffset[x, y] = hypArray[k]
                if hypArray[k] > self.output.maxOffset[x, y]:
                    self.output.maxOffset[x, y] = hypArray[k]
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex + 1)
            return True

        # Fast path: no analysis writes, just scatter-update the three
        # fold/offset arrays in one vectorized pass.
        if profileBaseIndex is not None:
            timer = perf_counter()
        np.add.at(self.output.binOutput, (nx, ny), 1)
        np.minimum.at(self.output.minOffset, (nx, ny), hypArray)
        np.maximum.at(self.output.maxOffset, (nx, ny), hypArray)
        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex + 2)
        return True

    def _applyBinUpdatesNumba(self, src, cmpPoints, recPoints, hypArray, aziArray, binMat, st2Mat, writeAnalysis, totalTime=None):
        """
        Numba-accelerated counterpart of ``_applyBinUpdatesVectorized``.

        Same inputs, same outputs. The only difference is the writeAnalysis
        branch: instead of running a Python ``for k in range(N):`` loop with
        per-element scalar writes into ``self.output.anaOutput``, this
        helper dispatches the per-trace work to the compiled kernel
        ``numbaApplyBinUpdatesAnalysis`` (aux_functions_numba.py). Filtering,
        bin/stake transforms, fold cap, and per-bin min/max offset
        semantics are preserved bit-for-bit.

        The fast (no-analysis) branch is identical to
        ``_applyBinUpdatesVectorized``: ``np.add.at`` /
        ``np.minimum.at`` / ``np.maximum.at`` already run at C speed there
        and there is no per-trace fold ordering to preserve, so wrapping it
        in numba would not help.
        """
        # bin transform: nx, ny = binMat @ (cmpX, cmpY, 1)
        nx = (binMat[0, 0] * cmpPoints[:, 0] + binMat[0, 1] * cmpPoints[:, 1] + binMat[0, 2]).astype(np.int64)
        ny = (binMat[1, 0] * cmpPoints[:, 0] + binMat[1, 1] * cmpPoints[:, 1] + binMat[1, 2]).astype(np.int64)

        valid = (
            (nx >= 0) & (ny >= 0) &                     # noqa: W504
            (nx < self.output.binOutput.shape[0]) &     # noqa: W504
            (ny < self.output.binOutput.shape[1])       # noqa: W504
        )
        if not valid.any():
            return False

        nx = nx[valid]
        ny = ny[valid]
        cmpPoints = cmpPoints[valid]
        recPoints = recPoints[valid]
        hypArray = hypArray[valid]
        aziArray = aziArray[valid]
        if totalTime is not None:
            totalTime = totalTime[valid]

        if writeAnalysis:
            # --- Bin-sort pre-pass (memmap-friendly) ------------------------
            # anaOutput is a (NX, NY, MAXFOLD, 16) float32 memmap. Each per-
            # trace store touches a different (x, y, fold, *) page. Without
            # sorting, traces arrive in template/seed order which is
            # essentially random across (x, y) -> random page faults +
            # dirty pages scattered across the file.
            #
            # Sorting traces by a flat (nx, ny) key before the kernel runs
            # converts that random scatter into monotonically-increasing
            # page accesses, so the OS page cache can reuse hot pages and
            # writes drain to disk near-sequentially. argsort(kind='stable')
            # also preserves the original arrival order among traces that
            # share a bin, so fold-slot assignment within a bin is
            # deterministic and unchanged in aggregate (downstream
            # consumers -- RMS, gap, unique-fold, distribution -- are all
            # order-independent over the [0:fold] slice anyway).
            #
            # Cost: O(N log N) on a small in-memory trace batch (typically
            # a few thousand entries per call); savings: many random 4 KB
            # page faults per call avoided on the much larger memmap.
            binY = self.output.binOutput.shape[1]
            order = np.argsort(nx * np.int64(binY) + ny, kind='stable')
            nx = nx[order]
            ny = ny[order]
            cmpPoints = cmpPoints[order]
            recPoints = recPoints[order]
            hypArray = hypArray[order]
            aziArray = aziArray[order]
            if totalTime is not None:
                totalTime = totalTime[order]

            stkX = (st2Mat[0, 0] * cmpPoints[:, 0] + st2Mat[0, 1] * cmpPoints[:, 1] + st2Mat[0, 2]).astype(np.int32)
            stkY = (st2Mat[1, 0] * cmpPoints[:, 0] + st2Mat[1, 1] * cmpPoints[:, 1] + st2Mat[1, 2]).astype(np.int32)

            # Numba kernel does not handle Optional[None]; pass a zeros
            # array of the same length when totalTime was not computed.
            if totalTime is None:
                totalTimeArr = np.zeros(nx.shape[0], dtype=np.float32)
            else:
                totalTimeArr = np.asarray(totalTime, dtype=np.float32)

            # Inputs come from boolean-mask / fancy-index reductions inside
            # buildBinningArraysFromSelectedReceivers and the order-reindex
            # above, which always produce C-contiguous float32 arrays. The
            # previous code used np.ascontiguousarray which always
            # allocates a new buffer + memcpy, even when not needed; we
            # use np.asarray instead which is a no-op when dtype already
            # matches and the array is already an ndarray.
            cmpC = np.asarray(cmpPoints, dtype=np.float32)
            recC = np.asarray(recPoints, dtype=np.float32)
            hypC = np.asarray(hypArray, dtype=np.float32)
            aziC = np.asarray(aziArray, dtype=np.float32)
            srcC = np.asarray(src, dtype=np.float32)

            fnb.numbaApplyBinUpdatesAnalysis(
                nx, ny,
                stkX, stkY,
                cmpC, recC,
                hypC, aziC,
                totalTimeArr,
                srcC,
                self.output.binOutput,
                self.output.minOffset,
                self.output.maxOffset,
                self.output.anaOutput,
                int(self.grid.fold),
            )
            return True

        # Fast path: identical to _applyBinUpdatesVectorized's fast path.
        np.add.at(self.output.binOutput, (nx, ny), 1)
        np.minimum.at(self.output.minOffset, (nx, ny), hypArray)
        np.maximum.at(self.output.maxOffset, (nx, ny), hypArray)
        return True

    def setupBinFromTemplates(self, fullAnalysis) -> bool:
        """this routine is used for working from templates only"""

        self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        if fullAnalysis:
            success = self.binFromTemplates(True)
            if isinstance(self.output.anaOutput, np.memmap):
                np.memmap.flush(self.output.anaOutput)                          # flush results to hard disk when using memmap
            return success
        return self.binFromTemplates(False)

    # can't use @jit here, as numba does not support handling exceptions (try -> except)
    # See: http://numba.pydata.org/numba-doc/dev/reference/pysupported.html
    # See: https://stackoverflow.com/questions/18176602/how-to-get-the-name-of-an-exception-that-was-caught-in-python for workaround
    def binFromTemplates(self, fullAnalysis) -> bool:
        appSettings = getActiveAppSettings()
        templateBinningRoutine = self.binTemplate10 if appSettings.useExperimental else self.binTemplate8

        # Announce which routine is actually being dispatched so we can
        # confirm at runtime that the useExperimental flag flowed through.
        self.logMessage.emit(
            f'Method : useExperimental={appSettings.useExperimental} -> {templateBinningRoutine.__name__}, fullAnalysis={fullAnalysis}'
        )

        try:
            self.calcPointArrays()                                              # first set up all point arrays
            for block in self.blockList:                                        # get all blocks
                for template in block.templateList:                             # get all templates
                    for templateOffset in self.iterTemplateRollOffsets(template):
                        templateBinningRoutine(block, template, templateOffset, fullAnalysis)

        except StopIteration:
            self.errorText = 'binning from templates cancelled by user'
            return False
        except BaseException as e:
            self._recordInnermostExceptionLocation(e)
            return False

        self.finalizeLiveBinningOutputs(fullAnalysis)
        return True

    def binTemplate7(self, block, template, templateOffset, fullAnalysis):
        """
        Vectorized template binning (faster).
        Keeps binTemplate6 intact.
        """
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)
        profile = getActiveAppSettings().debug

        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue

            if profile:
                timer = perf_counter()
            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)

            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    if profile:
                        self.elapsedTime(timer, 0)
                    continue
                srcArray = srcArray[included, :]
            if profile:
                self.elapsedTime(timer, 0)

            for src in srcArray:
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                for recSeed in template.seedList:
                    if recSeed.bSource:
                        continue

                    if profile:
                        timer = perf_counter()
                    recPoints = recSeed.pointArray + self._seedTemplateOffset(recSeed, npTemplateOffset)

                    if not block.borders.recBorder.isNull():
                        included = fnb.pointsInRect(recPoints, block.borders.recBorder)
                        if included.shape[0] == 0:
                            if profile:
                                self.elapsedTime(timer, 1)
                            continue
                        recPoints = recPoints[included, :]
                    if profile:
                        self.elapsedTime(timer, 1)

                    if recPoints.shape[0] == 0:
                        continue

                    if profile:
                        timer = perf_counter()
                    traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
                    if profile:
                        self.elapsedTime(timer, 2)
                    if traceArrays is None:
                        continue
                    cmpPoints, recPoints, hypArray, aziArray = traceArrays

                    # Compute travel time so anaOutput[..., 9] gets populated
                    # for the template path too (Option A).
                    if profile:
                        timer = perf_counter()
                    if self.binning.method == BinningType.cmp:
                        totalTime = np.linalg.norm(recPoints - src, axis=1)
                    else:
                        totalTime = np.linalg.norm(cmpPoints - src, axis=1) + np.linalg.norm(cmpPoints - recPoints, axis=1)
                    totalTime = totalTime * self.binning.slowness
                    if profile:
                        self.elapsedTime(timer, 3)

                    if not self.updateBinOutputsForValidCmpPoints(
                        src,
                        cmpPoints,
                        recPoints,
                        hypArray,
                        aziArray,
                        fullAnalysis,
                        totalTime,
                        profileBaseIndex=4 if profile else None,
                    ):
                        continue

    def binTemplate8(self, block, template, templateOffset, fullAnalysis):
        """
        Optimized variant of binTemplate7 with identical semantics.

        Differences from binTemplate7 (purely performance):
          * Receiver seed arrays are pre-translated by templateOffset and
            border-clipped *once* per template call, hoisted out of the
            per-source inner loop. binTemplate7 redoes this work
            nSources x nRecSeeds times despite neither operation depending
            on the source.
          * The bin / stake transform application uses the same vectorized
            2x3 matmul scatter helper (_applyBinUpdatesVectorized) that
            binFromGeometry10 uses, replacing the Python per-point
            QTransform.map() loop in updateBinOutputsForValidCmpPoints.
          * binTransform and st2Transform are extracted to numpy 2x3
            matrices once per call instead of being read off self via
            attribute lookup on every point.

        All filtering (src border, rec border, output rect, rectangular
        offset rect, radial offset filter, fold cap, anaOutput layout) is
        preserved exactly; only the order in which clipping is applied
        changes (recBorder is now applied before the src loop, which is
        equivalent because recBorder does not depend on src).
        """
        npTemplateOffset = np.array(
            [templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32
        )
        profile = getActiveAppSettings().debug

        # --- 1. Hoist receiver-seed preparation out of the source loop. ---
        # For each non-source seed we apply the template offset and the
        # block's recBorder (if any) exactly once.
        recBorderActive = not block.borders.recBorder.isNull()
        preparedRecArrays = []
        if profile:
            timer = perf_counter()
        for recSeed in template.seedList:
            if recSeed.bSource:
                continue
            recPoints = recSeed.pointArray + self._seedTemplateOffset(recSeed, npTemplateOffset)
            if recBorderActive:
                included = fnb.pointsInRect(recPoints, block.borders.recBorder)
                if included.shape[0] == 0:
                    continue
                recPoints = recPoints[included, :]
            if recPoints.shape[0] == 0:
                continue
            preparedRecArrays.append(recPoints)
        if profile:
            self.elapsedTime(timer, 1)

        if not preparedRecArrays:
            # No live receivers in this template; still need to advance the
            # shot counter for progress reporting, matching binTemplate7's
            # behavior (which also increments nShotPoint per source even
            # when no traces survive).
            for srcSeed in template.seedList:
                if not srcSeed.bSource:
                    continue
                srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)
                if not block.borders.srcBorder.isNull():
                    included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                    if included.shape[0] == 0:
                        continue
                    srcArray = srcArray[included, :]
                for _ in srcArray:
                    if QThread.currentThread().isInterruptionRequested():
                        raise StopIteration
                    self.nShotPoint += 1
                    threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                    if threadProgress > self.threadProgress:
                        self.threadProgress = threadProgress
                        self.progress.emit(threadProgress + 1)
            return

        # --- 2. Pre-extract bin and stake transforms once per call. ---
        T = self.binTransform
        binMat = np.array(
            [[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()]], dtype=np.float64
        )
        S = self.st2Transform
        st2Mat = np.array(
            [[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()]], dtype=np.float64
        )

        # --- 3. Source loop, now with pre-clipped receiver arrays. ---
        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue

            if profile:
                timer = perf_counter()
            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)

            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    if profile:
                        self.elapsedTime(timer, 0)
                    continue
                srcArray = srcArray[included, :]
            if profile:
                self.elapsedTime(timer, 0)

            for src in srcArray:
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                for recPoints in preparedRecArrays:
                    if profile:
                        timer = perf_counter()
                    traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
                    if profile:
                        self.elapsedTime(timer, 2)
                    if traceArrays is None:
                        continue
                    cmpPoints, filteredRec, hypArray, aziArray = traceArrays

                    # Travel time so anaOutput[..., 12] (TWT [ms]) is populated
                    # for cmp / plane / sphere binning alike.
                    if profile:
                        timer = perf_counter()
                    if self.binning.method == BinningType.cmp:
                        totalTime = np.linalg.norm(filteredRec - src, axis=1)
                    else:
                        totalTime = np.linalg.norm(cmpPoints - src, axis=1) + np.linalg.norm(cmpPoints - filteredRec, axis=1)
                    totalTime = totalTime * self.binning.slowness
                    if profile:
                        self.elapsedTime(timer, 3)

                    self._applyBinUpdatesVectorized(
                        src,
                        cmpPoints,
                        filteredRec,
                        hypArray,
                        aziArray,
                        binMat,
                        st2Mat,
                        fullAnalysis,
                        totalTime,
                        profileBaseIndex=4 if profile else None,
                    )

    def binTemplate9(self, block, template, templateOffset, fullAnalysis):
        """
        Optimized variant of binTemplate8 with identical semantics, using
        the numba-compiled bin-update kernel for the writeAnalysis hot path.

        Differences from binTemplate8 (purely performance):
          * The per-trace anaOutput-write loop in the writeAnalysis branch
            of _applyBinUpdatesVectorized was a Python ``for k in range(N):``
            loop with 15 scalar element-stores per iteration into
            ``self.output.anaOutput`` (typically a memmap-backed float32
            array). binTemplate9 routes the same call through
            _applyBinUpdatesNumba(), which dispatches that loop body to
            ``fnb.numbaApplyBinUpdatesAnalysis`` -- a compiled kernel that
            performs identical fold-cap + min/max offset updates in C
            speed. The non-analysis fast path is unchanged because it
            already runs at C speed via np.add.at / np.minimum.at /
            np.maximum.at.

        Filtering, transforms, fold cap, and anaOutput layout are
        preserved exactly. binTemplate8 is left in place for A/B testing.
        """
        npTemplateOffset = np.array(
            [templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32
        )

        # --- 1. Hoist receiver-seed preparation out of the source loop. ---
        recBorderActive = not block.borders.recBorder.isNull()
        preparedRecArrays = []
        for recSeed in template.seedList:
            if recSeed.bSource:
                continue
            recPoints = recSeed.pointArray + self._seedTemplateOffset(recSeed, npTemplateOffset)
            if recBorderActive:
                included = fnb.pointsInRect(recPoints, block.borders.recBorder)
                if included.shape[0] == 0:
                    continue
                recPoints = recPoints[included, :]
            if recPoints.shape[0] == 0:
                continue
            preparedRecArrays.append(recPoints)

        if not preparedRecArrays:
            # No live receivers in this template; still advance the shot
            # counter for progress reporting (matches binTemplate7 / 8).
            for srcSeed in template.seedList:
                if not srcSeed.bSource:
                    continue
                srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)
                if not block.borders.srcBorder.isNull():
                    included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                    if included.shape[0] == 0:
                        continue
                    srcArray = srcArray[included, :]
                for _ in srcArray:
                    if QThread.currentThread().isInterruptionRequested():
                        raise StopIteration
                    self.nShotPoint += 1
                    threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                    if threadProgress > self.threadProgress:
                        self.threadProgress = threadProgress
                        self.progress.emit(threadProgress + 1)
            return

        # --- 2. Pre-extract bin and stake transforms once per call. ---
        T = self.binTransform
        binMat = np.array(
            [[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()]], dtype=np.float64
        )
        S = self.st2Transform
        st2Mat = np.array(
            [[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()]], dtype=np.float64
        )

        # --- 3. Source loop, with pre-clipped receiver arrays. ---
        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue

            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)

            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    continue
                srcArray = srcArray[included, :]

            for src in srcArray:
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

                for recPoints in preparedRecArrays:
                    traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
                    if traceArrays is None:
                        continue
                    cmpPoints, filteredRec, hypArray, aziArray = traceArrays

                    if self.binning.method == BinningType.cmp:
                        totalTime = np.linalg.norm(filteredRec - src, axis=1)
                    else:
                        totalTime = np.linalg.norm(cmpPoints - src, axis=1) + np.linalg.norm(cmpPoints - filteredRec, axis=1)
                    totalTime = totalTime * self.binning.slowness

                    self._applyBinUpdatesNumba(
                        src, cmpPoints, filteredRec, hypArray, aziArray, binMat, st2Mat, fullAnalysis, totalTime
                    )

    def binTemplate10(self, block, template, templateOffset, fullAnalysis):
        """
        Whole-template trace-batched binning, see comment block above
        _iterTemplateSourceChunks. Same semantics as binTemplate7/8/9
        (cmp / plane / sphere, rctOutput, rctOffsets, radOffsets, fold cap,
        anaOutput layout) but the entire (Ns*Nr) trace bundle of a template
        is dispatched in one (or a few chunked) numba kernel calls.
        """
        # ------------------------------------------------------------------
        # binTemplate10: whole-template trace batching.
        #
        # binTemplate7/8/9 all walk one source at a time and call
        # buildBinningArraysFromSelectedReceivers() per source. A template by
        # definition shares its receiver set across every source, so the full
        # (Ns x Nr) trace bundle can be built and binned in one (or a few
        # chunked) NumPy/Numba batches. binTemplate10 does exactly that:
        #
        #   * Per template, the source array (border-clipped, all source seeds
        #     concatenated) and the prepared receiver array (border-clipped,
        #     all rec seeds concatenated) are flattened once into paired
        #     (Ns*Nr, 3) src / rec arrays.
        #   * cmp / plane / sphere math, rctOutput / rctOffsets / radOffsets
        #     filters, hypot/atan2, bin-transform, in-bounds mask, stake
        #     transform, bin-key sort and the analysis kernel all run once
        #     per chunk on the whole batch.
        #   * The numba dispatch + per-source argsort overhead binTemplate9
        #     pays Ns x N_recSeed times per template is paid once per chunk.
        #
        # binTemplate7/8/9, _applyBinUpdatesVectorized, _applyBinUpdatesNumba,
        # buildBinningArraysFromSelectedReceivers, the existing
        # numbaApplyBinUpdatesAnalysis kernel, and roll_plane / roll_sphere are
        # all left untouched -- binTemplate10 is purely additive.
        # ------------------------------------------------------------------
        npTemplateOffset = np.array(
            [templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32
        )
        profile = getActiveAppSettings().debug

        # --- 1. Hoist receiver-seed prep out of the source loop. -----
        recBorderActive = not block.borders.recBorder.isNull()
        preparedRecArrays = []
        if profile:
            timer = perf_counter()
        for recSeed in template.seedList:
            if recSeed.bSource:
                continue
            recPoints = recSeed.pointArray + self._seedTemplateOffset(recSeed, npTemplateOffset)
            if recBorderActive:
                included = fnb.pointsInRect(recPoints, block.borders.recBorder)
                if included.shape[0] == 0:
                    continue
                recPoints = recPoints[included, :]
            if recPoints.shape[0] == 0:
                continue
            preparedRecArrays.append(recPoints)
        if profile:
            self.elapsedTime(timer, 1)

        # Also pre-clip the source seeds; we still need to advance the
        # progress counter even when no live receivers exist.
        preparedSrcArrays = []
        for srcSeed in template.seedList:
            if not srcSeed.bSource:
                continue
            if profile:
                timer = perf_counter()
            srcArray = srcSeed.pointArray + self._seedTemplateOffset(srcSeed, npTemplateOffset)
            if not block.borders.srcBorder.isNull():
                included = fnb.pointsInRect(srcArray, block.borders.srcBorder)
                if included.shape[0] == 0:
                    if profile:
                        self.elapsedTime(timer, 0)
                    continue
                srcArray = srcArray[included, :]
            if srcArray.shape[0] == 0:
                if profile:
                    self.elapsedTime(timer, 0)
                continue
            preparedSrcArrays.append(srcArray.astype(np.float32, copy=False))
            if profile:
                self.elapsedTime(timer, 0)

        if not preparedSrcArrays:
            return  # no live sources, no progress to report either

        if not preparedRecArrays:
            # No live receivers; advance shot counter for UI parity with
            # binTemplate7/8/9, then bail.
            for srcArray in preparedSrcArrays:
                for _ in range(srcArray.shape[0]):
                    if QThread.currentThread().isInterruptionRequested():
                        raise StopIteration
                    self.nShotPoint += 1
                    threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                    if threadProgress > self.threadProgress:
                        self.threadProgress = threadProgress
                        self.progress.emit(threadProgress + 1)
            return

        # Concatenate all rec seeds once -- the template shares this set
        # across every source.
        recArrAll = np.concatenate(preparedRecArrays, axis=0).astype(np.float32, copy=False)
        nRec = recArrAll.shape[0]

        # --- 2. Pre-extract bin / stake transforms once per call. ---
        T = self.binTransform
        binMat = np.array(
            [[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()]], dtype=np.float64
        )
        S = self.st2Transform
        st2Mat = np.array(
            [[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()]], dtype=np.float64
        )

        # --- 3. Per source-seed: chunk over Ns and dispatch one kernel call per chunk. ---
        for srcArray in preparedSrcArrays:
            for srcChunk in self._iterTemplateSourceChunks(srcArray, nRec):
                if QThread.currentThread().isInterruptionRequested():
                    raise StopIteration

                if profile:
                    timer = perf_counter()
                batch = self._buildTemplateTraceBatch(srcChunk, recArrAll)
                if profile:
                    self.elapsedTime(timer, 2)
                if batch is not None:
                    cmpPoints, srcExp, recExp, hypArray, aziArray = batch
                    self._applyBinUpdatesNumbaBatch(
                        cmpPoints,
                        srcExp,
                        recExp,
                        hypArray,
                        aziArray,
                        binMat,
                        st2Mat,
                        fullAnalysis,
                        profileBaseIndex=4 if profile else None,
                    )

                # Advance progress per source in the chunk for UI parity.
                self.nShotPoint += srcChunk.shape[0]
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)

    def _iterTemplateSourceChunks(self, srcArr, nRec):
        """
        Yield contiguous slices of srcArr such that one chunk's flat
        (Ns_chunk * Nr) intermediate float32 working set stays under
        config.TEMPLATE_BATCH_BUDGET_BYTES. With strided (iSrc, iRec)
        indices the persistent per-trace footprint is small (8 b for
        indices + 12 b cmp + 12 b off ~= 32 b/trace), but the plane/
        sphere math briefly allocates srcExp + recExp + ray/etc. pushing
        peak to ~80 b/trace. We budget 80 b/trace as the safe ceiling.
        """
        ns = srcArr.shape[0]
        if ns == 0 or nRec == 0:
            return
        bytesPerTrace = 80
        budget = max(int(config.TEMPLATE_BATCH_BUDGET_BYTES), bytesPerTrace * nRec)
        chunkNs = max(1, budget // (bytesPerTrace * nRec))
        for i in range(0, ns, chunkNs):
            yield srcArr[i:i + chunkNs]

    def _buildTemplateTraceBatch(self, srcArr, recArr):
        """
        Build a flat (M, ...) trace batch for a (Ns x Nr) template chunk.

        Inputs:
          srcArr (Ns, 3) float32 -- one chunk of pre-clipped source points.
          recArr (Nr, 3) float32 -- pre-clipped receivers shared by all
                                    sources of the template.

        Returns (cmp, srcExp, recExp, hyp, azi) all aligned float32 arrays
        of shape (M, 3) / (M, 3) / (M, 3) / (M,) / (M,) where M <= Ns*Nr,
        or None if every trace was filtered out.

        Mirrors the filter chain of buildBinningArraysFromSelectedReceivers
        exactly: cmp/plane/sphere math, rctOutput, rctOffsets, radOffsets.

        Memory strategy: instead of expanding srcExp/recExp up-front via
        np.repeat / np.tile (24 b/trace), we keep cheap (i_src, i_rec)
        index arrays (8 b/trace) through every filter pass and gather the
        final srcExp/recExp only once after all masks have been applied.
        For cmp/plane/sphere math we still gather srcExp/recExp briefly,
        but explicitly drop them right after the per-method mask is built.
        """
        ns = srcArr.shape[0]
        nr = recArr.shape[0]
        if ns == 0 or nr == 0:
            return None

        srcArr = srcArr.astype(np.float32, copy=False)
        recArr = recArr.astype(np.float32, copy=False)

        # Strided indices: row k <-> (srcArr[iSrc[k]], recArr[iRec[k]]).
        iSrc = np.repeat(np.arange(ns, dtype=np.int32), nr)
        iRec = np.tile(np.arange(nr, dtype=np.int32), ns)

        method = self.binning.method
        if method == BinningType.cmp:
            cmpPoints = 0.5 * (srcArr[iSrc] + recArr[iRec])
        elif method == BinningType.plane:
            plane = self.localPlane
            npNormal = np.array(
                [plane.normal.x(), plane.normal.y(), plane.normal.z()], dtype=np.float32
            )
            dist = np.float32(plane.dist)
            aoiMin = math.radians(self.angles.reflection.x())
            aoiMax = math.radians(self.angles.reflection.y())

            srcExp = srcArr[iSrc]
            recExp = recArr[iRec]

            # Per-row mirror of src in the plane: srcMirror = src - 2 * (src . n + d) * n
            sDist2 = (srcExp @ npNormal + dist) * np.float32(2.0)             # (M,)
            srcMirror = srcExp - sDist2[:, None] * npNormal                   # (M, 3)

            ray = recExp - srcMirror                                          # (M, 3)
            denom = ray @ npNormal                                            # (M,)
            mask = denom != 0.0
            if not mask.any():
                return None

            nominator = recExp @ npNormal + dist                              # (M,)
            U = np.empty_like(denom)
            U[mask] = nominator[mask] / denom[mask]
            mask &= (U >= 0.0) & (U <= 1.0)
            if not mask.any():
                return None

            length = np.linalg.norm(ray, axis=1)
            cosAoI = np.zeros_like(denom)
            valid_len = mask & (length > 0.0)
            cosAoI[valid_len] = denom[valid_len] / length[valid_len]
            # arccos undefined outside [-1, 1]; clamp to keep downstream sane.
            np.clip(cosAoI, -1.0, 1.0, out=cosAoI)
            aoi = np.arccos(cosAoI)
            mask &= (aoi >= aoiMin) & (aoi <= aoiMax)
            if not mask.any():
                return None

            cmpPoints = (recExp - ray * U[:, None])[mask]
            iSrc = iSrc[mask]
            iRec = iRec[mask]
            # Drop large per-trace temporaries before the filter chain.
            del srcExp, recExp, ray, denom, U, length, cosAoI, aoi, mask
            del srcMirror, sDist2, nominator, valid_len
        elif method == BinningType.sphere:
            sphere = self.localSphere
            npOrig = np.array(
                [sphere.origin.x(), sphere.origin.y(), sphere.origin.z()], dtype=np.float32
            )
            radius = np.float32(sphere.radius)
            aoiMin = math.radians(self.angles.reflection.x())
            aoiMax = math.radians(self.angles.reflection.y())

            srcExp = srcArr[iSrc]
            recExp = recArr[iRec]

            raySrc = srcExp - npOrig                                          # (M, 3)
            rayRec = recExp - npOrig
            lenSrc = np.linalg.norm(raySrc, axis=1)
            lenRec = np.linalg.norm(rayRec, axis=1)
            valid = (lenSrc > 0.0) & (lenRec > 0.0)
            if not valid.any():
                return None
            # Avoid divide-by-zero; rows with zero length are masked out below.
            lenSrc = np.where(valid, lenSrc, np.float32(1.0))
            lenRec = np.where(valid, lenRec, np.float32(1.0))
            raySrc = raySrc / lenSrc[:, None]
            rayRec = rayRec / lenRec[:, None]

            rayMid = 0.5 * (raySrc + rayRec)
            ptRef = npOrig + rayMid * radius                                  # (M, 3)

            raySrc2 = srcExp - ptRef
            len2 = np.linalg.norm(raySrc2, axis=1)
            valid &= len2 > 0.0
            if not valid.any():
                return None
            len2 = np.where(valid, len2, np.float32(1.0))
            raySrc2 = raySrc2 / len2[:, None]

            cosAoI = np.sum(raySrc2 * rayMid, axis=1)
            np.clip(cosAoI, -1.0, 1.0, out=cosAoI)
            aoi = np.arccos(cosAoI)
            mask = valid & (aoi >= aoiMin) & (aoi <= aoiMax)
            if not mask.any():
                return None

            cmpPoints = ptRef[mask]
            iSrc = iSrc[mask]
            iRec = iRec[mask]
            del srcExp, recExp, raySrc, rayRec, rayMid, ptRef, raySrc2
            del lenSrc, lenRec, len2, cosAoI, aoi, valid, mask
        else:
            return None

        # Build offArray fresh from filtered indices (single 12 b/trace gather).
        offArray = recArr[iRec] - srcArr[iSrc]

        # rctOutput on cmp
        included = fnb.pointsInRect(cmpPoints, self.output.rctOutput)
        if not np.any(included):
            return None
        cmpPoints = cmpPoints[included]
        iSrc = iSrc[included]
        iRec = iRec[included]
        offArray = offArray[included]

        # rctOffsets on (dx, dy)
        included = fnb.pointsInRect(offArray, self.offset.rctOffsets)
        if not np.any(included):
            return None
        cmpPoints = cmpPoints[included]
        iSrc = iSrc[included]
        iRec = iRec[included]
        offArray = offArray[included]

        hypArray = np.hypot(offArray[:, 0], offArray[:, 1]).astype(np.float32, copy=False)
        aziArray = np.rad2deg(np.arctan2(offArray[:, 0], offArray[:, 1]))
        aziArray = ((aziArray + 360.0) % 360.0).astype(np.float32, copy=False)

        r1 = self.offset.radOffsets.x()
        r2 = self.offset.radOffsets.y()
        if r2 > 0:
            included = (hypArray >= r1) & (hypArray <= r2)
            if not np.any(included):
                return None
            cmpPoints = cmpPoints[included]
            iSrc = iSrc[included]
            iRec = iRec[included]
            hypArray = hypArray[included]
            aziArray = aziArray[included]

        # Final materialisation: gather srcExp / recExp exactly once, after
        # every filter has reduced M to its post-mask size.
        cmpPoints = np.ascontiguousarray(cmpPoints, dtype=np.float32)
        srcExp = np.ascontiguousarray(srcArr[iSrc], dtype=np.float32)
        recExp = np.ascontiguousarray(recArr[iRec], dtype=np.float32)
        return cmpPoints, srcExp, recExp, hypArray, aziArray

    def _applyBinUpdatesNumbaBatch(self, cmpPoints, srcExp, recPoints, hypArray, aziArray, binMat, st2Mat, writeAnalysis, profileBaseIndex=None):
        """
        Whole-chunk variant of _applyBinUpdatesNumba: each trace carries its
        own src row in `srcExp` (M, 3), so the kernel call dispatches the
        full (Ns*Nr) batch at once via numbaApplyBinUpdatesAnalysisBatch.
        Travel time is computed per-trace inside this helper from the same
        cmp/src/rec arrays the kernel writes to anaOutput.
        """
        if cmpPoints.shape[0] == 0:
            return False

        if profileBaseIndex is not None:
            timer = perf_counter()
        # Travel time: cmp uses ||src - rec||, plane/sphere uses ||src->cmp|| + ||cmp->rec||.
        if self.binning.method == BinningType.cmp:
            totalTime = np.linalg.norm(recPoints - srcExp, axis=1)
        else:
            totalTime = (
                np.linalg.norm(cmpPoints - srcExp, axis=1) +        # noqa: W504
                np.linalg.norm(cmpPoints - recPoints, axis=1)       # noqa: W504
            )
        totalTime = (totalTime * self.binning.slowness).astype(np.float32, copy=False)
        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex - 1)

        if profileBaseIndex is not None:
            timer = perf_counter()
        nx = (binMat[0, 0] * cmpPoints[:, 0] + binMat[0, 1] * cmpPoints[:, 1] + binMat[0, 2]).astype(np.int64)
        ny = (binMat[1, 0] * cmpPoints[:, 0] + binMat[1, 1] * cmpPoints[:, 1] + binMat[1, 2]).astype(np.int64)

        valid = (
            (nx >= 0) & (ny >= 0) &                     # noqa: W504
            (nx < self.output.binOutput.shape[0]) &     # noqa: W504
            (ny < self.output.binOutput.shape[1])       # noqa: W504
        )
        if not valid.any():
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex)
            return False

        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex)

        nx = nx[valid]
        ny = ny[valid]
        cmpPoints = cmpPoints[valid]
        srcExp = srcExp[valid]
        recPoints = recPoints[valid]
        hypArray = hypArray[valid]
        aziArray = aziArray[valid]
        totalTime = totalTime[valid]

        if writeAnalysis:
            if profileBaseIndex is not None:
                timer = perf_counter()
            # Bin-key sort for memmap page locality (same rationale as
            # _applyBinUpdatesNumba; the win is bigger here because the
            # batch is whole-template / whole-chunk, not per-source).
            binY = self.output.binOutput.shape[1]
            order = np.argsort(nx * np.int64(binY) + ny, kind='stable')
            nx = nx[order]
            ny = ny[order]
            cmpPoints = cmpPoints[order]
            srcExp = srcExp[order]
            recPoints = recPoints[order]
            hypArray = hypArray[order]
            aziArray = aziArray[order]
            totalTime = totalTime[order]

            stkX = (st2Mat[0, 0] * cmpPoints[:, 0] + st2Mat[0, 1] * cmpPoints[:, 1] + st2Mat[0, 2]).astype(np.int32)
            stkY = (st2Mat[1, 0] * cmpPoints[:, 0] + st2Mat[1, 1] * cmpPoints[:, 1] + st2Mat[1, 2]).astype(np.int32)

            cmpC = np.ascontiguousarray(cmpPoints, dtype=np.float32)
            recC = np.ascontiguousarray(recPoints, dtype=np.float32)
            srcC = np.ascontiguousarray(srcExp, dtype=np.float32)
            hypC = np.ascontiguousarray(hypArray, dtype=np.float32)
            aziC = np.ascontiguousarray(aziArray, dtype=np.float32)

            fnb.numbaApplyBinUpdatesAnalysisBatch(
                nx, ny,
                stkX, stkY,
                cmpC, recC,
                hypC, aziC,
                totalTime,
                srcC,
                self.output.binOutput,
                self.output.minOffset,
                self.output.maxOffset,
                self.output.anaOutput,
                int(self.grid.fold),
            )
            if profileBaseIndex is not None:
                self.elapsedTime(timer, profileBaseIndex + 1)
            return True

        # Fast path (no analysis writes): same primitives binTemplate9 uses,
        # but on the whole chunk -- which is where np.add.at / minimum.at /
        # maximum.at actually amortise their per-call overhead.
        if profileBaseIndex is not None:
            timer = perf_counter()
        np.add.at(self.output.binOutput, (nx, ny), 1)
        np.minimum.at(self.output.minOffset, (nx, ny), hypArray)
        np.maximum.at(self.output.maxOffset, (nx, ny), hypArray)
        if profileBaseIndex is not None:
            self.elapsedTime(timer, profileBaseIndex + 2)
        return True

    def calcFoldAndOffsetEssentials(self):
        # max fold is straightforward
        self.message.emit('Calc min/max offsets - step 1/9')
        self.progress.emit(10)
        self.output.maximumFold = self.output.binOutput.max()

        # min fold is straightforward
        self.message.emit('Calc min/max offsets - step 2/9')
        self.progress.emit(20)
        self.output.minimumFold = self.output.binOutput.min()

        # calc min offset against max (inf) values
        self.message.emit('Calc min/max offsets - step 3/9')
        self.progress.emit(30)
        self.output.minMinOffset = self.output.minOffset.min()

        # replace (inf) by (-inf) for max values
        self.message.emit('Calc min/max offsets - step 4/9')
        self.progress.emit(40)
        self.output.minOffset[self.output.minOffset == np.inf] = -np.inf

        # calc max values against (-inf) minimum
        self.message.emit('Calc min/max offsets - step 5/9')
        self.progress.emit(50)
        self.output.maxMinOffset = self.output.minOffset.max()

        # calc max offset against max (-inf) values
        self.message.emit('Calc min/max offsets - step 6/9')
        self.progress.emit(60)
        self.output.maxMaxOffset = self.output.maxOffset.max()

        # replace (-inf) by (inf) for min values
        self.message.emit('Calc min/max offsets - step 7/9')
        self.progress.emit(70)
        self.output.maxOffset[self.output.maxOffset == -np.inf] = np.inf

        # calc min offset against min (inf) values
        self.message.emit('Calc min/max offsets - step 8/9')
        self.progress.emit(80)
        self.output.minMaxOffset = self.output.maxOffset.min()

        # replace (inf) by (-inf) for max values
        self.message.emit('Calc min/max offsets - step 9/9')
        self.progress.emit(90)
        self.output.maxOffset[self.output.maxOffset == np.inf] = -np.inf

        self.progress.emit(100)
        return True

    def calcUniqueFoldValues(self) -> bool:
        """code to calculate unique offsets as a post-processing step
        it prunes the data in the fold array using offset and azimuth slots"""
        if self.unique.apply is False:                                          # slot offsets and azimuths and prune data
            return False

        if self.output.anaOutput is None or self.output.binOutput is None:      # these arrays are essential to calculate unique fold
            return False

        # Now we need to find unique rows in terms of line, stake, offset and azimuth values
        # See: https://stackoverflow.com/questions/16970982/find-unique-rows-in-numpy-array
        # See: https://www.geeksforgeeks.org/find-unique-rows-in-a-numpy-array/
        # See: https://www.sharpsightlabs.com/blog/numpy-unique/
        # See: https://www.sharpsightlabs.com/blog/numpy-axes-explained/
        # See: https://www.geeksforgeeks.org/python-slicing-multi-dimensional-arrays/

        self.message.emit('Calc unique fold')

        offSlot = self.unique.dOffset                                       # slots and scalars for unique offset, azimuth
        offScalar = 1.0 / offSlot
        aziSlot = self.unique.dAzimuth
        aziScalar = 1.0 / aziSlot
        writeBack = self.unique.write

        rows = self.output.anaOutput.shape[0]                               # get dimensions from analysis array itself
        cols = self.output.anaOutput.shape[1]

        self.nShotPoint = 0                                                 # reuse nShotPoint(s) to implement progress in statusbar
        self.nShotPoints = rows * cols                                      # calc nr of applicable points
        self.threadProgress = 0                                             # reset counter

        for row in range(rows):
            for col in range(cols):

                # begin of thread progress code
                if QThread.currentThread().isInterruptionRequested():       # maybe stop at each shot...
                    raise StopIteration

                self.nShotPoint += 1
                threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                if threadProgress > self.threadProgress:
                    self.threadProgress = threadProgress
                    self.progress.emit(threadProgress + 1)
                # end of thread progress code

                fold = self.output.binOutput[row, col]                      # check available traces for this bin
                if fold <= 0:
                    continue                                                # nothing to see here, move to next bin

                slice2D = self.output.anaOutput[row, col, 0:fold, :]        # get all available traces belonging to this bin

                slottedOffset = slice2D[:, 13]                              # grab 14th item of 2nd dimension (=offset)
                slottedOffset = slottedOffset * offScalar
                slottedOffset = np.round(slottedOffset)
                slottedOffset = slottedOffset * offSlot
                if writeBack:
                    slice2D[:, 13] = slottedOffset                          # write it back into the 2D slice

                slottedAzimuth = slice2D[:, 14]                             # grab 15th item of 2nd dimension (=azimuth)
                slottedAzimuth = slottedAzimuth * aziScalar
                slottedAzimuth = np.round(slottedAzimuth)
                slottedAzimuth = slottedAzimuth * aziSlot
                if writeBack:
                    slice2D[:, 14] = slottedAzimuth                         # write it back into the 2D slice

                slottedOffAzi = np.column_stack((slottedOffset, slottedAzimuth))

                # return_index gives the indices of the first occurrence of the unique values in the original array; these are the traces we want to keep
                _, indices = np.unique(slottedOffAzi, return_index=True, axis=0)

                for index in indices:                                       # flag unique offset, azimuth values
                    slice2D[index, 15] = -1.0

                slice2D = slice2D[slice2D[:, -1].argsort()]                 # sort the traces on last column (unique -1 flag)
                self.output.anaOutput[row, col, 0:fold, :] = slice2D        # put sorted traces back into analysis array

                uniqueFld = np.count_nonzero(slice2D[:, -1], axis=0)        # get unique fold count from last column (nr15)
                if uniqueFld > 0:
                    minOffset = np.min(slice2D[0:uniqueFld, 13], axis=0)    # first dimension may be affected by 0 values
                    maxOffset = np.max(slice2D[0:uniqueFld, 13], axis=0)    # first dimension may be affected by 0 values
                else:
                    minOffset = 0.0                                         # no traces available
                    maxOffset = 0.0                                         # no traces available

                self.output.binOutput[row, col] = uniqueFld                 # adjust fold value table
                self.output.minOffset[row, col] = minOffset                 # adjust min offset table
                self.output.maxOffset[row, col] = maxOffset                 # adjust max offset table

        return True

    def calcRmsOffsetValues(self) -> bool:
        """code to calculate RMS offset increments as a post-processing step"""

        if self.output.anaOutput is None or self.output.binOutput is None:      # these arrays are essential to calculate rms offsets
            return False

        self.message.emit('Calc RMS offset increments')

        rows = self.output.anaOutput.shape[0]                                   # get dimensions from analysis array itself
        cols = self.output.anaOutput.shape[1]

        # by defining the array only here, we prevent having a 'null' array that would result in a plot with 'empty' rms values
        self.output.rmsOffset = np.zeros(shape=(rows, cols), dtype=np.float32)  # start with empty array of the right size and type
        self.output.rmsOffset.fill(-np.inf)                                     # start max offset with -inf (use np.full instead)

        self.nShotPoint = 0                                                     # reuse nShotPoint(s) to implement progress in statusbar
        self.nShotPoints = rows * cols                                          # calc nr of applicable points
        self.threadProgress = 0                                                 # reset counter

        for row in range(rows):
            try:
                for col in range(cols):
                    try:
                        # begin of thread progress code
                        if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
                            raise StopIteration

                        self.nShotPoint += 1
                        threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
                        if threadProgress > self.threadProgress:
                            self.threadProgress = threadProgress
                            self.progress.emit(threadProgress + 1)
                        # end of thread progress code

                        fold = self.output.binOutput[row, col]                          # check available traces for this bin
                        if fold <= 0:                                                   # nothing to see here, move to next bin
                            continue                                                    # rms values prefilled with -np.inf

                        slice2D = self.output.anaOutput[row, col, 0:fold, :]            # get all available traces belonging to this bin
                        offset1D = slice2D[:, 13]                                       # grab 14th item of 2nd dimension (=offset)

                        if fold > 2:
                            rms = 0.0
                            offsetSorted = np.sort(offset1D)
                            offsetRange = offsetSorted[-1] - offsetSorted[0]            # range from min to max offsets
                            offsetStep = offsetRange / (fold - 1)
                            offsetDiff = np.diff(offsetSorted)                          # array is one element shorter than offsetRange

                            rms = 0.0
                            for index in range(fold - 1):
                                rms += (offsetDiff[index] - offsetStep) ** 2.0

                            rms /= fold - 1
                            rms = np.sqrt(rms)
                        else:
                            rms = 0.0

                        self.output.rmsOffset[row, col] = rms                           # fill in rms offset table
                    except IndexError:
                        continue
            except IndexError:
                continue

        self.output.minRmsOffset = self.output.rmsOffset.min()
        self.output.maxRmsOffset = self.output.rmsOffset.max()

        return True

    def calcOffsetGapValues(self) -> bool:
        """code to calculate maximum offset gaps as a post-processing step"""

        if self.output.anaOutput is None or self.output.binOutput is None:      # these arrays are essential to calculate max offset gaps
            return False

        self.message.emit('Calc max offset gaps')

        rows = self.output.anaOutput.shape[0]
        cols = self.output.anaOutput.shape[1]

        self.output.gapOffset = np.zeros(shape=(rows, cols), dtype=np.float32)
        self.output.gapOffset.fill(-np.inf)

        self.nShotPoint = 0
        self.nShotPoints = rows * cols
        self.threadProgress = 0

        for row in range(rows):
            try:
                for col in range(cols):
                    try:
                        if QThread.currentThread().isInterruptionRequested():
                            raise StopIteration

                        self.nShotPoint += 1
                        threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                        if threadProgress > self.threadProgress:
                            self.threadProgress = threadProgress
                            self.progress.emit(threadProgress + 1)

                        fold = self.output.binOutput[row, col]
                        if fold <= 0:
                            continue

                        slice2D = self.output.anaOutput[row, col, 0:fold, :]
                        offset1D = slice2D[:, 13]

                        if fold > 1:
                            offsetSorted = np.sort(offset1D)
                            maxGap = np.max(np.diff(offsetSorted))
                        else:
                            maxGap = 0.0

                        self.output.gapOffset[row, col] = maxGap
                    except IndexError:
                        continue
            except IndexError:
                continue

        validMask = np.isfinite(self.output.gapOffset)
        if np.any(validMask):
            validGapValues = self.output.gapOffset[validMask]
            self.output.maxOffsetGap = float(validGapValues.max())
            self.output.minOffsetGap = max(float(validGapValues.min()), 0.0)
            self.output.gapOffset[~validMask] = 0.0
        else:
            self.output.gapOffset.fill(0.0)
            self.output.maxOffsetGap = 0.0
            self.output.minOffsetGap = 0.0

        return True

    def calcOffsetAndAzimuthDistribution(self) -> bool:
        """code to calculate offsets / azimuth distribution as a post-processing step"""

        if self.output.anaOutput is None:                                       # this array is essential to calculate the distribution
            return False

        self.message.emit('Calc offset/azimuth distribution - 1/2')
        offsets, azimuth, noData = fnb.numbaSliceStats(self.output.anaOutput, self.unique.apply)
        if noData:
            return False

        dA = 5.0                                                                # azimuth increments
        dO = 100.0                                                              # offsets increments

        aMin = 0.0                                                              # min x-scale
        aMax = 360.0                                                            # max x-scale
        aMax += dA                                                              # make sure end value is included
        oMax = math.ceil(self.output.maxMaxOffset / dO) * dO + dO               # max y-scale; make sure end value is included

        aR = np.arange(aMin, aMax, dA)                                          # numpy array with values [0 ... fMax]
        oR = np.arange(0, oMax, dO)                                             # numpy array with values [0 ... oMax]
        self.output.ofAziHist = np.histogram2d(x=azimuth, y=offsets, bins=[aR, oR], range=None, density=None, weights=None)[0]

        self.message.emit('Calc offset/azimuth distribution - 2/2')
        dO = 50.0                                                               # offsets increments
        oR = np.arange(0, oMax, dO)                                             # numpy array with values [0 ... oMax]
        y, x = np.histogram(offsets, bins=oR)                                   # create a histogram with 100m offset increments

        y1 = np.append(y, 0)                                                    # add a dummy value to make x- and y-arrays equal size
        self.output.offstHist = np.stack((x, y1))                               # See: https://numpy.org/doc/stable/reference/generated/numpy.stack.html#numpy.stack

        return True

    def toXmlString(self, indent=4) -> str:
        # build the xml-tree by creating a QDomDocument and populating it
        doc = QDomDocument()
        self.writeXml(doc)
        # plain text representation of xml content
        plainText = doc.toString(indent)
        return plainText

    def fromXmlString(self, xmlString, createArrays=False) -> bool:

        # allow for surveys without any blocks or templates; useful when using SPS data only, so comment the following out
        # first get a QDomDocument to work with
        doc = QDomDocument()
        # errorMsg, errorLine, errorColumn not being used
        success = doc.setContent(xmlString)

        # parsing went ok, start with a new survey object
        if success:
            self.readXml(doc)                                                   # build the RollSurvey object tree
            self.calcTransforms(createArrays)                                   # calculate transforms to plot items at the right location
            self.calcSeedData()                                                 # needed for circles, spirals & well-seeds; may affect bounding box
            self.calcBoundingRect()                                             # (re)calculate the boundingBox as part of parsing the data
        return success

    def checkIntegrity(self) -> bool:
        """this routine checks survey integrity, after edits have been made"""

        e = 'Survey format error'
        # allow for surveys without any blocks or templates; useful when using SPS data only, so comment the following out
        # if len(self.blockList) == 0:
        #     QMessageBox.warning(None, e, 'A survey needs at least one block')
        #     return False

        # for block in self.blockList:
        #     if len(block.templateList) == 0:
        #         QMessageBox.warning(None, e, 'Each block needs at least one template')
        #         return False

        for block in self.blockList:
            for template in block.templateList:
                if len(template.rollList) != 3:
                    QMessageBox.warning(None, e, f'Template "{template.name}" should have exactly three roll steps')
                    return False

                for seed in template.seedList:
                    if seed.type == SeedType.rollingGrid or seed.type == SeedType.fixedGrid:    # rolling or fixed grid
                        if len(seed.grid.growList) != 3:
                            QMessageBox.warning(None, e, f'Seed "{seed.name}" should have exactly three grow steps')
                            return False

                    elif seed.type == SeedType.well:                            # well site; check for errors
                        wellName = seed.well.name                                 # may be relative to projectDirectory

                        if wellName is None or not os.path.exists(wellName):  # check if well file exists
                            QMessageBox.warning(None, e, f'A well-seed should point to an existing well-file\nRemove seed or adjust name in well-seed "{seed.name}"')
                            return False

                        try:
                            seed.well.refreshHeaderFromCurrentStateOrRaise(
                                survey=self,
                                surveyCrs=self.crs,
                                glbTransform=self.glbTransform,
                                recalcSurveyTransforms=self.glbTransform is None,
                            )
                        except RollWellError as exc:
                            QMessageBox.warning(None, e, f'{exc} in well file:\n{wellName}\nRemove seed or correct error in well-seed "{seed.name}"')
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

    def calcPointArrays(self):
        # this routine relies on self.checkIntegrity() to spot any errors
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    seed.calcPointArray()                                   # setup the numpy arrays for more efficient processing

    def makeWellPathsAbsolute(self, projectDirectory=None):
        """ make well paths absolute, if they are not already. Used when loading a survey """
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type == SeedType.well:
                        seed.well.makePathAbsolute(projectDirectory)

    def makeWellPathsRelative(self, projectDirectory=None):
        """ make well paths relative, if possible. Used when saving a survey """
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type == SeedType.well:
                        seed.well.makePathRelative(projectDirectory)

    def writeXml(self, doc: QDomDocument):
        doc.clear()

        instruction = doc.createProcessingInstruction('xml', 'version="1.0" encoding="UTF-8"')
        doc.appendChild(instruction)

        # root is created within the survey object; other elements are appended to root
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
                    self.type = SurveyType[e.text()]

                elif tagName == 'name':
                    self.name = e.text()

                elif tagName == 'surveyCrs':
                    self.crs.readXml(e)
                    # print( self.crs.authid())
                    # print( self.crs.srsid())
                    # print( self.crs.isGeographic())

                elif tagName == 'limits':
                    self.output.readXml(e)
                    self.angles.readXml(e)
                    self.offset.readXml(e)
                    self.unique.readXml(e)
                    self.binning.readXml(e)

                elif tagName == 'grid':
                    self.grid.readXml(e)

                elif tagName == 'reflectors':
                    self.globalPlane.readXml(e)
                    self.globalSphere.readXml(e)

                elif tagName == 'block_list':
                    # b = e.namedItem('block')

                    b = e.firstChildElement('block')
                    while not b.isNull():
                        block = RollBlock()
                        block.readXml(b)
                        self.blockList.append(block)
                        b = b.nextSiblingElement('block')

                elif tagName == 'pattern_list':
                    p = e.firstChildElement('pattern')
                    while not p.isNull():
                        pattern = RollPattern()
                        pattern.readXml(p)
                        self.patternList.append(pattern)
                        p = p.nextSiblingElement('pattern')
            n = n.nextSibling()

        return True

    def calcBoundingRect(self):
        """Calculate RollSurvey boundaries"""

        # reset survey spatial extent
        self.srcBoundingRect = QRectF()                                         # source extent
        self.recBoundingRect = QRectF()                                         # receiver extent
        self.cmpBoundingRect = QRectF()                                         # cmp extent
        self.boundingBox = QRectF()                                             # src|rec extent

        # initialise pattern figures; usually there are only a few different patterns, so this is very quick
        for pattern in self.patternList:
            pattern.calcPatternPicture()

        # we also need to update the template-seeds giving them the right pattern type and picture
        # here we need to make some optimizations; with a marine survey you can easily get 16,000 templates, or 16,000 SPs, as there is one shot per template
        # But each shot comes with some 11 seeds; one for the source and 10 for 10 streamers. This results in 176,000 seeds.
        # only a few seeds are shown at the same time, as it requires a signficant zoom to show individual seeds
        # We could initialize the seed's point figures and pattern figures just before they are painted (and NOT here).
        # this could significantly speed up initial loading of an existing survey.
        # In that case, start with a None object, take it from there.

        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.type < SeedType.circle and seed.patternNo > -1 and seed.patternNo < len(self.patternList):
                        growStep = seed.grid.growList[-1]
                        if growStep is not None and seed.bAzimuth:
                            # need to reorient the pattern; get the slant angle (deviation from orthogonal)
                            angle = math.degrees(math.atan2(growStep.increment.x(), growStep.increment.y()))
                            seed.patternPicture = QPicture()                    # create initial picture object
                            painter = QPainter(seed.patternPicture)             # create painter object to draw against
                            painter.rotate(-angle)                              # rotate painter in opposite direction before drawing
                            painter.drawPicture(0, 0, self.patternList[seed.patternNo].patternPicture)
                            painter.end()
                        else:
                            seed.patternPicture = self.patternList[seed.patternNo].patternPicture
                    else:
                        seed.patternPicture = None

        # do the real work here...
        for block in self.blockList:
            srcBounds, recBounds, cmpBounds = block.calcBoundingRect()
            self.srcBoundingRect |= srcBounds                                   # add it
            self.recBoundingRect |= recBounds                                   # add it
            self.cmpBoundingRect |= cmpBounds                                   # add it

        self.boundingBox = self.srcBoundingRect | self.recBoundingRect
        # stretch it to capture overflowing patterns
        self.boundingBox += QMarginsF(50, 50, 50, 50)

        return self.boundingBox

    def boundingRect(self):
        """required for painting a pg.GraphicsObject"""
        if self.boundingBox.isEmpty():
            return self.calcBoundingRect()
        # earlier derived result, from blocks -> templates -> seeds
        return self.boundingBox

    def lineWidthForScreen(self, screen) -> float:
        # geometry() is logical (DIPs); multiply by DPR to get native pixels
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        nativeW = round(geo.width() * dpr)
        nativeH = round(geo.height() * dpr)

        # Simple classification; adjust thresholds if you want to be stricter
        if nativeW >= 3840 or nativeH >= 2160:    # UHD (4K)
            return 3.0
        if nativeW >= 2560 or nativeH >= 1440:    # QHD (2K)
            return 2.0
        return 1.5                                  # fallback for FHD/others

    def _paintStartNow(self):
        # painting a survey layout can take a long time. This has now been optimized by using two framebuffers; one for invariant layers (bin/src/rec/cmp rectangles)
        # and one for progressive layers (templates/seeds). The invariant layers are drawn once per framebuffer, the progressive layers are drawn repeatedly until the time budget is exhausted.
        # The time budget is set to 50ms by default, which should be ok for 20fps. You can adjust this value using setPaintBudget()
        # See: https://pypi.org/project/dvg-pyqtgraph-threadsafe/ for threadsafe plotting with pyqtgraph as an alternative to this approach.
        self._paintStart = perf_counter()

    def _shouldAbortPaint(self) -> bool:
        """ time budget OR external cancel """

        elapsedMs = (perf_counter() - self._paintStart) * 1000.0
        return self._cancelPaint or elapsedMs > self._paintBudgetMs

    def invalidatePaintCache(self) -> None:
        """Call this whenever data, transforms, colors/pens, or PaintDetails/PaintMode affecting areas change."""

        self._paintEpoch += 1
        self._fbBase = None
        self._fbProg = None
        self._fbKey = None
        self._ps = None
        self.update()

    def _makeFramebufferKey(self, painter: QPainter, option) -> tuple:
        """Build a key representing the current paint device/transform/LOD/flags/epoch."""
        dev = painter.device()

        w = getattr(dev, "width", lambda: 0)()
        h = getattr(dev, "height", lambda: 0)()
        T: QTransform = painter.worldTransform()
        m = (T.m11(), T.m12(), T.m13(), T.m21(), T.m22(), T.m23(), T.m31(), T.m32(), T.m33(),)
        lod = option.levelOfDetailFromTransform(T) * self.lodScale
        return (w, h, m, round(lod, 3), int(self.paintMode), int(self.paintDetails), getattr(self, "_paintEpoch", 0),)

    def _ensureBuffers(self, painter: QPainter, option, penWidth=2) -> None:
        """ Ensure the base and progressive framebuffers exist and match the current view.
        Rebuilds and re-renders the base layer (bin/src/rec/cmp rectangles) if the key changes. """

        key = self._makeFramebufferKey(painter, option)
        if key == self._fbKey and self._fbBase is not None and self._fbProg is not None:
            return

        dev = painter.device()
        # device pixel ratio
        try:
            dpr = dev.devicePixelRatioF()
        except AttributeError:
            dpr = float(getattr(dev, "devicePixelRatio", lambda: 1.0)())

        wLog = max(1, int(getattr(dev, "width", lambda: 0)()))
        hLog = max(1, int(getattr(dev, "height", lambda: 0)()))
        wPx = max(1, int(round(wLog * dpr)))
        hPx = max(1, int(round(hLog * dpr)))

        def newImg():
            img = QImage(wPx, hPx, QImage.Format.Format_ARGB32_Premultiplied)
            img.setDevicePixelRatio(dpr)
            img.fill(0)  # fully transparent
            return img

        # Allocate both layers
        self._fbBase = newImg()   # invariant (bin/src/rec/cmp)
        self._fbProg = newImg()   # progressive (templates/seeds)
        self._fbKey = key

        # Reset progressive state for a fresh accumulation in this view
        self._initPaintState()

        # Render invariant layers once into the base buffer
        p = QPainter(self._fbBase)
        try:
            p.setWorldTransform(painter.worldTransform())
            p.setClipRect(self.viewRect())
            p.setRenderHints(painter.renderHints())
            self._renderBaseLayers(p, option, penWidth=penWidth)
        finally:
            p.end()

    def _renderBaseLayers(self, p: QPainter, option, penWidth=2) -> None:
        """ Draw only invariant layers into the base framebuffer:
        - survey outline at very low LOD
        - bin area (if enabled)
        - per-block rec/src/cmp rectangles (if enabled)

        This is drawn once per framebuffer, so semi-transparent brushes retain intended opacity.
        """
        vb: QRectF = self.viewRect()
        lod = option.levelOfDetailFromTransform(p.worldTransform()) * self.lodScale
        appSettings = getActiveAppSettings()

        if lod < appSettings.lod0:
            p.setPen(pg.mkPen('k'))
            p.setBrush(pg.mkBrush((64, 64, 64, 255)))
            p.drawRect(self.boundingRect())                                     # draw survey bounding box
            return

        # Per-block outlines (if enabled); culled by viewRect
        for block in self.blockList:
            if not block.boundingBox.intersects(vb):
                continue

            p.setPen(pg.mkPen(1.0))                                             # use a grey pen for template borders
            p.setBrush(pg.mkBrush((192, 192, 192, 64)))                         # grey & semi-transparent, use for all templates

            if self.paintDetails & PaintDetails.recArea:
                # p.setOpacity(1.0)
                p.setPen(appSettings.recAreaPen)
                p.setBrush(QBrush(QColor(appSettings.recAreaColor)))
                p.drawRect(block.recBoundingRect)

            if self.paintDetails & PaintDetails.srcArea:
                # p.setOpacity(1.0)
                p.setPen(appSettings.srcAreaPen)
                p.setBrush(QBrush(QColor(appSettings.srcAreaColor)))
                p.drawRect(block.srcBoundingRect)

            if self.paintDetails & PaintDetails.cmpArea:
                # p.setOpacity(1.0)
                p.setPen(appSettings.cmpAreaPen)
                p.setBrush(QBrush(QColor(appSettings.cmpAreaColor)))
                p.drawRect(block.cmpBoundingRect)

            if self.paintMode == PaintMode.justBlocks:                          # draw block outlines on top of any requested areas
                p.setPen(pg.mkPen(1.0))
                p.setBrush(pg.mkBrush((192, 192, 192, 64)))
                p.drawRect(block.boundingBox)
                continue                                                        # we've done enough

            # Draw invariant seeds once per template (circle/spiral/well)
            for template in block.templateList:
                if not template.totTemplateRect.intersects(vb):
                    continue
                self._renderInvariantSeedsIntoBase(p, lod, template, penWidth=penWidth)

    def _renderInvariantSeedsIntoBase(self, painter, lod, template, penWidth=2):
        # Draw circle/spiral/well once into the base framebuffer
        # As these seeds are invariant with respect to rolling, we can draw them once into the base framebuffer,
        # and they will be reused for all rolled positions. This is a significant optimization,
        # as it avoids redrawing these complex seeds for every rolled position, which can be very costly in terms of performance.
        # For that reason, it isn't needed to test them against the viewbox, as they are only drawn once into the base framebuffer.

        appSettings = getActiveAppSettings()

        for seed in getattr(template, 'seedList', []):

            if seed.type < SeedType.circle:             # rolling or fixed grid
                continue

            # Receiver/source mask
            paintDetail = (self.paintDetails >> 3) if seed.bSource else self.paintDetails                            # divide by 8 to make source flag equal to receiver flag

            painter.setPen(pg.mkPen(seed.color, width=penWidth))

            if seed.type == SeedType.circle:
                if paintDetail & PaintDetails.recLin:
                    painter.setBrush(QBrush())
                    r = seed.circle.radius
                    o = seed.origin.toPointF()
                    painter.drawEllipse(o, r, r)
                if lod >= appSettings.lod2 and self.paintMode != PaintMode.justLines:
                    if paintDetail & PaintDetails.recPnt:
                        for pt in seed.pointList:
                            painter.drawPicture(pt.toPointF(), seed.getPointPicture())

            if seed.type == SeedType.spiral:
                if paintDetail & PaintDetails.recLin:
                    painter.setBrush(QBrush())
                    painter.drawPath(seed.spiral.path)
                if lod >= appSettings.lod2 and self.paintMode != PaintMode.justLines:
                    if paintDetail & PaintDetails.recPnt:
                        for pt in seed.pointList:
                            painter.drawPicture(pt.toPointF(), seed.getPointPicture())

            if seed.type == SeedType.well:
                if (paintDetail & PaintDetails.recLin) and getattr(seed.well, 'polygon', None) is not None:
                    painter.drawPolyline(seed.well.polygon)
                    painter.drawEllipse(seed.well.origL, 5.0, 5.0)
                if lod >= appSettings.lod2 and self.paintMode != PaintMode.justLines:
                    if paintDetail & PaintDetails.recPnt:
                        for pt in getattr(seed, 'pointList', []):
                            painter.drawPicture(pt.toPointF(), seed.getPointPicture())

    def _initPaintState(self) -> None:
        """ Initialize or reset the progressive pass state (resume indices) for templates.
        Keep this separate from any legacy _initPaintState you may have. """

        self._ps = {"b": 0, "t": 0, "i": 0, "j": 0, "k": 0}

    def _paintPassIntoProgressive(self, p: QPainter, option, penWidth=2) -> bool:
        """ Draw a time-budgeted chunk of template content into self._fbProg using painter p.
        Honors current LOD and PaintMode for deciding between outlines vs. detailed template painting.
        Returns True when fully done; False when more passes are needed. """

        if self.paintMode == PaintMode.justBlocks:  # nothing to do here
            return True

        vb: QRectF = self.viewRect()
        lod = option.levelOfDetailFromTransform(p.worldTransform()) * self.lodScale
        appSettings = getActiveAppSettings()

        if self._ps is None:
            self._initPaintState()

        # Start/refresh time budget for this pass
        self._paintStartNow()

        # Ensure default blending for progressive content
        try:
            p.setOpacity(1.0)
        except (AttributeError, TypeError, RuntimeError):
            pass

        b = self._ps["b"]; t = self._ps["t"]; i = self._ps["i"]; j = self._ps["j"]; k = self._ps["k"]  # noqa: E702

        while b < len(self.blockList):
            block = self.blockList[b]
            if not block.boundingBox.intersects(vb):
                b += 1
                t = i = j = k = 0
                if self._shouldAbortPaint():
                    self._ps.update({"b": b, "t": 0, "i": 0, "j": 0, "k": 0})
                    return False
                continue

            templates = block.templateList
            while t < len(templates):
                template = templates[t]
                # Normalized template invariant.
                assert len(template.rollList) == 3, 'there must always be 3 roll steps / grow steps'  # nosec B101
                s0 = template.rollList[0].steps
                s1 = template.rollList[1].steps
                s2 = template.rollList[2].steps

                while i < s0:
                    while j < s1:
                        while k < s2:
                            if self._shouldAbortPaint():
                                self._ps.update({"b": b, "t": t, "i": i, "j": j, "k": k})
                                return False

                            offset = template.rollList[0].increment * i
                            offset += template.rollList[1].increment * j
                            offset += template.rollList[2].increment * k

                            rect = template.totTemplateRect.translated(offset.toPointF())
                            if rect.intersects(vb):
                                if lod < appSettings.lod1 or self.paintMode == PaintMode.justTemplates:
                                    p.drawRect(rect & self.boundingRect())
                                else:
                                    self._paintTemplate(p, vb, lod, template, offset, penWidth=penWidth)
                            k += 1
                        k = 0; j += 1   # noqa: E702
                    j = 0; i += 1       # noqa: E702
                i = 0; t += 1           # noqa: E702

            b += 1; t = i = j = k = 0   # noqa: E702
            if self._shouldAbortPaint():
                self._ps.update({"b": b, "t": 0, "i": 0, "j": 0, "k": 0})
                return False

        # Finished the whole survey
        self._ps = None
        return True

    def paint(self, painter, option, widget):
        """ Progressive, two-layer paint:
        - Base buffer (_fbBase): invariant layers (bin/src/rec/cmp) drawn once per view.
        - Progressive buffer (_fbProg): templates/seeds drawn incrementally over multiple passes.
        """

        # Reset only grid-based seeds; invariant seeds (circle/spiral/well) will be painted once into the base buffer
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    try:
                        if seed.type < SeedType.circle:  # rolling/fixed grids
                            seed.rendered = False
                        # leave circle/spiral/well flags untouched; base pass handles them
                    except (AttributeError, TypeError):
                        pass

        # Determine the screen (for width choices if you use it)
        screen = None
        try:
            wh = widget.windowHandle() if widget is not None else None
            screen = wh.screen() if wh is not None else QGuiApplication.primaryScreen()
        except (AttributeError, TypeError):
            screen = QGuiApplication.primaryScreen()

        penWidth = self.lineWidthForScreen(screen)

        # Ensure buffers for current view/transform/flags/epoch (this also resets self._ps on key change)
        self._ensureBuffers(painter, option, penWidth)

        # 1) Do ONE progressive pass first (so the new content is visible in this same paint)
        finished = True
        if getattr(self, "_ps", None) is not None and getattr(self, "_fbProg", None) is not None:
            self._cancelPaint = False
            self._paintBudgetMs = 20.0
            fbp = QPainter(self._fbProg)

            try:
                fbp.setWorldTransform(painter.worldTransform())
                fbp.setClipRect(self.viewRect())
                fbp.setRenderHints(painter.renderHints())
                finished = self._paintPassIntoProgressive(fbp, option, penWidth=penWidth)
            finally:
                fbp.end()

        # 2) Blit the latest buffers now (so the just-drawn chunk is visible immediately)
        painter.save()
        try:
            painter.setWorldTransform(QTransform())  # draw images in device coords
            if getattr(self, "_fbBase", None) is not None:
                painter.drawImage(0, 0, self._fbBase)
            if getattr(self, "_fbProg", None) is not None:
                painter.drawImage(0, 0, self._fbProg)
        finally:
            painter.restore()

        # If only blocks are requested, we’re done
        if self.paintMode == PaintMode.justBlocks:
            return

        # 3) If not finished, schedule another frame
        if getattr(self, "_ps", None) is not None and not finished:
            self.update()

    def _paintTemplate(self, painter, viewbox, lod, template, templateOffset, penWidth=2):
        # we are now painting a template; this is a bit more complex. We need to paint the seeds in the template
        # we need to check if the seed is within the viewbox; if not, we skip it
        # we need to check if the seed is within the block's src/rec area; if not, we skip it
        # we need to check the level-of-detail (lod) to decide whether to draw a line, a series of points or a series of patterns
        # this is controlled by the lod, the paintMode and the paintDetails flags

        appSettings = getActiveAppSettings()

        for seed in template.seedList:                                          # iterate over all seeds in a template
            painter.setPen(pg.mkPen(seed.color, width=penWidth))                # use a solid pen, 2 pixels wide

            # Skip invariant seeds here; they are drawn into base buffer
            if seed.type >= SeedType.circle:                                    # circle, spiral, well
                continue

            if seed.bSource is True:
                paintDetail = self.paintDetails >> 3                            # divide by 8 to make source flag equal to receiver flag
            else:
                paintDetail = self.paintDetails                                 # we have a receiver seed; no further action required

            if seed.type < SeedType.circle and seed.rendered is False:          # grid based seed, rolling or fixed
                if seed.type == SeedType.fixedGrid:                             # no rolling along; fixed grid
                    templateOffset = QVector3D()                                # no offset applicable
                    seed.rendered = True                                        # paint fixed grid only once

                length = len(seed.grid.growList)                                # how deep is the grow list ?

                # Normalized seed invariant.
                assert length == 3, 'there must always be 3 roll steps / grow steps'  # nosec B101

                for i in range(seed.grid.growList[0].steps):
                    for j in range(seed.grid.growList[1].steps):
                        offset = QVector3D(templateOffset)
                        offset += seed.grid.growList[0].increment * i
                        offset += seed.grid.growList[1].increment * j
                        salvo = seed.grid.salvo.translated(offset.toPointF())
                        salvo = fnb.clipLineF(salvo, seed.blockBorder)
                        salvo = fnb.clipLineF(salvo, viewbox)

                        if salvo.isNull():
                            continue

                        if paintDetail & PaintDetails.recLin != PaintDetails.none:
                            painter.drawLine(salvo)

                if lod < appSettings.lod2 or self.paintMode == PaintMode.justLines:
                    continue

                for seedOffset in self.iterSeedGrowOffsets(seed, templateOffset):
                    seedOrigin = seedOffset + seed.origin

                    if not containsPoint3D(seed.blockBorder, seedOrigin):
                        continue

                    if not containsPoint3D(viewbox, seedOrigin):
                        continue

                    if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                        painter.drawPicture(seedOrigin.toPointF(), seed.getPointPicture())

                    if lod < appSettings.lod3 or self.paintMode == PaintMode.justPoints:
                        continue

                    if seed.patternPicture is not None and paintDetail & PaintDetails.recPat != PaintDetails.none:
                        painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy

    def itemChange(self, change, value):
        try:
            return super().itemChange(change, value)
        except TypeError:
            # PyQt/PyQtGraph QVariant conversion mismatch in some runtimes.
            # Keep app responsive instead of flooding traceback.
            # This can be triggered by zooming/panning in the view, or by resizing the window, or by any change that triggers a redraw.
            # The offending call is likely in GraphicsObject.itemChange, which is called by the framework when certain properties change (like position, scale, etc.).
            # The exact change types that trigger this can vary, but it’s often related to transformations or geometry changes.
            # The error occurs because the base implementation of itemChange in GraphicsObject expects a QVariant,
            # but in some PyQt/PyQtGraph versions or configurations, it might receive a native Python type instead, leading to a TypeError when it tries to convert it to QVariant.
            # By catching this exception, we can prevent the application from crashing due to this mismatch. However, it’s important to note that this is more of a workaround than a proper fix.
            # Ideally, the underlying issue in the PyQt/PyQtGraph version should be addressed to ensure compatibility with native Python types.
            # This routine was introduced when allowing the use of Roll as a standalone module without PyQtGraph,
            # but it can also be useful in the integrated application to prevent crashes due to this issue.
            return value
