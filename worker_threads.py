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
    compute_xy_beam_images_numba, scan_cfp_geometry_relations_numba)
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


def computeMonochromaticBeamXyGridSafe(evalX, evalY, evalZ, surfX, surfY, surfZ, frequency, vint, focalX=0.0, focalY=0.0):

    """
    KISS: Try Numba; if it fails, raise a clear error.
    No silent fallback. This is the only supported wrapper for CFP beam grid calculation.
    """
    try:
        return compute_monochromatic_beam_xy_grid(evalX, evalY, evalZ, surfX, surfY, surfZ, frequency, vint, focal_x=focalX, focal_y=focalY)
    except Exception as e:
        raise RuntimeError(f"CFP beam grid calculation failed: {e}") from e


def computeMonochromaticWeightedBeamXyGridSafe(evalX, evalY, evalZ, surfX, surfY, surfZ, surfWeights, frequency, vint, focalX=0.0, focalY=0.0):
    """
    KISS: Try Numba; if it fails, raise a clear error.
    No silent fallback. This is the only supported wrapper for weighted CFP beam grid calculation.
    """
    try:
        return compute_monochromatic_weighted_beam_xy_grid(evalX, evalY, evalZ, surfX, surfY, surfZ, surfWeights, frequency, vint, focal_x=focalX, focal_y=focalY)
    except Exception as e:
        raise RuntimeError(f"CFP weighted beam grid calculation failed: {e}") from e


