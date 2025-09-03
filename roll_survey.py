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
from qgis.PyQt.QtGui import QBrush, QColor, QPainter, QPicture, QTransform, QVector3D
from qgis.PyQt.QtWidgets import QMessageBox, qApp
from qgis.PyQt.QtXml import QDomDocument, QDomElement

from . import config  # used to pass initial settings
from .functions import containsPoint3D
from .functions_numba import clipLineF, numbaFixRelationRecord, numbaSetPointRecord, numbaSetRelationRecord, numbaSliceStats, pointsInRect
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


class PaintMode(IntFlag):
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
        qApp.processEvents()
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

    def geomTemplate2(self, nBlock, block, template, templateOffset):
        """Use numpy arrays instead of iterating over the growList.
        This provides a much faster approach then using the growlist.

        The function is however still rather slow.
        Use time.perf_counter() to analyse bottlenecks
        """

        # convert the template offset to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # iterate over all seeds in a template; make sure we start wih *source* seeds
        for srcSeed in template.seedList:
            time = perf_counter()   ###
            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            if not block.borders.srcBorder.isNull():                            # deal with block's source  border if it isn't null()
                I = pointsInRect(srcArray, block.borders.srcBorder)
                if I.shape[0] == 0:
                    continue
                time = self.elapsedTime(time, 0)    ###
                srcArray = srcArray[I, :]                                       # filter the source array
                time = self.elapsedTime(time, 1)    ###

            for src in srcArray:                                                # iterate over all sources

                self.nShotPoint += 1
                self.nOldRecLine = -999999                                      # a new shotpoint always starts with new relation records

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

                time = self.elapsedTime(time, 2)    ###

                # determine line & stake nrs for source point
                srcX = src[0]
                srcY = src[1]
                # srcZ = src[2]

                srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)            # get line and point indices
                srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)            # we need global positions

                numbaSetPointRecord(self.output.srcGeom, nSrc, srcStkY, srcStkX, nBlock, srcLocX, srcLocY, src)
                # self.output.srcGeom[nSrc]['Line'] = int(srcStkY)
                # self.output.srcGeom[nSrc]['Point'] = int(srcStkX)
                # self.output.srcGeom[nSrc]['Index'] = nBlock % 10 + 1            # the single digit point index is used to indicate block nr
                # self.output.srcGeom[nSrc]['Code' ] = 'E1'                       # can do this in one go at the end
                # self.output.srcGeom[nSrc]['Depth'] = 0.0                        # not needed; zero when initialized
                # self.output.srcGeom[nSrc]['East'] = srcLocX
                # self.output.srcGeom[nSrc]['North'] = srcLocY
                # self.output.srcGeom[nSrc]['LocX'] = srcX                        # x-component of 3D-location
                # self.output.srcGeom[nSrc]['LocY'] = srcY                        # y-component of 3D-location
                # self.output.srcGeom[nSrc]['Elev'] = srcZ                        # z-value not affected by transform

                time = self.elapsedTime(time, 3)    ###

                # now iterate over all seeds to find the receivers
                for recSeed in template.seedList:                               # iterate over all rec seeds in a template
                    if recSeed.bSource:                                         # work with receiver seeds here
                        continue

                    # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
                    recPoints = recSeed.pointArray + npTemplateOffset

                    time = self.elapsedTime(time, 4)    ###

                    if not block.borders.recBorder.isNull():                    # deal with block's receiver border if it isn't null()
                        I = pointsInRect(recPoints, block.borders.recBorder)
                        if I.shape[0] == 0:
                            continue
                        else:
                            time = self.elapsedTime(time, 5)    ###
                            recPoints = recPoints[I, :]
                            time = self.elapsedTime(time, 6)    ###

                    for rec in recPoints:                                       # iterate over all receivers

                        time = perf_counter()                                   # reset at start of receiver loop

                        # determine line & stake nrs for receiver point
                        recX = rec[0]
                        recY = rec[1]
                        # recZ = rec[2]

                        time = self.elapsedTime(time, 7)    ###

                        recStkX, recStkY = self.st2Transform.map(recX, recY)    # get line and point indices
                        recLocX, recLocY = self.glbTransform.map(recX, recY)    # we need global positions

                        time = self.elapsedTime(time, 8)    ###

                        # we have a new receiver record
                        self.nRecRecord += 1

                        numbaSetPointRecord(self.output.recGeom, self.nRecRecord, recStkY, recStkX, nBlock, recLocX, recLocY, rec)
                        # self.output.recGeom[self.nRecRecord]['Line'] = int(recStkY)
                        # self.output.recGeom[self.nRecRecord]['Point'] = int(recStkX)
                        # self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1   # the single digit point index is used to indicate block nr
                        # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'  # can do this in one go at the end
                        # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0   # not needed; zero when initialized
                        # self.output.recGeom[self.nRecRecord]['East'] = recLocX
                        # self.output.recGeom[self.nRecRecord]['North'] = recLocY
                        # self.output.recGeom[self.nRecRecord]['LocX'] = recX   # x-component of 3D-location
                        # self.output.recGeom[self.nRecRecord]['LocY'] = recY   # y-component of 3D-location
                        # self.output.recGeom[self.nRecRecord]['Elev'] = recZ   # z-value not affected by transform
                        # self.output.recGeom[self.nRecRecord]['Uniq'] = 1      # We want to use Uniq == 1 later, to remove empty records

                        time = self.elapsedTime(time, 9)    ###

                        # apply self.output.recGeom.resize(N) when more memory is needed, after cleaning duplicates
                        arraySize = self.output.recGeom.shape[0]
                        if self.nRecRecord + 100 > arraySize:                               # room for less than 100 left ?
                            time = perf_counter()
                            self.output.recGeom = np.unique(self.output.recGeom)            # first remove all duplicates
                            arraySize = self.output.recGeom.shape[0]                        # get array size (again)
                            self.nRecRecord = arraySize                                     # adjust nRecRecord to the next available spot
                            self.output.recGeom.resize(arraySize + 10000, refcheck=False)   # append 10000 more records
                            time = self.elapsedTime(time, 10)    ###

                        time = perf_counter()

                        # time to work with the relation records, now we have both a valid src-point and rec-point;
                        self.nNewRecLine = int(recStkY)
                        if self.nNewRecLine != self.nOldRecLine:                # we're on a 'new' receiver line and need a new rel-record
                            self.nOldRecLine = self.nNewRecLine                 # save current line number
                            self.nRelRecord += 1                                # increment relation record number

                            # create new relation record; fill it in completely
                            numbaSetRelationRecord(self.output.relGeom, self.nRelRecord, srcStkX, srcStkY, nBlock, self.nShotPoint, recStkY, recStkX, recStkX)
                            # self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStkY)
                            # self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStkX)
                            # self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
                            # self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
                            # self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStkY)
                            # self.output.relGeom[self.nRelRecord]['RecMin'] = int(recStkX)
                            # self.output.relGeom[self.nRelRecord]['RecMax'] = int(recStkX)
                            # self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
                            # self.output.relGeom[self.nRelRecord]['Uniq'] = 1    # needed for compacting array later (remove empty records)
                        else:
                            # existing relation record; just update min/max rec stake numbers
                            numbaFixRelationRecord(self.output.relGeom, self.nRelRecord, recStkX)
                            # recMin = min(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMin'])
                            # recMax = max(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMax'])
                            # self.output.relGeom[self.nRelRecord]['RecMin'] = recMin
                            # self.output.relGeom[self.nRelRecord]['RecMax'] = recMax

                        time = self.elapsedTime(time, 11)    ###

                        # apply self.output.relGeom.resize(N) when more memory is needed
                        arraySize = self.output.relGeom.shape[0]
                        if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
                            time = perf_counter()
                            self.output.relGeom.resize(arraySize + 10000, refcheck=False)   # append 10000 more records

                            time = self.elapsedTime(time, 12)    ###

    def geomTemplate3(self, nBlock, block, template, templateOffset):
        """Use numpy arrays instead of iterating over the growList.
        This provides a much faster approach then using the growlist.

        The function is however still rather slow.
        Use time.perf_counter() to analyse bottlenecks

        Note: a template is a collection of shots that all record in the same set of receivers.
        Upon completion, the template is rolled, and the process starts over again
        Therefore:
        a) the shots from a template can directly be appended to the src list
        b) the same can be done for the receivers, as far as they are not already included in the rec list
        c) Per shot, several relation records  need to be created.
           Apart from the source info, these relation records are identical for all shots in the template
        """

        # convert the template offset to a numpy array
        npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

        # begin thread progress code
        if QThread.currentThread().isInterruptionRequested():                   # maybe stop at each shot...
            raise StopIteration

        self.nTemplate += 1                                                     # work on a new template
        threadProgress = (100 * self.nTemplate) // self.nTemplates              # apply integer divide
        if threadProgress > self.threadProgress:
            self.threadProgress = threadProgress
            self.progress.emit(threadProgress + 1)
        # end thread progress code

        nShotPoint = self.nShotPoint                                            # create a copy for relation records creation later on

        # iterate over all seeds in a template; make sure we deal wih *source* seeds
        for srcSeed in template.seedList:
            if not srcSeed.bSource:                                             # work with source seeds here
                continue

            # we are in a source seed right now; use the numpy array functions to apply selection criteria
            srcArray = srcSeed.pointArray + npTemplateOffset

            if not block.borders.srcBorder.isNull():                            # deal with block's source border if it isn't null()
                I = pointsInRect(srcArray, block.borders.srcBorder)
                if I.shape[0] == 0:
                    continue
                srcArray = srcArray[I, :]                                       # filter the source array

            for src in srcArray:                                                # iterate over all sources
                # useful source point; pointsInRect passed it through

                # determine line & stake nrs for source point
                srcX = src[0]
                srcY = src[1]

                srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)            # get line and point indices
                srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)            # we need global positions

                numbaSetPointRecord(self.output.srcGeom, self.nShotPoint, srcStkY, srcStkX, nBlock, srcLocX, srcLocY, src)
                self.nShotPoint += 1                                            # increment for the next shot

        nRelRecord = -1                                                         # start with invalid value (will be 0 for 1st record)
        nOldRecLine = -999999                                                   # start with 'funny' value

        # now iterate over all seeds to find the receivers
        for recSeed in template.seedList:                                       # iterate over all rec seeds in a template
            if recSeed.bSource:                                                 # work with receiver seeds here
                continue

            # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
            recPoints = recSeed.pointArray + npTemplateOffset

            if not block.borders.recBorder.isNull():                            # deal with block's receiver border if it isn't null()
                I = pointsInRect(recPoints, block.borders.recBorder)
                if I.shape[0] == 0:
                    continue
                else:
                    recPoints = recPoints[I, :]

            for rec in recPoints:                                               # iterate over all receivers
                # determine line & stake nrs for receiver point
                recX = rec[0]
                recY = rec[1]

                recStkX, recStkY = self.st2Transform.map(recX, recY)            # get line and point indices
                recLocX, recLocY = self.glbTransform.map(recX, recY)            # we need global positions

                recPoint = int(recStkX)
                recLine = int(recStkY)

                # the problem with receiver records is that they overlap by some 90% from shot to shot.
                # rather than adding all receivers first, followed by removing all duplicates later,
                # we use a nested dictionary to find out if a rec station already exists in our 'list'
                # sofar,block nr (=index) has been neglected, but this could be added as a third nesting level

                try:                                                            # has it been used before ?
                    _ = self.output.recDict[recLine][recPoint]                  # test with dummy variable
                except KeyError:
                    self.output.recDict[recLine][recPoint] = self.nRecRecord    # use self.nRecRecord to create an entry in the self.output.recGeom table

                    numbaSetPointRecord(self.output.recGeom, self.nRecRecord, recStkY, recStkX, nBlock, recLocX, recLocY, rec)
                    self.nRecRecord += 1                                        # increment for the next receiver

                    arraySize = self.output.recGeom.shape[0]
                    if self.nRecRecord + 1000 > arraySize:                      # room for less than 1000 left ?
                        self.output.recGeom.resize(arraySize + 10000, refcheck=False)    # append 10000 more receiver records

                # now create the framework for relation records for all shots in the template
                # adapt these records with slight modifications for all  shots in the template

                if recLine != nOldRecLine:                                      # we're on a 'new' receiver line and need a new rel-record
                    nOldRecLine = recLine                                       # save current line number
                    nRelRecord += 1                                             # increment relation record number (that started at -1)

                    self.output.relTemp[nRelRecord]['RecLin'] = recStkY         # create new relation record; fill it in with all rec info
                    self.output.relTemp[nRelRecord]['RecMin'] = recStkX
                    self.output.relTemp[nRelRecord]['RecMax'] = recStkX
                    self.output.relTemp[nRelRecord]['RecInd'] = nBlock % 10 + 1

                    arraySize = self.output.relTemp.shape[0]                    # do we have enough space for more relation records ?
                    if nRelRecord + 10 > arraySize:                             # room for less than 50 left ?
                        self.output.relTemp.resize(arraySize + 100, refcheck=False)    # append 100 more records

                else:
                    # existing relation record; just update min/max rec stake numbers
                    self.output.relTemp[nRelRecord]['RecMin'] = min(recStkX, self.output.relTemp[nRelRecord]['RecMin'])
                    self.output.relTemp[nRelRecord]['RecMax'] = max(recStkX, self.output.relTemp[nRelRecord]['RecMax'])

        # at this moment:
        # nRelRecord holds the nr of relation records for each shot in this template
        # self.output.relTemp holds the receiver info for these records
        # self.output.srcGeom holds the source records that made it through the selection
        # nShotPoint holds the first shot point for which relation records need to be created

        for i in range(nShotPoint, self.nShotPoint):                            # these are the shots from this template, we have added

            # apply self.output.relGeom.resize(N) when more memory is needed
            arraySize = self.output.relGeom.shape[0]
            if self.nRelRecord + 1000 > arraySize:                              # room for less than 1,000 left ?
                self.output.relGeom.resize(arraySize + 10000, refcheck=False)   # append 10,000 more records

            srcLin = self.output.srcGeom[i]['Line']
            srcPnt = self.output.srcGeom[i]['Point']
            srcInd = self.output.srcGeom[i]['Index']                            # the single digit point index is used to indicate block nr

            for j in range(nRelRecord + 1):                                     # every shot needs this many relation records; read the back and complete them

                recLin = self.output.relTemp[j]['RecLin']
                recMin = self.output.relTemp[j]['RecMin']
                recMax = self.output.relTemp[j]['RecMax']

                # recInd equals srcInd (both are linked to the block number) so it is not entered separately
                numbaSetRelationRecord(self.output.relGeom, self.nRelRecord, srcLin, srcPnt, srcInd, i + 1, recLin, recMin, recMax)
                self.nRelRecord += 1

    def setupBinFromGeometry(self, fullAnalysis) -> bool:
        """this routine is used for both geometry files and SPS files"""

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0

        # Now do the binning
        if fullAnalysis:
            success = self.binFromGeometry4(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromGeometry4(False)

    def binFromGeometry4(self, fullAnalysis) -> bool:
        """
        all binning methods (cmp, plane, sphere) implemented, using numpy arrays, rather than a for-loop.
        On 09/04/2024 the earlier implementations of binFromGeometry v1 to v3 have been removed.
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

        # to be sure; sort the three geometry arrays in the proper order: index; line; point
        self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
        self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

        assert self.output.relGeom[0]['SrcLin'] == self.output.srcGeom[0]['Line'], 'Line error in geometry files'
        assert self.output.relGeom[0]['SrcPnt'] == self.output.srcGeom[0]['Point'], 'Point error in geometry files'
        assert self.output.relGeom[0]['SrcInd'] == self.output.srcGeom[0]['Index'], 'Index error in geometry files'

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
        # assume the receivers have been sorted based on index; line; point

        self.nShotPoint = 0
        self.nShotPoints = self.output.srcGeom.shape[0]

        try:
            for index, srcRecord in enumerate(self.output.srcGeom):

                if srcRecord['InUse'] == 0:                                     # this record has been disabled
                    continue

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

                if maxRecord <= minRecord:                                      # no receivers found; move to next shot !
                    continue                                                    # test on <= instead of == in case maxRecord = 0

                relSlice = self.output.relGeom[minRecord:maxRecord]             # create a slice out of the relation file

                recIndex = relSlice[0]['RecInd']
                minLine = np.min(relSlice['RecLin'])
                maxLine = np.max(relSlice['RecLin'])
                minMinPoint = np.min(relSlice['RecMin'])
                maxMinPoint = np.max(relSlice['RecMin'])
                minMaxPoint = np.min(relSlice['RecMax'])
                maxMaxPoint = np.max(relSlice['RecMax'])

                if minMinPoint == maxMinPoint and minMaxPoint == maxMaxPoint:   # determine if it is a purely square block
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
                    recArray = np.zeros(shape=(0), dtype=pntType1)             # setup empty numpy array, to append data to
                    for relRecord in relSlice:
                        recInd = relRecord['RecInd']
                        recLin = relRecord['RecLin']
                        recMin = relRecord['RecMin']
                        recMax = relRecord['RecMax']

                        # select appropriate receivers on a receiver line
                        I = (self.output.recGeom['Index'] == recInd) & (self.output.recGeom['Line'] == recLin) & (self.output.recGeom['Point'] >= recMin) & (self.output.recGeom['Point'] <= recMax)
                        if np.count_nonzero(I) == 0:
                            continue                                            # no receivers found; move to next shot !

                        recLine = self.output.recGeom[I]                        # select the filtered receivers
                        recArray = np.concatenate((recArray, recLine))          # need to supply arrays to be concatenated as a tuple !
                        # See: https://stackoverflow.com/questions/50997928/typeerror-only-integer-scalar-arrays-can-be-converted-to-a-scalar-index-with-1d

                # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
                # we combine recPoints with a source point to create cmp array, define offsets, etc...

                # we are NOT DEALING with the block's src border; this should have been done while generating geometry
                # we are NOT DEALING with the block's rec border; this should have been done while generating geometry

                # but we are dealing with the "InUse" attribute, that allows for killing a point in QGIS

                I = recArray['InUse'] > 0
                if np.count_nonzero(I) == 0:
                    continue                                                    # no receivers found; move to next shot !
                recArray = recArray[I]                                          # select the filtered receivers

                # it is ESSENTIAL that any orphans & duplicates in recPoints have been removed at this stage
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

                I = pointsInRect(cmpPoints, self.output.rctOutput)              # find the cmp locations that contribute to the output area
                if I.shape[0] == 0:
                    continue

                cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array
                recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this for offsets

                size = recPoints.shape[0]
                offArray = np.zeros(shape=(size, 3), dtype=np.float32)          # allocate the offset array according to rec array
                offArray = recPoints - src                                      # define the offset array

                I = pointsInRect(offArray, self.offset.rctOffsets)
                if I.shape[0] == 0:
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
                                self.output.anaOutput[nx, ny, fold, 0] = int(stkX)
                                self.output.anaOutput[nx, ny, fold, 1] = int(stkY)
                                self.output.anaOutput[nx, ny, fold, 2] = fold + 1       # to make fold run from 1 to N
                                self.output.anaOutput[nx, ny, fold, 3] = src[0]
                                self.output.anaOutput[nx, ny, fold, 4] = src[1]
                                self.output.anaOutput[nx, ny, fold, 5] = recPoints[count, 0]
                                self.output.anaOutput[nx, ny, fold, 6] = recPoints[count, 1]
                                self.output.anaOutput[nx, ny, fold, 7] = cmpPoints[count, 0]
                                self.output.anaOutput[nx, ny, fold, 8] = cmpPoints[count, 1]
                                self.output.anaOutput[nx, ny, fold, 9] = totalTime[count]
                                self.output.anaOutput[nx, ny, fold, 10] = hypArray[count]
                                self.output.anaOutput[nx, ny, fold, 11] = aziArray[count]
                                # self.output.anaOutput[nx, ny, fold, 12] = -1

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
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            return False

        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None

        return True

    def setupBinFromTemplates(self, fullAnalysis) -> bool:
        """this routine is used for working from templates only"""

        self.binning.slowness = (1000.0 / self.binning.vint) if self.binning.vint > 0.0 else 0.0

        if self.nShotPoints == -1:                                              # calcNoShotPoints has been skipped ?!?
            raise ValueError('nr shot points must be known at this point')

        if fullAnalysis:
            success = self.binFromTemplates(True)
            self.output.anaOutput.flush()                                       # flush results to hard disk
            return success
        else:
            return self.binFromTemplates(False)

    # can't use @jit here, as numba does not support handling exceptions (try -> except)
    # See: http://numba.pydata.org/numba-doc/dev/reference/pysupported.html
    # See: https://stackoverflow.com/questions/18176602/how-to-get-the-name-of-an-exception-that-was-caught-in-python for workaround
    def binFromTemplates(self, fullAnalysis) -> bool:
        try:
            self.calcPointArrays()                                              # first set up all point arrays
            for block in self.blockList:                                        # get all blocks
                for template in block.templateList:                             # get all templates
                    # how deep is the list ?
                    length = len(template.rollList)

                    assert length == 3, 'there must always be 3 roll steps / grow steps'

                    if length == 0:
                        off0 = QVector3D()                                      # always start at (0, 0, 0)
                        self.binTemplate6(block, template, off0, fullAnalysis)

                    elif length == 1:
                        # get the template boundaries
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            self.binTemplate6(block, template, off0, fullAnalysis)

                    elif length == 2:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
                            off0 += template.rollList[0].increment * i
                            for j in range(template.rollList[1].steps):
                                off1 = off0 + template.rollList[1].increment * j
                                self.binTemplate6(block, template, off1, fullAnalysis)
                                # print("length = 2. Template offset: ", off1.x(), off1.y() )

                    elif length == 3:
                        for i in range(template.rollList[0].steps):
                            off0 = QVector3D()                                  # always start at (0, 0, 0)
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
            self.errorText = 'binning from templates cancelled by user'
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

        self.calcFoldAndOffsetEssentials()

        if fullAnalysis:
            self.calcRmsOffsetValues()
            self.calcUniqueFoldValues()
            self.calcOffsetAndAzimuthDistribution()
        else:
            self.output.anaOutput = None
        return True

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

            if not block.borders.srcBorder.isNull():                            # deal with block's source  border if it isn't null()
                I = pointsInRect(srcArray, block.borders.srcBorder)
                if I.shape[0] == 0:
                    continue
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

                    if not block.borders.recBorder.isNull():                    # deal with block's receiver border if it isn't null()
                        I = pointsInRect(recPoints, block.borders.recBorder)
                        if I.shape[0] == 0:
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

                    I = pointsInRect(cmpPoints, self.output.rctOutput)
                    if I.shape[0] == 0:
                        continue

                    cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array
                    recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

                    size = recPoints.shape[0]
                    offArray = np.zeros(shape=(size, 3), dtype=np.float32)      # allocate the offset array according to rec array
                    offArray = recPoints - src                                  # fill the offset array with  (x,y,z) values

                    I = pointsInRect(offArray, self.offset.rctOffsets)
                    if I.shape[0] == 0:
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
                                if fold < self.grid.fold:                       # prevent overwriting next bin
                                    # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)
                                    # line & stake nrs for reporting in extended np-array

                                    # from numpy documentation: it follows that x[0, 2] == x[0][2] though the second case is less efficient;
                                    # as a new temporary array is created after the first index that is subsequently indexed by 2.
                                    # for this reason I replaced all [a][b][c][d] indices by [a, b, c, d]

                                    stkX, stkY = self.st2Transform.map(cmpX, cmpY)
                                    self.output.anaOutput[nx, ny, fold, 0] = int(stkX)
                                    self.output.anaOutput[nx, ny, fold, 1] = int(stkY)
                                    self.output.anaOutput[nx, ny, fold, 2] = fold + 1           # to make fold run from 1 to N
                                    self.output.anaOutput[nx, ny, fold, 3] = src[0]
                                    self.output.anaOutput[nx, ny, fold, 4] = src[1]
                                    self.output.anaOutput[nx, ny, fold, 5] = recPoints[count, 0]
                                    self.output.anaOutput[nx, ny, fold, 6] = recPoints[count, 1]
                                    self.output.anaOutput[nx, ny, fold, 7] = cmpPoints[count, 0]
                                    self.output.anaOutput[nx, ny, fold, 8] = cmpPoints[count, 1]
                                    self.output.anaOutput[nx, ny, fold, 9] = totalTime[count]
                                    self.output.anaOutput[nx, ny, fold, 10] = hypArray[count]
                                    self.output.anaOutput[nx, ny, fold, 11] = aziArray[count]
                                    # self.output.anaOutput[nx, ny, fold, 12] = -1

                            # all selection criteria have been fullfilled; use the trace
                            self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
                            self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
                            self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

                        # rather than checking nx, ny & fold, use exception handling to deal with index errors
                        # note: the other exceptions are handled in binFromTemplates()
                        except IndexError:
                            continue

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
        self.output.minOffset[self.output.minOffset == np.Inf] = np.NINF

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
        self.output.maxOffset[self.output.maxOffset == np.NINF] = np.inf

        # calc min offset against min (inf) values
        self.message.emit('Calc min/max offsets - step 8/9')
        self.progress.emit(80)
        self.output.minMaxOffset = self.output.maxOffset.min()

        # replace (inf) by (-inf) for max values
        self.message.emit('Calc min/max offsets - step 9/9')
        self.progress.emit(90)
        self.output.maxOffset[self.output.maxOffset == np.Inf] = np.NINF

        self.progress.emit(100)
        return True

    def calcUniqueFoldValues(self) -> bool:
        """code to calculate unique offsets as a post-processing step"""
        if self.unique.apply is False:                                          # slot offsets and azimuths and prune data
            return False

        if self.output.anaOutput is None:                                       # this array is essential to calculate unique fold
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

                slottedOffset = slice2D[:, 10]                              # grab 10th item of 2nd dimension (=offset)
                slottedOffset = slottedOffset * offScalar
                slottedOffset = np.round(slottedOffset)
                slottedOffset = slottedOffset * offSlot
                if writeBack:
                    slice2D[:, 10] = slottedOffset                          # write it back into the 2D slice

                slottedAzimuth = slice2D[:, 11]                             # grab 11th item of 2nd dimension (=azimuth)
                slottedAzimuth = slottedAzimuth * aziScalar
                slottedAzimuth = np.round(slottedAzimuth)
                slottedAzimuth = slottedAzimuth * aziSlot
                if writeBack:
                    slice2D[:, 11] = slottedAzimuth                         # write it back into the 2D slice

                slottedOffAzi = np.column_stack((slottedOffset, slottedAzimuth))
                _, indices = np.unique(slottedOffAzi, return_index=True, axis=0)

                for index in indices:                                       # flag unique offset, azimuth values
                    slice2D[index, 12] = -1.0

                slice2D = slice2D[slice2D[:, -1].argsort()]                 # sort the traces on last column (unique -1 flag)
                self.output.anaOutput[row, col, 0:fold, :] = slice2D        # put sorted traces back into analysis array

                uniqueFld = np.count_nonzero(slice2D[:, -1], axis=0)        # get unique fold count from last column (nr12)
                if uniqueFld > 0:
                    minOffset = np.min(slice2D[0:uniqueFld, 10], axis=0)    # first dimension may be affected by 0 values
                    maxOffset = np.max(slice2D[0:uniqueFld, 10], axis=0)    # first dimension may be affected by 0 values
                else:
                    minOffset = 0.0                                         # no traces available
                    maxOffset = 0.0                                         # no traces available

                self.output.binOutput[row, col] = uniqueFld                 # adjust fold value table
                self.output.minOffset[row, col] = minOffset                 # adjust min offset table
                self.output.maxOffset[row, col] = maxOffset                 # adjust max offset table

        return True

    def calcRmsOffsetValues(self) -> bool:
        """code to calculate RMS offset increments as a post-processing step"""

        if self.output.anaOutput is None:                                       # this array is essential to calculate rms offsets
            return False

        self.message.emit('Calc RMS offset increments')

        rows = self.output.anaOutput.shape[0]                                   # get dimensions from analysis array itself
        cols = self.output.anaOutput.shape[1]

        # by defining the array only here, we prevent having a 'null' array that would result in a plot with 'empty' rms values
        self.output.rmsOffset = np.zeros(shape=(rows, cols), dtype=np.float32)  # start with empty array of the right size and type
        self.output.rmsOffset.fill(np.NINF)                                     # start max offset with -inf (use np.full instead)

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
                            continue                                                    # rms values prefilled with np.NINF

                        slice2D = self.output.anaOutput[row, col, 0:fold, :]            # get all available traces belonging to this bin
                        offset1D = slice2D[:, 10]                                       # grab 10th item of 2nd dimension (=offset)

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

    def calcOffsetAndAzimuthDistribution(self) -> bool:
        """code to calculate offsets / azimuth distribution as a post-processing step"""

        if self.output.anaOutput is None:                                       # this array is essential to calculate the distribution
            return False

        self.message.emit('Calc offset/azimuth distribution - 1/2')
        offsets, azimuth, noData = numbaSliceStats(self.output.anaOutput, self.unique.apply)
        if noData:
            return False

        dA = 5.0                                                                # azimuth increments
        dO = 100.0                                                              # offsets increments

        aMin = -180.0                                                           # max x-scale
        aMax = 180.0                                                            # max x-scale
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
        # if len(self.blockList) == 0:
        #     QMessageBox.warning(None, e, 'A survey needs at least one block')
        #     return False

        # for block in self.blockList:
        #     if len(block.templateList) == 0:
        #         QMessageBox.warning(None, e, 'Each block needs at least one template')
        #         return False

        for block in self.blockList:
            for template in block.templateList:

                while len(template.rollList) < 3:                               # make sure there are always 3 roll steps in the list
                    template.rollList.insert(0, RollTranslate())

                for seed in template.seedList:
                    if seed.type == SeedType.rollingGrid or seed.type == SeedType.fixedGrid:    # rolling or fixed grid
                        while len(seed.grid.growList) < 3:                      # make sure there are three grow steps for every grid seed
                            seed.grid.growList.insert(0, RollTranslate())

                    elif seed.type == SeedType.well:                            # well site; check for errors
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

    def calcPointArrays(self):
        # this routine relies on self.checkIntegrity() to spot any errors
        for block in self.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    seed.calcPointArray()                                   # setup the numpy arrays for more efficient processing

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

        # Only for patterns create a pointlist in the grid-seed; don't use it for normal 'rolling' or 'fixed' seeds
        for pattern in self.patternList:
            for seed in pattern.seedList:
                seed.pointList = seed.grid.calcPointList(seed.origin)           # calculate the point list for all seeds

    def createBasicSkeleton(self, nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=2):

        assert nBlocks > 0, 'Need at least 1 block'
        assert nTemplates > 0, 'Need at least 1 template'
        assert nSrcSeeds > 0, 'Need at least 1 source seed'
        assert nRecSeeds > 0, 'Need at least 1 receiver seed'
        # nPatterns may be zero

        self.blockList = []                                                     # make sure, we start with an empty list

        for nBlock in range(nBlocks):
            blockName = f'block-{nBlock + 1}'                                   # get suitable block name
            block = RollBlock(blockName)                                        # create block
            self.blockList.append(block)                                        # add block to survey object

            for nTemplate in range(nTemplates):
                templateName = f'template-{nTemplate + 1}'                      # get suitable template name
                template = RollTemplate(templateName)                           # create template

                roll1 = RollTranslate()                                         # create the 'first' roll object
                template.rollList.append(roll1)                                 # add roll object to template's rollList
                roll2 = RollTranslate()                                         # create a 'second' roll object
                template.rollList.append(roll2)                                 # add roll object to template's rollList

                # Todo: Need to add this for completeness; but consequently will have to test the code for every rollList appearance !!!
                # roll3 = RollTranslate()                                         # create a 'second' roll object
                # template.rollList.append(roll3)                                 # add roll object to template's rollList

                block.templateList.append(template)                             # add template to block object

                for nSrcSeed in range(nSrcSeeds):
                    seedName = f'src-{nSrcSeed + 1}'                            # create a source seed object
                    seedSrc = RollSeed(seedName)
                    seedSrc.bSource = True
                    seedSrc.color = QColor('#77FF8989')

                    growR1 = RollTranslate()                                    # create a 'lines' grow object
                    seedSrc.grid.growList.append(growR1)                        # add grow object to seed
                    growR2 = RollTranslate()                                    # create a 'points' grow object
                    seedSrc.grid.growList.append(growR2)                        # add grow object to seed
                    growR3 = RollTranslate()                                    # create a 'points' grow object
                    seedSrc.grid.growList.append(growR3)                        # add grow object to seed

                    template.seedList.append(seedSrc)                           # add seed object to template

                for nRecSeed in range(nRecSeeds):
                    seedName = f'rec-{nRecSeed + 1}'                            # create a receiver seed object
                    seedRec = RollSeed(seedName)
                    seedRec.bSource = False
                    seedRec.color = QColor('#7787A4D9')

                    growR1 = RollTranslate()                                    # create a 'lines' grow object
                    seedRec.grid.growList.append(growR1)                        # add grow object to seed's growlist
                    growR2 = RollTranslate()                                    # create a 'points' grow object
                    seedRec.grid.growList.append(growR2)                        # add grow object to seed
                    growR3 = RollTranslate()                                    # create a 'points' grow object
                    seedRec.grid.growList.append(growR3)                        # add grow object to seed

                    template.seedList.append(seedRec)                           # add seed object to template

        self.patternList = []                                                   # make sure, we start with an empty list
        for nPattern in range(nPatterns):
            patternName = f'pattern-{nPattern + 1}'                             # create suitable pattern name
            pattern = RollPattern(patternName)                                  # create the pattern
            self.patternList.append(pattern)                                    # add pattern to patternList

            seed = RollPatternSeed()                                            # create a new seed (we need just one)
            pattern.seedList.append(seed)                                       # add this seed to pattern's seedList

            for _ in range(3):                                                  # do this three times
                growStep = RollTranslate()                                      # create a translation
                seed.grid.growList.append(growStep)                             # add translation to seed's grid-growlist

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

        # we also need to update the template-seeds giving them the right pattern type
        # here we need to make some uptimizations; with a marine survey you can easily get 16,000 templates, or 16,000 SPs, as there is one shot per template
        # But each shot comes with some 11 seeds; one for the source and 10 for 10 streamers. This results in 176,000 seeds.
        # only a few seeds are shown at the same time, as it requires a signficant zoom to show individual seeds
        # todo: initialize the seed's point figures and pattern figures just before they are painted (and NOT here).
        # this should significantly speed up initial loading of an existing survey.
        # Start with a None object, take it from there.

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
        else:
            # earlier derived result, from blocks -> templates -> seeds
            return self.boundingBox

    # painting can take a long time. Sometimes you may want to kill painting by interupting a half complete paint call.
    # this can be done by processing a keyboardInterrupt. I think (right now) you need to have the message pump working, for this to have any effect.
    # QtGui.qApp.processEvents() - called at certain points in the paint() call
    # See: https://stackoverflow.com/questions/23027447/how-to-set-push-button-to-keyboard-interrupt-in-pyqt
    # See: https://stackoverflow.com/questions/1353823/handling-keyboardinterrupt-in-a-kde-python-application
    # See: https://www.geeksforgeeks.org/how-to-create-a-custom-keyboardinterrupt-in-python/
    # See: https://stackoverflow.com/questions/51485285/stop-a-while-loop-by-escape-key
    # See: https://pypi.org/project/dvg-pyqtgraph-threadsafe/ for threadsafe plotting with pyqtgraph

    def paint(self, painter, option, _):
        # just to check if we can interrupt painting using Ctrl+C
        try:
            self.paint_OriginalRoutine(painter, option, _)
        except KeyboardInterrupt:
            return

    def paint_OriginalRoutine(self, painter, option, _):
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

            lod = option.levelOfDetailFromTransform(painter.worldTransform()) * self.lodScale
            # print('LOD = ' + str(lod))

            if lod < config.lod0:                                               # so small; just paint the survey outline
                painter.setPen(pg.mkPen('k'))                                   # use a black pen for borders
                painter.setBrush(pg.mkBrush((64, 64, 64, 255)))                 # dark grey solid brush
                painter.drawRect(self.boundingRect())                           # that's all that needs to be painted
                return

            # a survey has only one binning output area; show this in black if the self.paintDetails flag has been set accordingly
            if self.output.rctOutput.isValid() and self.paintDetails & PaintDetails.binArea:
                painter.setPen(config.binAreaPen)
                painter.setBrush(QBrush(QColor(config.binAreaColor)))
                painter.drawRect(self.output.rctOutput)

            for block in self.blockList:                                        # get all blocks
                for template in block.templateList:                             # get all templates
                    for seed in template.seedList:                              # get all seeds
                        seed.rendered = False                                   # reset rendered flag for non-rolling seeds

            for block in self.blockList:                                        # get all blocks
                if block.boundingBox.intersects(vb):                            # is block within viewbox ?

                    # a survey may have more than a single block; therefore do this for each block
                    if self.paintDetails & PaintDetails.recArea:
                        painter.setPen(config.recAreaPen)
                        painter.setBrush(QBrush(QColor(config.recAreaColor)))
                        painter.drawRect(block.recBoundingRect)

                    if self.paintDetails & PaintDetails.srcArea:
                        painter.setPen(config.srcAreaPen)
                        painter.setBrush(QBrush(QColor(config.srcAreaColor)))
                        painter.drawRect(block.srcBoundingRect)

                    if self.paintDetails & PaintDetails.cmpArea:
                        painter.setPen(config.cmpAreaPen)
                        painter.setBrush(QBrush(QColor(config.cmpAreaColor)))
                        painter.drawRect(block.cmpBoundingRect)

                    painter.setPen(pg.mkPen(0.5))                               # use a grey pen for template borders
                    painter.setBrush(pg.mkBrush((192, 192, 192, 32)))           # grey & semi-transparent, use for all templates

                    if self.paintMode == PaintMode.justBlocks:                  # just paint the blocks bounding box, irrespective of LOD
                        painter.drawRect(block.boundingBox)                     # draw bloc's rectangle
                        continue                                                # we've done enough

                    painter.setBrush(pg.mkBrush((192, 192, 192, 3)))            # grey & semi-transparent, use for all templates

                    for template in block.templateList:                         # get all templates
                        length = len(template.rollList)                         # how deep is the list ?

                        ### todo; fix this later in land wizard
                        #   assert length == 3, 'there must always be 3 roll steps / grow steps in each template'

                        if length == 0:
                            offset = QVector3D()                                # always start at (0, 0, 0)
                            templt = template.totTemplateRect                   # no translation required
                            if not templt.intersects(vb):
                                continue                                        # outside viewbox; skip it

                            if lod < config.lod1 or self.paintMode == PaintMode.justTemplates:  # so small; just paint the template outline
                                templt &= self.boundingBox                      # we need to restrict it
                                painter.drawRect(templt)                        # draw template rectangle
                            else:
                                self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 1:
                            # get the template boundaries
                            for i in range(template.rollList[0].steps):
                                offset = QVector3D()                            # always start at (0, 0, 0)
                                offset += template.rollList[0].increment * i
                                templt = template.totTemplateRect.translated(offset.toPointF())  # we now have the correct location
                                if not templt.intersects(vb):
                                    continue                                    # outside viewbox; skip it

                                if lod < config.lod1 or self.paintMode == PaintMode.justTemplates:  # so small; just paint the template outline
                                    templt &= self.boundingBox                  # we need to restrict it
                                    painter.drawRect(templt)                    # draw template rectangle
                                else:
                                    self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 2:
                            for i in range(template.rollList[0].steps):
                                for j in range(template.rollList[1].steps):
                                    offset = QVector3D()                        # always start at (0, 0, 0)
                                    offset += template.rollList[0].increment * i
                                    offset += template.rollList[1].increment * j
                                    templt = template.totTemplateRect.translated(offset.toPointF())  # we now have the correct location
                                    if not templt.intersects(vb):
                                        continue                                # outside viewbox; skip it

                                    if lod < config.lod1 or self.paintMode == PaintMode.justTemplates:  # so small; just paint the template outline
                                        templt &= self.boundingBox              # we need to restrict it
                                        painter.drawRect(templt)                # draw template rectangle
                                    else:
                                        self.paintTemplate(painter, vb, lod, template, offset)

                        elif length == 3:
                            for i in range(template.rollList[0].steps):
                                for j in range(template.rollList[1].steps):
                                    for k in range(template.rollList[2].steps):
                                        offset = QVector3D()                    # always start at (0, 0, 0)
                                        offset += template.rollList[0].increment * i
                                        offset += template.rollList[1].increment * j
                                        offset += template.rollList[2].increment * k
                                        templt = template.totTemplateRect.translated(offset.toPointF())  # we now have the correct location
                                        if not templt.intersects(vb):
                                            continue                            # outside viewbox; skip it

                                        if lod < config.lod1 or self.paintMode == PaintMode.justTemplates:  # so small; just paint the template outline
                                            templt &= self.boundingBox          # we need to restrict it
                                            painter.drawRect(templt)            # draw template rectangle
                                        else:
                                            self.paintTemplate(painter, vb, lod, template, offset)
                        else:
                            # do something recursively; not  implemented yet
                            raise NotImplementedError('More than three roll steps currently not allowed.')

            # done painting; next time maybe more details required
            self.mouseGrabbed = False

    def paintTemplate(self, painter, viewbox, lod, template, templateOffset):
        # we are now painting a template; this is a bit more complex. We need to paint the seeds in the template
        # we need to check if the seed is within the viewbox; if not, we skip it
        # we need to check if the seed is within the block's src/rec area; if not, we skip it
        # we need to check the level-of-detail (lod) to decide whether to draw a line, a series of points or a series of patterns
        # this is controlled by the lod, the paintMode and the paintDetails flags

        for seed in template.seedList:                                          # iterate over all seeds in a template
            painter.setPen(pg.mkPen(seed.color, width=2))                       # use a solid pen, 2 pixels wide
            if seed.bSource is True:
                paintDetail = self.paintDetails >> 3                            # divide by 8 to make source flag equal to receiver flag
            else:
                paintDetail = self.paintDetails                                 # we have a receiver seed; no further action required

            if seed.type < SeedType.circle and seed.rendered is False:          # grid based seed, rolling or fixed
                if seed.type == SeedType.fixedGrid:                             # no rolling along; fixed grid
                    templateOffset = QVector3D()                                # no offset applicable
                    seed.rendered = True                                        # paint fixed grid only once

                length = len(seed.grid.growList)                                # how deep is the grow list ?

                assert length == 3, 'there must always be 3 roll steps / grow steps'

                if length == 0:
                    offset = QVector3D()                                        # always start at (0, 0, 0)
                    offset += templateOffset                                    # start here
                    salvo = seed.grid.salvo.translated(offset.toPointF())       # move the line into place
                    salvo = clipLineF(salvo, seed.blockBorder)                  # check line against block's src/rec border
                    salvo = clipLineF(salvo, viewbox)                           # check line against viewbox

                    if salvo.isNull():
                        return

                    if self.mouseGrabbed:                                       # just draw lines
                        if paintDetail & PaintDetails.recLin != PaintDetails.none:
                            painter.drawLine(salvo)
                        return

                    if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # just draw lines
                        if paintDetail & PaintDetails.recLin != PaintDetails.none:
                            painter.drawLine(salvo)
                    else:
                        seedOrigin = offset + seed.origin                       # start at templateOffset and add seed's origin
                        if containsPoint3D(seed.blockBorder, seedOrigin):       # is it within block limits ?
                            if containsPoint3D(viewbox, seedOrigin):            # is it within the viewbox ?
                                if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                                    painter.drawPicture(seedOrigin.toPointF(), seed.getPointPicture())   # paint seed picture
                                if lod > config.lod3 and seed.patternPicture is not None and self.paintMode == PaintMode.all:       # paint pattern picture
                                    if paintDetail & PaintDetails.recPat != PaintDetails.none:
                                        painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 1:
                    offset = QVector3D()                                        # always start at (0, 0, 0)
                    offset += templateOffset                                    # start here
                    salvo = seed.salvo.grid.translated(offset.toPointF())       # move the line into place
                    salvo = clipLineF(salvo, seed.blockBorder)                  # check line against block's src/rec border
                    salvo = clipLineF(salvo, viewbox)                           # check line against viewbox

                    if salvo.isNull():
                        return

                    if self.mouseGrabbed:                                       # just draw lines
                        if paintDetail & PaintDetails.recLin != PaintDetails.none:
                            painter.drawLine(salvo)
                        return

                    if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # just draw lines
                        if paintDetail & PaintDetails.recLin != PaintDetails.none:
                            painter.drawLine(salvo)
                    else:
                        for i in range(seed.grid.growList[0].steps):            # iterate over 1st step
                            seedOrigin = offset + seed.origin                   # start at templateOffset and add seed's origin
                            seedOrigin += seed.grid.growList[0].increment * i   # we now have the correct location
                            if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                    if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                                        painter.drawPicture(seedOrigin.toPointF(), seed.getPointPicture())  # paint seed picture
                                    if lod > config.lod3 and seed.patternPicture is not None and self.paintMode == PaintMode.all:       # paint pattern picture
                                        if paintDetail & PaintDetails.recPat != PaintDetails.none:
                                            painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)

                elif length == 2:
                    for i in range(seed.grid.growList[0].steps):                # iterate over 1st step
                        offset = QVector3D()                                    # always start at (0, 0, 0)
                        offset += templateOffset                                # start here
                        offset += seed.grid.growList[0].increment * i           # we now have the correct location
                        salvo = seed.grid.salvo.translated(offset.toPointF())   # move the line into place
                        salvo = clipLineF(salvo, seed.blockBorder)              # check line against block's src/rec border
                        salvo = clipLineF(salvo, viewbox)                       # check line against viewbox

                        if salvo.isNull():
                            continue

                        if self.mouseGrabbed:                                   # just draw lines
                            if paintDetail & PaintDetails.recLin != PaintDetails.none:
                                painter.drawLine(salvo)
                                continue

                        if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # just draw lines
                            if paintDetail & PaintDetails.recLin != PaintDetails.none:
                                painter.drawLine(salvo)
                        else:
                            for j in range(seed.grid.growList[1].steps):
                                seedOrigin = offset + seed.origin               # start at templateOffset and add seed's origin
                                seedOrigin += seed.grid.growList[1].increment * j   # we now have the correct location
                                if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                    if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                        if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                                            painter.drawPicture(seedOrigin.toPointF(), seed.getPointPicture())   # paint seed picture
                                        if lod > config.lod3 and seed.patternPicture is not None and self.paintMode == PaintMode.all:       # paint pattern picture
                                            if paintDetail & PaintDetails.recPat != PaintDetails.none:
                                                painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)   # paint pattern picture

                elif length == 3:
                    for i in range(seed.grid.growList[0].steps):
                        for j in range(seed.grid.growList[1].steps):
                            offset = QVector3D()                                # always start at (0, 0)
                            offset += templateOffset                            # start here
                            offset += seed.grid.growList[0].increment * i       # we now have the correct location
                            offset += seed.grid.growList[1].increment * j       # we now have the correct location
                            salvo = seed.grid.salvo.translated(offset.toPointF())   # move the line into place
                            salvo = clipLineF(salvo, seed.blockBorder)          # check line against block's src/rec border
                            salvo = clipLineF(salvo, viewbox)                   # check line against viewbox

                            if salvo.isNull():
                                continue

                            if self.mouseGrabbed:                               # just draw lines
                                if paintDetail & PaintDetails.recLin != PaintDetails.none:
                                    painter.drawLine(salvo)
                                continue

                            if paintDetail & PaintDetails.recLin != PaintDetails.none:
                                painter.drawLine(salvo)                         # always draw a line, if the PaintDetails flag allow for this

                            if lod < config.lod2 or self.paintMode == PaintMode.justLines:   # nothing else to do
                                continue

                            for k in range(seed.grid.growList[2].steps):            # we are about to draw the points now
                                seedOrigin = offset + seed.origin                   # start at templateOffset and add seed's origin
                                seedOrigin += seed.grid.growList[2].increment * k   # we now have the correct location

                                if containsPoint3D(seed.blockBorder, seedOrigin):   # is it within block limits ?
                                    if containsPoint3D(viewbox, seedOrigin):        # is it within the viewbox ?
                                        if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                                            painter.drawPicture(seedOrigin.toPointF(), seed.getPointPicture())   # paint seed picture

                                        if lod < config.lod3 or self.paintMode == PaintMode.justPoints:   # nothing else to do
                                            continue

                                        if seed.patternPicture is not None and paintDetail & PaintDetails.recPat != PaintDetails.none:
                                            painter.drawPicture(seedOrigin.toPointF(), seed.patternPicture)   # paint pattern picture
                else:
                    # do something recursively; not  implemented yet
                    raise NotImplementedError('More than three grow steps currently not allowed.')

            # should we move this out of paintTemplate() into paint() ?
            # In order to do this, these seeds would not sit under Survey --> Block --> template
            # instead they would sit on the same level as Block list, i.e. Well list, Circle list and Spiral list
            # However, the advantage of keeping them under a 'block' is that the Src, Rec & Cmp outlines are valid, incl. these 'special' seeds

            if seed.type == SeedType.circle and seed.rendered is False:         # circle seed; only draw once
                seed.rendered = True

                if self.mouseGrabbed:                                           # just draw a circle and return
                    if paintDetail & PaintDetails.recLin != PaintDetails.none:
                        painter.setBrush(QBrush())                              # empty brush
                        r = seed.circle.radius
                        o = seed.origin.toPointF()
                        painter.drawEllipse(o, r, r)
                    continue

                if paintDetail & PaintDetails.recLin != PaintDetails.none:      # start drawing the circle
                    painter.setBrush(QBrush())                                  # empty brush
                    r = seed.circle.radius
                    o = seed.origin.toPointF()
                    painter.drawEllipse(o, r, r)

                if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # nothing else to do
                    continue

                if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                    length = len(seed.pointList)
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        painter.drawPicture(p, seed.getPointPicture())          # paint seed picture

            if seed.type == SeedType.spiral and seed.rendered is False:         # spiral seed
                seed.rendered = True

                if self.mouseGrabbed:                                           # just draw a spiral and return
                    if paintDetail & PaintDetails.recLin != PaintDetails.none:
                        painter.setBrush(QBrush())                                  # empty brush
                        painter.drawPath(seed.spiral.path)
                    continue

                if paintDetail & PaintDetails.recLin != PaintDetails.none:      # start drawing the spiral
                    painter.setBrush(QBrush())                                  # empty brush
                    painter.drawPath(seed.spiral.path)

                if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # nothing else to do
                    continue

                if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                    length = len(seed.pointList)
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        painter.drawPicture(p, seed.getPointPicture())          # paint seed picture

            if seed.type == SeedType.well and seed.rendered is False:           # well seed
                seed.rendered = True

                if self.mouseGrabbed:                                           # just draw a circle and return
                    if paintDetail & PaintDetails.recLin != PaintDetails.none:
                        painter.drawPolyline(seed.well.polygon)                 # draw well trajectory as part of this template
                        painter.drawEllipse(seed.well.origL, 5.0, 5.0)          # draw small circle where well surfaces
                    continue

                if paintDetail & PaintDetails.recLin != PaintDetails.none:      # start drawing the well trajectory
                    painter.drawPolyline(seed.well.polygon)                     # draw well trajectory as part of this template
                    painter.drawEllipse(seed.well.origL, 5.0, 5.0)              # draw small circle where well surfaces

                if lod < config.lod2 or self.paintMode == PaintMode.justLines:  # nothing else to do
                    continue

                if paintDetail & PaintDetails.recPnt != PaintDetails.none:
                    for i in range(length):
                        p = seed.pointList[i].toPointF()
                        painter.drawPicture(p, seed.getPointPicture())          # paint seed picture

    def generateSvg(self, nodes):
        pass                                                                    # for the time being don't do anything; just to keep PyLint happy
