"""
This module provides the main classes used in Roll
"""
from qgis.PyQt.QtCore import pyqtSignal

# class SurveyTypeOld(Enum):
#     Orthogonal = 0
#     Parallel = 1
#     Slanted = 2
#     Brick = 3
#     Zigzag = 4
#     Streamer = 5


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


class RollSurvey_old_methods():
    progress = pyqtSignal(int)                                                  # signal to keep track of worker thread progress
    message = pyqtSignal(str)                                                   # signal to update statusbar progresss text

    # See: https://github.com/pyqtgraph/pyqtgraph/blob/develop/examples/CustomGraphItem.py
    # This example gives insight in the mouse drag event

    # assign default name value

    # def geomTemplate(self, nBlock, block, template, templateOffset):
    #     """iterate over all seeds in a template; make sure we start wih *source* seeds
    #     iterate using the three levels in the growList (slow approach)"""
    #     for srcSeed in template.seedList:
    #         assert len(srcSeed.grid.growList) == 3, 'there must always be 3 grow steps for source seeds'

    #         if not srcSeed.bSource:                                             # work with source seeds here
    #             continue

    #         for i in range(srcSeed.grid.growList[0].steps):
    #             # start with a new PointF object
    #             srcOff0 = QVector3D(templateOffset)
    #             srcOff0 += srcSeed.grid.growList[0].increment * i

    #             for j in range(srcSeed.grid.growList[1].steps):
    #                 srcOff1 = srcOff0 + srcSeed.grid.growList[1].increment * j

    #                 for k in range(srcSeed.grid.growList[2].steps):
    #                     # we now have the correct offset
    #                     srcOff2 = srcOff1 + srcSeed.grid.growList[2].increment * k
    #                     # we now have the correct source location
    #                     srcLoc = srcOff2 + srcSeed.origin

    #                     if QThread.currentThread().isInterruptionRequested():   # maybe stop at each shot...
    #                         raise StopIteration

    #                     # do this now, some shots may fall out of the areal limits later
    #                     self.nShotPoint += 1
    #                     # a new shotpoint always starts with new relation records
    #                     self.nOldRecLine = -999999
    #                     # apply integer divide
    #                     threadProgress = (100 * self.nShotPoint) // self.nShotPoints
    #                     if threadProgress > self.threadProgress:
    #                         self.threadProgress = threadProgress
    #                         # print("progress % = ", threadProgress)
    #                         self.progress.emit(threadProgress + 1)

    #                     # is src within block limits (or is the border empty) ?
    #                     if containsPoint3D(block.borders.srcBorder, srcLoc):

    #                         # useful source point; update the source geometry list here
    #                         # need to step back by one to arrive at start of array
    #                         nSrc = self.nShotPoint - 1
    #                         # line & stake nrs for source point
    #                         srcStake = self.st2Transform.map(srcLoc.toPointF())
    #                         srcGlob = self.glbTransform.map(srcLoc.toPointF())  # we need global positions

    #                         self.output.srcGeom[nSrc]['Line'] = int(srcStake.y())
    #                         self.output.srcGeom[nSrc]['Point'] = int(srcStake.x())
    #                         self.output.srcGeom[nSrc]['Index'] = nBlock % 10 + 1
    #                         # self.output.srcGeom[nSrc]['Code' ] = 'E1'         # can do this in one go at the end
    #                         # self.output.srcGeom[nSrc]['Depth'] = 0.0          # not needed; zero when initialized
    #                         self.output.srcGeom[nSrc]['East'] = srcGlob.x()
    #                         self.output.srcGeom[nSrc]['North'] = srcGlob.y()
    #                         self.output.srcGeom[nSrc]['LocX'] = srcLoc.x()      # x-component of 3D-location
    #                         self.output.srcGeom[nSrc]['LocY'] = srcLoc.y()      # y-component of 3D-location
    #                         self.output.srcGeom[nSrc]['Elev'] = srcLoc.z()      # z-component of 3D-location

    #                         # now iterate over all seeds to find the receivers
    #                         for recSeed in template.seedList:                   # iterate over all seeds in a template
    #                             assert len(recSeed.grid.growList) == 3, 'there must always be 3 grow steps for receiver seeds'

    #                             if recSeed.bSource:                             # work with receiver seeds here
    #                                 continue

    #                             # patches increase here
    #                             for l in range(recSeed.grid.growList[0].steps):
    #                                 # start with a new QVector3D object
    #                                 recOff0 = QVector3D(templateOffset)
    #                                 recOff0 += recSeed.grid.growList[0].increment * l

    #                                 # lines increase here
    #                                 for m in range(recSeed.grid.growList[1].steps):
    #                                     recOff1 = recOff0 + recSeed.grid.growList[1].increment * m

    #                                     # points increase here
    #                                     for n in range(recSeed.grid.growList[2].steps):
    #                                         recOff2 = recOff1 + recSeed.grid.growList[2].increment * n

    #                                         recLoc = QVector3D(recOff2)
    #                                         # we now have the correct receiver location
    #                                         recLoc += recSeed.origin

    #                                         # print("recLoc: ", recLoc.x(), recLoc.y(), recLoc.z() )

    #                                         # is it within block limits (or is the border empty) ?
    #                                         if containsPoint3D(block.borders.recBorder, recLoc):

    #                                             # now we have a valid src-point and rec-point
    #                                             # time to work with the relation records

    #                                             # line & stake nrs for receiver point
    #                                             recStake = self.st2Transform.map(recLoc.toPointF())
    #                                             # we need global positions for all points
    #                                             recGlob = self.glbTransform.map(recLoc.toPointF())
    #                                             recLine = int(recStake.y())
    #                                             recPoint = int(recStake.x())

    #                                             self.nNewRecLine = recLine

    #                                             # check if we're on a 'new' receiver line and need a new rel-record
    #                                             if self.nNewRecLine != self.nOldRecLine:
    #                                                 self.nOldRecLine = self.nNewRecLine

    #                                                 # first complete the previous record
    #                                                 if self.nRelRecord >= 0:                        # we need at least one earlier record
    #                                                     self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
    #                                                     self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    #                                                 self.nRelRecord += 1                            # now start with a new relation record
    #                                                 self.recMin = recPoint                          # reset minimum rec number
    #                                                 self.recMax = recPoint                          # reset maximum rec number

    #                                                 self.output.relGeom[self.nRelRecord]['SrcLin'] = int(srcStake.y())
    #                                                 self.output.relGeom[self.nRelRecord]['SrcPnt'] = int(srcStake.x())
    #                                                 self.output.relGeom[self.nRelRecord]['SrcInd'] = nBlock % 10 + 1
    #                                                 self.output.relGeom[self.nRelRecord]['RecNum'] = self.nShotPoint
    #                                                 self.output.relGeom[self.nRelRecord]['RecLin'] = int(recStake.y())
    #                                                 self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
    #                                                 self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax
    #                                                 self.output.relGeom[self.nRelRecord]['RecInd'] = nBlock % 10 + 1
    #                                                 self.output.relGeom[self.nRelRecord]['Uniq'] = 1
    #                                             else:
    #                                                 self.recMin = min(recPoint, self.recMin)
    #                                                 self.recMax = max(recPoint, self.recMax)
    #                                                 # self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
    #                                                 # self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    #                                             # apply self.output.relGeom.resize(N) when more memory is needed
    #                                             arraySize = self.output.relGeom.shape[0]
    #                                             if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
    #                                                 self.output.relGeom.resize(arraySize + 1000, refcheck=False)    # append 1000 more records

    #                                             # the problem with receiver records is that they overlap by some 90% from shot to shot.
    #                                             # rather than adding all receivers first, and removing all receiver duplicates later,
    #                                             # we use a nested dictionary to find out if a rec station already exists
    #                                             # sofar, (blocK) index has been neglected, but this could be added as a third nesting level

    #                                             try:                                                                # has it been used before ?
    #                                                 use = self.output.recDict[recLine][recPoint]
    #                                                 self.output.recDict[recLine][recPoint] = use + 1                # increment by one
    #                                             except KeyError:
    #                                                 self.output.recDict[recLine][recPoint] = 1                      # set to one (first time use)

    #                                                 self.nRecRecord += 1                                            # we have a new receiver record

    #                                                 self.output.recGeom[self.nRecRecord]['Line'] = int(recStake.y())
    #                                                 self.output.recGeom[self.nRecRecord]['Point'] = int(recStake.x())
    #                                                 self.output.recGeom[self.nRecRecord]['Index'] = nBlock % 10 + 1
    #                                                 # self.output.recGeom[self.nRecRecord]['Code' ] = 'G1'          # can do this in one go at the end
    #                                                 # self.output.recGeom[self.nRecRecord]['Depth'] = 0.0           # not needed; zero when initialized
    #                                                 self.output.recGeom[self.nRecRecord]['East'] = recGlob.x()
    #                                                 self.output.recGeom[self.nRecRecord]['North'] = recGlob.y()
    #                                                 self.output.recGeom[self.nRecRecord]['LocX'] = recLoc.x()       # x-component of 3D-location
    #                                                 self.output.recGeom[self.nRecRecord]['LocY'] = recLoc.y()       # y-component of 3D-location
    #                                                 self.output.recGeom[self.nRecRecord]['Elev'] = recLoc.z()       # z-component of 3D-location
    #                                                 # we want to remove empty records at the end
    #                                                 self.output.recGeom[self.nRecRecord]['Uniq'] = 1

    #                                             # apply self.output.recGeom.resize(N) when more memory is needed
    #                                             arraySize = self.output.recGeom.shape[0]
    #                                             if self.nRecRecord + 100 > arraySize:                               # room for less than 100 left ?
    #                                                 # first remove all duplicates
    #                                                 self.output.recGeom = np.unique(self.output.recGeom)
    #                                                 # get array size (again)
    #                                                 arraySize = self.output.recGeom.shape[0]
    #                                                 # adjust nRecRecord to the next available spot
    #                                                 self.nRecRecord = arraySize
    #                                                 # append 1000 more receiver records
    #                                                 self.output.recGeom.resize(arraySize + 1000, refcheck=False)

    #     # finally complete the very last relation record
    #     if self.nRelRecord >= 0:                        # we need at least one record
    #         self.output.relGeom[self.nRelRecord]['RecMin'] = self.recMin
    #         self.output.relGeom[self.nRelRecord]['RecMax'] = self.recMax

    # def geomTemplate2(self, nBlock, block, template, templateOffset):
    #     """Use numpy arrays instead of iterating over the growList.
    #     This provides a much faster approach then using the growlist.

    #     The function is however still rather slow.
    #     Use time.perf_counter() to analyse bottlenecks
    #     """

    #     # convert the template offset to a numpy array
    #     npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

    #     # iterate over all seeds in a template; make sure we start wih *source* seeds
    #     for srcSeed in template.seedList:
    #         time = perf_counter()   ###
    #         if not srcSeed.bSource:                                             # work with source seeds here
    #             continue

    #         # we are in a source seed right now; use the numpy array functions to apply selection criteria
    #         srcArray = srcSeed.pointArray + npTemplateOffset

    #         if not block.borders.srcBorder.isNull():                            # deal with block's source  border if it isn't null()
    #             I = fnb.pointsInRect(srcArray, block.borders.srcBorder)
    #             if I.shape[0] == 0:
    #                 continue
    #             time = self.elapsedTime(time, 0)    ###
    #             srcArray = srcArray[I, :]                                       # filter the source array
    #             time = self.elapsedTime(time, 1)    ###

    #         for src in srcArray:                                                # iterate over all sources

    #             self.nShotPoint += 1
    #             self.nOldRecLine = -999999                                      # a new shotpoint always starts with new relation records

    #             # begin thread progress code
    #             if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
    #                 raise StopIteration

    #             threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
    #             if threadProgress > self.threadProgress:
    #                 self.threadProgress = threadProgress
    #                 self.progress.emit(threadProgress + 1)
    #             # end thread progress code

    #             # useful source point; update the source geometry list here
    #             nSrc = self.nShotPoint - 1                                      # need to step back by one to arrive at start of array

    #             time = self.elapsedTime(time, 2)    ###

    #             # determine line & stake nrs for source point
    #             srcX = src[0]
    #             srcY = src[1]
    #             # srcZ = src[2]

    #             srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)            # get line and point indices
    #             srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)            # we need global positions

    #             fnb.numbaSetPointRecord(self.output.srcGeom, nSrc, srcStkY, srcStkX, nBlock, srcLocX, srcLocY, src)
    #             time = self.elapsedTime(time, 3)    ###

    #             # now iterate over all seeds to find the receivers
    #             for recSeed in template.seedList:                               # iterate over all rec seeds in a template
    #                 if recSeed.bSource:                                         # work with receiver seeds here
    #                     continue

    #                 # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
    #                 recPoints = recSeed.pointArray + npTemplateOffset

    #                 time = self.elapsedTime(time, 4)    ###

    #                 if not block.borders.recBorder.isNull():                    # deal with block's receiver border if it isn't null()
    #                     I = fnb.pointsInRect(recPoints, block.borders.recBorder)
    #                     if I.shape[0] == 0:
    #                         continue
    #                     time = self.elapsedTime(time, 5)    ###
    #                     recPoints = recPoints[I, :]
    #                     time = self.elapsedTime(time, 6)    ###

    #                 for rec in recPoints:                                       # iterate over all receivers

    #                     time = perf_counter()                                   # reset at start of receiver loop

    #                     # determine line & stake nrs for receiver point
    #                     recX = rec[0]
    #                     recY = rec[1]
    #                     # recZ = rec[2]

    #                     time = self.elapsedTime(time, 7)    ###

    #                     recStkX, recStkY = self.st2Transform.map(recX, recY)    # get line and point indices
    #                     recLocX, recLocY = self.glbTransform.map(recX, recY)    # we need global positions

    #                     time = self.elapsedTime(time, 8)    ###

    #                     # we have a new receiver record
    #                     self.nRecRecord += 1

    #                     fnb.numbaSetPointRecord(self.output.recGeom, self.nRecRecord, recStkY, recStkX, nBlock, recLocX, recLocY, rec)
    #                     time = self.elapsedTime(time, 9)    ###

    #                     # apply self.output.recGeom.resize(N) when more memory is needed, after cleaning duplicates
    #                     arraySize = self.output.recGeom.shape[0]
    #                     if self.nRecRecord + 100 > arraySize:                               # room for less than 100 left ?
    #                         time = perf_counter()
    #                         self.output.recGeom = np.unique(self.output.recGeom)            # first remove all duplicates
    #                         arraySize = self.output.recGeom.shape[0]                        # get array size (again)
    #                         self.nRecRecord = arraySize                                     # adjust nRecRecord to the next available spot
    #                         self.output.recGeom.resize(arraySize + 10000, refcheck=False)   # append 10000 more records
    #                         time = self.elapsedTime(time, 10)    ###

    #                     time = perf_counter()

    #                     # time to work with the relation records, now we have both a valid src-point and rec-point;
    #                     self.nNewRecLine = int(recStkY)
    #                     if self.nNewRecLine != self.nOldRecLine:                # we're on a 'new' receiver line and need a new rel-record
    #                         self.nOldRecLine = self.nNewRecLine                 # save current line number
    #                         self.nRelRecord += 1                                # increment relation record number

    #                         # create new relation record; fill it in completely
    #                         fnb.numbaSetRelationRecord(self.output.relGeom, self.nRelRecord, srcStkX, srcStkY, nBlock, self.nShotPoint, recStkY, recStkX, recStkX)
    #                     else:
    #                         # existing relation record; just update min/max rec stake numbers
    #                         fnb.numbaFixRelationRecord(self.output.relGeom, self.nRelRecord, recStkX)
    #                         # recMin = min(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMin'])
    #                         # recMax = max(int(recStkX), self.output.relGeom[self.nRelRecord]['RecMax'])
    #                         # self.output.relGeom[self.nRelRecord]['RecMin'] = recMin
    #                         # self.output.relGeom[self.nRelRecord]['RecMax'] = recMax

    #                     time = self.elapsedTime(time, 11)    ###

    #                     # apply self.output.relGeom.resize(N) when more memory is needed
    #                     arraySize = self.output.relGeom.shape[0]
    #                     if self.nRelRecord + 100 > arraySize:                               # room for less than 100 left ?
    #                         time = perf_counter()
    #                         self.output.relGeom.resize(arraySize + 10000, refcheck=False)   # append 10000 more records

    #                         time = self.elapsedTime(time, 12)    ###

    # def geomTemplate3(self, nBlock, block, template, templateOffset):
    #     """Use numpy arrays instead of iterating over the growList.
    #     This provides a much faster approach then using the growlist.

    #     The function is however still rather slow.
    #     Use time.perf_counter() to analyse bottlenecks

    #     Note: a template is a collection of shots that all record in the same set of receivers.
    #     Upon completion, the template is rolled, and the process starts over again
    #     Therefore:
    #     a) the shots from a template can directly be appended to the src list
    #     b) the same can be done for the receivers, as far as they are not already included in the rec list
    #     c) Per shot, several relation records  need to be created.
    #        Apart from the source info, these relation records are identical for all shots in the template
    #     """

    #     # convert the template offset to a numpy array
    #     npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

    #     # begin thread progress code
    #     if QThread.currentThread().isInterruptionRequested():                   # maybe stop at each shot...
    #         raise StopIteration

    #     self.nTemplate += 1                                                     # work on a new template
    #     threadProgress = (100 * self.nTemplate) // self.nTemplates              # apply integer divide
    #     if threadProgress > self.threadProgress:
    #         self.threadProgress = threadProgress
    #         self.progress.emit(threadProgress + 1)
    #     # end thread progress code

    #     nShotPoint = self.nShotPoint                                            # create a copy for relation records creation later on

    #     # iterate over all seeds in a template; make sure we deal wih *source* seeds
    #     for srcSeed in template.seedList:
    #         if not srcSeed.bSource:                                             # work with source seeds here
    #             continue

    #         # we are in a source seed right now; use the numpy array functions to apply selection criteria
    #         srcArray = srcSeed.pointArray + npTemplateOffset

    #         if not block.borders.srcBorder.isNull():                            # deal with block's source border if it isn't null()
    #             I = fnb.pointsInRect(srcArray, block.borders.srcBorder)
    #             if I.shape[0] == 0:
    #                 continue
    #             srcArray = srcArray[I, :]                                       # filter the source array

    #         for src in srcArray:                                                # iterate over all sources
    #             # useful source point; fnb.pointsInRect passed it through

    #             # determine line & stake nrs for source point
    #             srcX = src[0]
    #             srcY = src[1]

    #             srcStkX, srcStkY = self.st2Transform.map(srcX, srcY)            # get line and point indices
    #             srcLocX, srcLocY = self.glbTransform.map(srcX, srcY)            # we need global positions

    #             fnb.numbaSetPointRecord(self.output.srcGeom, self.nShotPoint, srcStkY, srcStkX, nBlock, srcLocX, srcLocY, src)
    #             self.nShotPoint += 1                                            # increment for the next shot

    #     nRelRecord = -1                                                         # start with invalid value (will be 0 for 1st record)
    #     nOldRecLine = -999999                                                   # start with 'funny' value

    #     # now iterate over all seeds to find the receivers
    #     for recSeed in template.seedList:                                       # iterate over all rec seeds in a template
    #         if recSeed.bSource:                                                 # work with receiver seeds here
    #             continue

    #         # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
    #         recPoints = recSeed.pointArray + npTemplateOffset

    #         if not block.borders.recBorder.isNull():                            # deal with block's receiver border if it isn't null()
    #             I = fnb.pointsInRect(recPoints, block.borders.recBorder)
    #             if I.shape[0] == 0:
    #                 continue
    #             recPoints = recPoints[I, :]

    #         for rec in recPoints:                                               # iterate over all receivers
    #             # determine line & stake nrs for receiver point
    #             recX = rec[0]
    #             recY = rec[1]

    #             recStkX, recStkY = self.st2Transform.map(recX, recY)            # get line and point indices
    #             recLocX, recLocY = self.glbTransform.map(recX, recY)            # we need global positions

    #             recPoint = int(recStkX)
    #             recLine = int(recStkY)

    #             # the problem with receiver records is that they overlap by some 90% from shot to shot.
    #             # rather than adding all receivers first, followed by removing all duplicates later,
    #             # we use a nested dictionary to find out if a rec station already exists in our 'list'
    #             # sofar,block nr (=index) has been neglected, but this could be added as a third nesting level

    #             try:                                                            # has it been used before ?
    #                 _ = self.output.recDict[recLine][recPoint]                  # test with dummy variable
    #             except KeyError:
    #                 self.output.recDict[recLine][recPoint] = self.nRecRecord    # use self.nRecRecord to create an entry in the self.output.recGeom table

    #                 fnb.numbaSetPointRecord(self.output.recGeom, self.nRecRecord, recStkY, recStkX, nBlock, recLocX, recLocY, rec)
    #                 self.nRecRecord += 1                                        # increment for the next receiver

    #                 arraySize = self.output.recGeom.shape[0]
    #                 if self.nRecRecord + 1000 > arraySize:                      # room for less than 1000 left ?
    #                     self.output.recGeom.resize(arraySize + 10000, refcheck=False)    # append 10000 more receiver records

    #             # now create the framework for relation records for all shots in the template
    #             # adapt these records with slight modifications for all  shots in the template

    #             if recLine != nOldRecLine:                                      # we're on a 'new' receiver line and need a new rel-record
    #                 nOldRecLine = recLine                                       # save current line number
    #                 nRelRecord += 1                                             # increment relation record number (that started at -1)

    #                 self.output.relTemp[nRelRecord]['RecLin'] = recStkY         # create new relation record; fill it in with all rec info
    #                 self.output.relTemp[nRelRecord]['RecMin'] = recStkX
    #                 self.output.relTemp[nRelRecord]['RecMax'] = recStkX
    #                 self.output.relTemp[nRelRecord]['RecInd'] = nBlock % 10 + 1


    #                 # --- DEBUG: validate relTemp for this template ---
    #                 # if self.output.relTemp[nRelRecord]['RecMin'] > self.output.relTemp[nRelRecord]['RecMax']:
    #                 #     self.errorText = 'geomTemplate3(): RecMin > RecMax detected'
    #                 #     raise StopIteration
    #                 # --- END DEBUG: validate relTemp for this template ---

    #                 arraySize = self.output.relTemp.shape[0]                    # do we have enough space for more relation records ?
    #                 if nRelRecord + 10 > arraySize:                             # room for less than 50 left ?
    #                     self.output.relTemp.resize(arraySize + 100, refcheck=False)    # append 100 more records

    #             else:
    #                 # existing relation record; just update min/max rec stake numbers
    #                 self.output.relTemp[nRelRecord]['RecMin'] = min(recStkX, self.output.relTemp[nRelRecord]['RecMin'])
    #                 self.output.relTemp[nRelRecord]['RecMax'] = max(recStkX, self.output.relTemp[nRelRecord]['RecMax'])

    #     # --- DEBUG: validate relTemp for this template ---
    #     # if nRelRecord < 0:
    #     #     self.errorText = 'geomTemplate3(): no relTemp records created for this template'
    #     #     raise StopIteration  # or return/raise to stop
    #     # --- END DEBUG: validate relTemp for this template ---

    #     # at this moment:
    #     # nRelRecord holds the nr of relation records for each shot in this template
    #     # self.output.relTemp holds the receiver info for these records
    #     # self.output.srcGeom holds the source records that made it through the selection
    #     # nShotPoint holds the first shot point for which relation records need to be created

    #     for i in range(nShotPoint, self.nShotPoint):                            # these are the shots from this template, we have added

    #         # apply self.output.relGeom.resize(N) when more memory is needed
    #         arraySize = self.output.relGeom.shape[0]
    #         if self.nRelRecord + 1000 > arraySize:                              # room for less than 1,000 left ?
    #             self.output.relGeom.resize(arraySize + 10000, refcheck=False)   # append 10,000 more records

    #         srcLin = self.output.srcGeom[i]['Line']
    #         srcPnt = self.output.srcGeom[i]['Point']
    #         srcInd = self.output.srcGeom[i]['Index']                            # the single digit point index is used to indicate block nr

    #         for j in range(nRelRecord + 1):                                     # every shot needs this many relation records; read the back and complete them

    #             recLin = self.output.relTemp[j]['RecLin']
    #             recMin = self.output.relTemp[j]['RecMin']
    #             recMax = self.output.relTemp[j]['RecMax']

    #             # recInd equals srcInd (both are linked to the block number) so it is not entered separately
    #             fnb.numbaSetRelationRecord(self.output.relGeom, self.nRelRecord, srcLin, srcPnt, srcInd, i + 1, recLin, recMin, recMax)
    #             self.nRelRecord += 1

    # def binFromGeometry4(self, fullAnalysis) -> bool:
    #     """
    #     all binning methods (cmp, plane, sphere) implemented, using numpy arrays, rather than a for-loop.
    #     On 09/04/2024 the earlier implementations of binFromGeometry v1 to v3 have been removed.
    #     They are still available in the roll-2024-08-04 folder in classes.py
    #     """
    #     self.threadProgress = 0                                                 # always start at zero

    #     toLocalTransform = QTransform()                                         # setup empty (unit) transform
    #     toLocalTransform, _ = self.glbTransform.inverted()                      # transform to local survey coordinates

    #     # if needed, fill the source and receiver arrays with local coordinates
    #     minLocX = np.min(self.output.srcGeom['LocX'])                           # determine if there's any data there...
    #     maxLocX = np.max(self.output.srcGeom['LocY'])                           # determine if there's any data there...
    #     if minLocX == 0.0 and maxLocX == 0.0:
    #         for record in self.output.srcGeom:
    #             srcX = record['East']
    #             srcY = record['North']
    #             x, y = toLocalTransform.map(srcX, srcY)
    #             record['LocX'] = x
    #             record['LocY'] = y

    #     minLocX = np.min(self.output.recGeom['LocX'])                           # determine if there's any data there...
    #     maxLocX = np.max(self.output.recGeom['LocY'])                           # determine if there's any data there...
    #     if minLocX == 0.0 and maxLocX == 0.0:
    #         for record in self.output.recGeom:
    #             recX = record['East']
    #             recY = record['North']
    #             x, y = toLocalTransform.map(recX, recY)
    #             record['LocX'] = x
    #             record['LocY'] = y

    #     # Find out where shots start and stop in the relation file
    #     # Therefore create reference to relation file.

    #     # The 1st element is the first entry into the rel file for a shot number
    #     # The 2nd element is the last  entry into the rel file for a shot number
    #     relFileIndices = np.zeros(shape=(self.output.srcGeom.shape[0], 2), dtype=np.int32)

    #     # now iterate over srcGeom to check where shots are referenced
    #     # the next for loop assumes that:
    #     # 1. any duplicate records have been removed
    #     # 2. any orphans (missing corresponding src/rel records) have been removed
    #     # 2. source records are ordered (sorted) on shotindex / shotline / shotpoint
    #     # 3. relation records are sorted on shotindex / shotline / shotpoint followed by recindex / recline / recpoint

    #     # to be sure; sort the three geometry arrays in the proper order: index; line; point
    #     self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    #     assert self.output.relGeom[0]['SrcLin'] == self.output.srcGeom[0]['Line'], 'Line error in geometry files'
    #     assert self.output.relGeom[0]['SrcPnt'] == self.output.srcGeom[0]['Point'], 'Point error in geometry files'
    #     assert self.output.relGeom[0]['SrcInd'] == self.output.srcGeom[0]['Index'], 'Index error in geometry files'

    #     marker = 0
    #     for index, srcRecord in enumerate(self.output.srcGeom):                 # find the relevant relation records for each shot point

    #         relFileIndices[index][0] = marker
    #         for j in range(marker, self.output.relGeom.shape[0]):

    #             if self.output.relGeom[j]['SrcPnt'] == srcRecord['Point'] and self.output.relGeom[j]['SrcLin'] == srcRecord['Line'] and self.output.relGeom[j]['SrcInd'] == srcRecord['Index']:
    #                 relFileIndices[index][1] = j + 1                            # last number will stay out of scope for range: 0 - n
    #             else:
    #                 marker = j
    #                 break

    #     # now iterate over the shot points and select the range of applicable receivers
    #     # assume the receivers have been sorted based on index; line; point

    #     self.nShotPoint = 0
    #     self.nShotPoints = self.output.srcGeom.shape[0]

    #     try:
    #         for index, srcRecord in enumerate(self.output.srcGeom):

    #             if srcRecord['InUse'] == 0:                                     # this record has been disabled
    #                 continue

    #             # convert the source record to a single [x, y, z] value
    #             src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

    #             # begin thread progress code
    #             if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
    #                 raise StopIteration

    #             self.nShotPoint += 1
    #             threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
    #             if threadProgress > self.threadProgress:
    #                 self.threadProgress = threadProgress
    #                 self.progress.emit(threadProgress + 1)
    #             # end thread progress code

    #             minRecord = relFileIndices[index][0]                            # range of relevant relation records
    #             maxRecord = relFileIndices[index][1]

    #             if maxRecord <= minRecord:                                      # no receivers found; move to next shot !
    #                 continue                                                    # test on <= instead of == in case maxRecord = 0

    #             relSlice = self.output.relGeom[minRecord:maxRecord]             # create a slice out of the relation file

    #             recIndex = relSlice[0]['RecInd']
    #             minLine = np.min(relSlice['RecLin'])
    #             maxLine = np.max(relSlice['RecLin'])
    #             minMinPoint = np.min(relSlice['RecMin'])
    #             maxMinPoint = np.max(relSlice['RecMin'])
    #             minMaxPoint = np.min(relSlice['RecMax'])
    #             maxMaxPoint = np.max(relSlice['RecMax'])

    #             if minMinPoint == maxMinPoint and minMaxPoint == maxMaxPoint:   # determine if it is a purely square block
    #                 # if it is a square block, make a simple single square selection in receiver array. See binTemplate4()
    #                 I = (
    #                     (self.output.recGeom['Index'] == recIndex)
    #                     & (self.output.recGeom['Line'] >= minLine)
    #                     & (self.output.recGeom['Line'] <= maxLine)
    #                     & (self.output.recGeom['Point'] >= minMinPoint)
    #                     & (self.output.recGeom['Point'] <= maxMaxPoint)
    #                 )
    #                 if np.count_nonzero(I) == 0:
    #                     continue                                                # no receivers found; move to next shot !
    #                 recArray = self.output.recGeom[I]                           # select the filtered receivers

    #             else:
    #                 # there are different min/max rec points on different rec lines.
    #                 # we need to determine the recPoints line by line; per relation record
    #                 recArray = np.zeros(shape=(0), dtype=pntType1)             # setup empty numpy array, to append data to
    #                 for relRecord in relSlice:
    #                     recInd = relRecord['RecInd']
    #                     recLin = relRecord['RecLin']
    #                     recMin = relRecord['RecMin']
    #                     recMax = relRecord['RecMax']

    #                     # select appropriate receivers on a receiver line
    #                     I = (self.output.recGeom['Index'] == recInd) & (self.output.recGeom['Line'] == recLin) & (self.output.recGeom['Point'] >= recMin) & (self.output.recGeom['Point'] <= recMax)
    #                     if np.count_nonzero(I) == 0:
    #                         continue                                            # no receivers found; move to next shot !

    #                     recLine = self.output.recGeom[I]                        # select the filtered receivers
    #                     recArray = np.concatenate((recArray, recLine))          # need to supply arrays to be concatenated as a tuple !
    #                     # See: https://stackoverflow.com/questions/50997928/typeerror-only-integer-scalar-arrays-can-be-converted-to-a-scalar-index-with-1d

    #             # at this stage we have recPoints defined. We can now use the same approach as used in template based binning.
    #             # we combine recPoints with a source point to create cmp array, define offsets, etc...

    #             # we are NOT DEALING with the block's src border; this should have been done while generating geometry
    #             # we are NOT DEALING with the block's rec border; this should have been done while generating geometry

    #             # but we are dealing with the "InUse" attribute, that allows for killing a point in QGIS

    #             I = recArray['InUse'] > 0
    #             if np.count_nonzero(I) == 0:
    #                 continue                                                    # no receivers found; move to next shot !
    #             recArray = recArray[I]                                          # select the filtered receivers

    #             # it is ESSENTIAL that any orphans & duplicates in recPoints have been removed at this stage
    #             # for cmp and offset calcuations, we need numpy arrays in the form of local (x, y, z) coordinates

    #             recPoints = np.zeros(shape=(recArray.shape[0], 3), dtype=np.float32)
    #             recPoints[:, 0] = recArray['LocX']
    #             recPoints[:, 1] = recArray['LocY']
    #             recPoints[:, 2] = recArray['Elev']

    #             # setup a cmp array with the same size as recPoints
    #             cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

    #             if self.binning.method == BinningType.cmp:
    #                 # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
    #                 cmpPoints = (recPoints + src) * 0.5
    #             elif self.binning.method == BinningType.plane:
    #                 # create all cmp-locations using the following steps:
    #                 # 1. mirror the source location against the plane
    #                 # 2. find out where/if the lines defined by the source-mirror to the receivers cut through the plane
    #                 # 3. these locations are the cmp locations for binning against a dipping plane
    #                 srcMirrorNp = self.localPlane.mirrorPointNp(src)

    #                 # now find all intersection points with the dipping plane, and prune any non-contributing receivers
    #                 cmpPoints, recPoints = self.localPlane.IntersectLinesAtPointNp(srcMirrorNp, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

    #                 if cmpPoints is None:
    #                     continue
    #             elif self.binning.method == BinningType.sphere:

    #                 # now find all intersection points with the sphere, and prune any non-contributing receivers
    #                 cmpPoints, recPoints = self.localSphere.ReflectSphereAtPointsNp(src, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

    #                 if cmpPoints is None:
    #                     continue

    #             I = fnb.pointsInRect(cmpPoints, self.output.rctOutput)              # find the cmp locations that contribute to the output area
    #             if I.shape[0] == 0:
    #                 continue

    #             cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array
    #             recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this for offsets

    #             size = recPoints.shape[0]
    #             offArray = np.zeros(shape=(size, 3), dtype=np.float32)          # allocate the offset array according to rec array
    #             offArray = recPoints - src                                      # define the offset array

    #             I = fnb.pointsInRect(offArray, self.offset.rctOffsets)
    #             if I.shape[0] == 0:
    #                 continue

    #             offArray = offArray[I, :]                                       # filter the offset-array
    #             cmpPoints = cmpPoints[I, :]                                     # filter the cmp-array too, as we still need this
    #             recPoints = recPoints[I, :]                                     # filter the rec-array too, as we still need this

    #             size = recPoints.shape[0]
    #             hypArray = np.zeros(shape=(size, 1), dtype=np.float32)          # allocate the radius array according to rec array
    #             hypArray = np.hypot(offArray[:, 0], offArray[:, 1])             # calculate radial offset size
    #             aziArray = np.arctan2(offArray[:, 0], offArray[:, 1])           # calculate offset angles
    #             aziArray = np.rad2deg(aziArray)                                 # get angles in degrees instead of radians
    #             aziArray = (aziArray + 360.0) % 360.0                           # convert angles to 0-360 range

    #             r1 = self.offset.radOffsets.x()                                 # r1 = minimum radius
    #             r2 = self.offset.radOffsets.y()                                 # r2 = maximum radius
    #             if r2 > 0:                                                      # we need to apply the radial offset selection criteria
    #                 I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
    #                 if np.count_nonzero(I) == 0:
    #                     continue                                                # continue with next recSeed
    #                 # print(I)
    #                 hypArray = hypArray[I]                                      # filter the radial offset-array
    #                 aziArray = aziArray[I]                                      # filter the offset-angle array too
    #                 offArray = offArray[I, :]                                   # filter the off-array too, as we still need this
    #                 cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
    #                 recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

    #             # now work on the TWT aspect of the src, cmp & rec positions
    #             if self.binning.method == BinningType.cmp:
    #                 upDnArray = recPoints - src                                 # straigth rays; total length of both legs
    #                 totalTime = np.linalg.norm(upDnArray, axis=1)               # get length of the rays
    #             else:
    #                 dnArray = cmpPoints - src                                   # 1st leg of the rays
    #                 upArray = cmpPoints - recPoints                             # 2nd leg of the rays
    #                 dnTime = np.linalg.norm(dnArray, axis=1)                    # get length of the 1st leg
    #                 upTime = np.linalg.norm(upArray, axis=1)                    # get length of the 2nd leg
    #                 totalTime = dnTime + upTime                                 # total length of both legs

    #             totalTime *= self.binning.slowness                              # convert distance into travel time

    #             #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
    #             for count, cmp in enumerate(cmpPoints):                         # process all traces
    #                 try:
    #                     cmpX = cmp[0]
    #                     cmpY = cmp[1]

    #                     x, y = self.binTransform.map(cmpX, cmpY)                # local position in bin area
    #                     nx = int(x)
    #                     ny = int(y)

    #                     if fullAnalysis:
    #                         fold = self.output.binOutput[nx, ny]
    #                         if fold < self.grid.fold:                           # prevent overwriting next bin
    #                             # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)

    #                             # line & stake nrs for reporting in extended np-array
    #                             stkX, stkY = self.st2Transform.map(cmpX, cmpY)
    #                             self.output.anaOutput[nx, ny, fold, 0] = int(stkX)
    #                             self.output.anaOutput[nx, ny, fold, 1] = int(stkY)
    #                             self.output.anaOutput[nx, ny, fold, 2] = fold + 1       # to make fold run from 1 to N
    #                             self.output.anaOutput[nx, ny, fold, 3] = src[0]
    #                             self.output.anaOutput[nx, ny, fold, 4] = src[1]
    #                             self.output.anaOutput[nx, ny, fold, 5] = recPoints[count, 0]
    #                             self.output.anaOutput[nx, ny, fold, 6] = recPoints[count, 1]
    #                             self.output.anaOutput[nx, ny, fold, 7] = cmpPoints[count, 0]
    #                             self.output.anaOutput[nx, ny, fold, 8] = cmpPoints[count, 1]
    #                             self.output.anaOutput[nx, ny, fold, 9] = totalTime[count]
    #                             self.output.anaOutput[nx, ny, fold, 10] = hypArray[count]
    #                             self.output.anaOutput[nx, ny, fold, 11] = aziArray[count]
    #                             # self.output.anaOutput[nx, ny, fold, 12] = -1

    #                     # all selection criteria have been fullfilled; use the trace
    #                     self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
    #                     self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
    #                     self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

    #                 # rather than checking nx, ny & fold, use exception handling to deal with index errors
    #                 except IndexError:
    #                     continue

    #     except StopIteration:
    #         self.errorText = 'binning from geometry cancelled by user'
    #         return False
    #     except BaseException as e:
    #         # self.errorText = str(e)
    #         # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
    #         fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
    #         funcName = sys.exc_info()[2].tb_frame.f_code.co_name
    #         lineNo = str(sys.exc_info()[2].tb_lineno)
    #         self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
    #         del (fileName, funcName, lineNo)
    #         return False

    #     self.finalizeLiveBinningOutputs(fullAnalysis)

    #     return True

    # def binFromGeometry5(self, _) -> bool:
    #     """
    #     Optimized version of binFromGeometry4 by Gemini 2.5 Pro
    #     - Vectorized receiver selection.
    #     - Vectorized bin assignment using np.add.at.
    #     """
    #     #  unfortunately; this version was completely faulty, trying to access non-existing methods & attributes.
    #     return True

    # def binFromGeometry6(self, _) -> bool:
    #     """
    #     Optimized version of binFromGeometry4 by GPT-4o
    #     - Vectorized receiver selection.
    #     - Vectorized CMP and offset calculations.
    #     - Efficient bin assignment using np.add.at.

    #     Not sure if this one works better than binFromGeometry4; needs testing.

    #     """
    #     self.threadProgress = 0  # Always start at zero

    #     # Transform to local survey coordinates
    #     toLocalTransform, _ = self.glbTransform.inverted()

    #     # Fill source and receiver arrays with local coordinates if needed
    #     if np.all(self.output.srcGeom['LocX'] == 0.0) and np.all(self.output.srcGeom['LocY'] == 0.0):
    #         self.output.srcGeom['LocX'], self.output.srcGeom['LocY'] = toLocalTransform.map(self.output.srcGeom['East'], self.output.srcGeom['North'])

    #     if np.all(self.output.recGeom['LocX'] == 0.0) and np.all(self.output.recGeom['LocY'] == 0.0):
    #         self.output.recGeom['LocX'], self.output.recGeom['LocY'] = toLocalTransform.map(self.output.recGeom['East'], self.output.recGeom['North'])

    #     # Sort geometry arrays to ensure proper order
    #     self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    #     # Create reference to relation file
    #     relFileIndices = np.zeros((self.output.srcGeom.shape[0], 2), dtype=np.int32)

    #     # Find relevant relation records for each shot point
    #     marker = 0
    #     for index, srcRecord in enumerate(self.output.srcGeom):
    #         relFileIndices[index][0] = marker
    #         for j in range(marker, self.output.relGeom.shape[0]):
    #             if self.output.relGeom[j]['SrcPnt'] == srcRecord['Point'] and self.output.relGeom[j]['SrcLin'] == srcRecord['Line'] and self.output.relGeom[j]['SrcInd'] == srcRecord['Index']:
    #                 relFileIndices[index][1] = j + 1
    #             else:
    #                 marker = j
    #                 break

    #     # Iterate over shot points
    #     self.nShotPoint = 0
    #     self.nShotPoints = self.output.srcGeom.shape[0]

    #     try:
    #         for index, srcRecord in enumerate(self.output.srcGeom):
    #             if srcRecord['InUse'] == 0:
    #                 continue

    #             # Convert source record to a single [x, y, z] value
    #             src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

    #             # Thread progress
    #             if QThread.currentThread().isInterruptionRequested():
    #                 raise StopIteration

    #             self.nShotPoint += 1
    #             threadProgress = (100 * self.nShotPoint) // self.nShotPoints
    #             if threadProgress > self.threadProgress:
    #                 self.threadProgress = threadProgress
    #                 self.progress.emit(threadProgress + 1)

    #             # Get range of relevant relation records
    #             minRecord, maxRecord = relFileIndices[index]
    #             if maxRecord <= minRecord:
    #                 continue

    #             relSlice = self.output.relGeom[minRecord:maxRecord]

    #             # Vectorized receiver selection
    #             recMask = np.zeros(self.output.recGeom.shape[0], dtype=bool)
    #             for relRecord in relSlice:
    #                 recMask |= (
    #                     (self.output.recGeom['Index'] == relRecord['RecInd'])
    #                     & (self.output.recGeom['Line'] == relRecord['RecLin'])
    #                     & (self.output.recGeom['Point'] >= relRecord['RecMin'])
    #                     & (self.output.recGeom['Point'] <= relRecord['RecMax'])
    #                 )

    #             recArray = self.output.recGeom[recMask]
    #             recArray = recArray[recArray['InUse'] > 0]
    #             if recArray.shape[0] == 0:
    #                 continue

    #             # Prepare source and receiver points for vectorized calculations
    #             recPoints = np.vstack((recArray['LocX'], recArray['LocY'], recArray['Elev'])).T

    #             # Calculate CMPs and offsets for all pairs at once
    #             if self.binning.method == BinningType.cmp:
    #                 cmpPoints = (recPoints + src) * 0.5
    #                 offArray = recPoints - src

    #             # Filter CMPs that are outside the geometry
    #             I = fnb.pointsInRect(cmpPoints, self.output.rctOutput)
    #             if np.all(~I):
    #                 continue

    #             cmpPoints = cmpPoints[I]
    #             offArray = offArray[I]

    #             # Calculate hypotenuse (offset distance) and azimuth
    #             hypArray = np.hypot(offArray[:, 0], offArray[:, 1])
    #             aziArray = np.rad2deg(np.arctan2(offArray[:, 0], offArray[:, 1]))
    #             aziArray = (aziArray + 360.0) % 360.0                           # convert angles to 0-360 range

    #             if not self.updateBinOutputsForValidCmpPoints(src, cmpPoints, recPoints, hypArray, aziArray, False):
    #                 continue

    #             # if fullAnalysis:
    #             #     np.minimum.at(self.output.minAzimuth, (nx, ny), aziArray)
    #             #     np.maximum.at(self.output.maxAzimuth, (nx, ny), aziArray)

    #     except StopIteration:
    #         self.errorText = 'binning from geometry cancelled by user'
    #         return False
    #     except BaseException as e:
    #         fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
    #         funcName = sys.exc_info()[2].tb_frame.f_code.co_name
    #         lineNo = str(sys.exc_info()[2].tb_lineno)
    #         self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
    #         return False

    #     return True

    # def binFromGeometry7(self, fullAnalysis) -> bool:
    #     """
    #     Optimized version of binFromGeometry4 by GPT-5.2-Codex
    #     Vectorized receiver selection + bin updates using np.add.at.
    #     Keeps plane/sphere logic intact, but avoids per-trace Python loops for binning.

    #     After some bug fixes, the code seems much faster than v4.
    #     2026-01-23T15:36:58     binning    Thread : Binning completed. Elapsed time:0:03:43
    #     2026-01-20T18:49:41     binning    Thread : Binning completed. Elapsed time:0:15:43
    #     Data used: SPS data from Amstelland survey Swath 1
    #     """
    #     self.threadProgress = 0

    #     toLocalTransform, _ = self.glbTransform.inverted()

    #     # Fill source and receiver arrays with local coordinates if needed
    #     if np.all(self.output.srcGeom['LocX'] == 0.0) and np.all(self.output.srcGeom['LocY'] == 0.0):
    #         mapped = np.array([toLocalTransform.map(float(x), float(y)) for x, y in zip(self.output.srcGeom['East'], self.output.srcGeom['North'])], dtype=np.float32)
    #         self.output.srcGeom['LocX'] = mapped[:, 0]
    #         self.output.srcGeom['LocY'] = mapped[:, 1]

    #     if np.all(self.output.recGeom['LocX'] == 0.0) and np.all(self.output.recGeom['LocY'] == 0.0):
    #         mapped = np.array([toLocalTransform.map(float(x), float(y)) for x, y in zip(self.output.recGeom['East'], self.output.recGeom['North'])], dtype=np.float32)
    #         self.output.recGeom['LocX'] = mapped[:, 0]
    #         self.output.recGeom['LocY'] = mapped[:, 1]

    #     # Sort geometry arrays to ensure proper order
    #     self.output.srcGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.recGeom.sort(order=['Index', 'Line', 'Point'])
    #     self.output.relGeom.sort(order=['SrcInd', 'SrcLin', 'SrcPnt', 'RecInd', 'RecLin', 'RecMin', 'RecMax'])

    #     # Build relation index lookup
    #     relFileIndices = np.zeros((self.output.srcGeom.shape[0], 2), dtype=np.int32)
    #     marker = 0
    #     for i, srcRecord in enumerate(self.output.srcGeom):
    #         relFileIndices[i, 0] = marker
    #         for j in range(marker, self.output.relGeom.shape[0]):
    #             rel = self.output.relGeom[j]
    #             if rel['SrcPnt'] == srcRecord['Point'] and rel['SrcLin'] == srcRecord['Line'] and rel['SrcInd'] == srcRecord['Index']:
    #                 relFileIndices[i, 1] = j + 1
    #             else:
    #                 marker = j
    #                 break

    #     self.nShotPoint = 0
    #     self.nShotPoints = self.output.srcGeom.shape[0]

    #     try:
    #         for i, srcRecord in enumerate(self.output.srcGeom):
    #             if srcRecord['InUse'] == 0:
    #                 continue

    #             src = np.array([srcRecord['LocX'], srcRecord['LocY'], srcRecord['Elev']], dtype=np.float32)

    #             if QThread.currentThread().isInterruptionRequested():
    #                 raise StopIteration

    #             self.nShotPoint += 1
    #             threadProgress = (100 * self.nShotPoint) // self.nShotPoints
    #             if threadProgress > self.threadProgress:
    #                 self.threadProgress = threadProgress
    #                 self.progress.emit(threadProgress + 1)

    #             minRecord, maxRecord = relFileIndices[i]
    #             if maxRecord <= minRecord:
    #                 continue

    #             relSlice = self.output.relGeom[minRecord:maxRecord]

    #             # Vectorized receiver selection (still loop over relSlice but no concatenations)
    #             recMask = np.zeros(self.output.recGeom.shape[0], dtype=bool)
    #             for rel in relSlice:
    #                 recMask |= (
    #                     (self.output.recGeom['Index'] == rel['RecInd'])
    #                     & (self.output.recGeom['Line'] == rel['RecLin'])
    #                     & (self.output.recGeom['Point'] >= rel['RecMin'])
    #                     & (self.output.recGeom['Point'] <= rel['RecMax'])
    #                 )

    #             recArray = self.output.recGeom[recMask]
    #             recArray = recArray[recArray['InUse'] > 0]
    #             if recArray.shape[0] == 0:
    #                 continue

    #             recPoints = np.vstack((recArray['LocX'], recArray['LocY'], recArray['Elev'])).T

    #             traceArrays = self.buildBinningArraysFromSelectedReceivers(src, recPoints)
    #             if traceArrays is None:
    #                 continue
    #             cmpPoints, recPoints, hypArray, aziArray = traceArrays

    #             # mapped = np.array([self.binTransform.map(p[0], p[1]) for p in cmpPoints])
    #             if not self.updateBinOutputsForValidCmpPoints(src, cmpPoints, recPoints, hypArray, aziArray, fullAnalysis):
    #                 continue

    #     except StopIteration:
    #         self.errorText = 'binning from geometry cancelled by user'
    #         return False
    #     except BaseException as e:
    #         fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
    #         funcName = sys.exc_info()[2].tb_frame.f_code.co_name
    #         lineNo = str(sys.exc_info()[2].tb_lineno)
    #         self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
    #         return False

    #     self.calcFoldAndOffsetEssentials()

    #     if fullAnalysis:
    #         self.calcRmsOffsetValues()
    #         self.calcOffsetGapValues()
    #         self.calcUniqueFoldValues()
    #         self.calcOffsetAndAzimuthDistribution()
    #     else:
    #         self.output.anaOutput = None

    #     return True

    # def binFromGeometry9(self, fullAnalysis) -> bool:
    #     """
    #     Optimized binning with integer-normalized relation indexing to avoid gaps.
    #     """
    #     self.threadProgress = 0
    #     lookup = self.prepareGeometryRelationBinningLookup()

    #     self.nShotPoint = 0
    #     self.nShotPoints = self.output.srcGeom.shape[0]

    #     # Pre-extract data for Numba (cannot pass 'self')
    #     srcLocs = np.column_stack((self.output.srcGeom['LocX'], self.output.srcGeom['LocY'], self.output.srcGeom['Elev'], self.output.srcGeom['Line'], self.output.srcGeom['Point']))
    #     relFileIndices = np.column_stack((lookup.relLeft, lookup.relRight))
    #     recLocs = np.column_stack((self.output.recGeom['LocX'], self.output.recGeom['LocY'], self.output.recGeom['Elev']))

    #     # Extract Transform Matrix as raw array
    #     T = self.binTransform
    #     binMat = np.array([[T.m11(), T.m21(), T.m31()], [T.m12(), T.m22(), T.m32()], [0, 0, 1]], dtype=np.float32)
    #     S = self.st2Transform
    #     st2Mat = np.array([[S.m11(), S.m21(), S.m31()], [S.m12(), S.m22(), S.m32()], [0, 0, 1]], dtype=np.float32)

    #     # PRE-CALCULATE RECEIVER LINE BOUNDARIES
    #     # Create unique keys for (Index, Line) combinations
    #     recKeys = self.output.recGeom['Index'].astype(np.int64) * 1000000 + np.rint(self.output.recGeom['Line']).astype(np.int64)
    #     relKeys = lookup.relRecIndI.astype(np.int64) * 1000000 + lookup.relRecLinI.astype(np.int64)

    #     # Find start and end of every line in the receiver array
    #     relRecStartI = np.searchsorted(recKeys, relKeys, side='left').astype(np.int32)
    #     relRecEndI = np.searchsorted(recKeys, relKeys, side='right').astype(np.int32)

    #     maxFold = self.grid.fold if self.grid.fold > 0 else 1000

    #     try:
    #         batchSize = 500  # Larger batch size for better throughput
    #         for i in range(0, self.nShotPoints, batchSize):
    #             if QThread.currentThread().isInterruptionRequested(): raise StopIteration

    #             end = min(i + batchSize, self.nShotPoints)

    #             # Call the Parallel Kernel for this batch
    #             fnb.numbaBinBatchParallel(
    #                 srcLocs[i:end], # Pass srcLocs as a slice
    #                 relFileIndices[i:end],
    #                 recLocs,
    #                 self.output.recGeom['InUse'],
    #                 lookup.recPointI,
    #                 lookup.relRecMinI,
    #                 lookup.relRecMaxI,
    #                 relRecStartI,
    #                 relRecEndI,
    #                 self.output.binOutput,
    #                 self.output.minOffset,
    #                 self.output.maxOffset,
    #                 self.output.anaOutput,
    #                 binMat,
    #                 st2Mat,
    #                 fullAnalysis,
    #                 maxFold
    #             )

    #             self.nShotPoint = end
    #             self.progress.emit(int(100 * end / self.nShotPoints))

    #     except Exception as e: # Catch generic exceptions, but not StopIteration for interruption
    #         self.errorText = 'binning from geometry cancelled by user'
    #         return False
    #     except BaseException as e:
    #         fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
    #         funcName = sys.exc_info()[2].tb_frame.f_code.co_name
    #         lineNo = str(sys.exc_info()[2].tb_lineno)
    #         self.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
    #         return False

    #     self.calcFoldAndOffsetEssentials()

    #     if fullAnalysis:
    #         self.calcRmsOffsetValues()
    #         self.calcOffsetGapValues()
    #         self.calcUniqueFoldValues()
    #         self.calcOffsetAndAzimuthDistribution()
    #     else:
    #         self.output.anaOutput = None

    #     return True

    # def binTemplate6(self, block, template, templateOffset, fullAnalysis):
    #     """
    #     using *pointArray* for a significant speed up,
    #     introduced *vectorized* binning methods, removed need for a for loop

    #     On 25/03/2024 the earlier implementations of binTemplate v1 to v5 have been removed.
    #     They are still available in the roll-2024-03-04 folder in classes.py
    #     """

    #     # convert the template offset (a QVector3D) to a numpy array
    #     npTemplateOffset = np.array([templateOffset.x(), templateOffset.y(), templateOffset.z()], dtype=np.float32)

    #     # iterate over all seeds in a template; make sure we start wih *source* seeds
    #     for srcSeed in template.seedList:

    #         if not srcSeed.bSource:                                             # work only with source seeds here
    #             continue

    #         # we are in a source seed right now; use the numpy array functions to apply selection criteria
    #         srcArray = srcSeed.pointArray + npTemplateOffset

    #         if not block.borders.srcBorder.isNull():                            # deal with block's source  border if it isn't null()
    #             I = fnb.pointsInRect(srcArray, block.borders.srcBorder)
    #             if I.shape[0] == 0:
    #                 continue
    #             srcArray = srcArray[I, :]                                       # filter the source array

    #         for src in srcArray:                                                # iterate over all sources

    #             # begin thread progress code
    #             if QThread.currentThread().isInterruptionRequested():           # maybe stop at each shot...
    #                 raise StopIteration

    #             self.nShotPoint += 1
    #             threadProgress = (100 * self.nShotPoint) // self.nShotPoints    # apply integer divide
    #             if threadProgress > self.threadProgress:
    #                 self.threadProgress = threadProgress
    #                 self.progress.emit(threadProgress + 1)
    #             # end thread progress code

    #             # now iterate over all seeds to find the receivers
    #             for recSeed in template.seedList:                               # iterate over all rec seeds in a template
    #                 if recSeed.bSource:                                         # work with receiver seeds here
    #                     continue

    #                 # we are in a receiver seed right now; use the numpy array functions to apply selection criteria
    #                 recPoints = recSeed.pointArray + npTemplateOffset

    #                 if not block.borders.recBorder.isNull():                    # deal with block's receiver border if it isn't null()
    #                     I = fnb.pointsInRect(recPoints, block.borders.recBorder)
    #                     if I.shape[0] == 0:
    #                         continue
    #                     recPoints = recPoints[I, :]

    #                 cmpPoints = np.zeros(shape=(recPoints.shape[0], 3), dtype=np.float32)

    #                 if self.binning.method == BinningType.cmp:
    #                     # create all cmp-locations for this shot point, by simply taking the average from src and rec locations
    #                     cmpPoints = (recPoints + src) * 0.5
    #                 elif self.binning.method == BinningType.plane:
    #                     # create all cmp-locations using the following steps:
    #                     # 1. mirror the source location against the plane
    #                     # 2. find out where/if the lines defined by the source-mirror with the receivers cuts through the plane
    #                     # 3. these locations are the cmp locations for binnenig against a dipping plane
    #                     srcMirrorNp = self.localPlane.mirrorPointNp(src)

    #                     # now find all intersection points with the dipping plane, and prune any non-contributing receivers
    #                     cmpPoints, recPoints = self.localPlane.IntersectLinesAtPointNp(srcMirrorNp, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

    #                     if cmpPoints is None:
    #                         continue
    #                 elif self.binning.method == BinningType.sphere:

    #                     # now find all intersection points with the sphere, and prune any non-contributing receivers
    #                     cmpPoints, recPoints = self.localSphere.ReflectSphereAtPointsNp(src, recPoints, self.angles.reflection.x(), self.angles.reflection.y())

    #                     if cmpPoints is None:
    #                         continue

    #                 I = fnb.pointsInRect(cmpPoints, self.output.rctOutput)
    #                 if I.shape[0] == 0:
    #                     continue

    #                 cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array
    #                 recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

    #                 size = recPoints.shape[0]
    #                 offArray = np.zeros(shape=(size, 3), dtype=np.float32)      # allocate the offset array according to rec array
    #                 offArray = recPoints - src                                  # fill the offset array with  (x,y,z) values

    #                 I = fnb.pointsInRect(offArray, self.offset.rctOffsets)
    #                 if I.shape[0] == 0:
    #                     continue

    #                 offArray = offArray[I, :]                                   # filter the off-array
    #                 cmpPoints = cmpPoints[I, :]                                 # filter the cmp-array too, as we still need this
    #                 recPoints = recPoints[I, :]                                 # filter the rec-array too, as we still need this

    #                 size = recPoints.shape[0]
    #                 hypArray = np.zeros(shape=(size, 1), dtype=np.float32)      # allocate the radius array according to rec array
    #                 hypArray = np.hypot(offArray[:, 0], offArray[:, 1])         # calculate radial offset per row
    #                 aziArray = np.arctan2(offArray[:, 0], offArray[:, 1])       # calculate offset angles
    #                 aziArray = np.rad2deg(aziArray)                             # get angles in degrees instead of radians
    #                 aziArray = (aziArray + 360.0) % 360.0                       # convert angles to 0-360 range

    #                 r1 = self.offset.radOffsets.x()                             # r1 = minimum radius
    #                 r2 = self.offset.radOffsets.y()                             # r2 = maximum radius
    #                 if r2 > 0:                                                  # we need to apply the radial offset selection criteria
    #                     I = (hypArray[:] >= r1) & (hypArray[:] <= r2)
    #                     if np.count_nonzero(I) == 0:
    #                         continue                                            # continue with next recSeed

    #                     hypArray = hypArray[I]                                  # filter the radial offset-array
    #                     aziArray = aziArray[I]                                  # filter the offset-angle array
    #                     offArray = offArray[I, :]                               # filter the off-array too, as we still need this
    #                     cmpPoints = cmpPoints[I, :]                             # filter the cmp-array too, as we still need this
    #                     recPoints = recPoints[I, :]                             # filter the rec-array too, as we still need this

    #                 # now work on the TWT aspect of the src, cmp & rec positions
    #                 if self.binning.method == BinningType.cmp:
    #                     upDnArray = recPoints - src                             # straigth rays; total length of both legs
    #                     totalTime = np.linalg.norm(upDnArray, axis=1)           # get length of the rays
    #                 else:
    #                     dnArray = cmpPoints - src                             # 1st leg of the rays
    #                     upArray = cmpPoints - recPoints                       # 2nd leg of the rays
    #                     dnTime = np.linalg.norm(dnArray, axis=1)            # get length of the 1st leg
    #                     upTime = np.linalg.norm(upArray, axis=1)            # get length of the 2nd leg
    #                     totalTime = dnTime + upTime                         # total length of both legs

    #                 totalTime *= self.binning.slowness                          # convert distance into travel time

    #                 #  we have applied all filters now; time to save the traces that 'pass' all selection criteria
    #                 for count, cmp in enumerate(cmpPoints):                     # process all traces
    #                     try:                                                    # protect against potential index errors
    #                         cmpX = cmp[0]                                       # decompose (x, y, z) cmp into x, y components
    #                         cmpY = cmp[1]

    #                         x, y = self.binTransform.map(cmpX, cmpY)            # get local position in bin area
    #                         nx = int(x)                                         # truncate into integer indices
    #                         ny = int(y)                                         # truncate into integer indices

    #                         if fullAnalysis:
    #                             fold = self.output.binOutput[nx, ny]
    #                             if fold < self.grid.fold:                       # prevent overwriting next bin
    #                                 # self.output.anaOutput[nx, ny, fold] = ( srcLoc.x(), srcLoc.y(), recLoc.x(), recLoc.y(), cmpLoc.x(), cmpLoc.y(), 0, 0, 0, 0)
    #                                 # line & stake nrs for reporting in extended np-array

    #                                 # from numpy documentation: it follows that x[0, 2] == x[0][2] though the second case is less efficient;
    #                                 # as a new temporary array is created after the first index that is subsequently indexed by 2.
    #                                 # for this reason I replaced all [a][b][c][d] indices by [a, b, c, d]

    #                                 stkX, stkY = self.st2Transform.map(cmpX, cmpY)
    #                                 self.output.anaOutput[nx, ny, fold, 0] = int(stkX)
    #                                 self.output.anaOutput[nx, ny, fold, 1] = int(stkY)
    #                                 self.output.anaOutput[nx, ny, fold, 2] = fold + 1           # to make fold run from 1 to N
    #                                 self.output.anaOutput[nx, ny, fold, 3] = src[0]
    #                                 self.output.anaOutput[nx, ny, fold, 4] = src[1]
    #                                 self.output.anaOutput[nx, ny, fold, 5] = recPoints[count, 0]
    #                                 self.output.anaOutput[nx, ny, fold, 6] = recPoints[count, 1]
    #                                 self.output.anaOutput[nx, ny, fold, 7] = cmpPoints[count, 0]
    #                                 self.output.anaOutput[nx, ny, fold, 8] = cmpPoints[count, 1]
    #                                 self.output.anaOutput[nx, ny, fold, 9] = totalTime[count]
    #                                 self.output.anaOutput[nx, ny, fold, 10] = hypArray[count]
    #                                 self.output.anaOutput[nx, ny, fold, 11] = aziArray[count]
    #                                 # self.output.anaOutput[nx, ny, fold, 12] = -1

    #                         # all selection criteria have been fullfilled; use the trace
    #                         self.output.binOutput[nx, ny] = self.output.binOutput[nx, ny] + 1
    #                         self.output.minOffset[nx, ny] = min(self.output.minOffset[nx, ny], hypArray[count])
    #                         self.output.maxOffset[nx, ny] = max(self.output.maxOffset[nx, ny], hypArray[count])

    #                     # rather than checking nx, ny & fold, use exception handling to deal with index errors
    #                     # note: the other exceptions are handled in binFromTemplates()
    #                     except IndexError:
    #                         continue
