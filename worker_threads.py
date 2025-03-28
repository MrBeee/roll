import time

from qgis.PyQt.QtCore import QMutex, QObject, QThread, pyqtSignal

from . import config  # used to pass initial settings
from .functions import myPrint
from .roll_survey import RollSurvey

# ptvsd  is needed to debug a worker thread.
# See: https://github.com/microsoft/ptvsd/issues/1189

try:                                                                            # uncomment to debug thread
    havePtvsd = True                                                            # uncomment to debug thread
    import ptvsd  # uncomment to debug thread
except ImportError as ie:                                                       # uncomment to debug thread
    havePtvsd = False                                                           # uncomment to debug thread

# See: https://stackoverflow.com/questions/20324804/how-to-use-qthread-correctly-in-pyqt-with-movetothread
# See: https://realpython.com/python-pyqt-qthread/#using-qthread-vs-pythons-threading
# See: https://mayaposch.wordpress.com/2011/11/01/how-to-really-truly-use-qthreads-the-full-explanation/
# See: http://ilearnstuff.blogspot.com/2012/08/when-qthread-isnt-thread.html
# See: http://ilearnstuff.blogspot.com/2012/09/qthread-best-practices-when-qthread.html

# first approach; subclass QThread - no longer recommended with Python 3.0
# See: https://stackoverflow.com/questions/9190169/threading-and-information-passing-how-to
# See: https://www.programiz.com/python-programming/shallow-deep-copy for deep copy info


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
    finished = pyqtSignal(bool)

    def __init__(self, xmlString):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = False
        self.fileName = None

        # the following function also calculates the required transforms
        self.survey.fromXmlString(xmlString, True)                              # fully populate the object AND create arrays

    def setExtended(self, extended):
        self.extended = extended

    def setMemMappedFile(self, analysisFile):
        self.survey.output.anaOutput = analysisFile

    def setGeometryArrays(self, srcGeom, relGeom, recGeom):
        self.survey.output.srcGeom = srcGeom
        self.survey.output.relGeom = relGeom
        self.survey.output.recGeom = recGeom

    def run(self):
        """Long-running task."""
        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            # Please comment the next two lines when you are not debugging, as it will cause an exception (ConnectionRefusedError)
            if havePtvsd and config.ptvsd:
                ptvsd.debug_this_thread()                                       # uncomment to debug thread

            success = self.survey.setupBinFromGeometry(self.extended)           # calculate fold map and min/max offsets
        except BaseException as e:
            self.survey.errorText = str(e)
            success = False

        self.finished.emit(success)


class BinningWorker(QObject):
    # Example Worker using getters and setter using a mutex
    # See: https://stackoverflow.com/questions/9190169/threading-and-information-passing-how-to
    finished = pyqtSignal(bool)

    def __init__(self, xmlString):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = False
        self.fileName = None

        # the following function also calculates the required transforms, and optionally creates th binning arrays
        self.survey.fromXmlString(xmlString, True)                              # fully populate the object AND create arrays

    def setExtended(self, extended):
        self.extended = extended

    def setMemMappedFile(self, analysisFile):
        self.survey.output.anaOutput = analysisFile

    def run(self):
        """Long-running task."""
        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            # Please comment the next two lines when you are not debugging, as it will cause an exception (ConnectionRefusedError)
            if havePtvsd and config.ptvsd:
                ptvsd.debug_this_thread()                                       # uncomment to debug thread

            success = self.survey.setupBinFromTemplates(self.extended)          # calculate fold map and min/max offsets
        except BaseException as e:
            self.survey.errorText = str(e)
            success = False

        self.finished.emit(success)


class GeometryWorker(QObject):
    finished = pyqtSignal(bool)

    def __init__(self, xmlString):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = False
        self.fileName = None

        # the following function also calculates the required transforms
        self.survey.fromXmlString(xmlString, False)                             # populate the object; but don't need binning arrays

    def run(self):
        """Long-running task."""

        self.survey.calcNoShotPoints()                                          # necessary step before calculating geometry

        try:
            # Next line is needed to debug a 'native thread' in VS Code. See: https://github.com/microsoft/ptvsd/issues/1189
            # Please comment the next two lines when you are not debugging, as it will cause an exception (ConnectionRefusedError)
            if havePtvsd and config.ptvsd:
                ptvsd.debug_this_thread()                                       # uncomment to debug thread

            success = self.survey.setupGeometryFromTemplates()                  # calculate src, rel, rec geometry arrays
        except BaseException as e:
            self.survey.errorText = str(e)
            success = False

        self.finished.emit(success)


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
