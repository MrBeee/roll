# coding=utf-8

from datetime import timedelta
from typing import Callable

from .enums_and_int_flags import MsgType


def _copyCfpDisplayOutputs(window, result) -> None:
    window.output.cfpSourceBeamImage = result.sourceBeamImage
    window.output.cfpReceiverBeamImage = result.receiverBeamImage
    window.output.cfpResolutionImage = result.resolutionImage
    window.output.cfpRadonSourceBeamImage = result.radonSourceBeamImage
    window.output.cfpRadonReceiverBeamImage = result.radonReceiverBeamImage
    window.output.cfpRadonAvpImage = result.radonAvpImage
    window.output.cfpSourceBeamX0 = result.sourceBeamX0
    window.output.cfpSourceBeamY0 = result.sourceBeamY0
    window.output.cfpSourceBeamDx = result.sourceBeamDx
    window.output.cfpSourceBeamDy = result.sourceBeamDy
    window.output.cfpRadonX0 = result.radonX0
    window.output.cfpRadonY0 = result.radonY0
    window.output.cfpRadonDx = result.radonDx
    window.output.cfpRadonDy = result.radonDy
    window.output.cfpFrequency = result.frequency
    window.output.cfpFocalZ = result.focalZ


def _showCfpAnalysisTab(window) -> None:
    mainTabWidget = getattr(window, 'mainTabWidget', None)
    analysisTabWidget = getattr(window, 'analysisTabWidget', None)
    tabCfp = getattr(window, 'tabCfp', None)

    if mainTabWidget is not None and analysisTabWidget is not None and hasattr(mainTabWidget, 'setCurrentWidget'):
        mainTabWidget.setCurrentWidget(analysisTabWidget)

    if analysisTabWidget is not None and tabCfp is not None and hasattr(analysisTabWidget, 'setCurrentWidget'):
        analysisTabWidget.setCurrentWidget(tabCfp)


def _logCfpSnr(window, result) -> None:
    """Unified helper to log Radon-domain SNR metrics."""
    window.appendLogMessage(
        (
            'Thread : . . . '
            f'SNR (Radon): Source={result.sourceSnr:.1f}dB, '
            f'Receiver={result.receiverSnr:.1f}dB, '
            f'AVP={result.avpSnr:.1f}dB'
        ),
        MsgType.Analysis,
    )


class CfpAmplitudeMapResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        if not result.success:
            self.window.appendLogMessage(f'Thread : CFP Amplitude Map failed - {result.errorText}', MsgType.Error)
            return

        # Update output
        self.window.output.cfpOutput = result.amplitudeMap

        # Update layout image view
        self.window.imageType = 6  # New type for CFP Illumination
        self.window.layoutImg = result.amplitudeMap

        # For partial updates, determine scaling based on current data
        import numpy as np
        maxVal = float(np.nanmax(result.amplitudeMap)) if np.any(np.isfinite(result.amplitudeMap)) else 1.0
        levels = (0.0, maxVal if maxVal > 0 else 1.0)

        self.window.prepareLayoutImageAndColorBar(
            self.window.layoutImg,
            self.window.appSettings.foldDispCmap,
            'CFP illumination',
            levels=levels,
        )
        self.window.plotLayout()

        if not getattr(result, 'isPartial', False):
            self.window.appendLogMessage(f'Thread : CFP Amplitude Map completed. Elapsed: {elapsed}', MsgType.Analysis)
            self.runtimeDependenciesProvider()['QMessageBox'].information(
                self.window, 'Done', f'CFP Illumination Map calculation completed.\nElapsed time: {elapsed}'
            )


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
        self.window.output.rmsOffset = result.rmsOffset
        self.window.output.gapOffset = result.gapOffset

        self.window.output.minimumFold = result.minimumFold
        self.window.output.maximumFold = result.maximumFold
        self.window.output.minMinOffset = result.minMinOffset
        self.window.output.maxMinOffset = result.maxMinOffset
        self.window.output.minMaxOffset = result.minMaxOffset
        self.window.output.maxMaxOffset = result.maxMaxOffset
        self.window.output.minRmsOffset = 0.0 if result.minRmsOffset is None else result.minRmsOffset
        self.window.output.maxRmsOffset = 0.0 if result.maxRmsOffset is None else result.maxRmsOffset
        self.window.output.minOffsetGap = 0.0 if result.minOffsetGap is None else result.minOffsetGap
        self.window.output.maxOffsetGap = 0.0 if result.maxOffsetGap is None else result.maxOffsetGap
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
        if self.window.output.gapOffset is not None:
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


class CfpFromTemplatesResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        if not result.success:
            self.window.appendLogMessage('Thread : . . . aborted CFP template scan', MsgType.Error)
            self.window.appendLogMessage(f'Thread : . . . {result.errorText}', MsgType.Error)
            self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Interrupted', 'Worker thread aborted')
            return

        self.window.appendLogMessage(
            f"Thread : Completed 'CFP analysis from Templates'. Elapsed time:{elapsed} ",
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'local target=({result.focalX:.2f}, {result.focalY:.2f}, {result.focalZ:.2f}), '
                f'aperture={result.maxDipDegrees:.1f}deg, radius={result.apertureRadius:.2f}m, '
                f'frequency={result.frequency:.1f}Hz, Vint={result.vint:.1f}m/s'
            ),
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'contributing rolled template positions: {result.templateContributionCount:,} '
                f'out of a total of: {result.totalTemplateCount:,}'
            ),
            MsgType.Analysis,
        )

        _copyCfpDisplayOutputs(self.window, result)
        _logCfpSnr(self.window, result)
        self.window.renderSelectedCfpSlice()
        _showCfpAnalysisTab(self.window)
        self.runtimeDependenciesProvider()['QMessageBox'].information(
            self.window,
            'Done',
            f'Worker thread completed. {result.templateContributionCount:,} rolled template positions contributed.',
        )


class CfpFromTraceTableResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        if not result.success:
            self.window.appendLogMessage('Thread : . . . aborted CFP trace-table scan', MsgType.Error)
            self.window.appendLogMessage(f'Thread : . . . {result.errorText}', MsgType.Error)
            self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Interrupted', 'Worker thread aborted')
            return

        self.window.appendLogMessage(
            f"Thread : Completed 'CFP analysis from Trace Table'. Elapsed time:{elapsed} ",
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'local target=({result.focalX:.2f}, {result.focalY:.2f}, {result.focalZ:.2f}), '
                f'aperture={result.maxDipDegrees:.1f}deg, radius={result.apertureRadius:.2f}m, Vint={result.vint:.1f}m/s'
            ),
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            f'Thread : . . . trace-table chunks processed: {result.chunkCount:,}',
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'contributing traces surviving aperture filter: {result.contributingTraceCount:,} '
                f'out of: {result.totalTraceCount:,} active trace rows'
            ),
            MsgType.Analysis,
        )

        _copyCfpDisplayOutputs(self.window, result)
        _logCfpSnr(self.window, result)

        self.window.renderSelectedCfpSlice()
        _showCfpAnalysisTab(self.window)
        self.runtimeDependenciesProvider()['QMessageBox'].information(
            self.window,
            'Done',
            (
                'Worker thread completed. '
                f'{result.contributingTraceCount:,} traces contributed across {result.chunkCount:,} chunks.'
            ),
        )


class CfpFromGeometryTablesResultApplier:
    def __init__(self, window, runtimeDependenciesProvider: Callable[[], dict[str, object]]) -> None:
        self.window = window
        self.runtimeDependenciesProvider = runtimeDependenciesProvider

    def apply(self, result, elapsed: timedelta) -> None:
        sourceName = getattr(result, 'sourceName', 'Geometry Tables')
        if not result.success:
            self.window.appendLogMessage(f'Thread : . . . aborted CFP scan from {sourceName}', MsgType.Error)
            self.window.appendLogMessage(f'Thread : . . . {result.errorText}', MsgType.Error)
            self.runtimeDependenciesProvider()['QMessageBox'].information(self.window, 'Interrupted', 'Worker thread aborted')
            return

        self.window.appendLogMessage(
            f"Thread : Completed 'CFP analysis from {sourceName}'. Elapsed time:{elapsed} ",
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'local target=({result.focalX:.2f}, {result.focalY:.2f}, {result.focalZ:.2f}), '
                f'aperture={result.maxDipDegrees:.1f}deg, radius={result.apertureRadius:.2f}m, '
                f'frequency={result.frequency:.1f}Hz, Vint={result.vint:.1f}m/s'
            ),
            MsgType.Analysis,
        )
        self.window.appendLogMessage(
            (
                'Thread : . . . '
                f'contributing relation records: {result.contributingRelationCount:,} '
                f'out of: {result.totalRelationCount:,}; '
                f'contributing receiver traces: {result.contributingTraceCount:,} '
                f'out of: {result.totalTraceCount:,} resolved traces'
            ),
            MsgType.Analysis,
        )
        if result.inactiveSourceCount or result.inactiveReceiverCount:
            self.window.appendLogMessage(
                (
                    'Thread : . . . '
                    f'inactive source records ignored: {result.inactiveSourceCount:,}; '
                    f'inactive receiver records ignored: {result.inactiveReceiverCount:,}'
                ),
                MsgType.Analysis,
            )
        if result.inactiveSourceRelationCount:
            self.window.appendLogMessage(
                f'Thread : . . . relation records ignored because source is inactive: {result.inactiveSourceRelationCount:,}',
                MsgType.Analysis,
            )
        if result.sourceOrphanRelationCount or result.receiverOrphanRelationCount:
            self.window.appendLogMessage(
                (
                    'Thread : . . . '
                    f'relation records flagged as source orphans: {result.sourceOrphanRelationCount:,}; '
                    f'receiver orphans: {result.receiverOrphanRelationCount:,}'
                ),
                MsgType.Warning,
            )
        if result.missingSourceCount or result.missingReceiverCount:
            self.window.appendLogMessage(
                (
                    'Thread : . . . '
                    f'missing source lookups: {result.missingSourceCount:,}; '
                    f'missing receiver ranges: {result.missingReceiverCount:,}'
                ),
                MsgType.Warning,
            )

        _copyCfpDisplayOutputs(self.window, result)
        _logCfpSnr(self.window, result)

        self.window.renderSelectedCfpSlice()
        _showCfpAnalysisTab(self.window)
        self.runtimeDependenciesProvider()['QMessageBox'].information(
            self.window,
            'Done',
            (
                'Worker thread completed. '
                f'{result.contributingTraceCount:,} traces contributed from {sourceName}.'
            ),
        )
