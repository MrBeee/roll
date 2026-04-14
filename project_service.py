# coding=utf-8

import os
from dataclasses import dataclass, field
from math import ceil
from typing import cast

import numpy as np
from numpy.lib import recfunctions as rfn
from qgis.PyQt.QtCore import QFile, QIODevice, QTextStream

from .sps_io_and_qc import pntType1


@dataclass
class ProjectReadResult:
    success: bool
    plainText: str = ''
    errorText: str = ''


@dataclass
class ProjectWriteResult:
    success: bool
    xmlText: str = ''
    errorText: str = ''


@dataclass
class ArraySidecarResult:
    exists: bool
    valid: bool
    array: np.ndarray | None = None
    errorText: str = ''


@dataclass
class AnalysisMemmapResult:
    success: bool
    memmap: np.memmap | None = None
    an2Output: np.ndarray | None = None
    errorText: str = ''


@dataclass
class AnalysisDimensions:
    nx: int
    ny: int


@dataclass
class SidecarLoadMessage:
    level: str
    text: str


@dataclass
class ProjectSidecarLoadResult:
    dimensions: AnalysisDimensions
    existingSidecars: dict[str, bool] = field(default_factory=dict)
    messages: list[SidecarLoadMessage] = field(default_factory=list)
    binOutput: np.ndarray | None = None
    minOffset: np.ndarray | None = None
    maxOffset: np.ndarray | None = None
    rmsOffset: np.ndarray | None = None
    offstHist: np.ndarray | None = None
    ofAziHist: np.ndarray | None = None
    minimumFold: int = 0
    maximumFold: int = 0
    minMinOffset: float = 0.0
    maxMinOffset: float = 0.0
    minMaxOffset: float = 0.0
    maxMaxOffset: float = 0.0
    minRmsOffset: float = 0.0
    maxRmsOffset: float = 0.0
    analysisFold: int = 0
    analysisMemmapResult: AnalysisMemmapResult | None = None
    rpsImport: np.ndarray | None = None
    spsImport: np.ndarray | None = None
    xpsImport: np.ndarray | None = None
    recGeom: np.ndarray | None = None
    srcGeom: np.ndarray | None = None
    relGeom: np.ndarray | None = None


