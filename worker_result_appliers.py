# coding=utf-8

from datetime import timedelta
from typing import Callable

from .enums_and_int_flags import MsgType


class BinningResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        if not result.success:
            self._applyFailure(result.errorText)
            return

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
