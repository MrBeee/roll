# coding=utf-8

from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from typing import Any, Callable, Protocol, cast

from qgis.PyQt.QtCore import QThread

from .enums_and_int_flags import MsgType
from .worker_threads import (BinningFromGeometryRequest,
                             BinningFromTemplatesRequest,
                             GeometryFromTemplatesRequest)


class WorkerThreadProtocol(Protocol):
    started: Any
    finished: Any

    def isRunning(self) -> bool: ...
    def requestInterruption(self) -> None: ...
    def quit(self) -> None: ...
    def wait(self, msecs: int = ...) -> bool: ...
    def start(self, priority: QThread.Priority = ...) -> None: ...
    def deleteLater(self) -> None: ...


@dataclass(frozen=True)
class WorkerJobSpec:
    name: str
    progressLabelText: str
    startMessage: str
    startMessageType: MsgType
    workerFactory: Callable[[object], object]
    request: object
    resultHandler: Callable[[object, timedelta], None]
    resetAnalysisOnFinish: bool = False
    completionTabIndex: int | None = None


@dataclass
class ActiveWorkerOperation:
    job: WorkerJobSpec
    thread: WorkerThreadProtocol
    worker: object
    cancelRequested: bool = False


class WorkerOperationController:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider
        self.activeOperation: ActiveWorkerOperation | None = None

    def startBinningFromTemplates(self, fullAnalysis: bool) -> bool:
        if fullAnalysis:
            if not self.window.prepFullBinningConditions():
                return False
            progressLabelText = 'Bin from Templates - full analysis'
        else:
            progressLabelText = 'Bin from Templates - basic analysis'

        return self._startJob(self._buildBinningFromTemplatesJob(fullAnalysis, progressLabelText))

    def startBinningFromGeometry(self, fullAnalysis: bool) -> bool:
        if self.window.srcGeom is None or self.window.relGeom is None or self.window.recGeom is None:
            self.window.appendLogMessage('Thread : One or more of the geometry files have not been defined', MsgType.Error)
            return False

        if fullAnalysis:
            if not self.window.prepFullBinningConditions():
                return False
            progressLabelText = 'Bin from Geometry - full analysis'
        else:
            progressLabelText = 'Bin from Geometry - basic analysis'

        return self._startJob(self._buildBinningFromGeometryJob(fullAnalysis, progressLabelText))

    def startBinningFromSps(self, fullAnalysis: bool) -> bool:
        if self.window.spsImport is None or self.window.rpsImport is None:
            self.window.appendLogMessage('Thread : One or more of the sps files have not been defined', MsgType.Error)
            return False

        if fullAnalysis:
            if not self.window.prepFullBinningConditions():
                return False
            progressLabelText = 'Bin from imported SPS - full analysis'
        else:
            progressLabelText = 'Bin from imported SPS - basic analysis'

        if self.window.xpsImport is None:
            self.window.appendLogMessage(
                'Thread : Relation file has not been defined; using all available receivers for each shot',
                MsgType.Binning,
            )

        return self._startJob(self._buildBinningFromSpsJob(fullAnalysis, progressLabelText))

    def startGeometryFromTemplates(self) -> bool:
        return self._startJob(self._buildGeometryFromTemplatesJob())

    def stopCurrentOperation(self) -> None:
        activeOperation = self.activeOperation
        if activeOperation is None or not activeOperation.thread.isRunning():
            return

        activeOperation.cancelRequested = True
        self.window.progressLabel.setText('Cancelling work in progress...')
        activeOperation.thread.requestInterruption()

    def cancelCurrentOperation(self, waitTimeout: int | None = None, clearLayoutImage: bool = True) -> None:
        activeOperation = self.activeOperation
        if activeOperation is not None and activeOperation.thread.isRunning():
            self.stopCurrentOperation()
            activeOperation.thread.quit()
            if waitTimeout is None:
                activeOperation.thread.wait()
            else:
                activeOperation.thread.wait(waitTimeout)

        self._cleanupAfterOperation(resetAnalysis=True, clearLayoutImage=clearLayoutImage)

    def shutdownCurrentOperation(self, waitTimeout: int = 2000) -> None:
        self.cancelCurrentOperation(waitTimeout=waitTimeout, clearLayoutImage=False)

    def hasRunningOperation(self) -> bool:
        activeOperation = self.activeOperation
        return activeOperation is not None and activeOperation.thread.isRunning()

    def elapsedTime(self) -> timedelta:
        if self.window.startTime is None:
            return timedelta(0)

        timerFunc = self.runtimeDependenciesProvider()['timer']
        endTime = timerFunc()
        elapsed = timedelta(seconds=endTime - self.window.startTime)
        return timedelta(seconds=ceil(elapsed.total_seconds()))

    def _buildBinningFromTemplatesJob(self, fullAnalysis: bool, progressLabelText: str) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        request = BinningFromTemplatesRequest(
            xmlString=self.window.survey.toXmlString(),
            extended=fullAnalysis,
            analysisFile=self.window.output.anaOutput,
            debugpyEnabled=self.window.appSettings.debugpy,
        )
        return WorkerJobSpec(
            name='bin-from-templates',
            progressLabelText=progressLabelText,
            startMessage=f"Thread : Started 'Bin from templates', using {self.window.survey.nShotPoints:,} shot points",
            startMessageType=MsgType.Binning,
            workerFactory=dependencies['BinningWorker'],
            request=request,
            resultHandler=self.window.applyBinningWorkerResult,
        )

    def _buildBinningFromGeometryJob(self, fullAnalysis: bool, progressLabelText: str) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        request = BinningFromGeometryRequest(
            xmlString=self.window.survey.toXmlString(),
            srcGeom=self.window.srcGeom,
            relGeom=self.window.relGeom,
            recGeom=self.window.recGeom,
            extended=fullAnalysis,
            analysisFile=self.window.output.anaOutput,
            debugpyEnabled=self.window.appSettings.debugpy,
        )
        return WorkerJobSpec(
            name='bin-from-geometry',
            progressLabelText=progressLabelText,
            startMessage=f"Thread : Started 'Bin from geometry', using {self.window.srcGeom.shape[0]:,} shot points",
            startMessageType=MsgType.Binning,
            workerFactory=dependencies['BinFromGeometryWorker'],
            request=request,
            resultHandler=self.window.applyBinningWorkerResult,
        )

    def _buildBinningFromSpsJob(self, fullAnalysis: bool, progressLabelText: str) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        request = BinningFromGeometryRequest(
            xmlString=self.window.survey.toXmlString(),
            srcGeom=self.window.spsImport,
            relGeom=self.window.xpsImport,
            recGeom=self.window.rpsImport,
            extended=fullAnalysis,
            analysisFile=self.window.output.anaOutput,
            debugpyEnabled=self.window.appSettings.debugpy,
        )
        return WorkerJobSpec(
            name='bin-from-sps',
            progressLabelText=progressLabelText,
            startMessage=f"Thread : Started 'Bin from Imported SPS', using {self.window.spsImport.shape[0]:,} shot points",
            startMessageType=MsgType.Binning,
            workerFactory=dependencies['BinFromGeometryWorker'],
            request=request,
            resultHandler=self.window.applyBinningWorkerResult,
        )

    def _buildGeometryFromTemplatesJob(self) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        request = GeometryFromTemplatesRequest(
            xmlString=self.window.survey.toXmlString(),
            debugpyEnabled=self.window.appSettings.debugpy,
            includeProfiling=self.window.appSettings.debug,
        )
        return WorkerJobSpec(
            name='geometry-from-templates',
            progressLabelText='Create Geometry from Templates',
            startMessage=f"Thread : Started 'Create Geometry from Templates', from {self.window.survey.nShotPoints:,} shot points",
            startMessageType=MsgType.Geometry,
            workerFactory=dependencies['GeometryWorker'],
            request=request,
            resultHandler=self.window.applyGeometryWorkerResult,
            completionTabIndex=3,
        )

    def _startJob(self, job: WorkerJobSpec) -> bool:
        self._showRunningUi(job.progressLabelText)
        self.window.appendLogMessage(job.startMessage, job.startMessageType)

        threadFactory = self.runtimeDependenciesProvider()['QThread']
        thread = cast(WorkerThreadProtocol, threadFactory())
        worker = job.workerFactory(job.request)
        worker.moveToThread(thread)

        self.activeOperation = ActiveWorkerOperation(job=job, thread=thread, worker=worker)
        self.window.thread = thread
        self.window.worker = worker

        self._bindJobSignals(thread, worker, job)
        self._setStartTime()
        thread.start(QThread.Priority.NormalPriority)
        return True

    def _bindJobSignals(self, thread: WorkerThreadProtocol, worker, job: WorkerJobSpec) -> None:
        thread.started.connect(worker.run)
        worker.survey.progress.connect(self.window.threadProgress)
        worker.survey.message.connect(self.window.threadMessage)
        worker.resultReady.connect(lambda result, currentJob=job: self._handleJobResult(currentJob, result))
        worker.finished.connect(thread.quit)
        workerDeleteLater = getattr(worker, 'deleteLater', None)
        if callable(workerDeleteLater):
            worker.finished.connect(workerDeleteLater)

        threadDeleteLater = getattr(thread, 'deleteLater', None)
        finishedSignal = getattr(thread, 'finished', None)
        if callable(threadDeleteLater) and finishedSignal is not None:
            finishedSignal.connect(threadDeleteLater)

    def finishCurrentOperation(self, result, resultHandler: Callable[[object, timedelta], None], *, resetAnalysis: bool, completionTabIndex: int | None = None) -> None:
        activeOperation = self.activeOperation
        if activeOperation is not None and activeOperation.cancelRequested:
            self._cleanupAfterOperation(resetAnalysis=True, clearLayoutImage=True)
            return

        resultHandler(result, self.elapsedTime())
        self._cleanupAfterOperation(resetAnalysis=resetAnalysis, completionTabIndex=completionTabIndex)

    def _handleJobResult(self, job: WorkerJobSpec, result) -> None:
        activeOperation = self.activeOperation
        if activeOperation is None or activeOperation.job is not job:
            return

        self.finishCurrentOperation(
            result,
            job.resultHandler,
            resetAnalysis=job.resetAnalysisOnFinish,
            completionTabIndex=job.completionTabIndex,
        )

    def _showRunningUi(self, labelText: str) -> None:
        self.window.progressLabel.setText(labelText)
        self.window.showStatusbarWidgets()
        self.window.enableProcessingMenuItems(False)

    def _cleanupAfterOperation(self, *, resetAnalysis: bool, clearLayoutImage: bool = False, completionTabIndex: int | None = None) -> None:
        self.activeOperation = None
        self.window.worker = None
        self.window.thread = None
        self.window.startTime = None

        self.window.hideStatusbarWidgets()

        if clearLayoutImage:
            self.window.layoutImg = None
            self.window.layoutImItem = None
            self.window.handleImageSelection()

        self.window.updateMenuStatus(resetAnalysis)
        self.window.enableProcessingMenuItems(True)

        if completionTabIndex is not None:
            self.window.mainTabWidget.setCurrentIndex(completionTabIndex)

    def _setStartTime(self) -> None:
        timerFunc = self.runtimeDependenciesProvider()['timer']
        self.window.startTime = timerFunc()
