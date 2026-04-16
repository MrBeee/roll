# binning_worker_mixin.py
# -*- coding: utf-8 -*-

import os
from datetime import timedelta
from math import ceil
from timeit import default_timer as timer

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QThread
from qgis.PyQt.QtWidgets import QMessageBox

from .enums_and_int_flags import MsgType
from .worker_threads import (BinFromGeometryWorker, BinningFromGeometryRequest,
                             BinningFromGeometryResult,
                             BinningFromTemplatesRequest,
                             BinningFromTemplatesResult, BinningWorker,
                             GeometryFromTemplatesRequest,
                             GeometryFromTemplatesResult, GeometryWorker)


class BinningWorkerMixin:
    """Keeps the binning/geometry worker-thread lifecycle outside RollMainWindow."""

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
        if fullAnalysis:
            if not self.prepFullBinningConditions():
                return
            self.progressLabel.setText('Bin from Templates - full analysis')
        else:
            self.progressLabel.setText('Bin from Templates - basic analysis')

        self.showStatusbarWidgets()
        self.enableProcessingMenuItems(False)

        self.appendLogMessage(
            f"Thread : Started 'Bin from templates', using {self.survey.nShotPoints:,} shot points",
            MsgType.Binning,
        )

        self.thread = QThread()
        request = BinningFromTemplatesRequest(
            xmlString=self.survey.toXmlString(),
            extended=fullAnalysis,
            analysisFile=self.output.anaOutput,
            debugpyEnabled=self.appSettings.debugpy,
        )
        self.worker = BinningWorker(request)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.resultReady.connect(self.binningTemplatesThreadFinished)
        self.worker.finished.connect(self.thread.quit)

        self.startTime = timer()
        self.thread.start(QThread.Priority.NormalPriority)

    def binningTemplatesThreadFinished(self, result: BinningFromTemplatesResult):
        self.binningResultThreadFinished(result)

    def binningGeometryThreadFinished(self, result: BinningFromGeometryResult):
        self.binningResultThreadFinished(result)

    def binningResultThreadFinished(self, result):
        if not result.success:
            self.layoutImg = None
            self.layoutImItem = None
            self.handleImageSelection()

            self.appendLogMessage('Thread : . . . aborted binning operation', MsgType.Error)
            self.appendLogMessage(f'Thread : . . . {result.errorText}', MsgType.Error)
            QMessageBox.information(self, 'Interrupted', 'Worker thread aborted')
        else:
            self.output.binOutput = result.binOutput
            self.output.minOffset = result.minOffset
            self.output.maxOffset = result.maxOffset
            self.output.minimumFold = result.minimumFold
            self.output.maximumFold = result.maximumFold
            self.output.minMinOffset = result.minMinOffset
            self.output.maxMinOffset = result.maxMinOffset
            self.output.minMaxOffset = result.minMaxOffset
            self.output.maxMaxOffset = result.maxMaxOffset
            self.output.minRmsOffset = 0.0 if result.minRmsOffset is None else result.minRmsOffset
            self.output.maxRmsOffset = 0.0 if result.maxRmsOffset is None else result.maxRmsOffset
            self.output.rmsOffset = result.rmsOffset
            self.output.ofAziHist = result.ofAziHist
            self.output.offstHist = result.offstHist

            endTime = timer()
            elapsed = timedelta(seconds=endTime - self.startTime)
            elapsed = timedelta(seconds=ceil(elapsed.total_seconds()))

            self.appendLogMessage(f'Thread : Binning completed. Elapsed time:{elapsed} ', MsgType.Binning)
            self.appendLogMessage(
                f'Thread : . . . Fold&nbsp; &nbsp; &nbsp; &nbsp;: Min:{self.output.minimumFold} - Max:{self.output.maximumFold} ',
                MsgType.Binning,
            )
            self.appendLogMessage(
                f'Thread : . . . Min-offsets: Min:{self.output.minMinOffset:.2f}m - Max:{self.output.maxMinOffset:.2f}m ',
                MsgType.Binning,
            )
            self.appendLogMessage(
                f'Thread : . . . Max-offsets: Min:{self.output.minMaxOffset:.2f}m - Max:{self.output.maxMaxOffset:.2f}m ',
                MsgType.Binning,
            )
            if self.output.rmsOffset is not None:
                self.appendLogMessage(
                    f'Thread : . . . Rms-offsets: Min:{self.output.minRmsOffset:.2f}m - Max:{self.output.maxRmsOffset:.2f}m ',
                    MsgType.Binning,
                )

            if result.anaOutputShape is not None:
                self.finalizeAnalysisMemmap(result.anaOutputShape)

            if self.survey.grid.fold <= 0:
                self.survey.grid.fold = self.output.maximumFold
                plainText = self.survey.toXmlString()
                self.textEdit.setTextViaCursor(plainText)
                self.textEdit.document().setModified(True)

            if self.imageType == 0:
                self.actionFold.setChecked(True)
                self.imageType = 1

            self.survey.cmpTransform = result.cmpTransform
            self.handleImageSelection()

            if not self.fileName:
                self.textEdit.document().setModified(True)
                info = 'Analysis results are yet to be saved.'
            else:
                self.saveAnalysisSidecars(includeHistograms=True)
                info = 'Analysis results have been saved.'

            QMessageBox.information(self, 'Done', f'Worker thread completed. {info} ')

        self.updateMenuStatus(False)
        self.enableProcessingMenuItems()
        self.hideStatusbarWidgets()

    def binFromGeometry(self, fullAnalysis: bool):
        if self.srcGeom is None or self.relGeom is None or self.recGeom is None:
            self.appendLogMessage('Thread : One or more of the geometry files have not been defined', MsgType.Error)
            return

        if fullAnalysis:
            if not self.prepFullBinningConditions():
                return
            self.progressLabel.setText('Bin from Geometry - full analysis')
        else:
            self.progressLabel.setText('Bin from Geometry - basic analysis')

        self.showStatusbarWidgets()
        self.enableProcessingMenuItems(False)

        self.appendLogMessage(
            f"Thread : Started 'Bin from geometry', using {self.srcGeom.shape[0]:,} shot points",
            MsgType.Binning,
        )

        self.thread = QThread()
        request = BinningFromGeometryRequest(
            xmlString=self.survey.toXmlString(),
            srcGeom=self.srcGeom,
            relGeom=self.relGeom,
            recGeom=self.recGeom,
            extended=fullAnalysis,
            analysisFile=self.output.anaOutput,
            debugpyEnabled=self.appSettings.debugpy,
        )
        self.worker = BinFromGeometryWorker(request)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.resultReady.connect(self.binningGeometryThreadFinished)
        self.worker.finished.connect(self.thread.quit)

        self.startTime = timer()
        self.thread.start(QThread.Priority.NormalPriority)

    def binFromSps(self, fullAnalysis: bool):
        if self.spsImport is None or self.rpsImport is None:
            self.appendLogMessage('Thread : One or more of the sps files have not been defined', MsgType.Error)
            return

        if fullAnalysis:
            if not self.prepFullBinningConditions():
                return
            self.progressLabel.setText('Bin from imported SPS - full analysis')
        else:
            self.progressLabel.setText('Bin from imported SPS - basic analysis')

        self.showStatusbarWidgets()
        self.enableProcessingMenuItems(False)

        self.appendLogMessage(
            f"Thread : Started 'Bin from Imported SPS', using {self.spsImport.shape[0]:,} shot points",
            MsgType.Binning,
        )
        if self.xpsImport is None:
            self.appendLogMessage(
                'Thread : Relation file has not been defined; using all available receivers for each shot',
                MsgType.Binning,
            )

        self.thread = QThread()
        request = BinningFromGeometryRequest(
            xmlString=self.survey.toXmlString(),
            srcGeom=self.spsImport,
            relGeom=self.xpsImport,
            recGeom=self.rpsImport,
            extended=fullAnalysis,
            analysisFile=self.output.anaOutput,
            debugpyEnabled=self.appSettings.debugpy,
        )
        self.worker = BinFromGeometryWorker(request)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.resultReady.connect(self.binningGeometryThreadFinished)
        self.worker.finished.connect(self.thread.quit)

        self.startTime = timer()
        self.thread.start(QThread.Priority.NormalPriority)

    def createGeometryFromTemplates(self):
        self.progressLabel.setText('Create Geometry from Templates')

        self.showStatusbarWidgets()
        self.enableProcessingMenuItems(False)

        self.appendLogMessage(
            f"Thread : Started 'Create Geometry from Templates', from {self.survey.nShotPoints:,} shot points",
            MsgType.Geometry,
        )

        self.thread = QThread()
        request = GeometryFromTemplatesRequest(
            xmlString=self.survey.toXmlString(),
            debugpyEnabled=self.appSettings.debugpy,
            includeProfiling=self.appSettings.debug,
        )
        self.worker = GeometryWorker(request)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.resultReady.connect(self.geometryThreadFinished)
        self.worker.finished.connect(self.thread.quit)

        self.startTime = timer()
        self.thread.start(QThread.Priority.NormalPriority)

    def threadProgress(self, value: int):
        if self.progressBar is not None:
            self.progressBar.setValue(value)

    def threadMessage(self, text: str):
        if self.progressLabel is not None:
            self.progressLabel.setText(text)

    def stopWorkerThread(self):
        if self.thread is not None and self.thread.isRunning():
            self.thread.requestInterruption()

    def geometryThreadFinished(self, result: GeometryFromTemplatesResult):
        profiling = result.profiling
        if self.appSettings.debug:
            self.appendLogMessage('geometryFromTemplates() profiling information', MsgType.Debug)
            for i, _ in enumerate(profiling.timerTmin if profiling is not None else ()):
                tMin = profiling.timerTmin[i] * 1000.0 if profiling.timerTmin[i] != float('Inf') else 0.0
                tMax = profiling.timerTmax[i] * 1000.0
                tTot = profiling.timerTtot[i] * 1000.0
                freq = profiling.timerFreq[i]
                tAvr = tTot / freq if freq > 0 else 0.0
                message = f'{i:02d}: min:{tMin:011.3f}, max:{tMax:011.3f}, tot:{tTot:011.3f}, avr:{tAvr:011.3f}, freq:{freq:07d}'
                self.appendLogMessage(message, MsgType.Debug)

        if not result.success:
            self.appendLogMessage('Thread : . . . aborted geometry creation', MsgType.Error)
            self.appendLogMessage(f'Thread : . . . {result.errorText}', MsgType.Error)
            QMessageBox.information(self, 'Interrupted', 'Worker thread aborted')
        else:
            self.sessionService.setArray(self.sessionState, 'recGeom', result.recGeom)
            self.sessionService.setArray(self.sessionState, 'relGeom', result.relGeom)
            self.sessionService.setArray(self.sessionState, 'srcGeom', result.srcGeom)

            self.recModel.setData(self.recGeom)
            self.relModel.setData(self.relGeom)
            self.srcModel.setData(self.srcGeom)

            endTime = timer()
            elapsed = timedelta(seconds=endTime - self.startTime)
            elapsed = timedelta(seconds=ceil(elapsed.total_seconds()))

            self.appendLogMessage(
                f"Thread : Completed 'Create Geometry from Templates'. Elapsed time:{elapsed} ",
                MsgType.Geometry,
            )

            if not self.fileName:
                self.textEdit.document().setModified(True)
                info = 'Analysis results are yet to be saved.'
            else:
                self.saveSurveyDataSidecars()
                info = 'Analysis results have been saved.'
            QMessageBox.information(self, 'Done', f'Worker thread completed. {info} ')

        self.updateMenuStatus(False)
        self.enableProcessingMenuItems()
        self.mainTabWidget.setCurrentIndex(3)
        self.hideStatusbarWidgets()

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
