"""
This module provides the main classes used in Roll
"""
import math
import os
import sys
from collections import defaultdict
from enum import Enum, IntFlag
from time import perf_counter

import numpy as np
import pyqtgraph as pg
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QMarginsF, QRectF, QThread, pyqtSignal
from qgis.PyQt.QtGui import (QBrush, QColor, QPainter, QPicture, QTransform,
                             QVector3D)
from qgis.PyQt.QtWidgets import QApplication, QMessageBox
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from . import config  # used to pass initial settings
from .functions import containsPoint3D
from .functions_numba import (clipLineF, numbaFixRelationRecord,
                              numbaSetPointRecord, numbaSetRelationRecord,
                              numbaSliceStats, pointsInRect)
from .roll_angles import RollAngles
from .roll_bingrid import RollBinGrid
from .roll_binning import BinningType, RollBinning
from .roll_block import RollBlock
from .roll_offset import RollOffset
from .roll_output import RollOutput
from .roll_pattern import RollPattern
from .roll_pattern_seed import RollPatternSeed
from .roll_plane import RollPlane
from .roll_seed import RollSeed, SeedType
from .roll_sphere import RollSphere
from .roll_template import RollTemplate
from .roll_translate import RollTranslate
from .roll_unique import RollUnique
from .sps_io_and_qc import pntType1, relType2

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
#     name_elem = ET.SubElement(seed_elem, 'name')
#     name_elem.text = self.name

# The survey object contains several "lower" objects such as blocks, templates and patterns, all defined in separate modules
# When these need their parent "survey" object in a function, there's a chance of getting circular references
# See: https://www.mend.io/blog/closing-the-loop-on-python-circular-import-issue/


class SurveyType(Enum):
    Orthogonal = 0
    Parallel = 1
    Slanted = 2
    Brick = 3
    Zigzag = 4
    Streamer = 5


# Note: we need to keep SurveyType and SurveyList in sync; maybe combine in a dictionary ?!
SurveyList = [
    'Orthogonal - standard manner of acquiring land data',
    'Parallel - standard manner of acquiring OBN data',
    'Slanted - legacy variation on orthogonal, aiming to reduce LMOS',
    'Brick - legacy variation on orthogonal, aiming to reduce LMOS',
    'zigzag - legacy manner acquiring narrrow azimuth vibroseis data',
    'streamer - towed streamer marine survey',
]


class PaintMode(Enum):
    none = 0            # reset the whole lot
    justBlocks = 1      # just src, rec & cmp block outlines
    justTemplates = 2   # just template rect boundaries
    justLines = 3       # just lines
    justPoints = 4      # just points
    all = 5             # down to patterns