class ProjectService:
    analysisSidecarSuffixes = ('.bin.npy', '.min.npy', '.max.npy', '.rms.npy', '.off.npy', '.azi.npy', '.ana.npy')

    def readProjectText(self, fileName):
        qFile = QFile(fileName)
        if not qFile.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            return ProjectReadResult(success=False, errorText=qFile.errorString())

        stream = QTextStream(qFile)
        plainText = stream.readAll()
        qFile.close()
        return ProjectReadResult(success=True, plainText=plainText)

    def buildProjectXml(self, survey, projectDirectory=None, useRelativePaths=False, indent=4):
        if useRelativePaths:
            survey.makeWellPathsRelative(projectDirectory)
        return survey.toXmlString(indent)

    def writeProjectXml(self, fileName, survey, projectDirectory=None, useRelativePaths=False, indent=4):
        xmlText = self.buildProjectXml(survey, projectDirectory, useRelativePaths, indent)

        qFile = QFile(fileName)
        if not qFile.open(QIODevice.OpenModeFlag.WriteOnly | QIODevice.OpenModeFlag.Truncate):
            return ProjectWriteResult(success=False, xmlText=xmlText, errorText=qFile.errorString())

        _ = QTextStream(qFile) << xmlText
        qFile.close()
        return ProjectWriteResult(success=True, xmlText=xmlText)

    def sidecarPath(self, fileName, suffix):
        return fileName + suffix

    def sidecarExists(self, fileName, suffix):
        return os.path.exists(self.sidecarPath(fileName, suffix))

    def touchSidecar(self, fileName, suffix):
        path = self.sidecarPath(fileName, suffix)
        if not os.path.exists(path):
            return False
        os.utime(path, None)
        return True

    def calculateAnalysisDimensions(self, survey):
        dx = survey.grid.binSize.x()
        dy = survey.grid.binSize.y()
        nx = ceil(survey.output.rctOutput.width() / dx) if dx else 0
        ny = ceil(survey.output.rctOutput.height() / dy) if dy else 0
        return AnalysisDimensions(nx=nx, ny=ny)

    def saveArraySidecar(self, fileName, suffix, array):
        if not fileName or array is None:
            return False
        np.save(self.sidecarPath(fileName, suffix), array)
        return True

    def loadArraySidecar(self, fileName, suffix):
        path = self.sidecarPath(fileName, suffix)
        if not os.path.exists(path):
            return ArraySidecarResult(exists=False, valid=False)

        try:
            array = np.load(path)
        except (OSError, ValueError) as exc:
            return ArraySidecarResult(exists=True, valid=False, errorText=str(exc))

        return ArraySidecarResult(exists=True, valid=True, array=array)

    def loadSizedArraySidecar(self, fileName, suffix, expectedShape):
        result = self.loadArraySidecar(fileName, suffix)
        if not result.valid:
            return result

        array = cast(np.ndarray | None, result.array)
        if not isinstance(array, np.ndarray):
            return ArraySidecarResult(exists=True, valid=False, errorText='not-an-array')

        if array.shape != expectedShape:
            return ArraySidecarResult(exists=True, valid=False, errorText='shape-mismatch')

        return ArraySidecarResult(exists=result.exists, valid=True, array=array, errorText=result.errorText)

    def loadHistogramSidecar(self, fileName, suffix, expectedRows):
        result = self.loadArraySidecar(fileName, suffix)
        if not result.valid:
            return result

        array = cast(np.ndarray | None, result.array)
        if not isinstance(array, np.ndarray):
            return ArraySidecarResult(exists=True, valid=False, errorText='not-an-array')

        if array.shape[0] != expectedRows:
            return ArraySidecarResult(exists=True, valid=False, errorText='shape-mismatch')

        return ArraySidecarResult(exists=result.exists, valid=True, array=array, errorText=result.errorText)

    def openAnalysisMemmap(self, fileName, shape, mode='r+'):
        path = self.sidecarPath(fileName, '.ana.npy')
        if not os.path.exists(path):
            return AnalysisMemmapResult(success=False, errorText='missing-file')

        try:
            memmap = np.memmap(path, dtype=np.float32, mode=mode, shape=shape)
            an2Output = memmap.reshape(shape[0] * shape[1] * shape[2], shape[3])
        except (OSError, PermissionError, ValueError) as exc:
            return AnalysisMemmapResult(success=False, errorText=str(exc))

        return AnalysisMemmapResult(success=True, memmap=memmap, an2Output=an2Output)

    def saveAnalysisSidecars(self, fileName, output, includeHistograms=False):
        if not fileName:
            return False

        self.saveArraySidecar(fileName, '.bin.npy', output.binOutput)
        self.saveArraySidecar(fileName, '.min.npy', output.minOffset)
        self.saveArraySidecar(fileName, '.max.npy', output.maxOffset)
        self.saveArraySidecar(fileName, '.rms.npy', output.rmsOffset)

        if includeHistograms:
            self.saveArraySidecar(fileName, '.off.npy', output.offstHist)
            self.saveArraySidecar(fileName, '.azi.npy', output.ofAziHist)

        return True

    def saveSurveyDataSidecars(self, fileName, *, rpsImport=None, spsImport=None, xpsImport=None, recGeom=None, relGeom=None, srcGeom=None):
        if not fileName:
            return False

        self.saveArraySidecar(fileName, '.rps.npy', rpsImport)
        self.saveArraySidecar(fileName, '.sps.npy', spsImport)
        self.saveArraySidecar(fileName, '.xps.npy', xpsImport)
        self.saveArraySidecar(fileName, '.rec.npy', recGeom)
        self.saveArraySidecar(fileName, '.rel.npy', relGeom)
        self.saveArraySidecar(fileName, '.src.npy', srcGeom)
        return True

    def _appendMessage(self, result, level, text):
        result.messages.append(SidecarLoadMessage(level=level, text=text))

    def _appendNormalizedSidecarMessage(self, result, fileName, suffix, recordLabel):
        sidecarPath = self.sidecarPath(fileName, suffix)
        self._appendMessage(result, 'info', f'Loaded : . . . normalized legacy {recordLabel} sidecar to current point schema: {sidecarPath}')

    def _normalizePointArraySidecar(self, array):
        if not isinstance(array, np.ndarray) or array.dtype.names is None:
            return array, False

        names = set(array.dtype.names)
        if 'InUse' in names:
            return array, False

        requiredFields = {'Line', 'Point', 'Index', 'Code', 'Depth', 'East', 'North', 'Elev'}
        if not requiredFields.issubset(names):
            return array, False

        normalized = np.zeros(shape=array.shape, dtype=pntType1)

        for fieldName in ('Line', 'Point', 'Index', 'Code', 'Depth', 'East', 'North', 'Elev'):
            normalized[fieldName] = array[fieldName]

        if 'Uniq' in names:
            normalized['Uniq'] = array['Uniq']
        else:
            normalized['Uniq'] = 1

        if 'InXps' in names:
            normalized['InXps'] = array['InXps']
        else:
            normalized['InXps'] = 1

        normalized['InUse'] = 1

        if 'LocX' in names:
            normalized['LocX'] = array['LocX']
        if 'LocY' in names:
            normalized['LocY'] = array['LocY']

        return normalized, True

    def _loadAnalysisArraySidecars(self, fileName, survey, result):
        nx = result.dimensions.nx
        ny = result.dimensions.ny

        binResult = self.loadSizedArraySidecar(fileName, '.bin.npy', (nx, ny))
        if binResult.valid:
            result.binOutput = binResult.array
            result.maximumFold = int(result.binOutput.max())
            result.minimumFold = int(result.binOutput.min())
            self._appendMessage(result, 'info', f'Loaded : . . . Fold map&nbsp; : Min:{result.minimumFold} - Max:{result.maximumFold} ')
        elif binResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . Fold map&nbsp; : Wrong dimensions, compared to analysis area - file ignored')

        minResult = self.loadSizedArraySidecar(fileName, '.min.npy', (nx, ny))
        if minResult.valid:
            result.minOffset = minResult.array
            result.minOffset[result.minOffset == -np.inf] = np.inf
            result.minMinOffset = float(result.minOffset.min())
            result.minOffset[result.minOffset == np.inf] = -np.inf
            result.maxMinOffset = max(float(result.minOffset.max()), 0.0)
            self._appendMessage(result, 'info', f'Loaded : . . . Min-offset: Min:{result.minMinOffset:.2f}m - Max:{result.maxMinOffset:.2f}m ')
        elif minResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . Min-offset: Wrong dimensions, compared to analysis area - file ignored')

        maxResult = self.loadSizedArraySidecar(fileName, '.max.npy', (nx, ny))
        if maxResult.valid:
            result.maxOffset = maxResult.array
            result.maxMaxOffset = max(float(result.maxOffset.max()), 0.0)
            result.maxOffset[result.maxOffset == -np.inf] = np.inf
            result.minMaxOffset = float(result.maxOffset.min())
            result.maxOffset[result.maxOffset == np.inf] = -np.inf
            self._appendMessage(result, 'info', f'Loaded : . . . Max-offset: Min:{result.minMaxOffset:.2f}m - Max:{result.maxMaxOffset:.2f}m ')
        elif maxResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . Max-offset: Wrong dimensions, compared to analysis area - file ignored')

        rmsResult = self.loadSizedArraySidecar(fileName, '.rms.npy', (nx, ny))
        if rmsResult.valid:
            result.rmsOffset = rmsResult.array
            result.maxRmsOffset = float(result.rmsOffset.max())
            result.minRmsOffset = max(float(result.rmsOffset.min()), 0.0)
            self._appendMessage(result, 'info', f'Loaded : . . . Rms-offset: Min:{result.minRmsOffset:.2f}m - Max:{result.maxRmsOffset:.2f}m ')
        elif rmsResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . Rms-offset: Wrong dimensions, compared to analysis area - file ignored')

        offResult = self.loadHistogramSidecar(fileName, '.off.npy', 2)
        if offResult.valid:
            result.offstHist = offResult.array
            self._appendMessage(result, 'info', 'Loaded : . . . offset histogram')
        elif offResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . offset: Wrong dimensions of histogram - file ignored')

        aziResult = self.loadHistogramSidecar(fileName, '.azi.npy', 360 // 5)
        if aziResult.valid:
            result.ofAziHist = aziResult.array
            self._appendMessage(result, 'info', 'Loaded : . . . azi-offset histogram')
        elif aziResult.exists:
            self._appendMessage(result, 'error', 'Loaded : . . . azi-offset: Wrong dimensions of histogram - file ignored')

        if result.binOutput is None or not self.sidecarExists(fileName, '.ana.npy'):
            return

        fold = survey.grid.fold if survey.grid.fold > 0 else result.maximumFold
        result.analysisFold = fold
        self._appendMessage(result, 'info', f'Analysis load: fold={fold}, maxFold={result.maximumFold}')

        memmapResult = self.openAnalysisMemmap(fileName, (nx, ny, fold, 13), mode='r+')
        if not memmapResult.success:
            self._appendMessage(result, 'error', f'Loaded : . . . Analysis &nbsp;: read error {fileName + ".ana.npy"}. {memmapResult.errorText}')
            return

        nT = memmapResult.memmap.size
        expected = nx * ny * fold * 13
        delta = nT - expected
        self._appendMessage(result, 'info', f'Analysis load: nT={nT}, expected={expected}, delta={delta}')

        if delta != 0:
            self._appendMessage(result, 'error', f'Loaded : . . . Analysis &nbsp;: mismatch in trace table compared to fold {fold:,} x-size {nx}, and y-size {ny}. Please rerun extended analysis')
            return

        result.analysisMemmapResult = memmapResult
        self._appendMessage(result, 'info', f'Analysis load: an2Output.shape={memmapResult.an2Output.shape}')

        if result.maximumFold > fold:
            self._appendMessage(result, 'info', f'Loaded : . . . Analysis &nbsp;: observed fold in binning file: {result.maximumFold:,}. This is larger than allowed in the trace table ({fold:,}), expect missing traces in spider plot !')

        self._appendMessage(result, 'info', f'Loaded : . . . Analysis &nbsp;: {memmapResult.an2Output.shape[0]:,} traces (reserved space)')

    def _loadSurveyDataArrays(self, fileName, result):
        rpsResult = self.loadArraySidecar(fileName, '.rps.npy')
        if rpsResult.valid and rpsResult.array is not None:
            result.rpsImport = rfn.rename_fields(rpsResult.array, {'Record': 'RecNum'})
            result.rpsImport, normalized = self._normalizePointArraySidecar(result.rpsImport)
            if normalized:
                self._appendNormalizedSidecarMessage(result, fileName, '.rps.npy', 'rps-record')
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.rpsImport.shape[0]:,} rps-records')

        spsResult = self.loadArraySidecar(fileName, '.sps.npy')
        if spsResult.valid and spsResult.array is not None:
            result.spsImport, normalized = self._normalizePointArraySidecar(spsResult.array)
            if normalized:
                self._appendNormalizedSidecarMessage(result, fileName, '.sps.npy', 'sps-record')
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.spsImport.shape[0]:,} sps-records')

        xpsResult = self.loadArraySidecar(fileName, '.xps.npy')
        if xpsResult.valid:
            result.xpsImport = xpsResult.array
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.xpsImport.shape[0]:,} xps-records')

        recResult = self.loadArraySidecar(fileName, '.rec.npy')
        if recResult.valid and recResult.array is not None:
            result.recGeom, normalized = self._normalizePointArraySidecar(recResult.array)
            if normalized:
                self._appendNormalizedSidecarMessage(result, fileName, '.rec.npy', 'rec-record')
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.recGeom.shape[0]:,} rec-records')

        srcResult = self.loadArraySidecar(fileName, '.src.npy')
        if srcResult.valid and srcResult.array is not None:
            result.srcGeom, normalized = self._normalizePointArraySidecar(srcResult.array)
            if normalized:
                self._appendNormalizedSidecarMessage(result, fileName, '.src.npy', 'src-record')
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.srcGeom.shape[0]:,} src-records')

        relResult = self.loadArraySidecar(fileName, '.rel.npy')
        if relResult.valid and relResult.array is not None:
            result.relGeom = rfn.rename_fields(relResult.array, {'Record': 'RecNum'})
            self._appendMessage(result, 'info', f'Loaded : . . . read {result.relGeom.shape[0]:,} rel-records')

    def loadProjectSidecars(self, fileName, survey):
        result = ProjectSidecarLoadResult(dimensions=self.calculateAnalysisDimensions(survey))

        dx = survey.grid.binSize.x()
        dy = survey.grid.binSize.y()
        self._appendMessage(result, 'info', f'Analysis dims: nx={result.dimensions.nx}, ny={result.dimensions.ny}, binSize=({dx:.3f},{dy:.3f})')

        for suffix in self.analysisSidecarSuffixes:
            exists = self.sidecarExists(fileName, suffix)
            result.existingSidecars[suffix] = exists
            self._appendMessage(result, 'info', f'Analysis file: {suffix} exists={exists}')

        self._loadAnalysisArraySidecars(fileName, survey, result)
        self._loadSurveyDataArrays(fileName, result)
        return result
