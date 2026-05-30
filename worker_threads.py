import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from qgis.PyQt.QtCore import QObject, QThread, pyqtSignal

from .cfp_aux_functions_numba import (
    calculate_panel_snr_numba, compute_illumination_row_numba,
    compute_monochromatic_beam_xy_grid,
    compute_monochromatic_weighted_beam_xy_grid, compute_radon_images_numba,
    compute_xy_beam_images_numba, filter_sps_relations_by_aperture)
from .roll_survey import RollSurvey

# debugpy  is needed to debug a worker thread.
# See: https://github.com/microsoft/ptvsd/issues/1189

try:
    haveDebugpy = True
    import debugpy
except ImportError:
    haveDebugpy = False

# See: https://stackoverflow.com/questions/20324804/how-to-use-qthread-correctly-in-pyqt-with-movetothread
# See: https://realpython.com/python-pyqt-qthread/#using-qthread-vs-pythons-threading
# See: https://mayaposch.wordpress.com/2011/11/01/how-to-really-truly-use-qthreads-the-full-explanation/
# See: http://ilearnstuff.blogspot.com/2012/08/when-qthread-isnt-thread.html
# See: http://ilearnstuff.blogspot.com/2012/09/qthread-best-practices-when-qthread.html

# first approach; subclass QThread - no longer recommended with Python 3.0
# See: https://stackoverflow.com/questions/9190169/threading-and-information-passing-how-to
# See: https://www.programiz.com/python-programming/shallow-deep-copy for deep copy info


def _callPythonFallback(pyFunc: object, *args):
    if not callable(pyFunc):
        raise ImportError('Numba fallback function is not callable')
    return cast(Callable[..., Any], pyFunc)(*args)


def computeMonochromaticBeamXyGridSafe(evalX, evalY, evalZ, surfX, surfY, surfZ, frequency, vint):

    """
    KISS: Try Numba, if it fails, log and tell user to disable Numba in settings, then raise.
    No silent fallback. This is the only supported wrapper for CFP beam grid calculation.
    """
    import logging
    import traceback
    try:
        return compute_monochromatic_beam_xy_grid(evalX, evalY, evalZ, surfX, surfY, surfZ, frequency, vint)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"CFP beam grid calculation failed: {e}\nTraceback:\n{tb}")
        raise RuntimeError(f"CFP beam grid calculation failed: {e}\nSee log for traceback and details.") from e


def computeMonochromaticWeightedBeamXyGridSafe(evalX, evalY, evalZ, surfX, surfY, surfZ, surfWeights, frequency, vint):
    """
    KISS: Try Numba, if it fails, log and tell user to disable Numba in settings, then raise.
    No silent fallback. This is the only supported wrapper for weighted CFP beam grid calculation.
    """
    import logging
    import traceback
    try:
        return compute_monochromatic_weighted_beam_xy_grid(evalX, evalY, evalZ, surfX, surfY, surfZ, surfWeights, frequency, vint)
    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"CFP weighted beam grid calculation failed: {e}\nTraceback:\n{tb}")
        raise RuntimeError(f"CFP weighted beam grid calculation failed: {e}\nSee log for traceback and details.") from e


def filterSpsRelationsByApertureSafe(focalX, focalY, apertureRadius, srcX, srcY, recX, recY):
    try:
        return filter_sps_relations_by_aperture(focalX, focalY, apertureRadius, srcX, srcY, recX, recY)
    except ImportError:
        pyFunc = getattr(filter_sps_relations_by_aperture, 'py_func', None)
        if pyFunc is None or not callable(pyFunc):
            raise
        return _callPythonFallback(pyFunc, focalX, focalY, apertureRadius, srcX, srcY, recX, recY)


def computeRadonImagesSafe(sourceField, receiverField, evalX, evalY, px, py, frequency):
    try:
        return compute_radon_images_numba(sourceField, receiverField, evalX, evalY, px, py, frequency)
    except ImportError:
        pyFunc = getattr(compute_radon_images_numba, 'py_func', None)
        if pyFunc is None or not callable(pyFunc):
            raise
        return _callPythonFallback(pyFunc, sourceField, receiverField, evalX, evalY, px, py, frequency)


def computeXyBeamImagesSafe(sourceField, receiverField, dbMin=-60.0):

    """
    KISS: Try Numba, if it fails, log and tell user to disable Numba in settings, then raise.
    No silent fallback. This is the only supported wrapper for beam image calculation.
    """
    try:
        return compute_xy_beam_images_numba(sourceField, receiverField, dbMin)
    except Exception as e:
        import logging
        logging.error(f"Numba beam image calculation failed: {e}")
        logging.error("Numba failed; please disable Numba in the settings panel and retry.")
        raise RuntimeError("Numba failed; please disable Numba in the settings panel and retry.") from e


def _emitWorkerPhase(progressHandler, messageHandler, progress: int, message: str | None = None) -> None:
    if progressHandler is not None:
        progressHandler(int(progress))
    if messageHandler is not None and message:
        messageHandler(message)


def _copyArrayIfNumpy(arr: Any) -> Any:
    """Helper to ensure NumPy arrays are copied before crossing thread boundaries."""
    if isinstance(arr, np.ndarray):
        return np.copy(arr)
    return arr


@dataclass
class BinningFromTemplatesRequest:
    xmlString: str
    extended: bool = False
    analysisFile: object = None
    debugpyEnabled: bool = False
    includeProfiling: bool = False


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
    minOffsetGap: float | None = None
    maxOffsetGap: float | None = None
    gapOffset: Any = None
    ofAziHist: Any = None
    offstHist: Any = None
    cmpTransform: Any = None
    anaOutputShape: tuple[int, ...] | None = None
    profiling: 'GeometryProfilingPayload | None' = None
    profilingKind: str = 'templates'


