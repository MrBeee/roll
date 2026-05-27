# coding=utf-8

from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from typing import Any, Callable, Protocol, cast

from qgis.PyQt.QtCore import QThread

from .enums_and_int_flags import MsgType
from .worker_threads import (BinningFromGeometryRequest,
                             BinningFromTemplatesRequest,
                             CfpFromTemplatesRequest, CfpFromTraceTableRequest,
                             GeometryFromTemplatesRequest)


class WorkerThreadProtocol(Protocol):
    started: Any
    finished: Any

    def isRunning(self) -> bool:
        ...

    def requestInterruption(self) -> None:
        ...

    def quit(self) -> None:
        ...

    def wait(self, msecs: int = ...) -> bool:
        ...

    def start(self, priority: QThread.Priority = ...) -> None:
        ...

    def deleteLater(self) -> None:
        ...


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
    cancellationWarningShown: bool = False


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

    def startCfpAnalysisFromTemplates(self) -> bool:
        if self.window.survey is None:
            self.window.appendLogMessage('Thread : No survey has been defined', MsgType.Error)
            return False

        return self._startJob(self._buildCfpAnalysisFromTemplatesJob())

    def startCfpAnalysisFromTraceTable(self) -> bool:
        if self.window.survey is None:
            self.window.appendLogMessage('Thread : No survey has been defined', MsgType.Error)
            return False

        if self.window.output.anaOutput is None:
            self.window.appendLogMessage('Thread : Trace table has not been defined', MsgType.Error)
            return False

        return self._startJob(self._buildCfpAnalysisFromTraceTableJob())

    def stopCurrentOperation(self) -> None:
        activeOperation = self.activeOperation
        # Defensive: check for deleted thread object
        if (
            activeOperation is None or                              # noqa: W503, W504
            getattr(activeOperation, 'thread', None) is None or     # noqa: W503, W504
            not hasattr(activeOperation.thread, 'isRunning')
        ):
            return

        try:
            if not activeOperation.thread.isRunning():
                return
        except RuntimeError:
            # QThread C++ object already deleted; clean up references
            self.activeOperation = None
            self.window.worker = None
            self.window.thread = None
            return

        if activeOperation.cancelRequested:
            return

        activeOperation.cancelRequested = True
        self.window.progressLabel.setText('Cancelling work in progress...')
        self.window.appendLogMessage('Thread : User interrupted worker thread', MsgType.Warning)
        try:
            if hasattr(activeOperation.thread, 'requestInterruption'):
                activeOperation.thread.requestInterruption()
        except RuntimeError:
            # QThread C++ object already deleted; clean up references
            self.activeOperation = None
            self.window.worker = None
            self.window.thread = None
            return

        self._scheduleCancellationWarning(activeOperation)

    def cancelCurrentOperation(self, waitTimeout: int | None = None, clearLayoutImage: bool = True) -> bool:
        activeOperation = self.activeOperation
        if activeOperation is not None and self._threadIsRunning(activeOperation.thread):
            self.stopCurrentOperation()
            activeOperation.thread.quit()
            threadWait = activeOperation.thread.wait
            if waitTimeout is None:
                threadWait()
            else:
                threadWait(waitTimeout)

            if self._threadIsRunning(activeOperation.thread):
                return False

        if activeOperation is not None and self.activeOperation is activeOperation:
            self._finalizeCancelledOperation(activeOperation, clearLayoutImage=clearLayoutImage)
        return True

    def shutdownCurrentOperation(self, waitTimeout: int = 2000) -> bool:
        return self.cancelCurrentOperation(waitTimeout=waitTimeout, clearLayoutImage=False)

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
            includeProfiling=self.window.appSettings.debug,
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
            includeProfiling=self.window.appSettings.debug,
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

    def _buildCfpAnalysisFromTemplatesJob(self) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        focalX, focalY = self._resolveLocalCfpTargetXY()
        localPlane = getattr(self.window.survey, 'localPlane', None)
        focalZ = localPlane.anchor.z() if localPlane is not None else self.window.survey.globalPlane.anchor.z()
        maxDipDegrees = self._resolveCfpMaxDipDegrees()
        request = CfpFromTemplatesRequest(
            xmlString=self.window.survey.toXmlString(),
            focalX=focalX,
            focalY=focalY,
            focalZ=focalZ,
            frequency=40.0,
            maxDipDegrees=maxDipDegrees,
            vint=self.window.survey.binning.vint,
            debugpyEnabled=self.window.appSettings.debugpy,
        )
        return WorkerJobSpec(
            name='cfp-from-templates',
            progressLabelText='CFP from Templates - rolling template scan',
            startMessage=(
                "Thread : Started 'CFP analysis from Templates'"
                f' at local x={focalX:.2f}, y={focalY:.2f}, z={focalZ:.2f}, Vint={self.window.survey.binning.vint:.1f}m/s'
            ),
            startMessageType=MsgType.Analysis,
            workerFactory=dependencies['CfpFromTemplatesWorker'],
            request=request,
            resultHandler=self.window.applyCfpFromTemplatesWorkerResult,
        )

    def _buildCfpAnalysisFromTraceTableJob(self) -> WorkerJobSpec:
        dependencies = self.runtimeDependenciesProvider()
        focalX, focalY = self._resolveLocalCfpTargetXY()
        localPlane = getattr(self.window.survey, 'localPlane', None)
        focalZ = localPlane.anchor.z() if localPlane is not None else self.window.survey.globalPlane.anchor.z()
        maxDipDegrees = self._resolveCfpMaxDipDegrees()
        analysisRows = self.window.output.an2Output
        if analysisRows is None:
            analysisRows = self.window.output.anaOutput.reshape(-1, self.window.output.anaOutput.shape[-1])

        request = CfpFromTraceTableRequest(
            xmlString=self.window.survey.toXmlString(),
            analysisRows=analysisRows,
            focalX=focalX,
            focalY=focalY,
            focalZ=focalZ,
            frequency=40.0,
            maxDipDegrees=maxDipDegrees,
            vint=self.window.survey.binning.vint,
            chunkSize=100_000,
            debugpyEnabled=self.window.appSettings.debugpy,
        )
        return WorkerJobSpec(
            name='cfp-from-trace-table',
            progressLabelText='CFP from Trace Table - chunked relation scan',
            startMessage=(
                "Thread : Started 'CFP analysis from Trace Table'"
                f' at local x={focalX:.2f}, y={focalY:.2f}, z={focalZ:.2f}, Vint={self.window.survey.binning.vint:.1f}m/s'
            ),
            startMessageType=MsgType.Analysis,
            workerFactory=dependencies['CfpFromTraceTableWorker'],
            request=request,
            resultHandler=self.window.applyCfpFromTraceTableWorkerResult,
        )

    def _resolveLocalCfpTargetXY(self) -> tuple[float, float]:
        spiderPoint = getattr(self.window, 'spiderPoint', None)
        survey = self.window.survey
        fallbackTarget = self._resolveAnalysisAreaCenterXY()
        if (
            spiderPoint is None or
            survey is None or
            survey.binTransform is None or
            not hasattr(spiderPoint, 'x') or
            not hasattr(spiderPoint, 'y') or
            (spiderPoint.x() == -1 and spiderPoint.y() == -1)
        ):
            return fallbackTarget

        invBinTransform, invertOk = survey.binTransform.inverted()
        if not invertOk:
            return fallbackTarget

        focalX, focalY = invBinTransform.map(spiderPoint.x(), spiderPoint.y())
        return (float(focalX), float(focalY))

    def _resolveAnalysisAreaCenterXY(self) -> tuple[float, float]:
        survey = self.window.survey
        if survey is None:
            return (0.0, 0.0)

        outputRect = getattr(getattr(survey, 'output', None), 'rctOutput', None)
        if outputRect is None or not hasattr(outputRect, 'isValid') or not outputRect.isValid():
            return (0.0, 0.0)

        center = outputRect.center()
        return (float(center.x()), float(center.y()))

    def _resolveCfpMaxDipDegrees(self) -> float:
        defaultMaxDipDegrees = 40.0
        survey = self.window.survey
        if survey is None:
            return defaultMaxDipDegrees

        reflection = getattr(getattr(survey, 'angles', None), 'reflection', None)
        if reflection is None or not hasattr(reflection, 'y'):
            return defaultMaxDipDegrees

        try:
            maxDipDegrees = float(reflection.y())
        except (TypeError, ValueError):
            return defaultMaxDipDegrees

        if maxDipDegrees < 0.0:
            return 0.0
        if maxDipDegrees > 90.0:
            return 90.0
        return maxDipDegrees

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
        logMessageSignal = getattr(worker.survey, 'logMessage', None)
        if logMessageSignal is not None and hasattr(self.window, 'appendLogMessage'):
            logMessageSignal.connect(lambda message, msgType=job.startMessageType: self.window.appendLogMessage(message, msgType))
        worker.resultReady.connect(lambda result, currentJob=job: self._handleJobResult(currentJob, result))
        worker.finished.connect(thread.quit)
        workerDeleteLater = getattr(worker, 'deleteLater', None)
        if callable(workerDeleteLater):
            worker.finished.connect(workerDeleteLater)

        threadDeleteLater = getattr(thread, 'deleteLater', None)
        finishedSignal = getattr(thread, 'finished', None)
        if callable(threadDeleteLater) and finishedSignal is not None:
            finishedSignal.connect(threadDeleteLater)

        # Always clean up after thread finishes (normal or cancelled)
        if finishedSignal is not None:
            finishedSignal.connect(self._onThreadFinished)

    def _onThreadFinished(self):
        # Defensive: only clean up if there is an active operation
        activeOperation = self.activeOperation
        if activeOperation is not None:
            if activeOperation.cancelRequested:
                self._finalizeCancelledOperation(activeOperation, clearLayoutImage=True)
            else:
                self._cleanupAfterOperation(resetAnalysis=True, clearLayoutImage=True)

    def finishCurrentOperation(self, result, resultHandler: Callable[[object, timedelta], None], *, resetAnalysis: bool, completionTabIndex: int | None = None) -> None:
        activeOperation = self.activeOperation
        if activeOperation is not None and activeOperation.cancelRequested:
            if not self._threadIsRunning(activeOperation.thread):
                self._finalizeCancelledOperation(activeOperation, clearLayoutImage=True)
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

    def _threadIsRunning(self, thread: WorkerThreadProtocol) -> bool:
        try:
            return thread.isRunning()
        except RuntimeError:
            return False

    def _scheduleCancellationWarning(self, activeOperation: ActiveWorkerOperation) -> None:
        timerType = self.runtimeDependenciesProvider().get('QTimer')
        singleShot = getattr(timerType, 'singleShot', None)
        if callable(singleShot):
            singleShot(4000, lambda operation=activeOperation: self._warnIfCancellationStillRunning(operation))

    def _warnIfCancellationStillRunning(self, activeOperation: ActiveWorkerOperation) -> None:
        if self.activeOperation is not activeOperation or not activeOperation.cancelRequested or activeOperation.cancellationWarningShown:
            return

        if self._threadIsRunning(activeOperation.thread):
            activeOperation.cancellationWarningShown = True
            self.window.appendLogMessage('Thread : worker thread is still running; waiting for thread to finish', MsgType.Warning)

    def _finalizeCancelledOperation(self, activeOperation: ActiveWorkerOperation, *, clearLayoutImage: bool) -> None:
        if self.activeOperation is not activeOperation:
            return

        self.window.appendLogMessage('Thread : Worker thread has  stopped', MsgType.Warning)
        self._cleanupAfterOperation(resetAnalysis=True, clearLayoutImage=clearLayoutImage)

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
