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

from . import config
from .enums_and_int_flags import MsgType
from .sps_io_and_qc import getAliveAndDead
from .worker_threads import (BinFromGeometryWorker, BinningWorker,
                             GeometryWorker)


class BinningWorkerMixin:
    """Keeps the binning/geometry worker-thread lifecycle outside RollMainWindow."""

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
        xmlString = self.survey.toXmlString()
        self.worker = BinningWorker(xmlString)
        self.worker.setExtended(fullAnalysis)
        self.worker.setMemMappedFile(self.output.anaOutput)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.finished.connect(self.binningThreadFinished)
        self.worker.finished.connect(self.thread.quit)

        self.startTime = timer()
        self.thread.start(QThread.Priority.NormalPriority)

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
        xmlString = self.survey.toXmlString()
        self.worker = BinFromGeometryWorker(xmlString)
        self.worker.setExtended(fullAnalysis)
        self.worker.setMemMappedFile(self.output.anaOutput)
        self.worker.setGeometryArrays(self.srcGeom, self.relGeom, self.recGeom)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.finished.connect(self.binningThreadFinished)
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
        xmlString = self.survey.toXmlString()
        self.worker = BinFromGeometryWorker(xmlString)
        self.worker.setExtended(fullAnalysis)
        self.worker.setMemMappedFile(self.output.anaOutput)
        self.worker.setGeometryArrays(self.spsImport, self.xpsImport, self.rpsImport)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.finished.connect(self.binningThreadFinished)
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
        xmlString = self.survey.toXmlString()
        self.worker = GeometryWorker(xmlString)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.survey.progress.connect(self.threadProgress)
        self.worker.survey.message.connect(self.threadMessage)
        self.worker.finished.connect(self.geometryThreadFinished)
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

    def binningThreadFinished(self, success: bool):
        if not success:
            self.layoutImg = None
            self.layoutImItem = None
            self.handleImageSelection()

            self.appendLogMessage('Thread : . . . aborted binning operation', MsgType.Error)
            self.appendLogMessage(f'Thread : . . . {self.worker.survey.errorText}', MsgType.Error)
            QMessageBox.information(self, 'Interrupted', 'Worker thread aborted')
        else:
            self.output.binOutput = self.worker.survey.output.binOutput.copy()
            self.output.minOffset = self.worker.survey.output.minOffset.copy()
            self.output.maxOffset = self.worker.survey.output.maxOffset.copy()

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

            if self.worker.survey.output.anaOutput is not None:
                self.output.rmsOffset = self.worker.survey.output.rmsOffset.copy()
                self.output.ofAziHist = self.worker.survey.output.ofAziHist.copy()
                self.output.offstHist = self.worker.survey.output.offstHist.copy()

                anaFileName = self.fileName + '.ana.npy'
                shape = self.worker.survey.output.anaOutput.shape
                self.output.anaOutput = np.memmap(anaFileName, dtype=np.float32, mode='r', shape=shape)
                self.output.D2_Output = self.output.anaOutput.reshape(shape[0] * shape[1] * shape[2], shape[3])
                self.setDataAnaTableModel()

            self.output.minimumFold = max(self.worker.survey.output.minimumFold, 0)
            self.output.maximumFold = max(self.worker.survey.output.maximumFold, 0)
            self.output.minMinOffset = max(self.worker.survey.output.minMinOffset, 0)
            self.output.maxMinOffset = max(self.worker.survey.output.maxMinOffset, 0)
            self.output.minMaxOffset = max(self.worker.survey.output.minMaxOffset, 0)
            self.output.maxMaxOffset = max(self.worker.survey.output.maxMaxOffset, 0)
            self.output.minRmsOffset = max(self.worker.survey.output.minRmsOffset, 0)
            self.output.maxRmsOffset = max(self.worker.survey.output.maxRmsOffset, 0)

            if self.survey.grid.fold <= 0:
                self.survey.grid.fold = self.output.maximumFold
                plainText = self.survey.toXmlString()
                self.textEdit.setTextViaCursor(plainText)
                self.textEdit.document().setModified(True)

            if self.imageType == 0:
                self.actionFold.setChecked(True)
                self.imageType = 1

            if self.imageType == 1:
                self.layoutImg = self.output.binOutput
                self.layoutMax = self.output.maximumFold
                label = 'fold'
            elif self.imageType == 2:
                self.layoutImg = self.output.minOffset
                self.layoutMax = self.output.maxMinOffset
                label = 'minimum offset'
            elif self.imageType == 3:
                self.layoutImg = self.output.maxOffset
                self.layoutMax = self.output.maxMaxOffset
                label = 'maximum offset'
            elif self.imageType == 4:
                self.layoutImg = self.output.rmsOffset
                self.layoutMax = self.output.maxRmsOffset
                label = 'rms delta-offset'
            else:
                raise NotImplementedError('selected analysis type currently not implemented.')

            self.layoutImItem = pg.ImageItem()
            self.layoutImItem.setImage(self.layoutImg, levels=(0.0, self.layoutMax))
            self.survey.cmpTransform = self.worker.survey.cmpTransform

            if self.layoutColorBar is None:
                self.layoutColorBar = self.layoutWidget.plotItem.addColorBar(
                    self.layoutImItem,
                    colorMap=config.fold_OffCmap,
                    label=label,
                    limits=(0, None),
                    rounding=10.0,
                    values=(0.0, self.layoutMax),
                )
            else:
                self.layoutColorBar.setImageItem(self.layoutImItem)
                self.layoutColorBar.setLevels(low=0.0, high=self.layoutMax)
                self.layoutColorBar.setColorMap(config.fold_OffCmap)
                self.setColorbarLabel(label)

            self.plotLayout()

            if not self.fileName:
                self.textEdit.document().setModified(True)
                info = 'Analysis results are yet to be saved.'
            else:
                np.save(self.fileName + '.bin.npy', self.output.binOutput)
                np.save(self.fileName + '.min.npy', self.output.minOffset)
                np.save(self.fileName + '.max.npy', self.output.maxOffset)
                if self.output.rmsOffset is not None:
                    np.save(self.fileName + '.rms.npy', self.output.rmsOffset)
                info = 'Analysis results have been saved.'

            QMessageBox.information(self, 'Done', f'Worker thread completed. {info} ')

        self.updateMenuStatus(False)
        self.enableProcessingMenuItems()
        self.hideStatusbarWidgets()

    def geometryThreadFinished(self, success: bool):
        if config.debug:
            self.appendLogMessage('geometryFromTemplates() profiling information', MsgType.Debug)
            for i, _ in enumerate(self.worker.survey.timerTmin):
                tMin = self.worker.survey.timerTmin[i] * 1000.0 if self.worker.survey.timerTmin[i] != float('Inf') else 0.0
                tMax = self.worker.survey.timerTmax[i] * 1000.0
                tTot = self.worker.survey.timerTtot[i] * 1000.0
                freq = self.worker.survey.timerFreq[i]
                tAvr = tTot / freq if freq > 0 else 0.0
                message = f'{i:02d}: min:{tMin:011.3f}, max:{tMax:011.3f}, tot:{tTot:011.3f}, avr:{tAvr:011.3f}, freq:{freq:07d}'
                self.appendLogMessage(message, MsgType.Debug)

        if not success:
            self.appendLogMessage('Thread : . . . aborted geometry creation', MsgType.Error)
            self.appendLogMessage(f'Thread : . . . {self.worker.survey.errorText}', MsgType.Error)
            QMessageBox.information(self, 'Interrupted', 'Worker thread aborted')
        else:
            self.recGeom = self.worker.survey.output.recGeom.copy()
            self.relGeom = self.worker.survey.output.relGeom.copy()
            self.srcGeom = self.worker.survey.output.srcGeom.copy()

            self.recModel.setData(self.recGeom)
            self.relModel.setData(self.relGeom)
            self.srcModel.setData(self.srcGeom)

            self.recLiveE, self.recLiveN, self.recDeadE, self.recDeadN = getAliveAndDead(self.recGeom)
            self.srcLiveE, self.srcLiveN, self.srcDeadE, self.srcDeadN = getAliveAndDead(self.srcGeom)

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
                np.save(self.fileName + '.rec.npy', self.recGeom)
                np.save(self.fileName + '.rel.npy', self.relGeom)
                np.save(self.fileName + '.src.npy', self.srcGeom)
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