class PaintDetails(IntFlag):
    none = 0        # reset the whole lot

    # receiver details
    recPat = 1      # show rec patterns
    recPnt = 2      # show rec points
    recLin = 4      # show rec lines
    recAll = 7      # show all rec details

    # source details
    srcPat = 8      # show src patterns
    srcPnt = 16     # show src points
    srcLin = 32     # show src lines
    srcAll = 56     # show all source details

    # show all receiver and source details
    srcAndRec = 63  # show all src and rec details

    # show templates ... or not
    templat = 64    # complete templates

    # show relevant areas
    srcArea = 128   # just src area
    recArea = 256   # just rec area
    cmpArea = 512   # just cmp area
    binArea = 1024  # just binning area

    # show all above listed areas
    allArea = 1984  # show all areas

    all = 2047      # all bits defined sofar are set

    # note: clearing a flag works with flag &= ~flagToClear


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

    # See: https://github.com/pyqtgraph/pyqtgraph/blob/develop/examples/CustomGraphItem.py
    # This example gives insight in the mouse drag event

    # assign default name value
    def __init__(self, name: str = 'Untitled') -> None:

        pg.GraphicsObject.__init__(self)
        self.mouseGrabbed = False                                               # needed to speed up drawing, whilst dragging

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
        self.type = SurveyType.Orthogonal                                       # survey type as defined in class SurveyType()
        self.name: str = name

        # note: type() is a builtin Python function, so it is recommended NOT to use it as a variable name
        # as in that case you'll overwrite a built-in function, which can have undesired side effects
        # so using "self.type = xxx" is fine, but "type = xxx" is NOT fine

        # survey painting mode
        self.paintMode = PaintMode.all                                          # paints down to patterns
        self.paintDetails = PaintDetails.all                                    # template details to be painted
        self.lodScale = 1.0                                                     # force Level of Detail (LOD) to a higher value (for small Wizard plots)
        self.interruptedPainting = False                                        # flag to interrupt painting (when Esc is pressed)

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

        # Painting interruption controls
        self._painting = False                 # reentrancy guard to avoid nested paints
        self._paintBudgetMs = 25.0             # max milliseconds per paint call; tweak as needed
        # If you want external cancellation, set self._cancelPaint = True from UI actions
        self._cancelPaint = False

        # Optional: enable device-coordinate caching (helps when content is static under a transform)
        try:
            # Not all pg.GraphicsObject subclasses expose setCacheMode; guard just in case
            self.setCacheMode(self.DeviceCoordinateCache)
        except Exception:
            pass

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
            # self.output.rmsOffset = np.zeros(shape=(nx, ny), dtype=np.float32)  # start with empty array of the right size and type
            self.output.minOffset.fill(np.Inf)                                  # start min offset with +inf (use np.full instead)
            self.output.maxOffset.fill(np.NINF)                                 # start max offset with -inf (use np.full instead)
            # self.output.rmsOffset.fill(np.NINF)                                 # start max offset with -inf (use np.full instead)

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
                    nTemplateShots *= roll.steps                                # template is rolled a number of times

                nBlockShots += nTemplateShots
            self.nShotPoints += nBlockShots
        return self.nShotPoints

    def calcNoTemplates(self) -> int:
        self.nTemplates = 0
        for block in self.blockList:
            nTemplates = 0                                                      # reset for each block in case there no templates in a block
            for template in block.templateList:
                nTemplates = 1
                for roll in template.rollList:
                    nTemplates *= roll.steps                                    # template is rolled a number of times
            self.nTemplates += nTemplates
        return self.nTemplates

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
            self.output.recDict = defaultdict(dict)                             # nested dictionary to access rec positions

            self.nRecRecord = 0                                                 # zero based array index
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
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            success = False

        return success

    def geometryFromTemplates(self) -> bool:
        try:
            self.calcPointArrays()                                              # first set up all point arrays
            # get all blocks
            for nBlock, block in enumerate(self.blockList):
                for template in block.templateList:                             # get all templates
                    # how deep is the list ?
                    length = len(template.rollList)

                    assert length == 3, 'there must always be 3 roll steps / grow steps'
                    # todo: search everywhere for "< 3" and insert assertions for length of list

                    if length == 0:
                        off0 = QVector3D()                                      # always start at (0, 0, 0)
                        self.geomTemplate3(nBlock, block, template, off0)

                    elif length == 1:
                        # get the template boundaries
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            self.geomTemplate3(nBlock, block, template, off0)

                    elif length == 2:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j
                                self.geomTemplate3(nBlock, block, template, off1)

                    elif length == 3:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i

                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j

                                for k in range(template.rollList[2].steps):
                                    off2 = off1 + template.rollList[2].increment * k

                                    self.geomTemplate3(nBlock, block, template, off2)
                    else:
                        # do something recursively; not  implemented yet
                        raise NotImplementedError('More than three roll steps currently not allowed.')

        except StopIteration:
            self.errorText = 'geometry creation cancelled by user'
            return False
        except BaseException as e:
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            return False

        self.progress.emit(100)                                                 # make sure we stop at 100

        #  first remove all remaining receiver duplicates
        self.output.recGeom = np.unique(self.output.recGeom)

        # todo; because we keep track of 'self.nRelRecord'
        # there's no need to shrink the array based on the 'Uniq' == 1 condition.
        # need to change the code; resize the relGeom array based on self.nRelRecord

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

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
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
                            # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
                            # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
                            self.output.srcGeom[nSrc]['East'] = srcGlob.x()
                            self.output.srcGeom[nSrc]['North'] = srcGlob.y()
                            self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
                            self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
                            self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

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
                                                recLine = int(recStake.y())
                                                recPoint = int(recStake.x())

                                                self.nNewRecLine = recLine

                                                # check if we're on a 'new' receiver line and need a new rel-record
                                                if self.nNewRecLine != self.nOldRecLine:
                                                    self.nOldRecLine = self.nNewRecLine

                                                    # first complete the previous record
                                                    if self.nRelRecord >= 0:                        # we need at least one earlier record
                                                        self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                        self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                    self.nRelRecord += 1                            # now start with a new relation record
                                                    self.recMin = recPoint                          # reset minimum rec number
                                                    self.recMax = recPoint                          # reset maximum rec number

                                                    self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
                                                    self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
                                                    self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                                                    self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
                                                    self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
                                                    self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                                                    self.output.relGeom[self.nRelRecord]['Uniq'] = 1
                                                else:
                                                    self.recMin = min(recPoint, self.recMin)
                                                    self.recMax = max(recPoint, self.recMax)
                                                    # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
                                                    # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

                                                # apply self.output.relGeom.resize(N) when more memory is needed
                                                arraySize = self.output.relGeom.shape[0]
                                                if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                                                    self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

                                                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                                                # rather than adding all receivers first, and removing all receiver duplicates later,
                                                # we use a nested dictionary to find out if a rec station already exists
                                                # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

                                                try:                                                                # has it been used before ?
                                                    use = self.output.recDict[recLine][recPoint]
                                                    self.output.recDict[recLine][recPoint] = use + 1                # increment by one
                                                except KeyError:
                                                    self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

                                                    self.nRecRecord += 1                                            # we have a new receiver record

                                                    self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
                                                    self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
                                                    self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
                                                    # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
                                                    # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
                                                    self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
                                                    self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
                                                    self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
                                                    self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
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

        # finally complete the very last relation record
        if self.nRelRecord >= 0:                        # we need at least one record
            self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
            self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    def elapsedTime(self, startTime, index: int) -> None:
        currentTime = perf_counter()
        deltaTime = currentTime - startTime
        self.timerTmin[index] = min(deltaTime, self.timerTmin[index])
        self.timerTmax[index] = max(deltaTime, self.timerTmax[index])
        self.timerTtot[index] = self.timerTtot[index] + deltaTime
        self.timerFreq[index] = self.timerFreq[index] + 1
        QApplication.processEvents()
        return perf_counter()  # call again; to ignore any time spent in this funtion

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
                        self.nOldRecLine = -999999
                        # apply integer divide
                        threadProgress = (100 * self.nShotPoint) // self.nShotPoints
                       