@dataclass
class BinningFromGeometryRequest:
    xmlString: str
    srcGeom: Any
    relGeom: Any
    recGeom: Any
    extended: bool = False
    analysisFile: object = None
    debugpyEnabled: bool = False
    includeProfiling: bool = False


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
    minOffsetGap: float | None = None
    maxOffsetGap: float | None = None
    gapOffset: Any = None
    ofAziHist: Any = None
    offstHist: Any = None
    cmpTransform: Any = None
    anaOutputShape: tuple[int, ...] | None = None
    profiling: 'GeometryProfilingPayload | None' = None
    profilingKind: str = 'geometry'


@dataclass
class GeometryFromTemplatesRequest:
    xmlString: str
    debugpyEnabled: bool = False
    includeProfiling: bool = False


@dataclass
class CfpFromTemplatesRequest:
    xmlString: str
    focalX: float = 0.0
    focalY: float = 0.0
    focalZ: float = -2000.0
    frequency: float = 40.0
    maxDipDegrees: float = 40.0
    vint: float = 2000.0
    debugpyEnabled: bool = False
    matlab_compat: bool = True


@dataclass
class CfpFromTraceTableRequest:
    xmlString: str
    analysisRows: Any = None
    focalX: float = 0.0
    focalY: float = 0.0
    focalZ: float = -2000.0
    frequency: float = 40.0
    maxDipDegrees: float = 40.0
    vint: float = 2000.0
    chunkSize: int = 100_000
    debugpyEnabled: bool = False
    matlab_compat: bool = True


@dataclass
class CfpAmplitudeMapRequest:
    xmlString: str
    srcGeom: Any
    relGeom: Any
    recGeom: Any
    focalZ: float = -2000.0
    maxDipDegrees: float = 40.0
    vint: float = 2000.0
    frequencies: np.ndarray = None
    debugpyEnabled: bool = False
    matlab_compat: bool = True


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


@dataclass
class CfpFromTemplatesResult:
    success: bool
    errorText: str = ''
    templateContributionCount: int = 0
    totalTemplateCount: int = 0
    focalX: float = 0.0
    focalY: float = 0.0
    focalZ: float = 0.0
    frequency: float = 40.0
    maxDipDegrees: float = 0.0
    apertureRadius: float = 0.0
    vint: float = 0.0
    sourceBeamImage: Any = None
    receiverBeamImage: Any = None
    resolutionImage: Any = None
    radonSourceBeamImage: Any = None
    radonReceiverBeamImage: Any = None
    radonAvpImage: Any = None
    sourceSnr: float = 0.0
    receiverSnr: float = 0.0
    avpSnr: float = 0.0
    sourceBeamX0: float = 0.0
    sourceBeamY0: float = 0.0
    sourceBeamDx: float = 1.0
    sourceBeamDy: float = 1.0
    radonX0: float = 0.0
    radonY0: float = 0.0
    radonDx: float = 1.0
    radonDy: float = 1.0


@dataclass
class CfpAmplitudeMapResult:
    success: bool
    errorText: str = ''
    amplitudeMap: Any = None
    x0: float = 0.0
    y0: float = 0.0
    dx: float = 1.0
    dy: float = 1.0
    isPartial: bool = False
    elapsed: Any = None


@dataclass
class CfpFromTraceTableResult:
    success: bool
    errorText: str = ''
    chunkCount: int = 0
    totalTraceCount: int = 0
    contributingTraceCount: int = 0
    focalX: float = 0.0
    focalY: float = 0.0
    focalZ: float = 0.0
    frequency: float = 40.0
    maxDipDegrees: float = 0.0
    apertureRadius: float = 0.0
    vint: float = 0.0
    sourceBeamImage: Any = None
    receiverBeamImage: Any = None
    resolutionImage: Any = None
    radonSourceBeamImage: Any = None
    radonReceiverBeamImage: Any = None
    radonAvpImage: Any = None
    sourceSnr: float = 0.0
    receiverSnr: float = 0.0
    avpSnr: float = 0.0
    sourceBeamX0: float = 0.0
    sourceBeamY0: float = 0.0
    sourceBeamDx: float = 1.0
    sourceBeamDy: float = 1.0
    radonX0: float = 0.0
    radonY0: float = 0.0
    radonDx: float = 1.0
    radonDy: float = 1.0