def scanCfpGeometryRelationsSafe(*args):
    try:
        return scan_cfp_geometry_relations_numba(*args)
    except ImportError:
        pyFunc = getattr(scan_cfp_geometry_relations_numba, 'py_func', None)
        if pyFunc is None or not callable(pyFunc):
            raise
        return _callPythonFallback(pyFunc, *args)


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
    KISS: Try Numba; if it fails, raise a clear error.
    No silent fallback. This is the only supported wrapper for beam image calculation.
    """
    try:
        return compute_xy_beam_images_numba(sourceField, receiverField, dbMin)
    except Exception as e:
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


def _copyCfpImageForRollPlot(arr: Any) -> Any:
    """Copy CFP images from numerical row/column order into Roll plot x/y order."""
    if isinstance(arr, np.ndarray) and arr.ndim == 2:
        return np.ascontiguousarray(arr.T)
    return _copyArrayIfNumpy(arr)


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
class CfpFromGeometryTablesRequest:
    xmlString: str
    srcGeom: Any
    relGeom: Any
    recGeom: Any
    focalX: float = 0.0
    focalY: float = 0.0
    focalZ: float = -2000.0
    frequency: float = 40.0
    maxDipDegrees: float = 40.0
    vint: float = 2000.0
    chunkSize: int = 25_000
    debugpyEnabled: bool = False
    matlab_compat: bool = True
    sourceName: str = 'Geometry Tables'


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
class CfpFromGeometryTablesResult:
    success: bool
    errorText: str = ''
    sourceName: str = 'Geometry Tables'
    chunkCount: int = 0
    totalRelationCount: int = 0
    contributingRelationCount: int = 0
    totalTraceCount: int = 0
    contributingTraceCount: int = 0
    inactiveSourceCount: int = 0
    inactiveReceiverCount: int = 0
    inactiveSourceRelationCount: int = 0
    sourceOrphanRelationCount: int = 0
    receiverOrphanRelationCount: int = 0
    missingSourceCount: int = 0
    missingReceiverCount: int = 0
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
        self._bufferedSourceWeights = []
        self._bufferedReceiverWeights = []
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

        # added Bart, for quick settings:
        # width = height = 800
        # dx = dy = 12.5

        if dx <= 0.0 or dy <= 0.0:
            self.survey.errorText = 'analysis area sampling is invalid'
            return False

        nx = max(int(np.ceil(width / dx)), 1)
        ny = max(int(np.ceil(height / dy)), 1)
        self.sourceBeamDx = dx
        self.sourceBeamDy = dy
        if self.focalX is None:
            self.focalX = float(outputRect.center().x())
        if self.focalY is None:
            self.focalY = float(outputRect.center().y())
        self.sourceBeamX0 = self.focalX - width * 0.5
        self.sourceBeamY0 = self.focalY - height * 0.5
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
                self.focalX,
                self.focalY,
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
                self.focalX,
                self.focalY,
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
                self.focalX,
                self.focalY,
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
                self.focalX,
                self.focalY,
            )

    def _collapsePointWeights(self, points: np.ndarray, weights: np.ndarray | None = None, force: bool = False) -> tuple[np.ndarray, np.ndarray | None]:
        if points is None or points.shape[0] == 0:
            return np.empty((0, 3), dtype=np.float32), None

        if weights is not None:
            weights = np.ascontiguousarray(weights, dtype=np.float64)

        if not force and points.shape[0] < self.weightCollapseThresholdPoints:
            return points, weights

        pointCoords = np.ascontiguousarray(points[:, :3], dtype=np.float32)
        if weights is None:
            collapsedPoints, counts = np.unique(pointCoords, axis=0, return_counts=True)
            if collapsedPoints.shape[0] == points.shape[0]:
                return collapsedPoints, None

            return collapsedPoints, counts.astype(np.float64, copy=False)

        collapsedPoints, inverse = np.unique(pointCoords, axis=0, return_inverse=True)
        if collapsedPoints.shape[0] == points.shape[0]:
            return pointCoords, weights

        collapsedWeights = np.bincount(inverse, weights=weights).astype(np.float64, copy=False)
        return collapsedPoints, collapsedWeights

    def compactBufferedPointArrays(self) -> None:
        if not self._bufferedSourceArrays or not self._bufferedReceiverArrays:
            return

        sourcePoints = self._bufferedSourceArrays[0] if len(self._bufferedSourceArrays) == 1 else np.concatenate(self._bufferedSourceArrays, axis=0)
        receiverPoints = self._bufferedReceiverArrays[0] if len(self._bufferedReceiverArrays) == 1 else np.concatenate(self._bufferedReceiverArrays, axis=0)
        sourceWeights = self._combineBufferedWeights(self._bufferedSourceWeights, self._bufferedSourceArrays)
        receiverWeights = self._combineBufferedWeights(self._bufferedReceiverWeights, self._bufferedReceiverArrays)

        sourcePoints, sourceWeights = self._collapsePointWeights(sourcePoints, sourceWeights, force=True)
        receiverPoints, receiverWeights = self._collapsePointWeights(receiverPoints, receiverWeights, force=True)

        self._bufferedSourceArrays = [sourcePoints]
        self._bufferedReceiverArrays = [receiverPoints]
        self._bufferedSourceWeights = [sourceWeights]
        self._bufferedReceiverWeights = [receiverWeights]
        self._bufferedSourcePointCount = int(sourcePoints.shape[0])
        self._bufferedReceiverPointCount = int(receiverPoints.shape[0])

    @staticmethod
    def _combineBufferedWeights(weightArrays, pointArrays) -> np.ndarray | None:
        if not any(weights is not None for weights in weightArrays):
            return None

        combinedWeights = []
        for points, weights in zip(pointArrays, weightArrays):
            if weights is None:
                combinedWeights.append(np.ones(points.shape[0], dtype=np.float64))
            else:
                combinedWeights.append(np.ascontiguousarray(weights, dtype=np.float64))

        return combinedWeights[0] if len(combinedWeights) == 1 else np.concatenate(combinedWeights)

    def _bufferPointArrays(self, sourcePoints, receiverPoints, sourceWeights=None, receiverWeights=None) -> None:
        self._bufferedSourceArrays.append(sourcePoints)
        self._bufferedReceiverArrays.append(receiverPoints)
        self._bufferedSourceWeights.append(sourceWeights)
        self._bufferedReceiverWeights.append(receiverWeights)
        self._bufferedSourcePointCount += int(sourcePoints.shape[0])
        self._bufferedReceiverPointCount += int(receiverPoints.shape[0])

    def flushBufferedPointArrays(self) -> None:
        if not self._bufferedSourceArrays or not self._bufferedReceiverArrays:
            return

        sourcePoints = self._bufferedSourceArrays[0] if len(self._bufferedSourceArrays) == 1 else np.concatenate(self._bufferedSourceArrays, axis=0)
        receiverPoints = self._bufferedReceiverArrays[0] if len(self._bufferedReceiverArrays) == 1 else np.concatenate(self._bufferedReceiverArrays, axis=0)
        sourceWeights = self._combineBufferedWeights(self._bufferedSourceWeights, self._bufferedSourceArrays)
        receiverWeights = self._combineBufferedWeights(self._bufferedReceiverWeights, self._bufferedReceiverArrays)

        self._bufferedSourceArrays = []
        self._bufferedReceiverArrays = []
        self._bufferedSourceWeights = []
        self._bufferedReceiverWeights = []
        self._bufferedSourcePointCount = 0
        self._bufferedReceiverPointCount = 0

        sourcePoints, sourceWeights = self._collapsePointWeights(sourcePoints, sourceWeights)
        receiverPoints, receiverWeights = self._collapsePointWeights(receiverPoints, receiverWeights)

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

    def accumulateWeightedPointArrays(self, sourcePoints, receiverPoints, sourceWeights, receiverWeights) -> None:
        if sourcePoints is None or receiverPoints is None:
            return

        if sourcePoints.shape[0] == 0 or receiverPoints.shape[0] == 0:
            return

        if sourceWeights is None or receiverWeights is None:
            return

        if sourceWeights.shape[0] != sourcePoints.shape[0] or receiverWeights.shape[0] != receiverPoints.shape[0]:
            raise ValueError('weighted CFP point arrays must match their weight arrays')

        self._bufferPointArrays(sourcePoints, receiverPoints, sourceWeights, receiverWeights)
        if max(self._bufferedSourcePointCount, self._bufferedReceiverPointCount) >= self.flushThresholdPoints:
            self.compactBufferedPointArrays()

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
        sampleCount = 256
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

        self.radonX0 = float(px[0])
        self.radonY0 = float(py[0])
        self.radonDx = float(px[1] - px[0]) if sampleCount > 1 else 1.0
        self.radonDy = float(py[1] - py[0]) if sampleCount > 1 else 1.0
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
            'sourceBeamImage': _copyCfpImageForRollPlot(self.sourceBeamImage),
            'receiverBeamImage': _copyCfpImageForRollPlot(self.receiverBeamImage),
            'resolutionImage': _copyCfpImageForRollPlot(self.resolutionImage),
            'radonSourceBeamImage': _copyCfpImageForRollPlot(self.radonSourceBeamImage),
            'radonReceiverBeamImage': _copyCfpImageForRollPlot(self.radonReceiverBeamImage),
            'radonAvpImage': _copyCfpImageForRollPlot(self.radonAvpImage),
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
                    weightedContributionHandler=self.beamAccumulator.accumulateWeightedPointArrays,
                    progressStart=0,
                    progressEnd=100,
                )
            if success:
                self.survey.message.emit('CFP from Templates - Please wait, finalizing images...')
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
    # partialResultReady = pyqtSignal(object)

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
            evalX = np.ascontiguousarray(x0 + (np.arange(nx, dtype=np.float32) + 0.5) * dx)
            ampMap = np.zeros((ny, nx), dtype=np.float32)

            # Trace collection follows the input trajectory selected by the request.
            if self.survey.output.srcGeom is not None and self.survey.output.relGeom is not None and self.survey.output.recGeom is not None:
                self.survey.prepareGeometryRelationBinningLookup()
                srcCoords, srcWeights, recCoords, recWeights = self._gatherTracesFromRelations()
            else:
                srcCoords, srcWeights, recCoords, recWeights = self._gatherTracesFromTemplates()

            if srcCoords.shape[0] == 0 or recCoords.shape[0] == 0:
                raise ValueError("No active traces available for Illumination mapping")

            apertureRadius = abs(self.request.focalZ) * np.tan(np.radians(self.request.maxDipDegrees))
            freqs = self.request.frequencies if self.request.frequencies is not None else np.array([40.0], dtype=np.float32)
            # partialEmitEvery = max(1, ny // 20)

            # 3. Iterate over the Grid
            currentThread = QThread.currentThread()
            for iy in range(ny):
                if currentThread.isInterruptionRequested():
                    raise StopIteration

                focalY = y0 + (iy + 0.5) * dy

                # Parallel row computation via Numba
                ampMap[iy, :] = compute_illumination_row_numba(
                    focalY, evalX, self.request.focalZ,
                    srcCoords, srcWeights, recCoords, recWeights,
                    freqs, self.request.vint, apertureRadius
                )

                self.survey.progress.emit(int((iy + 1) * 100 / ny))
                self.survey.message.emit(f"CFP illumination - row {iy+1}/{ny}")

                # # Emit throttled partial results to limit UI redraw and copy overhead.
                # if (iy + 1) % partialEmitEvery == 0 or (iy + 1) == ny:
                #     partial = CfpAmplitudeMapResult(
                #         success=True,
                #         amplitudeMap=_copyCfpImageForRollPlot(ampMap),
                #         x0=x0,
                #         y0=y0,
                #         dx=dx,
                #         dy=dy,
                #         isPartial=True,
                #     )
                #     self.partialResultReady.emit(partial)

            # Normalize result
            maxVal = ampMap.max()
            if maxVal > 0:
                ampMap /= maxVal

            result = CfpAmplitudeMapResult(
                success=True, amplitudeMap=_copyCfpImageForRollPlot(ampMap), x0=x0, y0=y0, dx=dx, dy=dy
            )
            self.resultReady.emit(result)

        except StopIteration:
            self.resultReady.emit(CfpAmplitudeMapResult(success=False, errorText="Cancelled"))
        except Exception as e:
            self.resultReady.emit(CfpAmplitudeMapResult(success=False, errorText=str(e)))
        finally:
            self.finished.emit()

    @staticmethod
    def _emptyWeightedStations() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        emptyPoints = np.empty((0, 3), dtype=np.float32)
        emptyWeights = np.empty(0, dtype=np.float32)
        return emptyPoints, emptyWeights, emptyPoints, emptyWeights

    @staticmethod
    def _inUseMask(table) -> np.ndarray:
        if 'InUse' not in table.dtype.names:
            return np.ones(table.shape[0], dtype=bool)
        return table['InUse'] != 0

    @staticmethod
    def _collapseWeightedCoordinates(points: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if points.shape[0] == 0:
            return np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.float32)

        uniquePoints, inverse = np.unique(np.ascontiguousarray(points, dtype=np.float32), axis=0, return_inverse=True)
        uniqueWeights = np.zeros(uniquePoints.shape[0], dtype=np.float64)
        np.add.at(uniqueWeights, inverse, np.asarray(weights, dtype=np.float64))
        return np.ascontiguousarray(uniquePoints, dtype=np.float32), np.ascontiguousarray(uniqueWeights, dtype=np.float32)

    def _gatherTracesFromRelations(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract weighted source/receiver station arrays from relation and geometry tables."""
        rel = self.survey.output.relGeom
        srcGeom = self.survey.output.srcGeom
        recGeom = self.survey.output.recGeom
        if rel is None or srcGeom is None or recGeom is None:
            return self._emptyWeightedStations()

        if rel.shape[0] == 0 or srcGeom.shape[0] == 0 or recGeom.shape[0] == 0:
            return self._emptyWeightedStations()

        srcGeom = np.sort(srcGeom[self._inUseMask(srcGeom)], order=['Index', 'Line', 'Point'])
        recGeom = np.sort(recGeom[self._inUseMask(recGeom)], order=['Index', 'Line', 'Point'])
        if srcGeom.shape[0] == 0 or recGeom.shape[0] == 0:
            return self._emptyWeightedStations()

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

        relInSps = rel['InSps'] != 0 if 'InSps' in rel.dtype.names else np.ones(rel.shape[0], dtype=bool)
        relInRps = rel['InRps'] != 0 if 'InRps' in rel.dtype.names else np.ones(rel.shape[0], dtype=bool)
        validRange = rel['RecMax'] >= rel['RecMin']
        validMask = validSrc & relInSps & relInRps & validRange
        if not np.any(validMask):
            return self._emptyWeightedStations()

        recIndex = recGeom['Index'].astype(np.int32)
        recLine = np.rint(recGeom['Line']).astype(np.int32)
        recPoint = np.rint(recGeom['Point']).astype(np.int32)
        groupLookup = {}
        groupStart = 0
        while groupStart < recGeom.shape[0]:
            groupEnd = groupStart + 1
            while groupEnd < recGeom.shape[0] and recIndex[groupEnd] == recIndex[groupStart] and recLine[groupEnd] == recLine[groupStart]:
                groupEnd += 1
            groupLookup[(int(recIndex[groupStart]), int(recLine[groupStart]))] = (groupStart, groupEnd)
            groupStart = groupEnd

        sourceWeights = np.zeros(srcGeom.shape[0], dtype=np.float64)
        receiverWeights = np.zeros(recGeom.shape[0], dtype=np.float64)

        validRows = np.flatnonzero(validMask)
        relRecInd = rel['RecInd'].astype(np.int32)
        relRecLine = np.rint(rel['RecLin']).astype(np.int32)
        relRecMin = np.rint(rel['RecMin']).astype(np.int32)
        relRecMax = np.rint(rel['RecMax']).astype(np.int32)

        for relIdx in validRows:
            group = groupLookup.get((int(relRecInd[relIdx]), int(relRecLine[relIdx])))
            if group is None:
                continue

            start, end = group
            first = start + np.searchsorted(recPoint[start:end], relRecMin[relIdx], side='left')
            last = start + np.searchsorted(recPoint[start:end], relRecMax[relIdx], side='right')
            if last <= first:
                continue

            sourceWeights[safeSrcIdx[relIdx]] += float(last - first)
            receiverWeights[first:last] += 1.0

        sourceMask = sourceWeights > 0.0
        receiverMask = receiverWeights > 0.0
        if not np.any(sourceMask) or not np.any(receiverMask):
            return self._emptyWeightedStations()

        sourcePoints = np.column_stack(
            (
                srcGeom['LocX'][sourceMask].astype(np.float32),
                srcGeom['LocY'][sourceMask].astype(np.float32),
                (srcGeom['Elev'][sourceMask] - srcGeom['Depth'][sourceMask]).astype(np.float32),
            )
        )
        receiverPoints = np.column_stack(
            (
                recGeom['LocX'][receiverMask].astype(np.float32),
                recGeom['LocY'][receiverMask].astype(np.float32),
                (recGeom['Elev'][receiverMask] - recGeom['Depth'][receiverMask]).astype(np.float32),
            )
        )
        return (
            np.ascontiguousarray(sourcePoints, dtype=np.float32),
            np.ascontiguousarray(sourceWeights[sourceMask], dtype=np.float32),
            np.ascontiguousarray(receiverPoints, dtype=np.float32),
            np.ascontiguousarray(receiverWeights[receiverMask], dtype=np.float32),
        )

    def _gatherTracesFromTemplates(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract weighted source/receiver station arrays from rolling templates."""
        src_list = []
        src_weight_list = []
        rec_list = []
        rec_weight_list = []

        def contributionHandler(srcPoints, recPoints, srcWeights, recWeights):
            src_list.append(srcPoints)
            src_weight_list.append(srcWeights)
            rec_list.append(recPoints)
            rec_weight_list.append(recWeights)

        self.survey.scanCfpTemplates(
            self.survey.output.rctOutput.center().x(), self.survey.output.rctOutput.center().y(),
            self.request.focalZ, 90.0, self.request.vint, weightedContributionHandler=contributionHandler
        )

        if not src_list:
            return self._emptyWeightedStations()

        srcPoints, srcWeights = self._collapseWeightedCoordinates(np.concatenate(src_list, axis=0), np.concatenate(src_weight_list, axis=0))
        recPoints, recWeights = self._collapseWeightedCoordinates(np.concatenate(rec_list, axis=0), np.concatenate(rec_weight_list, axis=0))
        return srcPoints, srcWeights, recPoints, recWeights


class CfpFromGeometryTablesWorker(QObject):
    finished = pyqtSignal()
    resultReady = pyqtSignal(object)

    def __init__(self, request: CfpFromGeometryTablesRequest):
        super().__init__()
        self.survey = RollSurvey()
        self.debugpyEnabled = request.debugpyEnabled
        self.srcGeom = request.srcGeom
        self.relGeom = request.relGeom
        self.recGeom = request.recGeom
        self.sourceName = getattr(request, 'sourceName', 'Geometry Tables')
        self.focalX = request.focalX
        self.focalY = request.focalY
        self.focalZ = request.focalZ
        self.frequency = request.frequency
        self.maxDipDegrees = request.maxDipDegrees
        self.vint = request.vint
        self.matlab_compat = getattr(request, 'matlab_compat', False)
        self.chunkSize = max(int(request.chunkSize), 1)
        self.chunkCount = 0
        self.totalRelationCount = 0
        self.contributingRelationCount = 0
        self.totalTraceCount = 0
        self.contributingTraceCount = 0
        self.inactiveSourceCount = 0
        self.inactiveReceiverCount = 0
        self.inactiveSourceRelationCount = 0
        self.sourceOrphanRelationCount = 0
        self.receiverOrphanRelationCount = 0
        self.missingSourceCount = 0
        self.missingReceiverCount = 0
        self.inactiveSourceKeys = set()
        self.apertureRadius = abs(self.focalZ) * np.tan(np.radians(self.maxDipDegrees))
        self.beamAccumulator = CfpBeamAccumulator(self.survey, self.focalZ, self.frequency, self.vint, self.maxDipDegrees, self.focalX, self.focalY)

        self.survey.fromXmlString(request.xmlString, False)
        self.survey.output.srcGeom = request.srcGeom
        self.survey.output.relGeom = request.relGeom
        self.survey.output.recGeom = request.recGeom

    @staticmethod
    def _roundedIntField(table, fieldName: str) -> np.ndarray:
        return np.rint(table[fieldName]).astype(np.int64, copy=False)

    @staticmethod
    def _intField(table, fieldName: str) -> np.ndarray:
        return table[fieldName].astype(np.int64, copy=False)

    @staticmethod
    def _onesIntArray(size: int) -> np.ndarray:
        return np.ones(size, dtype=np.int64)

    @staticmethod
    def _inUseMask(table) -> np.ndarray:
        if 'InUse' not in table.dtype.names:
            return np.ones(table.shape[0], dtype=bool)
        return table['InUse'] != 0

    @staticmethod
    def _sortedSourceArrays(table):
        if table.shape[0] == 0:
            emptyInt = np.empty(0, dtype=np.int64)
            emptyFloat = np.empty(0, dtype=np.float32)
            return emptyInt, emptyInt, emptyInt, emptyFloat, emptyFloat, emptyFloat

        sourceInd = CfpFromGeometryTablesWorker._intField(table, 'Index')
        sourceLine = CfpFromGeometryTablesWorker._roundedIntField(table, 'Line')
        sourcePoint = CfpFromGeometryTablesWorker._roundedIntField(table, 'Point')
        order = np.lexsort((sourcePoint, sourceLine, sourceInd))
        sourceInd = np.ascontiguousarray(sourceInd[order], dtype=np.int64)
        sourceLine = np.ascontiguousarray(sourceLine[order], dtype=np.int64)
        sourcePoint = np.ascontiguousarray(sourcePoint[order], dtype=np.int64)
        sourceX = np.ascontiguousarray(table['LocX'][order], dtype=np.float32)
        sourceY = np.ascontiguousarray(table['LocY'][order], dtype=np.float32)
        sourceZ = np.ascontiguousarray(table['Elev'][order] - table['Depth'][order], dtype=np.float32)
        return sourceInd, sourceLine, sourcePoint, sourceX, sourceY, sourceZ

    @staticmethod
    def _sortedReceiverArrays(table):
        if table.shape[0] == 0:
            emptyInt = np.empty(0, dtype=np.int64)
            emptyFloat = np.empty(0, dtype=np.float32)
            return emptyInt, emptyInt, emptyInt, emptyFloat, emptyFloat, emptyFloat, emptyInt, emptyInt, emptyInt, emptyInt

        receiverInd = CfpFromGeometryTablesWorker._intField(table, 'Index')
        receiverLine = CfpFromGeometryTablesWorker._roundedIntField(table, 'Line')
        receiverPoint = CfpFromGeometryTablesWorker._roundedIntField(table, 'Point')
        order = np.lexsort((receiverPoint, receiverLine, receiverInd))
        receiverInd = np.ascontiguousarray(receiverInd[order], dtype=np.int64)
        receiverLine = np.ascontiguousarray(receiverLine[order], dtype=np.int64)
        receiverPoint = np.ascontiguousarray(receiverPoint[order], dtype=np.int64)
        receiverX = np.ascontiguousarray(table['LocX'][order], dtype=np.float32)
        receiverY = np.ascontiguousarray(table['LocY'][order], dtype=np.float32)
        receiverZ = np.ascontiguousarray(table['Elev'][order] - table['Depth'][order], dtype=np.float32)

        groupBreaks = np.empty(receiverInd.shape[0], dtype=bool)
        groupBreaks[0] = True
        groupBreaks[1:] = (receiverInd[1:] != receiverInd[:-1]) | (receiverLine[1:] != receiverLine[:-1])
        groupStart = np.flatnonzero(groupBreaks).astype(np.int64, copy=False)
        groupEnd = np.empty_like(groupStart)
        groupEnd[:-1] = groupStart[1:]
        groupEnd[-1] = receiverInd.shape[0]
        groupInd = np.ascontiguousarray(receiverInd[groupStart], dtype=np.int64)
        groupLine = np.ascontiguousarray(receiverLine[groupStart], dtype=np.int64)
        return receiverInd, receiverLine, receiverPoint, receiverX, receiverY, receiverZ, groupInd, groupLine, groupStart, groupEnd

    def _buildSourceScanArrays(self):
        sourceMask = self._inUseMask(self.srcGeom)
        self.inactiveSourceCount = int(np.count_nonzero(~sourceMask))
        activeSourceArrays = self._sortedSourceArrays(self.srcGeom[sourceMask])
        inactiveSourceArrays = self._sortedSourceArrays(self.srcGeom[~sourceMask])
        return activeSourceArrays, inactiveSourceArrays

    def _buildReceiverScanArrays(self):
        receiverMask = self._inUseMask(self.recGeom)
        self.inactiveReceiverCount = int(np.count_nonzero(~receiverMask))
        return self._sortedReceiverArrays(self.recGeom[receiverMask])

    def _relationChunkArrays(self, relationChunk):
        relationCount = relationChunk.shape[0]
        relInSps = self._intField(relationChunk, 'InSps') if 'InSps' in relationChunk.dtype.names else self._onesIntArray(relationCount)
        relInRps = self._intField(relationChunk, 'InRps') if 'InRps' in relationChunk.dtype.names else self._onesIntArray(relationCount)
        return (
            self._intField(relationChunk, 'SrcInd'),
            self._roundedIntField(relationChunk, 'SrcLin'),
            self._roundedIntField(relationChunk, 'SrcPnt'),
            self._intField(relationChunk, 'RecInd'),
            self._roundedIntField(relationChunk, 'RecLin'),
            self._roundedIntField(relationChunk, 'RecMin'),
            self._roundedIntField(relationChunk, 'RecMax'),
            np.ascontiguousarray(relInSps, dtype=np.int64),
            np.ascontiguousarray(relInRps, dtype=np.int64),
        )

    def run(self):
        try:
            if haveDebugpy and self.debugpyEnabled:
                debugpy.debug_this_thread()

            self.survey.progress.emit(0)
            success = self._scanGeometryTables()
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

    def _scanGeometryTables(self) -> bool:
        if self.srcGeom is None or self.relGeom is None or self.recGeom is None:
            self.survey.errorText = 'source, relation, or receiver geometry table has not been defined'
            return False

        if not self.beamAccumulator.initializeGrid():
            return False

        totalRelations = int(self.relGeom.shape[0])
        self.totalRelationCount = totalRelations
        self.chunkCount = (totalRelations + self.chunkSize - 1) // self.chunkSize if totalRelations > 0 else 0

        if totalRelations == 0:
            self.survey.progress.emit(100)
            self.survey.message.emit(f'CFP from {self.sourceName} - no relation records available')
            return True

        self.survey.message.emit(f'CFP from {self.sourceName} - building geometry scan arrays')
        activeSourceArrays, inactiveSourceArrays = self._buildSourceScanArrays()
        sourceInd, sourceLine, sourcePoint, sourceX, sourceY, sourceZ = activeSourceArrays
        inactiveSourceInd, inactiveSourceLine, inactiveSourcePoint, _, _, _ = inactiveSourceArrays
        _, _, receiverPoint, receiverX, receiverY, receiverZ, receiverGroupInd, receiverGroupLine, receiverGroupStart, receiverGroupEnd = self._buildReceiverScanArrays()

        sourceWeights = np.zeros(sourceInd.shape[0], dtype=np.float64)
        receiverWeights = np.zeros(receiverPoint.shape[0], dtype=np.float64)
        apertureRadiusSquared = self.apertureRadius * self.apertureRadius

        currentThread = QThread.currentThread()
        for chunkIndex in range(self.chunkCount):
            if currentThread.isInterruptionRequested():
                self.survey.errorText = f'CFP from {self.sourceName} cancelled'
                return False

            startRow = chunkIndex * self.chunkSize
            endRow = min(startRow + self.chunkSize, totalRelations)
            chunkArrays = self._relationChunkArrays(self.relGeom[startRow:endRow])
            (
                totalTraceCount,
                contributingRelationCount,
                contributingTraceCount,
                inactiveSourceRelationCount,
                sourceOrphanRelationCount,
                receiverOrphanRelationCount,
                missingSourceCount,
                missingReceiverCount,
            ) = scanCfpGeometryRelationsSafe(
                *chunkArrays,
                sourceInd,
                sourceLine,
                sourcePoint,
                sourceX,
                sourceY,
                inactiveSourceInd,
                inactiveSourceLine,
                inactiveSourcePoint,
                receiverGroupInd,
                receiverGroupLine,
                receiverGroupStart,
                receiverGroupEnd,
                receiverPoint,
                receiverX,
                receiverY,
                sourceWeights,
                receiverWeights,
                self.focalX,
                self.focalY,
                apertureRadiusSquared,
            )
            self.totalTraceCount += int(totalTraceCount)
            self.contributingRelationCount += int(contributingRelationCount)
            self.contributingTraceCount += int(contributingTraceCount)
            self.inactiveSourceRelationCount += int(inactiveSourceRelationCount)
            self.sourceOrphanRelationCount += int(sourceOrphanRelationCount)
            self.receiverOrphanRelationCount += int(receiverOrphanRelationCount)
            self.missingSourceCount += int(missingSourceCount)
            self.missingReceiverCount += int(missingReceiverCount)

            progress = ((chunkIndex + 1) * 100) // self.chunkCount
            self.survey.progress.emit(progress)
            self.survey.message.emit(f'CFP from {self.sourceName} - processed chunk {chunkIndex + 1:,}/{self.chunkCount:,}')

        self.survey.progress.emit(100)
        self.survey.message.emit(f'CFP from {self.sourceName} - Please wait, finalizing images...')

        sourceMask = sourceWeights > 0.0
        receiverMask = receiverWeights > 0.0
        self.beamAccumulator.accumulateCoordinates(
            sourceX[sourceMask],
            sourceY[sourceMask],
            sourceZ[sourceMask],
            receiverX[receiverMask],
            receiverY[receiverMask],
            receiverZ[receiverMask],
            sourceWeights[sourceMask],
            receiverWeights[receiverMask],
        )

        self.survey.progress.emit(0)
        self.beamAccumulator.finalizeImages(
            progressHandler=self.survey.progress.emit,
            messageHandler=self.survey.message.emit,
            progressStart=0,
            progressEnd=100,
            phaseLabel=f'CFP from {self.sourceName}',
        )
        return True

    def buildResult(self, success: bool) -> CfpFromGeometryTablesResult:
        payload = self.beamAccumulator.buildPayload()
        return CfpFromGeometryTablesResult(
            success=success,
            errorText='' if success else self.survey.errorText,
            sourceName=self.sourceName,
            chunkCount=self.chunkCount,
            totalRelationCount=self.totalRelationCount,
            contributingRelationCount=self.contributingRelationCount,
            totalTraceCount=self.totalTraceCount,
            contributingTraceCount=self.contributingTraceCount,
            inactiveSourceCount=self.inactiveSourceCount,
            inactiveReceiverCount=self.inactiveReceiverCount,
            inactiveSourceRelationCount=self.inactiveSourceRelationCount,
            sourceOrphanRelationCount=self.sourceOrphanRelationCount,
            receiverOrphanRelationCount=self.receiverOrphanRelationCount,
            missingSourceCount=self.missingSourceCount,
            missingReceiverCount=self.missingReceiverCount,
            focalX=self.focalX,
            focalY=self.focalY,
            focalZ=self.focalZ,
            frequency=self.frequency,
            maxDipDegrees=self.maxDipDegrees,
            apertureRadius=self.apertureRadius,
            vint=self.vint,
            **payload,
        )
