import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from qgis.PyQt.QtCore import QMutex, QObject, QThread, pyqtSignal

from .aux_functions import myPrint
from .roll_survey import RollSurvey

# debugpy  is needed to debug a worker thread.
# See: https://github.com/microsoft/ptvsd/issues/1189

try:
    haveDebugpy = True
    import debugpy
except ImportError as ie:
    haveDebugpy = False

# See: https://stackoverflow.com/questions/20324804/how-to-use-qthread-correctly-in-pyqt-with-movetothread
# See: https://realpython.com/python-pyqt-qthread/#using-qthread-vs-pythons-threading
# See: https://mayaposch.wordpress.com/2011/11/01/how-to-really-truly-use-qthreads-the-full-explanation/
# See: http://ilearnstuff.blogspot.com/2012/08/when-qthread-isnt-thread.html
# See: http://ilearnstuff.blogspot.com/2012/09/qthread-best-practices-when-qthread.html

# first approach; subclass QThread - no longer recommended with Python 3.0
# See: https://stackoverflow.com/questions/9190169/threading-and-information-passing-how-to
# See: https://www.programiz.com/python-programming/shallow-deep-copy for deep copy info


@dataclass
class BinningFromTemplatesRequest:
    xmlString: str
    extended: bool = False
    analysisFile: object = None
    debugpyEnabled: bool = False


@dataclass
class BinningFromTemplatesResult:
    success: bool
    errorText: str = ''
    binOutput: Any = None
    minOffset: Any = None
    maxOffset: Any = None
    minimumFold: float = 0.0
    maximumFold: float = 0.0
    minMinOffset: float = 0.0
    maxMinOffset: float = 0.0
    minMaxOffset: float = 0.0
    maxMaxOffset: float = 0.0
    minRmsOffset: float | None = None
    maxRmsOffset: float | None = None
    rmsOffset: Any = None
    ofAziHist: Any = None
    offstHist: Any = None
    cmpTransform: Any = None
    anaOutputShape: tuple[int, ...] | None = None


@dataclass
class BinningFromGeometryRequest:
    xmlString: str
    srcGeom: Any
    relGeom: Any
    recGeom: Any
    extended: bool = False
    analysisFile: object = None
    debugpyEnabled: bool = False


@dataclass
class BinningFromGeometryResult:
    success: bool
    errorText: str = ''
    binOutput: Any = None
    minOffset: Any = None
    maxOffset: Any = None
    minimumFold: float = 0.0
    maximumFold: float = 0.0
    minMinOffset: float = 0.0
    maxMinOffset: float = 0.0
    minMaxOffset: float = 0.0
    maxMaxOffset: float = 0.0
    minRmsOffset: float | None = None
    maxRmsOffset: float | None = None
    rmsOffset: Any = None
    ofAziHist: Any = None
    offstHist: Any = None
    cmpTransform: Any = None
    anaOutputShape: tuple[int, ...] | None = None


@dataclass
class GeometryFromTemplatesRequest:
    xmlString: str
    debugpyEnabled: bool = False
    includeProfiling: bool = False


@dataclass
class GeometryProfilingPayload:
    timerTmin: Any
    timerTmax: Any
    timerTtot: Any
    timerFreq: Any


@dataclass
class GeometryFromTemplatesResult:
    success: bool
    errorText: str = ''
    recGeom: Any = None
    relGeom: Any = None
    srcGeom: Any = None
    profiling: GeometryProfilingPayload | None = None


class BinningThread(QThread):
    progress = pyqtSignal(int)

    def __init__(self, xmlString):
        super().__init__()

        # the purpose of passing an xml-string instead of a survey-object is to fully decouple both objects.
        # this allows for updating self.survey in the main thread, wthout affecting the worker thread.
        # initially this was attemped using copy.deepcopy(self.survey) but this led to to 'pickle' errors.
        # most likely the survey object is too complex, so the to/from xml detour make an easy fix.
        # See: https://docs.python.org/3/library/pickle.html#what-can-be-pickled-and-unpickled

        self.survey = RollSurvey()                                              # create 'virgin' object
        self.survey.fromXmlString(xmlString, True)                              # fully populate the object AND create arrays

    def run(self):
        for x in range(5, 101, 2):
            myPrint(x)
            time.sleep(0.5)
            self.progress.emit(x)

            if self.isInterruptionRequested():
                break


# Second approach; create a worker QObject, then call worker.moveToThread() using the thread as an argument
# See: https://github.com/PyQt5/PyQt/blob/master/QThread/moveToThread.py good reference !
# See: https://stackoverflow.com/questions/74348042/how-to-assign-variables-to-worker-thread-in-python-pyqt5 for passing data


class BinFromGeometryWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: BinningFromGeometryRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = request.extended
        self.debugpyEnabled = request.debugpyEnabled

        # the following function also calculates the required transforms
        self.survey.fromXmlString(request.xmlString, True)                      # fully populate the object AND create arrays
        self.survey.output.anaOutput = request.analysisFile
        self.survey.output.srcGeom = request.srcGeom
        self.survey.output.relGeom = request.relGeom
        self.survey.output.recGeom = request.recGeom

    def run(self):
        """Long-running task."""
        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            # Things have changed a bit; see https://stackoverflow.com/questions/71834240/how-to-debug-pyqt5-threads-in-visual-studio-code
            # See also:https://code.visualstudio.com/docs/python/debugging#_troubleshooting
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()

            success = self.survey.setupBinFromGeometry(self.extended)           # calculate fold map and min/max offsets
        except BaseException as e:
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.survey.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            success = False

        self.resultReady.emit(self.buildResult(success))
        self.finished.emit()

    def buildResult(self, success: bool) -> BinningFromGeometryResult:
        if not success:
            return BinningFromGeometryResult(success=False, errorText=self.survey.errorText)

        output = self.survey.output
        minRmsOffset = None if output.rmsOffset is None else max(output.minRmsOffset, 0)
        maxRmsOffset = None if output.rmsOffset is None else max(output.maxRmsOffset, 0)
        return BinningFromGeometryResult(
            success=True,
            binOutput=output.binOutput,
            minOffset=output.minOffset,
            maxOffset=output.maxOffset,
            minimumFold=max(output.minimumFold, 0),
            maximumFold=max(output.maximumFold, 0),
            minMinOffset=max(output.minMinOffset, 0),
            maxMinOffset=max(output.maxMinOffset, 0),
            minMaxOffset=max(output.minMaxOffset, 0),
            maxMaxOffset=max(output.maxMaxOffset, 0),
            minRmsOffset=minRmsOffset,
            maxRmsOffset=maxRmsOffset,
            rmsOffset=output.rmsOffset,
            ofAziHist=output.ofAziHist,
            offstHist=output.offstHist,
            cmpTransform=self.survey.cmpTransform,
            anaOutputShape=None if output.anaOutput is None else output.anaOutput.shape,
        )


class BinningWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: BinningFromTemplatesRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = request.extended
        self.debugpyEnabled = request.debugpyEnabled

        # the following function also calculates the required transforms, and optionally creates th binning arrays
        self.survey.fromXmlString(request.xmlString, True)                      # fully populate the object AND create arrays
        self.survey.output.anaOutput = request.analysisFile

    def run(self):
        """Long-running task."""
        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()

            success = self.survey.setupBinFromTemplates(self.extended)          # calculate fold map and min/max offsets
        except BaseException as e:
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.survey.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            success = False

        self.resultReady.emit(self.buildResult(success))
        self.finished.emit()

    def buildResult(self, success: bool) -> BinningFromTemplatesResult:
        if not success:
            return BinningFromTemplatesResult(success=False, errorText=self.survey.errorText)

        output = self.survey.output
        minRmsOffset = None if output.rmsOffset is None else max(output.minRmsOffset, 0)
        maxRmsOffset = None if output.rmsOffset is None else max(output.maxRmsOffset, 0)
        return BinningFromTemplatesResult(
            success=True,
            binOutput=output.binOutput,
            minOffset=output.minOffset,
            maxOffset=output.maxOffset,
            minimumFold=max(output.minimumFold, 0),
            maximumFold=max(output.maximumFold, 0),
            minMinOffset=max(output.minMinOffset, 0),
            maxMinOffset=max(output.maxMinOffset, 0),
            minMaxOffset=max(output.minMaxOffset, 0),
            maxMaxOffset=max(output.maxMaxOffset, 0),
            minRmsOffset=minRmsOffset,
            maxRmsOffset=maxRmsOffset,
            rmsOffset=output.rmsOffset,
            ofAziHist=output.ofAziHist,
            offstHist=output.offstHist,
            cmpTransform=self.survey.cmpTransform,
            anaOutputShape=None if output.anaOutput is None else output.anaOutput.shape,
        )


class GeometryWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: GeometryFromTemplatesRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.debugpyEnabled = request.debugpyEnabled
        self.includeProfiling = request.includeProfiling

        # the following function also calculates the required transforms
        self.survey.fromXmlString(request.xmlString, False)                     # populate the object; but don't need binning arrays

    def run(self):
        """Long-running task."""

        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()                                       # uncomment to debug thread

            success = self.survey.setupGeometryFromTemplates()                  # calculate src, rel, rec geometry arrays
        except BaseException as e:
            # self.errorText = str(e)
            # See: https://stackoverflow.com/questions/1278705/when-i-catch-an-exception-how-do-i-get-the-type-file-and-line-number
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.survey.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            success = False

        self.resultReady.emit(self.buildResult(success))
        self.finished.emit()

    def buildResult(self, success: bool) -> GeometryFromTemplatesResult:
        profiling = None
        if self.includeProfiling:
            profiling = GeometryProfilingPayload(
                timerTmin=tuple(self.survey.timerTmin),
                timerTmax=tuple(self.survey.timerTmax),
                timerTtot=tuple(self.survey.timerTtot),
                timerFreq=tuple(self.survey.timerFreq),
            )

        if not success:
            return GeometryFromTemplatesResult(
                success=False,
                errorText=self.survey.errorText,
                profiling=profiling,
            )

        output = self.survey.output
        return GeometryFromTemplatesResult(
            success=True,
            recGeom=output.recGeom,
            relGeom=output.relGeom,
            srcGeom=output.srcGeom,
            profiling=profiling,
        )


class Worker(QObject):
    # Example Worker using getters and setters using a mutex
    # See: https://stackoverflow.com/questions/9190169/threading-and-information-passing-how-to

    finished = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        self.firstNameText = ''
        self._mutex = QMutex()

    def getFirstName(self):
        self._mutex.lock()
        text = self.firstNameText
        self._mutex.unlock()
        return text

    def setFirstName(self, text):
        self._mutex.lock()
        self.firstNameText = text
        self._mutex.unlock()

    def run(self):
        firstname = self.getFirstName()
        for _ in range(10):
            time.sleep(1)
            myPrint(firstname)
        self.finished.emit()