class CfpBeamAccumulator:
    def __init__(self, survey: RollSurvey, focalZ: float, frequency: float, vint: float, maxDipDegrees: float, focalX: float | None = None, focalY: float | None = None):
        self.survey = survey
        self.focalZ = focalZ
        self.frequency = frequency
        self.vint = vint
        self.maxDipDegrees = maxDipDegrees
        self.focalX = focalX
        self.focalY = focalY
        self.flushThresholdPoints = 250_000
        self.weightCollapseThresholdPoints = 2_048
        self.sourceBeamField = None
        self.receiverBeamField = None
        self.sourceBeamImage = None
        self.receiverBeamImage = None
        self.resolutionImage = None
        self.radonSourceBeamImage = None
        self.radonReceiverBeamImage = None
        self.radonAvpImage = None
        self.sourceSnr = 0.0
        self.receiverSnr = 0.0
        self.avpSnr = 0.0
        self.sourceBeamX0 = 0.0
        self.sourceBeamY0 = 0.0
        self.sourceBeamDx = 1.0
        self.sourceBeamDy = 1.0
        self.focalX = None if focalX is None else float(focalX)
        self.focalY = None if focalY is None else float(focalY)
        self.radonX0 = 0.0
        self.radonY0 = 0.0
        self.radonDx = 1.0
        self.radonDy = 1.0
        self.evalX = None
        self.evalY = None
        self._bufferedSourceArrays = []
        self._bufferedReceiverArrays = []
        self._bufferedSourcePointCount = 0
        self._bufferedReceiverPointCount = 0

    def initializeGrid(self) -> bool:
        outputRect = getattr(self.survey.output, 'rctOutput', None)
        grid = getattr(self.survey, 'grid', None)
        binSize = getattr(grid, 'binSize', None)
        if outputRect is None or binSize is None:
            self.survey.errorText = 'analysis area has not been defined'
            return False

        width = float(outputRect.width())
        height = float(outputRect.height())
        dx = float(binSize.x())
        dy = float(binSize.y())
        if dx <= 0.0 or dy <= 0.0:
            self.survey.errorText = 'analysis area sampling is invalid'
            return False

        nx = max(int(np.ceil(width / dx)), 1)
        ny = max(int(np.ceil(height / dy)), 1)
        self.sourceBeamX0 = float(outputRect.left())
        self.sourceBeamY0 = float(outputRect.top())
        self.sourceBeamDx = dx
        self.sourceBeamDy = dy
        if self.focalX is None:
            self.focalX = self.sourceBeamX0 + width * 0.5
        if self.focalY is None:
            self.focalY = self.sourceBeamY0 + height * 0.5
        self.evalX = np.ascontiguousarray(self.sourceBeamX0 + np.arange(nx, dtype=np.float32) * dx, dtype=np.float32)
        self.evalY = np.ascontiguousarray(self.sourceBeamY0 + np.arange(ny, dtype=np.float32) * dy, dtype=np.float32)
        self.sourceBeamField = np.zeros((ny, nx), dtype=np.complex64)
        self.receiverBeamField = np.zeros((ny, nx), dtype=np.complex64)
        self.sourceBeamImage = None
        self.receiverBeamImage = None
        self.resolutionImage = None
        self.radonSourceBeamImage = None
        self.radonReceiverBeamImage = None
        self.radonAvpImage = None
        return True

    def accumulateCoordinates(self, srcX, srcY, srcZ, recX, recY, recZ, srcWeights=None, recWeights=None) -> None:
        if self.sourceBeamField is None or self.receiverBeamField is None or self.evalX is None or self.evalY is None:
            return

        if srcX.size == 0 or recX.size == 0:
            return

        srcX = np.ascontiguousarray(srcX, dtype=np.float32)
        srcY = np.ascontiguousarray(srcY, dtype=np.float32)
        srcZ = np.ascontiguousarray(srcZ, dtype=np.float32)
        recX = np.ascontiguousarray(recX, dtype=np.float32)
        recY = np.ascontiguousarray(recY, dtype=np.float32)
        recZ = np.ascontiguousarray(recZ, dtype=np.float32)

        if srcWeights is None:
            self.sourceBeamField += computeMonochromaticBeamXyGridSafe(
                self.evalX,
                self.evalY,
                self.focalZ,
                srcX,
                srcY,
                srcZ,
                self.frequency,
                self.vint,
            )
        else:
            self.sourceBeamField += computeMonochromaticWeightedBeamXyGridSafe(
                self.evalX,
                self.evalY,
                self.focalZ,
                srcX,
                srcY,
                srcZ,
                np.ascontiguousarray(srcWeights, dtype=np.float64),
                self.frequency,
                self.vint,
            )

        if recWeights is None:
            self.receiverBeamField += computeMonochromaticBeamXyGridSafe(
                self.evalX,
                self.evalY,
                self.focalZ,
                recX,
                recY,
                recZ,
                self.frequency,
                self.vint,
            )
        else:
            self.receiverBeamField += computeMonochromaticWeightedBeamXyGridSafe(
                self.evalX,
                self.evalY,
                self.focalZ,
                recX,
                recY,
                recZ,
                np.ascontiguousarray(recWeights, dtype=np.float64),
                self.frequency,
                self.vint,
            )

    def _collapsePointWeights(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
        if points is None or points.shape[0] == 0:
            return np.empty((0, 3), dtype=np.float32), None

        if points.shape[0] < self.weightCollapseThresholdPoints:
            return points, None

        collapsedPoints, counts = np.unique(np.ascontiguousarray(points[:, :3], dtype=np.float32), axis=0, return_counts=True)
        if collapsedPoints.shape[0] == points.shape[0]:
            return collapsedPoints, None

        return collapsedPoints, counts.astype(np.float64, copy=False)

    def _bufferPointArrays(self, sourcePoints, receiverPoints) -> None:
        self._bufferedSourceArrays.append(sourcePoints)
        self._bufferedReceiverArrays.append(receiverPoints)
        self._bufferedSourcePointCount += int(sourcePoints.shape[0])
        self._bufferedReceiverPointCount += int(receiverPoints.shape[0])

    def flushBufferedPointArrays(self) -> None:
        if not self._bufferedSourceArrays or not self._bufferedReceiverArrays:
            return

        sourcePoints = self._bufferedSourceArrays[0] if len(self._bufferedSourceArrays) == 1 else np.concatenate(self._bufferedSourceArrays, axis=0)
        receiverPoints = self._bufferedReceiverArrays[0] if len(self._bufferedReceiverArrays) == 1 else np.concatenate(self._bufferedReceiverArrays, axis=0)

        self._bufferedSourceArrays = []
        self._bufferedReceiverArrays = []
        self._bufferedSourcePointCount = 0
        self._bufferedReceiverPointCount = 0

        sourcePoints, sourceWeights = self._collapsePointWeights(sourcePoints)
        receiverPoints, receiverWeights = self._collapsePointWeights(receiverPoints)

        self.accumulateCoordinates(
            sourcePoints[:, 0],
            sourcePoints[:, 1],
            sourcePoints[:, 2],
            receiverPoints[:, 0],
            receiverPoints[:, 1],
            receiverPoints[:, 2],
            sourceWeights,
            receiverWeights,
        )

    def accumulatePointArrays(self, sourcePoints, receiverPoints) -> None:
        if sourcePoints is None or receiverPoints is None:
            return

        if sourcePoints.shape[0] == 0 or receiverPoints.shape[0] == 0:
            return

        self._bufferPointArrays(sourcePoints, receiverPoints)
        if max(self._bufferedSourcePointCount, self._bufferedReceiverPointCount) >= self.flushThresholdPoints:
            self.flushBufferedPointArrays()

    def _fieldToDbImage(self, field) -> Any:
        from .cfp_aux_functions_numba import convert_to_db_image_numba
        try:
            return convert_to_db_image_numba(field)
        except ImportError:
            pyFunc = getattr(convert_to_db_image_numba, 'py_func', None)
            return _callPythonFallback(pyFunc, field)

    def _fieldToUnitImage(self, field) -> Any:
        from .cfp_aux_functions_numba import convert_to_unit_image_numba
        try:
            return convert_to_unit_image_numba(field)
        except ImportError:
            pyFunc = getattr(convert_to_unit_image_numba, 'py_func', None)
            return _callPythonFallback(pyFunc, field)

    def _finalizeRadonImages(self, progressHandler=None, messageHandler=None, progressStart: int = 0, progressEnd: int = 100, phaseLabel: str = 'CFP analysis') -> None:
        if self.sourceBeamField is None or self.receiverBeamField is None or self.evalX is None or self.evalY is None:
            self.radonSourceBeamImage = None
            self.radonReceiverBeamImage = None
            self.radonAvpImage = None
            return

        phaseStart = int(progressStart)
        phaseEnd = int(progressEnd)
        _emitWorkerPhase(progressHandler, messageHandler, phaseStart, f'{phaseLabel} - preparing Radon transform grids')

        sampleCount = 128
        velocity = max(abs(float(self.vint)), 1.0)
        limitP = 1.0 / velocity
        px = np.linspace(-limitP, limitP, sampleCount, dtype=np.float32)
        py = np.linspace(-limitP, limitP, sampleCount, dtype=np.float32)

        _emitWorkerPhase(progressHandler, messageHandler, phaseStart + max((phaseEnd - phaseStart) // 3, 1), f'{phaseLabel} - synthesizing Radon-domain fields')

        # Highly integrated Numba path computes everything: Transform, AVP, and Unit Images in fused passes.
        try:
            self.radonSourceBeamImage, self.radonReceiverBeamImage, self.radonAvpImage = computeRadonImagesSafe(
                self.sourceBeamField,
                self.receiverBeamField,
                np.ascontiguousarray(self.evalX - self.focalX, dtype=np.float32),
                np.ascontiguousarray(self.evalY - self.focalY, dtype=np.float32),
                px, py, self.frequency
            )
            self.sourceSnr = calculate_panel_snr_numba(self.radonSourceBeamImage)
            self.receiverSnr = calculate_panel_snr_numba(self.radonReceiverBeamImage)
            self.avpSnr = calculate_panel_snr_numba(self.radonAvpImage)
        except Exception as e:
            self.survey.errorText = f"Radon/SNR calculation failed: {e}"
            raise   # Re-raise to be caught by the worker's BaseException

        # BACKUP OLD CODE (Separate transform and normalization):
        # ---------------------------------------------------------------------
        # radonSourceField, radonReceiverField, radonAvpField = computeRadonImagesSafe(...)
        # radonAvpField = np.conj(radonSourceField) * radonReceiverField
        # self.radonSourceBeamImage = self._fieldToUnitImage(radonSourceField)
        # self.radonReceiverBeamImage = self._fieldToUnitImage(radonReceiverField)
        # self.radonAvpImage = self._fieldToUnitImage(radonAvpField)
        # ---------------------------------------------------------------------
        pxMs = px * 1000.0
        pyMs = py * 1000.0
        self.radonX0 = float(pxMs[0])
        self.radonY0 = float(pyMs[0])
        self.radonDx = float(pxMs[1] - pxMs[0]) if sampleCount > 1 else 1.0
        self.radonDy = float(pyMs[1] - pyMs[0]) if sampleCount > 1 else 1.0
        _emitWorkerPhase(progressHandler, messageHandler, phaseEnd, f'{phaseLabel} - Radon transforms completed')

    def finalizeImages(self, progressHandler=None, messageHandler=None, progressStart: int = 0, progressEnd: int = 100, phaseLabel: str = 'CFP analysis') -> None:
        phaseStart = int(progressStart)
        phaseEnd = int(progressEnd)
        phaseSpan = max(phaseEnd - phaseStart, 0)
        flushProgress = phaseStart + max(phaseSpan // 5, 1)
        xyProgress = phaseStart + max((2 * phaseSpan) // 5, 1)
        resolutionProgress = phaseStart + max((3 * phaseSpan) // 5, 1)
        radonStart = phaseStart + max((4 * phaseSpan) // 5, 1)

        _emitWorkerPhase(progressHandler, messageHandler, phaseStart, f'{phaseLabel} - flushing buffered template contributions')
        self.flushBufferedPointArrays()
        _emitWorkerPhase(progressHandler, messageHandler, flushProgress, f'{phaseLabel} - converting XY beam slices')

        try:
            # Fused Numba path computes Source, Receiver, and Resolution images in a single call.
            self.sourceBeamImage, self.receiverBeamImage, self.resolutionImage = computeXyBeamImagesSafe(
                self.sourceBeamField, self.receiverBeamField
            )
        except Exception as e:
            self.survey.errorText = f"XY beam image conversion failed: {e}"
            raise   # Re-raise to be caught by the worker's BaseException

        _emitWorkerPhase(progressHandler, messageHandler, xyProgress, f'{phaseLabel} - XY beam slices converted')
        _emitWorkerPhase(progressHandler, messageHandler, resolutionProgress, f'{phaseLabel} - building Radon transforms')
        self._finalizeRadonImages(progressHandler, messageHandler, radonStart, phaseEnd, phaseLabel)

    def buildPayload(self) -> dict[str, Any]:
        return {
            'sourceBeamImage': _copyArrayIfNumpy(self.sourceBeamImage),
            'receiverBeamImage': _copyArrayIfNumpy(self.receiverBeamImage),
            'resolutionImage': _copyArrayIfNumpy(self.resolutionImage),
            'radonSourceBeamImage': _copyArrayIfNumpy(self.radonSourceBeamImage),
            'radonReceiverBeamImage': _copyArrayIfNumpy(self.radonReceiverBeamImage),
            'radonAvpImage': _copyArrayIfNumpy(self.radonAvpImage),
            'sourceSnr': self.sourceSnr,
            'receiverSnr': self.receiverSnr,
            'avpSnr': self.avpSnr,
            'sourceBeamX0': self.sourceBeamX0,
            'sourceBeamY0': self.sourceBeamY0,
            'sourceBeamDx': self.sourceBeamDx,
            'sourceBeamDy': self.sourceBeamDy,
            'radonX0': self.radonX0,
            'radonY0': self.radonY0,
            'radonDx': self.radonDx,
            'radonDy': self.radonDy,
        }


class BinFromGeometryWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: BinningFromGeometryRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = request.extended
        self.debugpyEnabled = request.debugpyEnabled
        self.includeProfiling = request.includeProfiling

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

        finally:
            self.resultReady.emit(self.buildResult(success))
            self.finished.emit()

    def buildResult(self, success: bool) -> BinningFromGeometryResult:
        profiling = None
        if self.includeProfiling:
            profiling = GeometryProfilingPayload(
                timerTmin=tuple(self.survey.timerTmin),
                timerTmax=tuple(self.survey.timerTmax),
                timerTtot=tuple(self.survey.timerTtot),
                timerFreq=tuple(self.survey.timerFreq),
            )

        if not success:
            return BinningFromGeometryResult(success=False, errorText=self.survey.errorText, profiling=profiling)

        output = self.survey.output
        minRmsOffset = None if output.rmsOffset is None else max(output.minRmsOffset, 0)
        maxRmsOffset = None if output.rmsOffset is None else max(output.maxRmsOffset, 0)
        minOffsetGap = None if output.gapOffset is None else max(output.minOffsetGap, 0)
        maxOffsetGap = None if output.gapOffset is None else max(output.maxOffsetGap, 0)
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
            minOffsetGap=minOffsetGap,
            maxOffsetGap=maxOffsetGap,
            gapOffset=output.gapOffset,
            ofAziHist=output.ofAziHist,
            offstHist=output.offstHist,
            cmpTransform=self.survey.cmpTransform,
            anaOutputShape=None if output.anaOutput is None else output.anaOutput.shape,
            profiling=profiling,
        )


class BinningWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: BinningFromTemplatesRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.extended = request.extended
        self.debugpyEnabled = request.debugpyEnabled
        self.includeProfiling = request.includeProfiling

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

        finally:
            self.resultReady.emit(self.buildResult(success))
            self.finished.emit()

    def buildResult(self, success: bool) -> BinningFromTemplatesResult:
        profiling = None
        if self.includeProfiling:
            profiling = GeometryProfilingPayload(
                timerTmin=tuple(self.survey.timerTmin),
                timerTmax=tuple(self.survey.timerTmax),
                timerTtot=tuple(self.survey.timerTtot),
                timerFreq=tuple(self.survey.timerFreq),
            )

        if not success:
            return BinningFromTemplatesResult(success=False, errorText=self.survey.errorText, profiling=profiling)

        output = self.survey.output
        minRmsOffset = None if output.rmsOffset is None else max(output.minRmsOffset, 0)
        maxRmsOffset = None if output.rmsOffset is None else max(output.maxRmsOffset, 0)
        minOffsetGap = None if output.gapOffset is None else max(output.minOffsetGap, 0)
        maxOffsetGap = None if output.gapOffset is None else max(output.maxOffsetGap, 0)
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
            minOffsetGap=minOffsetGap,
            maxOffsetGap=maxOffsetGap,
            gapOffset=output.gapOffset,
            ofAziHist=output.ofAziHist,
            offstHist=output.offstHist,
            cmpTransform=self.survey.cmpTransform,
            anaOutputShape=None if output.anaOutput is None else output.anaOutput.shape,
            profiling=profiling,
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


class CfpFromTemplatesWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: CfpFromTemplatesRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.debugpyEnabled = request.debugpyEnabled
        self.focalX = request.focalX
        self.focalY = request.focalY
        self.focalZ = request.focalZ
        self.frequency = request.frequency
        self.maxDipDegrees = request.maxDipDegrees
        self.vint = request.vint
        self.matlab_compat = getattr(request, 'matlab_compat', False)
        self.beamAccumulator = CfpBeamAccumulator(self.survey, self.focalZ, self.frequency, self.vint, self.maxDipDegrees, self.focalX, self.focalY)

        self.survey.fromXmlString(request.xmlString, False)

    def run(self):
        """Long-running task."""

        try:
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()

            self.survey.progress.emit(0)
            success = self.beamAccumulator.initializeGrid()
            if success:
                success = self.survey.scanCfpTemplates(
                    self.focalX,
                    self.focalY,
                    self.focalZ,
                    self.maxDipDegrees,
                    self.vint,
                    contributionHandler=self.beamAccumulator.accumulatePointArrays,
                    progressStart=0,
                    progressEnd=100,
                )
            if success:
                self.survey.progress.emit(0)
                self.beamAccumulator.finalizeImages(
                    progressHandler=self.survey.progress.emit,
                    messageHandler=self.survey.message.emit,
                    progressStart=0,
                    progressEnd=100,
                    phaseLabel='CFP from Templates',
                )
        except BaseException as e:
            self.survey._recordInnermostExceptionLocation(e)
            success = False
        finally:
            try:
                self.resultReady.emit(self.buildResult(success))
            except BaseException as e:
                self.survey._recordInnermostExceptionLocation(e)
            finally:
                self.finished.emit()

    def buildResult(self, success: bool) -> CfpFromTemplatesResult:
        payload = self.beamAccumulator.buildPayload()
        if not success:
            return CfpFromTemplatesResult(
                success=False,
                errorText=self.survey.errorText,
                templateContributionCount=self.survey.cfpTemplateContributionCount,
                totalTemplateCount=max(self.survey.nTemplates, 0),
                focalX=self.focalX,
                focalY=self.focalY,
                focalZ=self.focalZ,
                frequency=self.frequency,
                maxDipDegrees=self.maxDipDegrees,
                apertureRadius=self.survey.cfpApertureRadius,
                vint=self.vint,
                **payload,
            )

        return CfpFromTemplatesResult(
            success=True,
            templateContributionCount=self.survey.cfpTemplateContributionCount,
            totalTemplateCount=max(self.survey.nTemplates, 0),
            focalX=self.focalX,
            focalY=self.focalY,
            focalZ=self.focalZ,
            frequency=self.frequency,
            maxDipDegrees=self.maxDipDegrees,
            apertureRadius=self.survey.cfpApertureRadius,
            vint=self.vint,
            **payload,
        )


class CfpAmplitudeMapWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)
    partialResultReady = pyqtSignal(object)

    def __init__(self, request: CfpAmplitudeMapRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.request = request
        self.matlab_compat = getattr(request, 'matlab_compat', False)
        self.survey.fromXmlString(request.xmlString, False)
        self.survey.output.srcGeom = request.srcGeom
        self.survey.output.relGeom = request.relGeom
        self.survey.output.recGeom = request.recGeom

    def run(self):
        try:
            if haveDebugpy and self.request.debugpyEnabled:
                debugpy.debug_this_thread()

            self.survey.progress.emit(0)

            # 1. Setup Grid based on Analysis Area
            outputRect = self.survey.output.rctOutput
            dx, dy = self.survey.grid.binSize.x(), self.survey.grid.binSize.y()
            nx = max(int(np.ceil(outputRect.width() / dx)), 1)
            ny = max(int(np.ceil(outputRect.height() / dy)), 1)

            x0, y0 = float(outputRect.left()), float(outputRect.top())
            evalX = np.ascontiguousarray(x0 + np.arange(nx, dtype=np.float32) * dx)
            ampMap = np.zeros((ny, nx), dtype=np.float32)

            # Unified trace collection
            if self.survey.output.relGeom is not None:
                self.survey.prepareGeometryRelationBinningLookup()
                srcCoords, recCoords, relWeights = self._gatherTracesFromRelations()
            else:
                srcCoords, recCoords, relWeights = self._gatherTracesFromTemplates()

            if srcCoords.shape[0] == 0:
                raise ValueError("No active traces available for Illumination mapping")

            apertureRadius = abs(self.request.focalZ) * np.tan(np.radians(self.request.maxDipDegrees))
            freqs = self.request.frequencies if self.request.frequencies is not None else np.array([20.0, 40.0], dtype=np.float32)
            partialEmitEvery = max(1, ny // 20)

            # 3. Iterate over the Grid
            currentThread = QThread.currentThread()
            for iy in range(ny):
                if currentThread.isInterruptionRequested():
                    raise StopIteration

                focalY = y0 + iy * dy

                # Parallel row computation via Numba
                ampMap[iy, :] = compute_illumination_row_numba(
                    focalY, evalX, self.request.focalZ,
                    srcCoords, recCoords, relWeights,
                    freqs, self.request.vint, apertureRadius,
                    self.matlab_compat
                )

                self.survey.progress.emit(int((iy + 1) * 100 / ny))
                self.survey.message.emit(f"CFP Amplitude Map - row {iy+1}/{ny}")

                # Emit throttled partial results to limit UI redraw and copy overhead.
                if (iy + 1) % partialEmitEvery == 0 or (iy + 1) == ny:
                    partial = CfpAmplitudeMapResult(
                        success=True,
                        amplitudeMap=np.copy(ampMap),
                        x0=x0,
                        y0=y0,
                        dx=dx,
                        dy=dy,
                        isPartial=True,
                    )
                    self.partialResultReady.emit(partial)

            # Normalize result
            maxVal = ampMap.max()
            if maxVal > 0:
                ampMap /= maxVal

            result = CfpAmplitudeMapResult(
                success=True, amplitudeMap=ampMap, x0=x0, y0=y0, dx=dx, dy=dy
            )
            self.resultReady.emit(result)

        except StopIteration:
            self.resultReady.emit(CfpAmplitudeMapResult(success=False, errorText="Cancelled"))
        except Exception as e:
            self.resultReady.emit(CfpAmplitudeMapResult(success=False, errorText=str(e)))
        finally:
            self.finished.emit()

    def _gatherTracesFromRelations(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Internal helper to extract aligned trace arrays from relation and geometry tables."""
        rel = self.survey.output.relGeom
        srcGeom = self.survey.output.srcGeom
        recGeom = self.survey.output.recGeom
        if rel is None or srcGeom is None or recGeom is None:
            return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32)

        if rel.shape[0] == 0 or srcGeom.shape[0] == 0 or recGeom.shape[0] == 0:
            return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32)

        srcGeom = np.sort(srcGeom, order=['Index', 'Line', 'Point'])
        recGeom = np.sort(recGeom, order=['Index', 'Line', 'Point'])

        srcKeys = np.rec.fromarrays(
            [
                srcGeom['Index'].astype(np.int32),
                np.rint(srcGeom['Line']).astype(np.int32),
                np.rint(srcGeom['Point']).astype(np.int32),
            ],
            names='Ind,Lin,Pnt',
        )
        relSrcKeys = np.rec.fromarrays(
            [
                rel['SrcInd'].astype(np.int32),
                np.rint(rel['SrcLin']).astype(np.int32),
                np.rint(rel['SrcPnt']).astype(np.int32),
            ],
            names='Ind,Lin,Pnt',
        )

        srcIdx = np.searchsorted(srcKeys, relSrcKeys, side='left')
        validSrc = srcIdx < srcKeys.shape[0]
        if srcKeys.shape[0] > 0:
            safeSrcIdx = np.minimum(srcIdx, srcKeys.shape[0] - 1)
            validSrc &= srcKeys[safeSrcIdx] == relSrcKeys
        else:
            safeSrcIdx = np.zeros(rel.shape[0], dtype=np.int64)

        recKeys = np.rec.fromarrays(
            [
                recGeom['Index'].astype(np.int32),
                np.rint(recGeom['Line']).astype(np.int32),
                np.rint(recGeom['Point']).astype(np.int32),
            ],
            names='Ind,Lin,Pnt',
        )
        relRecKeys = np.rec.fromarrays(
            [
                rel['RecInd'].astype(np.int32),
                np.rint(rel['RecLin']).astype(np.int32),
                np.rint(rel['RecMin']).astype(np.int32),
            ],
            names='Ind,Lin,Pnt',
        )

        recIdx = np.searchsorted(recKeys, relRecKeys, side='left')
        validRec = recIdx < recKeys.shape[0]
        if recKeys.shape[0] > 0:
            safeRecIdx = np.minimum(recIdx, recKeys.shape[0] - 1)
            validRec &= recKeys[safeRecIdx] == relRecKeys
        else:
            safeRecIdx = np.zeros(rel.shape[0], dtype=np.int64)

        validRange = rel['RecMax'] >= rel['RecMin']
        validMask = validSrc & validRec & validRange
        if not np.any(validMask):
            return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32)

        srcPick = safeSrcIdx[validMask]
        recPick = safeRecIdx[validMask]
        relValid = rel[validMask]

        # Aligned source trace arrays
        sX = srcGeom['LocX'][srcPick].astype(np.float32)
        sY = srcGeom['LocY'][srcPick].astype(np.float32)
        sZ = (srcGeom['Elev'][srcPick] - srcGeom['Depth'][srcPick]).astype(np.float32)
        src_xyz = np.column_stack((sX, sY, sZ))

        # Aligned receiver proxy arrays
        rX = recGeom['LocX'][recPick].astype(np.float32)
        rY = recGeom['LocY'][recPick].astype(np.float32)
        rZ = (recGeom['Elev'][recPick] - recGeom['Depth'][recPick]).astype(np.float32)
        rec_xyz = np.column_stack((rX, rY, rZ))

        weights = (relValid['RecMax'] - relValid['RecMin'] + 1.0).astype(np.float32)
        return src_xyz, rec_xyz, weights

    def _gatherTracesFromTemplates(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Expands rolling templates to full trace coordinate arrays for mapping."""
        src_list = []
        rec_list = []

        def contributionHandler(srcPoints, recPoints):
            src_list.append(srcPoints)
            rec_list.append(recPoints)

        self.survey.scanCfpTemplates(
            self.survey.output.rctOutput.center().x(), self.survey.output.rctOutput.center().y(),
            self.request.focalZ, 90.0, self.request.vint, contributionHandler=contributionHandler
        )

        if not src_list:
            return np.empty((0, 3), dtype=np.float32), np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32)

        src_xyz = np.concatenate(src_list, axis=0).astype(np.float32)
        rec_xyz = np.concatenate(rec_list, axis=0).astype(np.float32)
        return src_xyz, rec_xyz, np.ones(src_xyz.shape[0], dtype=np.float32)


class CfpFromTraceTableWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: CfpFromTraceTableRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.debugpyEnabled = request.debugpyEnabled
        self.analysisRows = request.analysisRows
        self.focalX = request.focalX
        self.focalY = request.focalY
        self.focalZ = request.focalZ
        self.frequency = request.frequency
        self.maxDipDegrees = request.maxDipDegrees
        self.vint = request.vint
        self.matlab_compat = getattr(request, 'matlab_compat', False)
        self.chunkSize = max(int(request.chunkSize), 1)
        self.chunkCount = 0
        self.totalTraceCount = 0
        self.contributingTraceCount = 0
        self.apertureRadius = abs(self.focalZ) * np.tan(np.radians(self.maxDipDegrees))
        self.beamAccumulator = CfpBeamAccumulator(self.survey, self.focalZ, self.frequency, self.vint, self.maxDipDegrees, self.focalX, self.focalY)

        self.survey.fromXmlString(request.xmlString, False)

    def run(self):
        """Long-running task."""

        try:
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()

            self.survey.progress.emit(0)
            success = self._scanTraceTable()
        except BaseException as e:
            fileName = os.path.split(sys.exc_info()[2].tb_frame.f_code.co_filename)[1]
            funcName = sys.exc_info()[2].tb_frame.f_code.co_name
            lineNo = str(sys.exc_info()[2].tb_lineno)
            self.survey.errorText = f'file: {fileName}, function: {funcName}(), line: {lineNo}, error: {str(e)}'
            del (fileName, funcName, lineNo)
            success = False

        finally:
            self.resultReady.emit(self.buildResult(success))
            self.finished.emit()

    def _scanTraceTable(self) -> bool:
        if self.analysisRows is None:
            self.survey.errorText = 'trace table has not been defined'
            return False

        if len(getattr(self.analysisRows, 'shape', ())) != 2 or self.analysisRows.shape[1] < 9:
            self.survey.errorText = 'trace table has invalid shape'
            return False

        totalRows = int(self.analysisRows.shape[0])
        self.chunkCount = (totalRows + self.chunkSize - 1) // self.chunkSize if totalRows > 0 else 0
        self.totalTraceCount = 0
        self.contributingTraceCount = 0

        if not self.beamAccumulator.initializeGrid():
            return False

        if self.chunkCount == 0:
            self.survey.progress.emit(100)
            self.survey.message.emit('CFP from Trace Table - no trace rows available')
            return True

        currentThread = QThread.currentThread()
        for chunkIndex in range(self.chunkCount):
            if currentThread.isInterruptionRequested():
                self.survey.errorText = 'CFP trace-table scan cancelled'
                return False

            startRow = chunkIndex * self.chunkSize
            endRow = min(startRow + self.chunkSize, totalRows)
            chunk = self.analysisRows[startRow:endRow]
            activeMask = chunk[:, 2] > 0.0
            activeTraceCount = int(np.count_nonzero(activeMask))
            self.totalTraceCount += activeTraceCount

            if activeTraceCount > 0:
                activeChunk = chunk[activeMask]
                validIndices = filterSpsRelationsByApertureSafe(
                    self.focalX,
                    self.focalY,
                    self.apertureRadius,
                    activeChunk[:, 3],
                    activeChunk[:, 4],
                    activeChunk[:, 6],
                    activeChunk[:, 7],
                    self.matlab_compat
                )
                self.contributingTraceCount += int(validIndices.shape[0])
                self._accumulateBeams(activeChunk, validIndices)

            progress = ((chunkIndex + 1) * 100) // self.chunkCount
            self.survey.progress.emit(progress)
            self.survey.message.emit(
                f'CFP from Trace Table - processed chunk {chunkIndex + 1:,}/{self.chunkCount:,}'
            )

        self.survey.progress.emit(0)
        self.beamAccumulator.finalizeImages(
            progressHandler=self.survey.progress.emit,
            messageHandler=self.survey.message.emit,
            progressStart=0,
            progressEnd=100,
            phaseLabel='CFP from Trace Table',
        )
        return True

    def _initializeSourceBeamGrid(self) -> bool:
        return self.beamAccumulator.initializeGrid()

    def _accumulateBeams(self, activeChunk, validIndices) -> None:
        if validIndices.shape[0] == 0:
            return

        srcX = np.ascontiguousarray(activeChunk[validIndices, 3], dtype=np.float64)
        srcY = np.ascontiguousarray(activeChunk[validIndices, 4], dtype=np.float64)
        srcZ = np.ascontiguousarray(activeChunk[validIndices, 5], dtype=np.float64)
        recX = np.ascontiguousarray(activeChunk[validIndices, 6], dtype=np.float64)
        recY = np.ascontiguousarray(activeChunk[validIndices, 7], dtype=np.float64)
        recZ = np.ascontiguousarray(activeChunk[validIndices, 8], dtype=np.float64)

        # Optimize Trace Table path by collapsing redundant stations within the chunk.
        srcPoints = np.column_stack((srcX, srcY, srcZ))
        recPoints = np.column_stack((recX, recY, recZ))

        # Use the same accumulation logic as templates to benefit from weight collapsing
        self.beamAccumulator.accumulatePointArrays(
            srcPoints.astype(np.float32, copy=False),
            recPoints.astype(np.float32, copy=False)
        )

    def buildResult(self, success: bool) -> CfpFromTraceTableResult:
        payload = self.beamAccumulator.buildPayload()
        if not success:
            return CfpFromTraceTableResult(
                success=False,
                errorText=self.survey.errorText,
                chunkCount=self.chunkCount,
                totalTraceCount=self.totalTraceCount,
                contributingTraceCount=self.contributingTraceCount,
                focalX=self.focalX,
                focalY=self.focalY,
                focalZ=self.focalZ,
                frequency=self.frequency,
                maxDipDegrees=self.maxDipDegrees,
                apertureRadius=self.apertureRadius,
                vint=self.vint,
                **payload,
            )

        return CfpFromTraceTableResult(
            success=True,
            chunkCount=self.chunkCount,
            totalTraceCount=self.totalTraceCount,
            contributingTraceCount=self.contributingTraceCount,
            focalX=self.focalX,
            focalY=self.focalY,
            focalZ=self.focalZ,
            frequency=self.frequency,
            maxDipDegrees=self.maxDipDegrees,
            apertureRadius=self.apertureRadius,
            vint=self.vint,
            **payload,
        )
