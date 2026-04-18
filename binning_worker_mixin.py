# binning_worker_mixin.py
# -*- coding: utf-8 -*-

import os
from math import ceil
from timeit import default_timer as timer

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QThread
from qgis.PyQt.QtWidgets import QMessageBox

from .enums_and_int_flags import MsgType
from .worker_operation_controller import WorkerOperationController
from .worker_result_appliers import BinningResultApplier, GeometryResultApplier
from .worker_threads import (BinFromGeometryWorker,
                             BinningFromGeometryResult,
                             BinningFromTemplatesResult, BinningWorker,
                             GeometryFromTemplatesResult, GeometryWorker)


class BinningWorkerMixin:
    """Keeps the binning/geometry worker-thread lifecycle outside RollMainWindow."""

    def _getWorkerRuntimeDependencies(self):
        return {
            'QThread': QThread,
            'BinningWorker': BinningWorker,
            'BinFromGeometryWorker': BinFromGeometryWorker,
            'GeometryWorker': GeometryWorker,
            'timer': timer,
            'QMessageBox': QMessageBox,
        }

    def _ensureWorkerOperationComponents(self):
        if getattr(self, 'workerOperationController', None) is None:
            self.workerOperationController = WorkerOperationController(self, self._getWorkerRuntimeDependencies)

        if getattr(self, 'binningResultApplier', None) is None:
            self.binningResultApplier = BinningResultApplier(self, self._getWorkerRuntimeDependencies)

        if getattr(self, 'geometryResultApplier', None) is None:
            self.geometryResultApplier = GeometryResultApplier(self, self._getWorkerRuntimeDependencies)

    def finalizeAnalysisMemmap(self, shape):
        if not self.fileName or self.output.anaOutput is None:
            return False

        self.resetAnaTableModel()

        if not self.projectService.touchSidecar(self.fileName, '.ana.npy'):
            return False

        memmapResult = self.projectService.openAnalysisMemmap(self.fileName, shape, mode='r+')
        if not memmapResult.success:
            return False

        self.output.anaOutput = memmapResult.memmap
        self.output.an2Output = memmapResult.an2Output
        self.setDataAnaTableModel()
        return True

    def saveAnalysisSidecars(self, includeHistograms=False):
        return self.projectService.saveAnalysisSidecars(self.fileName, self.output, includeHistograms=includeHistograms)

    def saveSurveyDataSidecars(self):
        return self.projectService.saveSurveyDataSidecars(
            self.fileName,
            rpsImport=self.rpsImport,
            spsImport=self.spsImport,
            xpsImport=self.xpsImport,
            recGeom=self.recGeom,
            relGeom=self.relGeom,
            srcGeom=self.srcGeom,
        )

    def resolveColorMapName(self, value, fallback='CET-L1'):
        name = None
        if isinstance(value, pg.ColorMap):
            name = getattr(value, 'name', None)
            if callable(name):
                name = name()
        elif isinstance(value, str):
            name = value
        elif isinstance(value, bytes):
            name = value.decode(errors='ignore')
        else:
            toString = getattr(value, 'toString', None)
            if callable(toString):
                try:
                    name = toString()
                except (AttributeError, TypeError, ValueError):
                    name = None
            if name is None:
                try:
                    name = str(value)
                except (AttributeError, TypeError, ValueError):
                    name = None

        available = pg.colormap.listMaps()
        if name and name in available:
            return name

        if fallback in available:
            return fallback

        for candidate in ('viridis', 'plasma', 'magma', 'inferno', 'grey', 'gray'):
            if candidate in available:
                return candidate

        if available:
            return available[0]

        return pg.ColorMap([0.0, 1.0], [(0, 0, 0, 255), (255, 255, 255, 255)])

    def coerceColorMap(self, value, fallback='CET-L1'):
        if isinstance(value, (str, pg.ColorMap)):
            return value

        name = None
        try:
            name = str(value)
        except (AttributeError, TypeError, ValueError):
            name = None

        if name:
            resolved = self.resolveColorMapName(name, fallback=fallback)
            if isinstance(resolved, (str, pg.ColorMap)):
                return resolved

        available = pg.colormap.listMaps()
        if available:
            return available[0]

        return pg.ColorMap([0.0, 1.0], [(0, 0, 0, 255), (255, 255, 255, 255)])

    def resolveColorMapObject(self, value, fallback='viridis'):
        if isinstance(value, pg.ColorMap):
            return value

        name = None
        if isinstance(value, str):
            name = value
        elif isinstance(value, bytes):
            name = value.decode(errors='ignore')
        else:
            toString = getattr(value, 'toString', None)
            if callable(toString):
                try:
                    name = toString()
                except (AttributeError, TypeError, ValueError):
                    name = None
            if name is None:
                try:
                    name = str(value)
                except (AttributeError, TypeError, ValueError):
                    name = None

        if name:
            cmap = pg.colormap.get(name)
            if cmap is not None:
                return cmap

        fallbackCmap = pg.colormap.get(fallback)
        if fallbackCmap is not None:
            return fallbackCmap

        available = pg.colormap.listMaps()
        for candidate in ('viridis', 'plasma', 'magma', 'inferno', 'grey', 'gray'):
            if candidate in available:
                cmap = pg.colormap.get(candidate)
                if cmap is not None:
                    return cmap

        if available:
            cmap = pg.colormap.get(available[0])
            if cmap is not None:
                return cmap

        return pg.ColorMap([0.0, 1.0], [(0, 0, 0, 255), (255, 255, 255, 255)])

    def testBasicBinningConditions(self) -> bool:
        if self.survey.unique.apply:
            QMessageBox.information(
                self,
                'Please adjust',
                "Applying 'Unique offsets' requires using a 'Full Binning' process, as it is implemented as a post-processing step on the trace table",
                QMessageBox.StandardButton.Cancel,
            )
            return False
        return True

    def testFullBinningConditions(self) -> bool:
        if self.survey.grid.fold <= 0:
            QMessageBox.information(
                self,
                'Please adjust',
                "'Full Binning' requires selecting a max fold value > 0 in the 'local grid' settings, to allocate space for a memory mapped file.\n\n"
                "You can determine the required max fold value by first running 'Basic Binning'",
                QMessageBox.StandardButton.Cancel,
            )
            return False

        if not self.fileName:
            QMessageBox.information(
                self,
                'Please adjust',
                "'Full Binning' requires saving this file first, to obtain a valid filename in a directory with write access.",
                QMessageBox.StandardButton.Cancel,
            )
            return False

        return True

    def prepFullBinningConditions(self) -> bool:
        self.resetAnaTableModel()

        w = self.survey.output.rctOutput.width()
        h = self.survey.output.rctOutput.height()
        dx = self.survey.grid.binSize.x()
        dy = self.survey.grid.binSize.y()
        nx = ceil(w / dx)
        ny = ceil(h / dy)
        fold = self.survey.grid.fold
        n = nx * ny * fold
        self.appendLogMessage(
            f'Thread : Prepare memory mapped file for {n:,} traces, with nx={nx}, ny={ny}, fold={fold:,}',
            MsgType.Binning,
        )

        try:
            anaFileName = self.fileName + '.ana.npy'
            shape = (nx, ny, fold, 13)
            mode = 'r+' if os.path.exists(anaFileName) else 'w+'
            self.output.anaOutput = np.memmap(anaFileName, shape=shape, dtype=np.float32, mode=mode)
            self.output.anaOutput.fill(0.0)

            nX, nY, nZ, nC = self.output.anaOutput.shape
            if (nx, ny, fold, 13) != (nX, nY, nZ, nC):
                self.appendLogMessage('Thread : Memory mapped file size error while allocating memory', MsgType.Error)
                return False
        except MemoryError as exc:
            self.appendLogMessage(f'Thread : Memory error {exc}', MsgType.Error)
            return False

        return True

    def basicBinFromTemplates(self):
        if self.testBasicBinningConditions():
            self.binFromTemplates(False)

    def fullBinFromTemplates(self):
        if self.testFullBinningConditions():
            self.binFromTemplates(True)

    def basicBinFromGeometry(self):
        if self.testBasicBinningConditions():
            self.binFromGeometry(False)

    def fullBinFromGeometry(self):
        if self.testFullBinningConditions():
            self.binFromGeometry(True)

    def basicBinFromSps(self):
        if self.testBasicBinningConditions():
            self.binFromSps(False)

    def fullBinFromSps(self):
        if self.testFullBinningConditions():
            self.binFromSps(True)

    def binFromTemplates(self, fullAnalysis: bool):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.startBinningFromTemplates(fullAnalysis)

    def applyBinningWorkerResult(self, result, elapsed):
        self._ensureWorkerOperationComponents()
        self.binningResultApplier.apply(result, elapsed)

    def binningTemplatesThreadFinished(self, result: BinningFromTemplatesResult):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.finishCurrentOperation(result, self.applyBinningWorkerResult, resetAnalysis=False)

    def binningGeometryThreadFinished(self, result: BinningFromGeometryResult):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.finishCurrentOperation(result, self.applyBinningWorkerResult, resetAnalysis=False)

    def binningResultThreadFinished(self, result):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.finishCurrentOperation(result, self.applyBinningWorkerResult, resetAnalysis=False)

    def binFromGeometry(self, fullAnalysis: bool):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.startBinningFromGeometry(fullAnalysis)

    def binFromSps(self, fullAnalysis: bool):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.startBinningFromSps(fullAnalysis)

    def createGeometryFromTemplates(self):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.startGeometryFromTemplates()

    def threadProgress(self, value: int):
        if self.progressBar is not None:
            self.progressBar.setValue(value)

    def threadMessage(self, text: str):
        if self.progressLabel is not None:
            self.progressLabel.setText(text)

    def stopWorkerThread(self):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.stopCurrentOperation()

    def applyGeometryWorkerResult(self, result, elapsed):
        self._ensureWorkerOperationComponents()
        self.geometryResultApplier.apply(result, elapsed)

    def geometryThreadFinished(self, result: GeometryFromTemplatesResult):
        self._ensureWorkerOperationComponents()
        self.workerOperationController.finishCurrentOperation(result, self.applyGeometryWorkerResult, resetAnalysis=False, completionTabIndex=3)

    def showStatusbarWidgets(self):
        self.progressBar.setValue(0)
        self.statusbar.addWidget(self.progressBar)
        self.progressBar.show()
        self.statusbar.addWidget(self.progressLabel)
        self.progressLabel.show()

    def hideStatusbarWidgets(self):
        self.statusbar.removeWidget(self.progressBar)
        self.progressBar.setValue(0)
        self.statusbar.removeWidget(self.progressLabel)
