# coding=utf-8

from datetime import timedelta
from typing import Callable

from .enums_and_int_flags import MsgType


class BinningResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider
        self._currentProfilingKind = 'templates'

    def apply(self, result, elapsed: timedelta) -> None:
        self._currentProfilingKind = getattr(result, 'profilingKind', 'templates')

        self._logProfiling(getattr(result, 'profiling', None))

        if not result.success:
            self._currentProfilingKind = 'templates'
            self._applyFailure(result.errorText)
            return

        self._currentProfilingKind = 'templates'
        self._applySuccess(result, elapsed)

    def _applyFailure(self, errorText: str) -> None:
        self.window.layoutImg = None
        self.window.layoutImItem = None
        self.window.handleImageSelection()

        self.window.appendLogMessage('Thread : . . . aborted binning operation', MsgType.Error)
        self.window.appendLogMessage(f'Thread : . . . {errorText}', MsgType.Error)
        self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Interrupted', 'Worker thread aborted')

    def _applySuccess(self, result, elapsed: timedelta) -> None:
        self._copyOutputArrays(result)
        self._logSummary(elapsed)

        if result.anaOutputShape is not None:
            self.window.finalizeAnalysisMemmap(result.anaOutputShape)

        self._updateSurveyFoldAndXml()
        self._selectDefaultImageIfNeeded()
        self._refreshLayout(result.cmpTransform)
        info = self._persistOutputs()
        self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Done', f'Worker thread completed. {info} ')

    def _copyOutputArrays(self, result) -> None:
        self.window.output.binOutput = result.binOutput
        self.window.output.minOffset = result.minOffset
        self.window.output.maxOffset = result.maxOffset
        self.window.output.minimumFold = result.minimumFold
        self.window.output.maximumFold = result.maximumFold
        self.window.output.minMinOffset = result.minMinOffset
        self.window.output.maxMinOffset = result.maxMinOffset
        self.window.output.minMaxOffset = result.minMaxOffset
        self.window.output.maxMaxOffset = result.maxMaxOffset
        self.window.output.minRmsOffset = 0.0 if result.minRmsOffset is None else result.minRmsOffset
        self.window.output.maxRmsOffset = 0.0 if result.maxRmsOffset is None else result.maxRmsOffset
        self.window.output.rmsOffset = result.rmsOffset
        self.window.output.minOffsetGap = 0.0 if result.minOffsetGap is None else result.minOffsetGap
        self.window.output.maxOffsetGap = 0.0 if result.maxOffsetGap is None else result.maxOffsetGap
        self.window.output.offsetGap = result.offsetGap
        self.window.output.ofAziHist = result.ofAziHist
        self.window.output.offstHist = result.offstHist

    def _logSummary(self, elapsed: timedelta) -> None:
        self.window.appendLogMessage(f'Thread : Binning completed. Elapsed time:{elapsed} ', MsgType.Binning)
        self.window.appendLogMessage(
            f'Thread : . . . Fold&nbsp; &nbsp; &nbsp; &nbsp;: Min:{self.window.output.minimumFold} - Max:{self.window.output.maximumFold} ',
            MsgType.Binning,
        )
        self.window.appendLogMessage(
            f'Thread : . . . Min-offsets: Min:{self.window.output.minMinOffset:.2f}m - Max:{self.window.output.maxMinOffset:.2f}m ',
            MsgType.Binning,
        )
        self.window.appendLogMessage(
            f'Thread : . . . Max-offsets: Min:{self.window.output.minMaxOffset:.2f}m - Max:{self.window.output.maxMaxOffset:.2f}m ',
            MsgType.Binning,
        )
        if self.window.output.rmsOffset is not None:
            self.window.appendLogMessage(
                f'Thread : . . . Rms-offsets: Min:{self.window.output.minRmsOffset:.2f}m - Max:{self.window.output.maxRmsOffset:.2f}m ',
                MsgType.Binning,
            )
        if self.window.output.offsetGap is not None:
            self.window.appendLogMessage(
                f'Thread : . . . Max-gap&nbsp; &nbsp;: Min:{self.window.output.minOffsetGap:.2f}m - Max:{self.window.output.maxOffsetGap:.2f}m ',
                MsgType.Binning,
            )

    def _updateSurveyFoldAndXml(self) -> None:
        if self.window.survey.grid.fold > 0:
            return

        self.window.survey.grid.fold = self.window.output.maximumFold
        plainText = self.window.survey.toXmlString()
        self.window.textEdit.setTextViaCursor(plainText)
        self.window.textEdit.document().setModified(True)

    def _selectDefaultImageIfNeeded(self) -> None:
        if self.window.imageType != 0:
            return

        self.window.actionFold.setChecked(True)
        self.window.imageType = 1

    def _refreshLayout(self, cmpTransform) -> None:
        self.window.survey.cmpTransform = cmpTransform
        self.window.handleImageSelection()

    def _persistOutputs(self) -> str:
        if not self.window.fileName:
            self.window.textEdit.document().setModified(True)
            return 'Analysis results are yet to be saved.'

        self.window.saveAnalysisSidecars(includeHistograms=True)
        return 'Analysis results have been saved.'

    def _logProfiling(self, profiling) -> None:
        if not self.window.appSettings.debug or profiling is None:
            return

        if self._currentProfilingKind == 'geometry':
            header = 'binFromGeometry() profiling information'
            labelText = '00=gatherReceivers, 01=buildTraceArrays, 02=travelTime, 03=writeHelper'
            buildTraceIndex = 1
            writeIndices = (3,)
            writeLabel = 'writeHelper'
        else:
            header = 'binFromTemplates() profiling information'
            labelText = '00=srcClip, 01=recPrepOrClip, 02=buildTraceArrays, 03=travelTime, 04=binMapFilter, 05=analysisWrite, 06=noAnalysisScatter'
            buildTraceIndex = 2
            writeIndices = (5,)
            writeLabel = 'analysisWrite'

        self.window.appendLogMessage(header, MsgType.Debug)
        self.window.appendLogMessage(labelText, MsgType.Debug)
        buildTraceTotal = profiling.timerTtot[buildTraceIndex] * 1000.0 if len(profiling.timerTtot) > buildTraceIndex else 0.0
        analysisWriteTotal = sum(profiling.timerTtot[index] for index in writeIndices if len(profiling.timerTtot) > index) * 1000.0
        buildTraceFreq = profiling.timerFreq[buildTraceIndex] if len(profiling.timerFreq) > buildTraceIndex else 0
        analysisWriteFreq = sum(profiling.timerFreq[index] for index in writeIndices if len(profiling.timerFreq) > index)

        if analysisWriteTotal > buildTraceTotal:
            dominant = writeLabel
        elif buildTraceTotal > analysisWriteTotal:
            dominant = 'buildTraceArrays'
        else:
            dominant = 'equal'

        if buildTraceTotal > 0.0 and analysisWriteTotal > 0.0:
            if analysisWriteTotal >= buildTraceTotal:
                ratioText = f'{writeLabel}/buildTraceArrays={analysisWriteTotal / buildTraceTotal:.2f}x'
            else:
                ratioText = f'buildTraceArrays/{writeLabel}={buildTraceTotal / analysisWriteTotal:.2f}x'
        else:
            ratioText = 'ratio=n/a'

        self.window.appendLogMessage(
            'Profiling summary: '
            f'buildTraceArrays tot={buildTraceTotal:011.3f} ms (freq={buildTraceFreq:07d}), '
            f'{writeLabel} tot={analysisWriteTotal:011.3f} ms (freq={analysisWriteFreq:07d}), '
            f'dominant={dominant}, {ratioText}',
            MsgType.Debug,
        )
        for i, _ in enumerate(profiling.timerTmin if profiling is not None else ()):
            tMin = profiling.timerTmin[i] * 1000.0 if profiling.timerTmin[i] != float('Inf') else 0.0
            tMax = profiling.timerTmax[i] * 1000.0
            tTot = profiling.timerTtot[i] * 1000.0
            freq = profiling.timerFreq[i]
            tAvr = tTot / freq if freq > 0 else 0.0
            message = f'{i:02d}: min:{tMin:011.3f}, max:{tMax:011.3f}, tot:{tTot:011.3f}, avr:{tAvr:011.3f}, freq:{freq:07d}'
            self.window.appendLogMessage(message, MsgType.Debug)


class GeometryResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        self._logProfiling(result.profiling)

        if not result.success:
            self._applyFailure(result.errorText)
            return

        self._applySuccess(result, elapsed)

    def _applyFailure(self, errorText: str) -> None:
        self.window.appendLogMessage('Thread : . . . aborted geometry creation', MsgType.Error)
        self.window.appendLogMessage(f'Thread : . . . {errorText}', MsgType.Error)
        self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Interrupted', 'Worker thread aborted')

    def _applySuccess(self, result, elapsed: timedelta) -> None:
        self._commitGeometryArrays(result)
        self._refreshGeometryModels()
        self.window.appendLogMessage(
            f"Thread : Completed 'Create Geometry from Templates'. Elapsed time:{elapsed} ",
            MsgType.Geometry,
        )
        info = self._persistOutputs()
        self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Done', f'Worker thread completed. {info} ')

    def _logProfiling(self, profiling) -> None:
        if not self.window.appSettings.debug:
            return

        self.window.appendLogMessage('geometryFromTemplates() profiling information', MsgType.Debug)
        for i, _ in enumerate(profiling.timerTmin if profiling is not None else ()):
            tMin = profiling.timerTmin[i] * 1000.0 if profiling.timerTmin[i] != float('Inf') else 0.0
            tMax = profiling.timerTmax[i] * 1000.0
            tTot = profiling.timerTtot[i] * 1000.0
            freq = profiling.timerFreq[i]
            tAvr = tTot / freq if freq > 0 else 0.0
            message = f'{i:02d}: min:{tMin:011.3f}, max:{tMax:011.3f}, tot:{tTot:011.3f}, avr:{tAvr:011.3f}, freq:{freq:07d}'
            self.window.appendLogMessage(message, MsgType.Debug)

    def _commitGeometryArrays(self, result) -> None:
        self.window.sessionService.setArray(self.window.sessionState, 'recGeom', result.recGeom)
        self.window.sessionService.setArray(self.window.sessionState, 'relGeom', result.relGeom)
        self.window.sessionService.setArray(self.window.sessionState, 'srcGeom', result.srcGeom)

    def _refreshGeometryModels(self) -> None:
        self.window.recModel.setData(self.window.recGeom)
        self.window.relModel.setData(self.window.relGeom)
        self.window.srcModel.setData(self.window.srcGeom)

    def _persistOutputs(self) -> str:
        if not self.window.fileName:
            self.window.textEdit.document().setModified(True)
            return 'Analysis results are yet to be saved.'

        self.window.saveSurveyDataSidecars()
        return 'Analysis results have been saved.'
