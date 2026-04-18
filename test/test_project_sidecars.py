# coding=utf-8
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QEvent, QRectF
from qgis.PyQt.QtWidgets import QAction

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey, getQgisApp, writeMinimalProjectFixture

QGIS_APP, _, IFACE, _ = getQgisApp()

rollMainWindowModule = loadPluginModule('roll_main_window')
rollSurveyModule = loadPluginModule('roll_survey')
settingsModule = loadPluginModule('settings')
spsImportDialogModule = loadPluginModule('sps_import_dialog')
spsModule = loadPluginModule('sps_io_and_qc')
configModule = loadPluginModule('config')
appSettingsModule = loadPluginModule('app_settings')
auxFunctionsModule = loadPluginModule('aux_functions')
workerThreadsModule = loadPluginModule('worker_threads')
binningWorkerMixinModule = loadPluginModule('binning_worker_mixin')
workerOperationControllerModule = loadPluginModule('worker_operation_controller')
printPresentationControllerModule = loadPluginModule('print_presentation_controller')

RollMainWindow = rollMainWindowModule.RollMainWindow
RollSurvey = rollSurveyModule.RollSurvey
readSettings = settingsModule.readSettings
writeSettings = settingsModule.writeSettings
SpsImportDialog = spsImportDialogModule.SpsImportDialog
pntType1 = spsModule.pntType1
pntType4 = spsModule.pntType4
relType2 = spsModule.relType2
config = configModule
myPrint = auxFunctionsModule.myPrint
isDebugLoggingEnabled = appSettingsModule.isDebugLoggingEnabled
isShowSummariesEnabled = appSettingsModule.isShowSummariesEnabled
isShowUnfinishedEnabled = appSettingsModule.isShowUnfinishedEnabled
readStoredDebugSetting = appSettingsModule.readStoredDebugSetting
readStoredDebugpySetting = appSettingsModule.readStoredDebugpySetting
readStoredShowSummariesSetting = appSettingsModule.readStoredShowSummariesSetting
readStoredShowUnfinishedSetting = appSettingsModule.readStoredShowUnfinishedSetting
setActiveDebugLogging = appSettingsModule.setActiveDebugLogging
setActiveShowSummaries = appSettingsModule.setActiveShowSummaries
setActiveShowUnfinished = appSettingsModule.setActiveShowUnfinished
BinningFromTemplatesRequest = workerThreadsModule.BinningFromTemplatesRequest
BinningFromTemplatesResult = workerThreadsModule.BinningFromTemplatesResult
BinningFromGeometryRequest = workerThreadsModule.BinningFromGeometryRequest
BinningFromGeometryResult = workerThreadsModule.BinningFromGeometryResult
GeometryFromTemplatesRequest = workerThreadsModule.GeometryFromTemplatesRequest
GeometryProfilingPayload = workerThreadsModule.GeometryProfilingPayload
GeometryFromTemplatesResult = workerThreadsModule.GeometryFromTemplatesResult
BinningWorker = workerThreadsModule.BinningWorker
BinFromGeometryWorker = workerThreadsModule.BinFromGeometryWorker
GeometryWorker = workerThreadsModule.GeometryWorker


class ProjectSidecarsTest(unittest.TestCase):
    def setUp(self):
        self.mainWindow = RollMainWindow(IFACE, standaloneMode=True)

    def tearDown(self):
        if self.mainWindow is not None:
            self.mainWindow.textEdit.document().setModified(False)
            self.mainWindow.close()
            self.mainWindow.deleteLater()
        self.mainWindow = None

    def createSurvey(self):
        return createTestSurvey('Phase0-Sidecars', QRectF(0.0, 0.0, 100.0, 50.0))

    def writeProjectFixture(self, folder):
        return writeMinimalProjectFixture(folder, 'phase0_sidecars.roll', survey=self.createSurvey())

    def testMinimalProjectFixtureLoadsSurveyAndAnalysisSidecars(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = writeMinimalProjectFixture(
                tempDir,
                'phase0_minimal_fixture.roll',
                survey=self.createSurvey(),
                includeSurveySidecars=True,
                includeAnalysisSidecars=True,
                includeHistograms=True,
            )

            success = self.mainWindow.fileLoad(projectPath)

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.rpsImport.shape[0], 1)
        self.assertEqual(self.mainWindow.spsImport.shape[0], 1)
        self.assertEqual(self.mainWindow.recGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.srcGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.relGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.xpsImport.shape[0], 1)
        self.assertIsNotNone(self.mainWindow.output.binOutput)
        self.assertIsNotNone(self.mainWindow.output.minOffset)
        self.assertIsNotNone(self.mainWindow.output.maxOffset)
        self.assertIsNotNone(self.mainWindow.output.rmsOffset)
        self.assertIsNotNone(self.mainWindow.output.offstHist)
        self.assertIsNotNone(self.mainWindow.output.ofAziHist)

    def testFileLoadIgnoresFoldSidecarWithWrongDimensions(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            np.save(projectPath + '.bin.npy', np.ones((3, 4), dtype=np.float32))

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIsNone(self.mainWindow.output.binOutput)
            self.assertEqual(self.mainWindow.imageType, 0)

    def testFileLoadLoadsFoldSidecarWithExpectedDimensions(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            expected = np.arange(50, dtype=np.float32).reshape(10, 5)
            np.save(projectPath + '.bin.npy', expected)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIsNotNone(self.mainWindow.output.binOutput)
            self.assertEqual(self.mainWindow.output.binOutput.shape, expected.shape)
            self.assertEqual(self.mainWindow.output.maximumFold, expected.max())
            self.assertEqual(self.mainWindow.imageType, 1)

    def testFileLoadLoadsSurveySidecarsAndRebuildsPointState(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            rpsImport = np.zeros(2, dtype=pntType1)
            rpsImport[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0)
            rpsImport[1] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 1, 0.0, 0.0)

            spsImport = np.zeros(1, dtype=pntType1)
            spsImport[0] = (200.0, 20.0, 1, 'BB', 0.0, 1100.0, 2100.0, 0.0, 1, 1, 1, 0.0, 0.0)

            recGeom = np.zeros(1, dtype=pntType1)
            recGeom[0] = (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0)

            srcGeom = np.zeros(1, dtype=pntType1)
            srcGeom[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 1, 1, 1, 0.0, 0.0)

            xpsImport = np.zeros(1, dtype=relType2)
            xpsImport[0] = (200.0, 20.0, 1, 1, 100.0, 10.0, 11.0, 1, 1, 1, 1)

            relGeom = np.zeros(1, dtype=relType2)
            relGeom[0] = (400.0, 40.0, 1, 1, 300.0, 30.0, 31.0, 1, 1, 1, 1)

            self.mainWindow.projectService.saveSurveyDataSidecars(
                projectPath,
                rpsImport=rpsImport,
                spsImport=spsImport,
                xpsImport=xpsImport,
                recGeom=recGeom,
                relGeom=relGeom,
                srcGeom=srcGeom,
            )

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.rpsImport.shape[0], 2)
            self.assertEqual(self.mainWindow.spsImport.shape[0], 1)
            self.assertEqual(self.mainWindow.recGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.srcGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.relGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.xpsImport.shape[0], 1)
            self.assertIs(self.mainWindow.sessionState.rpsImport, self.mainWindow.rpsImport)
            self.assertIs(self.mainWindow.sessionState.spsImport, self.mainWindow.spsImport)
            self.assertIs(self.mainWindow.sessionState.xpsImport, self.mainWindow.xpsImport)
            self.assertIs(self.mainWindow.sessionState.recGeom, self.mainWindow.recGeom)
            self.assertIs(self.mainWindow.sessionState.srcGeom, self.mainWindow.srcGeom)
            self.assertIs(self.mainWindow.sessionState.relGeom, self.mainWindow.relGeom)
            self.assertTrue(self.mainWindow.actionRpsPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionSpsPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionRecPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionSrcPoints.isEnabled())
            self.assertEqual(self.mainWindow.rpsLiveE.shape[0], 2)
            self.assertEqual(self.mainWindow.spsLiveE.shape[0], 1)
            self.assertEqual(self.mainWindow.recLiveE.shape[0], 1)
            self.assertEqual(self.mainWindow.srcLiveE.shape[0], 1)
            self.assertIsNotNone(self.mainWindow.rpsBound)
            self.assertIsNotNone(self.mainWindow.spsBound)

    def testFileLoadNormalizesLegacyPointSidecarsWithoutInUse(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            legacyRps = np.zeros(1, dtype=pntType4)
            legacyRps[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 100, 12, 30, 0, 0)

            legacySrc = np.zeros(1, dtype=pntType4)
            legacySrc[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 100, 12, 30, 0, 0)

            np.save(projectPath + '.rps.npy', legacyRps)
            np.save(projectPath + '.src.npy', legacySrc)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIn('InUse', self.mainWindow.rpsImport.dtype.names)
            self.assertIn('InUse', self.mainWindow.srcGeom.dtype.names)
            self.assertEqual(self.mainWindow.rpsImport['InUse'].tolist(), [1])
            self.assertEqual(self.mainWindow.srcGeom['InUse'].tolist(), [1])

    def testResetNumpyArraysAndModelsClearsSurveyArraysFromSessionState(self):
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)

        self.mainWindow.resetNumpyArraysAndModels()

        self.assertIsNone(self.mainWindow.sessionState.rpsImport)
        self.assertIsNone(self.mainWindow.sessionState.spsImport)
        self.assertIsNone(self.mainWindow.sessionState.xpsImport)
        self.assertIsNone(self.mainWindow.sessionState.recGeom)
        self.assertIsNone(self.mainWindow.sessionState.srcGeom)
        self.assertIsNone(self.mainWindow.sessionState.relGeom)

    def testSessionBackedArrayPropertiesRefreshDerivedState(self):
        rpsImport = np.array(
            [
                (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0),
                (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 0, 0.0, 0.0),
            ],
            dtype=pntType1,
        )
        recGeom = np.array(
            [
                (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0),
                (301.0, 31.0, 1, 'CC', 0.0, 1210.0, 2210.0, 0.0, 1, 1, 0, 0.0, 0.0),
            ],
            dtype=pntType1,
        )

        self.mainWindow.rpsImport = rpsImport
        self.mainWindow.recGeom = recGeom

        self.assertIs(self.mainWindow.sessionState.rpsImport, rpsImport)
        self.assertIs(self.mainWindow.sessionState.recGeom, recGeom)
        self.assertEqual(self.mainWindow.rpsLiveE.tolist(), [1000.0])
        self.assertEqual(self.mainWindow.rpsDeadE.tolist(), [1010.0])
        self.assertEqual(self.mainWindow.recLiveE.tolist(), [1200.0])
        self.assertEqual(self.mainWindow.recDeadE.tolist(), [1210.0])
        self.assertIsNotNone(self.mainWindow.rpsBound)

    def testFileOpenRecentRemovesMissingFileFromRecentList(self):
        with tempfile.TemporaryDirectory() as tempDir:
            missingProjectPath = os.path.join(tempDir, 'missing.roll')
            self.mainWindow.recentFileList = [missingProjectPath]

            action = self.mainWindow.recentFileActions[0]
            self.assertIsInstance(action, QAction)
            action.setData(missingProjectPath)
            action.setVisible(True)

            action.trigger()

            self.assertEqual(self.mainWindow.recentFileList, [])
            self.assertFalse(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [])

    def testFileOpenRecentLoadsExistingFile(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.recentFileList = [projectPath]
            self.mainWindow.updateRecentFileActions()

            action = self.mainWindow.recentFileActions[0]
            self.assertIsInstance(action, QAction)
            self.assertTrue(action.isVisible())

            action.trigger()

            self.assertEqual(self.mainWindow.fileName, projectPath)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.recentFileList[0], projectPath)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [projectPath])

    def testFileLoadPersistsRecentFileList(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.recentFileList[0], projectPath)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', [])[0], projectPath)

    def testFileLoadReadFailurePreservesProjectDirectory(self):
        originalProjectDirectory = self.mainWindow.projectDirectory

        with patch.object(self.mainWindow.projectService, 'readProjectText', return_value=MagicMock(success=False, errorText='read failure')):
            success = self.mainWindow.fileLoad(os.path.join('D:\\', 'missing', 'broken.roll'))

        self.assertFalse(success)
        self.assertEqual(self.mainWindow.projectDirectory, originalProjectDirectory)

    def testSaveAnalysisSidecarsWritesHistogramFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath

            self.mainWindow.output.binOutput = np.arange(50, dtype=np.float32).reshape(10, 5)
            self.mainWindow.output.minOffset = np.full((10, 5), 100.0, dtype=np.float32)
            self.mainWindow.output.maxOffset = np.full((10, 5), 250.0, dtype=np.float32)
            self.mainWindow.output.rmsOffset = np.full((10, 5), 175.0, dtype=np.float32)
            self.mainWindow.output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
            self.mainWindow.output.ofAziHist = np.ones((360 // 5, 4), dtype=np.float32)

            success = self.mainWindow.saveAnalysisSidecars(includeHistograms=True)

            self.assertTrue(success)
            np.testing.assert_array_equal(np.load(projectPath + '.off.npy'), self.mainWindow.output.offstHist)
            np.testing.assert_array_equal(np.load(projectPath + '.azi.npy'), self.mainWindow.output.ofAziHist)

    def testOffAziDisplayMethodDefaultsToRectangular(self):
        self.assertTrue(self.mainWindow.actionOffAziRectangular.isChecked())
        self.assertFalse(self.mainWindow.actionOffAziPolar.isChecked())

    def testPlotOffAziUsesSelectedDisplayMethod(self):
        self.mainWindow.output.ofAziHist = np.ones((360 // 5, 4), dtype=np.float32)
        self.mainWindow.output.maxMaxOffset = 400.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.actionOffAziRectangular.setChecked(True)
                self.mainWindow.plotOffAzi()

        renderRectangular.assert_called_once()
        renderPolar.assert_not_called()

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.actionOffAziPolar.setChecked(True)
                self.mainWindow.plotOffAzi()

        renderPolar.assert_called_once()
        renderRectangular.assert_not_called()

    def testPlotOffAziDelegatesToRedrawOffAzi(self):
        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.plotOffAzi()

        redrawOffAzi.assert_called_once()

    def testPlotOffsetDelegatesToRedrawOffset(self):
        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.plotOffset()

        redrawOffset.assert_called_once()

    def testRedrawOffsetUsesPreparedInputs(self):
        plotInputs = {
            'xValues': np.array([0.0, 50.0, 100.0], dtype=np.float32),
            'yValues': np.array([1.0, 2.0], dtype=np.float32),
            'plotTitle': 'Offset Histogram [4 traces]',
        }

        with patch.object(self.mainWindow, 'prepareOffsetPlotInputs', return_value=plotInputs) as prepareHelper:
            with patch.object(self.mainWindow, 'renderPreparedOffsetPlot') as renderPrepared:
                with patch.object(self.mainWindow.offsetWidget, 'setTitle') as setTitle:
                    self.mainWindow.redrawOffset()

        prepareHelper.assert_called_once()
        renderPrepared.assert_called_once_with(plotInputs)
        setTitle.assert_called_once_with(plotInputs['plotTitle'], color='b', size='16pt')

    def testPrepareOffsetPlotInputsUsesHistogramHelper(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        histogramInputs = {
            'histogram': histogram,
            'count': 4,
        }

        with patch.object(self.mainWindow, 'prepareOffsetHistogramInputs', return_value=histogramInputs) as histogramHelper:
            plotInputs = self.mainWindow.prepareOffsetPlotInputs()

        histogramHelper.assert_called_once()
        np.testing.assert_array_equal(plotInputs['xValues'], histogram[0, :])
        np.testing.assert_array_equal(plotInputs['yValues'], histogram[1, :-1])
        self.assertEqual(plotInputs['plotTitle'], f'{self.mainWindow.plotTitles[8]} [4 traces]')

    def testRenderPreparedOffsetPlotUpdatesWidget(self):
        plotInputs = {
            'xValues': np.array([0.0, 50.0, 100.0], dtype=np.float32),
            'yValues': np.array([1.0, 2.0], dtype=np.float32),
        }

        with patch.object(self.mainWindow.offsetWidget.plotItem, 'clear') as clearPlot:
            with patch.object(self.mainWindow.offsetWidget, 'plot') as plotHistogram:
                self.mainWindow.renderPreparedOffsetPlot(plotInputs)

        clearPlot.assert_called_once()
        plotHistogram.assert_called_once()
        self.assertIs(plotHistogram.call_args.args[0], plotInputs['xValues'])
        self.assertIs(plotHistogram.call_args.args[1], plotInputs['yValues'])
        self.assertEqual(plotHistogram.call_args.kwargs['stepMode'], 'center')
        self.assertEqual(plotHistogram.call_args.kwargs['fillLevel'], 0)
        self.assertTrue(plotHistogram.call_args.kwargs['fillOutline'])
        self.assertEqual(plotHistogram.call_args.kwargs['brush'], (0, 0, 255, 150))
        self.assertIsNotNone(plotHistogram.call_args.kwargs['pen'])

    def testRedrawOffAziUsesPreparedInputs(self):
        plotInputs = {
            'displayHistogram': np.ones((2, 2), dtype=np.float32),
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'colorMapObj': object(),
            'count': 4,
            'isPolar': False,
            'modeText': 'rectangular',
            'plotTitle': 'Offset/Azimuth [4 traces, rectangular]',
        }

        with patch.object(self.mainWindow, 'prepareOffAziPlotInputs', return_value=plotInputs) as prepareHelper:
            with patch.object(self.mainWindow, 'renderPreparedOffAziPlot') as renderPrepared:
                with patch.object(self.mainWindow.offAziWidget, 'setTitle') as setTitle:
                    self.mainWindow.actionOffAziRectangular.setChecked(True)
                    self.mainWindow.redrawOffAzi()

        prepareHelper.assert_called_once()
        renderPrepared.assert_called_once_with(plotInputs)
        setTitle.assert_called_once_with(plotInputs['plotTitle'], color='b', size='16pt')

    def testPrepareOffAziPlotInputsUsesHistogramHelper(self):
        histogram = np.full((2, 2), 2000.0, dtype=np.float32)
        histogramInputs = {
            'histogram': histogram,
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'count': 4,
        }

        with patch.object(self.mainWindow, 'prepareOffAziHistogramInputs', return_value=histogramInputs) as histogramHelper:
            with patch.object(self.mainWindow, 'resolveColorMapObject', return_value='viridis-map') as colorMapHelper:
                self.mainWindow.actionOffAziRectangular.setChecked(True)
                plotInputs = self.mainWindow.prepareOffAziPlotInputs()

        histogramHelper.assert_called_once()
        colorMapHelper.assert_called_once_with(self.mainWindow.appSettings.analysisCmap, fallback='viridis')
        np.testing.assert_array_equal(plotInputs['displayHistogram'], histogram / 1000.0)
        self.assertFalse(plotInputs['isPolar'])
        self.assertEqual(plotInputs['plotTitle'], f"{self.mainWindow.plotTitles[9]} [4 traces, rectangular]")

    def testRenderPreparedOffAziPlotUsesPolarRendererWhenRequested(self):
        plotInputs = {
            'displayHistogram': np.ones((2, 2), dtype=np.float32),
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'colorMapObj': object(),
            'isPolar': True,
        }

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.renderPreparedOffAziPlot(plotInputs)

        renderPolar.assert_called_once_with(plotInputs['displayHistogram'], 5.0, 100.0, 500.0, plotInputs['colorMapObj'])
        renderRectangular.assert_not_called()

    def testFileLoadResetsOffAziDisplayLevelsToDefaultRange(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            projectPath = self.writeProjectFixture(tmpDir)

            self.mainWindow.offAziColorBar = MagicMock()
            self.mainWindow.offAziColorBar.levels.return_value = (1.5, 2.5)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.mainWindow.output.ofAziHist = np.full((360 // 5, 4), 5000.0, dtype=np.float32)
            self.mainWindow.output.maxMaxOffset = 400.0
            self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
            self.mainWindow.actionOffAziRectangular.setChecked(True)

            with patch.object(self.mainWindow, 'updateOffAziColorBar') as updateColorBar:
                self.mainWindow.plotOffAzi()

        updateColorBar.assert_called_once()
        _, levelLow, levelHigh = updateColorBar.call_args.args
        self.assertEqual(levelLow, 0.0)
        self.assertEqual(levelHigh, 5.0)

    def testPrepareAnalysisImageAndColorBarStoresImageAndColorBar(self):
        imageData = np.ones((2, 3), dtype=np.float32)

        imageItem = self.mainWindow.prepareAnalysisImageAndColorBar(
            self.mainWindow.stkTrkWidget,
            imageData,
            10.0,
            20.0,
            5.0,
            2.5,
            'stkTrkImItem',
            'stkTrkColorBar',
        )

        self.assertIs(self.mainWindow.stkTrkImItem, imageItem)
        self.assertIsNotNone(self.mainWindow.stkTrkColorBar)

    def testPrepareLayoutImageAndColorBarStoresImageAndColorBar(self):
        imageData = np.ones((2, 3), dtype=np.float32)

        imageItem = self.mainWindow.prepareLayoutImageAndColorBar(
            imageData,
            'CET-L4',
            'fold',
            levels=(0.0, 12.0),
        )

        self.assertIs(self.mainWindow.layoutImItem, imageItem)
        self.assertIsNotNone(self.mainWindow.layoutColorBar)

    def testHandleImageSelectionUsesLayoutImageHelper(self):
        self.mainWindow.imageType = 1
        self.mainWindow.output.binOutput = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.output.maximumFold = 8

        with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar') as layoutHelper:
            with patch.object(self.mainWindow, 'plotLayout') as plotLayout:
                self.mainWindow.handleImageSelection()

        layoutHelper.assert_called_once()
        self.assertIs(layoutHelper.call_args.args[0], self.mainWindow.layoutImg)
        self.assertEqual(layoutHelper.call_args.args[2], 'fold')
        self.assertEqual(layoutHelper.call_args.kwargs['levels'], (0.0, 8))
        plotLayout.assert_called_once()

    def testDispatchAnalysisRedrawRoutesPatternsToPlotPatterns(self):
        with patch.object(self.mainWindow, 'plotPatterns') as plotPatterns:
            self.mainWindow.dispatchAnalysisRedraw('patterns', rollMainWindowModule.AnalysisRedrawReason.controller)

        plotPatterns.assert_called_once()

    def testDispatchAnalysisRedrawInvalidatesPatternResponseOnSelectionChange(self):
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((1, 2))

        with patch.object(self.mainWindow, 'plotPatterns') as plotPatterns:
            self.mainWindow.dispatchAnalysisRedraw('patterns', rollMainWindowModule.AnalysisRedrawReason.patternSelectionChanged)

        self.assertIsNone(self.mainWindow.xyPatResp)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.patternResponseKey)
        plotPatterns.assert_called_once()

    def testDispatchAnalysisRedrawRoutesOffAziToRedrawOffAzi(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.output.ofAziHist)
        redrawOffAzi.assert_called_once()

    def testDispatchAnalysisRedrawKeepsOffAziHistogramForDisplayModeChange(self):
        histogram = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = histogram

        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

        self.assertIs(self.mainWindow.output.ofAziHist, histogram)
        redrawOffAzi.assert_called_once()

    def testDispatchAnalysisRedrawOffAziPresentationReasonSkipsHistogramRecompute(self):
        histogram = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.ofAziHist = histogram
        self.mainWindow.output.maxMaxOffset = 400.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.actionOffAziPolar.setChecked(True)

        with patch.object(rollMainWindowModule.fnb, 'numbaSliceStats') as sliceStats:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
                    self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

        sliceStats.assert_not_called()
        self.assertIs(self.mainWindow.output.ofAziHist, histogram)
        renderPolar.assert_called_once()
        renderRectangular.assert_not_called()

    def testDispatchAnalysisRedrawRoutesOffsetToRedrawOffset(self):
        self.mainWindow.output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)

        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.output.offstHist)
        redrawOffset.assert_called_once()

    def testDispatchAnalysisRedrawKeepsOffsetHistogramForVisibleActivation(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        self.mainWindow.output.offstHist = histogram

        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

        self.assertIs(self.mainWindow.output.offstHist, histogram)
        redrawOffset.assert_called_once()

    def testDispatchAnalysisRedrawOffsetVisibleActivationReusesHistogramButControllerRecomputes(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.offstHist = histogram
        self.mainWindow.output.maxMaxOffset = 100.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.anaOutput = np.ones((1, 1, 1, 12), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSliceStats', return_value=(np.array([10.0, 20.0], dtype=np.float32), np.array([0.0, 0.0], dtype=np.float32), False)) as sliceStats:
            with patch.object(self.mainWindow, 'renderPreparedOffsetPlot') as renderPrepared:
                with patch.object(self.mainWindow.offsetWidget, 'setTitle'):
                    self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

                    self.assertIs(self.mainWindow.output.offstHist, histogram)
                    sliceStats.assert_not_called()

                    self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.controller)

        sliceStats.assert_called_once_with(self.mainWindow.output.anaOutput, self.mainWindow.survey.unique.apply)
        self.assertIsNot(self.mainWindow.output.offstHist, histogram)
        self.assertEqual(renderPrepared.call_count, 2)

    def testDispatchAnalysisRedrawRoutesStackInlineUsingContext(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context) as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-inline', rollMainWindowModule.AnalysisRedrawReason.controller)

        contextHelper.assert_called_once()
        redrawStackResponse.assert_called_once_with('stack-inline', context)

    def testDispatchAnalysisRedrawInvalidatesStackInlineCacheOnControllerReason(self):
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(3)
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context):
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-inline', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.inlineStk)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.inlineStkKey)
        redrawStackResponse.assert_called_once_with('stack-inline', context)

    def testDispatchAnalysisRedrawSkipsStackInlineForHorizontalMovement(self):
        with patch.object(self.mainWindow, 'getStackResponseRedrawContext') as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-inline',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Rt,
                )

        contextHelper.assert_not_called()
        redrawStackResponse.assert_not_called()

    def testDispatchAnalysisRedrawSkipsStackXlineForVerticalMovement(self):
        with patch.object(self.mainWindow, 'getStackResponseRedrawContext') as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-xline',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Up,
                )

        contextHelper.assert_not_called()
        redrawStackResponse.assert_not_called()

    def testDispatchAnalysisRedrawKeepsStackCellResponsiveInBothDirections(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context) as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-cell',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Up,
                )

        contextHelper.assert_called_once()
        redrawStackResponse.assert_called_once_with('stack-cell', context)

    def testDispatchAnalysisRedrawInvalidatesStackCellCacheOnPatternChange(self):
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((2, 3, True, 1, 2), 7)
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context):
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-cell', rollMainWindowModule.AnalysisRedrawReason.stackPatternChanged)

        self.assertIsNone(self.mainWindow.xyCellStk)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellResponseKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellFold)
        redrawStackResponse.assert_called_once_with('stack-cell', context)

    def testRedrawStackResponseRoutesStackInlineToPlotMethod(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'plotStkTrk') as plotStkTrk:
            self.mainWindow.redrawStackResponse('stack-inline', context)

        plotStkTrk.assert_called_once_with(3, 200.0, 25.0, 10.0)

    def testOnPattern1IndexChangedUsesAnalysisDispatcher(self):
        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onPattern1IndexChanged()

        dispatcher.assert_called_once_with('patterns', rollMainWindowModule.AnalysisRedrawReason.patternSelectionChanged)

    def testOnOffAziDisplayMethodChangedUsesAnalysisDispatcher(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onOffAziDisplayMethodChanged()

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

    def testOnOffAziColorBarLevelsChangedUsesPresentationReasonInPolarMode(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.actionOffAziPolar.setChecked(True)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onOffAziColorBarLevelsChanged()

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziColorBarLevelsChanged)

    def testGetVisiblePlotIndexMapsPatternResponseWidget(self):
        self.assertEqual(self.mainWindow.getVisiblePlotIndex(self.mainWindow.arraysWidget), 10)

    def testGetVisiblePlotWidgetReturnsFirstVisiblePlot(self):
        with patch.object(self.mainWindow.layoutWidget, 'isVisible', return_value=False):
            with patch.object(self.mainWindow.offTrkWidget, 'isVisible', return_value=True):
                plotWidget, index = self.mainWindow.getVisiblePlotWidget()

        self.assertIs(plotWidget, self.mainWindow.offTrkWidget)
        self.assertEqual(index, 1)

    def testUpdateVisiblePlotWidgetRoutesOffsetInlineUsingDerivedContext(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'plotOffTrk') as plotOffTrk:
            self.mainWindow.updateVisiblePlotWidget(1)

        plotOffTrk.assert_called_once()
        self.assertEqual(plotOffTrk.call_args[0][0], 1)
        self.assertEqual(plotOffTrk.call_args[0][2], 5.0)

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForStackInline(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(5, direction=rollMainWindowModule.Direction.Up)

        dispatcher.assert_called_once_with(
            'stack-inline',
            rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated,
            direction=rollMainWindowModule.Direction.Up,
        )

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForOffAzi(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(9)

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForOffset(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(8)

        dispatcher.assert_called_once_with('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

    def testEventFilterSyncsToolbarStateForVisiblePlot(self):
        self.mainWindow.offTrkWidget.showGrid(x=False, y=False)
        self.mainWindow.offTrkWidget.setAspectLocked(False)
        self.mainWindow.offTrkWidget.getViewBox().setMouseMode(pg.ViewBox.RectMode)

        with patch.object(self.mainWindow, 'updateVisiblePlotWidget') as updater:
            handled = self.mainWindow.eventFilter(self.mainWindow.offTrkWidget, QEvent(QEvent.Type.Show))

        self.assertTrue(handled)
        self.assertTrue(self.mainWindow.actionZoomAll.isEnabled())
        self.assertTrue(self.mainWindow.actionZoomRect.isEnabled())
        self.assertTrue(self.mainWindow.actionAspectRatio.isEnabled())
        self.assertTrue(self.mainWindow.actionAntiAlias.isEnabled())
        self.assertFalse(self.mainWindow.actionRuler.isEnabled())
        self.assertFalse(self.mainWindow.actionProjected.isEnabled())
        self.assertFalse(self.mainWindow.actionPlotGridX.isChecked())
        self.assertFalse(self.mainWindow.actionPlotGridY.isChecked())
        self.assertFalse(self.mainWindow.actionAspectRatio.isChecked())
        self.assertTrue(self.mainWindow.actionZoomRect.isChecked())
        updater.assert_called_once_with(1)

    def testEventFilterDisablesPlotToolbarActionsForNonPlotWidget(self):
        self.mainWindow.actionZoomAll.setEnabled(True)
        self.mainWindow.actionZoomRect.setEnabled(True)
        self.mainWindow.actionAspectRatio.setEnabled(True)
        self.mainWindow.actionAntiAlias.setEnabled(True)
        self.mainWindow.actionRuler.setEnabled(True)
        self.mainWindow.actionProjected.setEnabled(True)

        handled = self.mainWindow.eventFilter(self.mainWindow.tabGeom, QEvent(QEvent.Type.Show))

        self.assertTrue(handled)
        self.assertFalse(self.mainWindow.actionZoomAll.isEnabled())
        self.assertFalse(self.mainWindow.actionZoomRect.isEnabled())
        self.assertFalse(self.mainWindow.actionAspectRatio.isEnabled())
        self.assertFalse(self.mainWindow.actionAntiAlias.isEnabled())
        self.assertFalse(self.mainWindow.actionRuler.isEnabled())
        self.assertFalse(self.mainWindow.actionProjected.isEnabled())

    def testPlotZoomRectTogglesMouseModeOnVisiblePlot(self):
        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.offTrkWidget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

            self.mainWindow.plotZoomRect()
            self.assertEqual(self.mainWindow.offTrkWidget.getViewBox().getState()['mouseMode'], pg.ViewBox.RectMode)

            self.mainWindow.plotZoomRect()
            self.assertEqual(self.mainWindow.offTrkWidget.getViewBox().getState()['mouseMode'], pg.ViewBox.PanMode)

    def testPlotAntiAliasTogglesStoredStateForVisiblePlot(self):
        self.mainWindow.antiA[1] = False

        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.plotAntiAlias()
            self.assertTrue(self.mainWindow.antiA[1])

            self.mainWindow.plotAntiAlias()
            self.assertFalse(self.mainWindow.antiA[1])

    def testPlotGridActionsToggleVisiblePlotGridState(self):
        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.offTrkWidget.showGrid(x=True, y=True, alpha=0.75)

            self.mainWindow.plotGridX()
            self.mainWindow.plotGridY()

            state = self.mainWindow.offTrkWidget.getPlotItem().saveState()
            self.assertFalse(state['xGridCheck'])
            self.assertFalse(state['yGridCheck'])

    def testUpdateMenuStatusResetsAnalysisAndSyncsRepresentativeActions(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.fileName = 'example.roll'
        self.mainWindow.imageType = 4

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            self.mainWindow.updateMenuStatus(True)

        handleImageSelection.assert_called_once()
        self.assertEqual(self.mainWindow.imageType, 0)
        self.assertTrue(self.mainWindow.actionExportFoldMap.isEnabled())
        self.assertTrue(self.mainWindow.actionExportRecAsCsv.isEnabled())
        self.assertTrue(self.mainWindow.actionExportAreasToQGIS.isEnabled())
        self.assertTrue(self.mainWindow.actionMoveLt.isEnabled())
        self.assertFalse(self.mainWindow.actionSrcPoints.isEnabled())

    def testEnableProcessingMenuItemsUsesAvailableInputs(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertTrue(self.mainWindow.actionBasicBinFromTemplates.isEnabled())
        self.assertTrue(self.mainWindow.actionFullBinFromGeometry.isEnabled())
        self.assertTrue(self.mainWindow.actionFullBinFromSps.isEnabled())
        self.assertFalse(self.mainWindow.actionStopThread.isEnabled())

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=0):
            self.mainWindow.enableProcessingMenuItems(False)

        self.assertFalse(self.mainWindow.actionBasicBinFromTemplates.isEnabled())
        self.assertFalse(self.mainWindow.actionFullBinFromGeometry.isEnabled())
        self.assertFalse(self.mainWindow.actionFullBinFromSps.isEnabled())
        self.assertTrue(self.mainWindow.actionStopThread.isEnabled())

    def testCopyFallsBackToPlotClipboardWhenFocusCopyUnavailable(self):
        with patch.object(self.mainWindow.actionStateController, 'invokeFocusMethod', return_value=False) as invokeFocusMethod:
            with patch.object(self.mainWindow.actionStateController, 'copyPlotWidgetToClipboard', return_value=True) as copyPlotWidgetToClipboard:
                with patch.object(self.mainWindow.actionStateController, 'clipboardHasText', return_value=True):
                    self.mainWindow.copy()

        invokeFocusMethod.assert_called_once_with('copy')
        copyPlotWidgetToClipboard.assert_called_once_with()
        self.assertTrue(self.mainWindow.actionPaste.isEnabled())

    def testGrabPlotWidgetForPrintReturnsActiveAnalysisPlot(self):
        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.analysisTabWidget):
            with patch.object(self.mainWindow.analysisTabWidget, 'currentWidget', return_value=self.mainWindow.offTrkWidget):
                plotWidget = self.mainWindow._grabPlotWidgetForPrint()

        self.assertIs(plotWidget, self.mainWindow.offTrkWidget)

    def testFilePrintDelegatesToPrintPresentationController(self):
        with patch.object(self.mainWindow.printPresentationController, 'filePrint') as filePrint:
            self.mainWindow.filePrint()

        filePrint.assert_called_once_with()

    def testPrintPreviewPrintsXmlWhenXmlTabIsActive(self):
        printer = MagicMock()

        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.textEdit):
            with patch.object(self.mainWindow.textEdit, 'print') as textPrint:
                self.mainWindow.printPreview(printer)

        textPrint.assert_called_once_with(printer)

    def testPrintPreviewUsesPlotBranchWhenActivePlotExists(self):
        printer = MagicMock()

        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.tabGeom):
            with patch.object(self.mainWindow, '_grabPlotWidgetForPrint', return_value=self.mainWindow.offTrkWidget):
                with patch.object(self.mainWindow.printPresentationController, '_printPlotWidget') as printPlotWidget:
                    self.mainWindow.printPreview(printer)

        printPlotWidget.assert_called_once_with(printer, self.mainWindow.offTrkWidget)

    def testFilePrintPdfAppendsPdfSuffixBeforePrinting(self):
        printer = MagicMock()
        qprinterFactory = MagicMock(return_value=printer)
        qprinterFactory.PrinterMode = MagicMock(HighResolution='high-resolution')
        qprinterFactory.OutputFormat = MagicMock(PdfFormat='pdf-format')
        document = MagicMock()

        with patch.object(printPresentationControllerModule.QFileDialog, 'getSaveFileName', return_value=('report', 'PDF files (*.pdf)')):
            with patch.object(printPresentationControllerModule, 'QPrinter', qprinterFactory):
                with patch.object(self.mainWindow.textEdit, 'document', return_value=document):
                    self.mainWindow.filePrintPdf()

        qprinterFactory.assert_called_once_with(qprinterFactory.PrinterMode.HighResolution)
        printer.setOutputFormat.assert_called_once_with(qprinterFactory.OutputFormat.PdfFormat)
        printer.setOutputFileName.assert_called_once_with('report.pdf')
        document.print.assert_called_once_with(printer)


    def testPlotStkTrkUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 1, 1, 1), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D', return_value=(np.ones((2, 1, 1), dtype=np.float32), np.array([0, 1], dtype=np.int32))):
            with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D', return_value=np.ones((3, 4), dtype=np.float32)):
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkTrk(0, 1000, 25.0, 10.0)

        helper.assert_called_once()
        self.assertEqual(helper.call_args[0][6], 'stkTrkImItem')
        self.assertEqual(helper.call_args[0][7], 'stkTrkColorBar')

    def testPlotStkTrkReusesCachedResponseWhenLineIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 1, 1, 1), dtype=np.float32)
        cached = np.full((3, 4), -8.0, dtype=np.float32)
        self.mainWindow.inlineStk = cached
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(0)

        with patch.object(self.mainWindow.plotRedrawHelper, 'buildInlineStackAxisValues', return_value=(0.15, 0.05, -25.0, 50.0)) as axisHelper:
            with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D') as sliceHelper:
                with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D') as computeHelper:
                    with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                        self.mainWindow.plotStkTrk(0, 1000, 25.0, 10.0)

        axisHelper.assert_called_once_with(self.mainWindow)
        sliceHelper.assert_not_called()
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotStkBinUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 2, 1, 1), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D', return_value=(np.ones((2, 1, 1), dtype=np.float32), np.array([0, 1], dtype=np.int32))):
            with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D', return_value=np.ones((3, 4), dtype=np.float32)):
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkBin(0, 1000, 25.0, 10.0)

        helper.assert_called_once()
        self.assertEqual(helper.call_args[0][6], 'stkBinImItem')
        self.assertEqual(helper.call_args[0][7], 'stkBinColorBar')

    def testPlotStkBinReusesCachedResponseWhenStakeIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 2, 1, 1), dtype=np.float32)
        cached = np.full((3, 4), -7.0, dtype=np.float32)
        self.mainWindow.x0lineStk = cached
        self.mainWindow.plotRedrawHelper.storeXlineResponseKey(0)

        with patch.object(self.mainWindow.plotRedrawHelper, 'buildXlineStackAxisValues', return_value=(0.15, 0.05, -25.0, 50.0)) as axisHelper:
            with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D') as sliceHelper:
                with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D') as computeHelper:
                    with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                        self.mainWindow.plotStkBin(0, 1000, 25.0, 10.0)

        axisHelper.assert_called_once_with(self.mainWindow)
        sliceHelper.assert_not_called()
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotStkCelUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 1, 1, 1), dtype=np.float32)
        expected = np.ones((3, 3), dtype=np.float32)
        selectedPatterns = (object(), object())

        with patch.object(self.mainWindow, 'getSelectedStackCellPatterns', return_value=selectedPatterns) as selectionHelper:
            with patch.object(self.mainWindow, 'computeStackCellResponse', return_value=(expected, 25.0, 10.0, 7)) as computeHelper:
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkCel(0, 0, 1000, 1000)

        selectionHelper.assert_called_once()
        computeHelper.assert_called_once_with(0, 0, selectedPatterns[0], selectedPatterns[1])
        helper.assert_called_once()
        self.assertIs(self.mainWindow.xyCellStk, expected)
        self.assertIs(helper.call_args[0][1], expected)
        self.assertEqual(helper.call_args[0][6], 'stkCelImItem')
        self.assertEqual(helper.call_args[0][7], 'stkCelColorBar')

    def testPlotStkCelReusesCachedResponseWhenCellAndPatternsAreUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 1, 1, 1), dtype=np.float32)
        cached = np.full((3, 3), -6.0, dtype=np.float32)
        selectedPatterns = (object(), object())

        self.mainWindow.xyCellStk = cached
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((0, 0, False, 0, 0), 9)

        with patch.object(self.mainWindow, 'getSelectedStackCellPatterns', return_value=selectedPatterns) as selectionHelper:
            with patch.object(self.mainWindow.plotRedrawHelper, 'buildStackCellResponseKey', return_value=(0, 0, False, 0, 0)) as keyHelper:
                with patch.object(self.mainWindow.plotRedrawHelper, 'buildStackCellCachedAxisValues', return_value=(25.0, 10.0, 9)) as axisHelper:
                    with patch.object(self.mainWindow, 'computeStackCellResponse') as computeHelper:
                        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                            self.mainWindow.plotStkCel(0, 0, 1000, 1000)

        selectionHelper.assert_called_once()
        keyHelper.assert_called_once_with(self.mainWindow, 0, 0)
        axisHelper.assert_called_once_with(self.mainWindow)
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotPatternsUsesSharedAnalysisImageHelperInKxKyMode(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.patternLayout = False
        expected = np.full((3, 3), -12.5, dtype=np.float32)
        selectedPatterns = (object(), object())
        selectedTexts = ('Pattern A', 'Pattern B')

        with patch.object(self.mainWindow, 'getSelectedPatternInputs', return_value=(selectedPatterns[0], selectedPatterns[1], selectedTexts[0], selectedTexts[1])) as selectionHelper:
            with patch.object(self.mainWindow, 'computeKxyPatternResponse', return_value=(expected, 25.0, 10.0)) as computeHelper:
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as imageHelper:
                    self.mainWindow.plotPatterns()

        selectionHelper.assert_called_once()
        computeHelper.assert_called_once()
        self.assertIs(computeHelper.call_args[0][0], selectedPatterns[0])
        self.assertIs(computeHelper.call_args[0][1], selectedPatterns[1])
        imageHelper.assert_called_once()
        self.assertIs(self.mainWindow.xyPatResp, expected)
        self.assertIs(imageHelper.call_args[0][1], expected)
        self.assertEqual(imageHelper.call_args[0][6], 'kxyPatImItem')
        self.assertEqual(imageHelper.call_args[0][7], 'kxyPatColorBar')

    def testPlotPatternsReusesCachedResponseWhenSelectionIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.patternLayout = False
        cachedResponse = np.full((3, 3), -9.0, dtype=np.float32)
        selectedPatterns = (object(), object())
        selectedTexts = ('Pattern A', 'Pattern B')

        self.mainWindow.xyPatResp = cachedResponse
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((1, 2))

        with patch.object(self.mainWindow, 'getSelectedPatternInputs', return_value=(selectedPatterns[0], selectedPatterns[1], selectedTexts[0], selectedTexts[1])) as selectionHelper:
            with patch.object(self.mainWindow.plotRedrawHelper, 'buildPatternResponseKey', return_value=(1, 2)) as keyHelper:
                with patch.object(self.mainWindow.plotRedrawHelper, 'buildPatternAxisValues', return_value=(25.0, 10.0)) as axisHelper:
                    with patch.object(self.mainWindow, 'computeKxyPatternResponse') as computeHelper:
                        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as imageHelper:
                            self.mainWindow.plotPatterns()

        selectionHelper.assert_called_once()
        keyHelper.assert_called_once_with(self.mainWindow)
        axisHelper.assert_called_once_with(self.mainWindow)
        computeHelper.assert_not_called()
        imageHelper.assert_called_once()
        self.assertIs(imageHelper.call_args[0][1], cachedResponse)

    def testOnStackPatternIndexChangedUsesAnalysisDispatcher(self):
        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onStackPatternIndexChanged()

        dispatcher.assert_called_once_with('stack-cell', rollMainWindowModule.AnalysisRedrawReason.stackPatternChanged)

    def testFinalizeAnalysisMemmapRefreshesTimestampAndReopensFile(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            anaPath = projectPath + '.ana.npy'
            shape = (2, 2, 1, 13)
            oldTimestamp = 1_700_000_000

            self.mainWindow.fileName = projectPath
            self.mainWindow.output.anaOutput = np.memmap(anaPath, dtype=np.float32, mode='w+', shape=shape)
            self.mainWindow.output.anaOutput.fill(7.0)
            self.mainWindow.output.an2Output = self.mainWindow.output.anaOutput.reshape(shape[0] * shape[1] * shape[2], shape[3])
            os.utime(anaPath, (oldTimestamp, oldTimestamp))

            success = self.mainWindow.finalizeAnalysisMemmap(shape)

            self.assertTrue(success)
            self.assertIsNotNone(self.mainWindow.output.anaOutput)
            self.assertEqual(self.mainWindow.output.an2Output.shape, (4, 13))
            self.assertGreater(os.path.getmtime(anaPath), oldTimestamp)

            self.mainWindow.resetAnaTableModel()

    def testSaveSurveyDataSidecarsWritesGeometryFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath

            self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.recGeom[0] = (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0)
            self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.srcGeom[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 1, 1, 1, 0.0, 0.0)
            self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
            self.mainWindow.relGeom[0] = (400.0, 40.0, 1, 1, 300.0, 30.0, 31.0, 1, 1, 1, 1)

            success = self.mainWindow.saveSurveyDataSidecars()

            self.assertTrue(success)
            np.testing.assert_array_equal(np.load(projectPath + '.rec.npy'), self.mainWindow.recGeom)
            np.testing.assert_array_equal(np.load(projectPath + '.rel.npy'), self.mainWindow.relGeom)
            np.testing.assert_array_equal(np.load(projectPath + '.src.npy'), self.mainWindow.srcGeom)

    def testFileOpenRecentUsesSameOpenGuardsAsFileOpen(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.recentFileList = [projectPath]
            self.mainWindow.updateRecentFileActions()

            action = self.mainWindow.recentFileActions[0]

            with patch.object(self.mainWindow, 'maybeKillThread', return_value=False) as maybeKillThread:
                with patch.object(self.mainWindow, 'maybeSave', return_value=True) as maybeSave:
                    with patch.object(self.mainWindow, 'fileLoad', return_value=True) as fileLoad:
                        action.trigger()

            maybeKillThread.assert_called_once()
            maybeSave.assert_not_called()
            fileLoad.assert_not_called()

    def testUpdateRecentFileActionsPrunesMissingFilesAutomatically(self):
        with tempfile.TemporaryDirectory() as tempDir:
            existingProjectPath = self.writeProjectFixture(tempDir)
            missingProjectPath = os.path.join(tempDir, 'missing.roll')

            self.mainWindow.recentFileList = [missingProjectPath, existingProjectPath]
            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [existingProjectPath])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), existingProjectPath)
            self.assertFalse(self.mainWindow.recentFileActions[1].isVisible())
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [existingProjectPath])

    def testReadSettingsNormalizesSingleRecentFileString(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            self.mainWindow.settings.setValue('settings/recentFileList', projectPath)
            self.mainWindow.recentFileList = []

            readSettings(self.mainWindow)
            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [projectPath])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), projectPath)

    def testSettingsUseRuntimeAndAppStateOwners(self):
        with tempfile.TemporaryDirectory() as tempDir:
            importDir = os.path.join(tempDir, 'imports')
            os.makedirs(importDir)
            projectPath = self.writeProjectFixture(tempDir)

            self.mainWindow.settings.setValue('settings/projectDirectory', tempDir)
            self.mainWindow.settings.setValue('settings/importDirectory', importDir)
            self.mainWindow.settings.setValue('settings/recentFileList', [projectPath])
            self.mainWindow.settings.setValue('settings/sps/spsDialect', 'SEG rev2.1')
            self.mainWindow.settings.setValue('settings/colors/analysisCmap', 'CET-L5')

            readSettings(self.mainWindow)

            self.assertEqual(self.mainWindow.runtimeState.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.runtimeState.importDirectory, importDir)
            self.assertEqual(self.mainWindow.importDirectory, importDir)
            self.assertEqual(self.mainWindow.runtimeState.recentFileList, [projectPath])
            self.assertEqual(self.mainWindow.recentFileList, [projectPath])
            self.assertEqual(self.mainWindow.appSettings.spsDialect, 'SEG rev2.1')
            self.assertEqual(self.mainWindow.appSettings.analysisCmap, 'CET-L5')

            self.mainWindow.appSettings.useRelativePaths = False
            self.mainWindow.appSettings.spsDialect = 'New Zealand'
            self.mainWindow.projectDirectory = tempDir
            self.mainWindow.importDirectory = importDir
            self.mainWindow.recentFileList = [projectPath]

            writeSettings(self.mainWindow)

            self.assertFalse(self.mainWindow.settings.value('settings/misc/useRelativePaths', True, type=bool))
            self.assertEqual(self.mainWindow.settings.value('settings/projectDirectory', ''), tempDir)
            self.assertEqual(self.mainWindow.settings.value('settings/importDirectory', ''), importDir)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [projectPath])
            self.assertEqual(self.mainWindow.settings.value('settings/sps/spsDialect', ''), 'New Zealand')

    def testReadSettingsRestoresSavedWindowState(self):
        geometryState = b'geometry-bytes'
        windowState = b'window-state-bytes'

        self.mainWindow.settings.setValue('mainWindow/geometry', geometryState)
        self.mainWindow.settings.setValue('mainWindow/state', windowState)

        with patch.object(self.mainWindow, 'restoreGeometry') as restoreGeometry:
            with patch.object(self.mainWindow, 'restoreState') as restoreState:
                readSettings(self.mainWindow)

        restoreGeometry.assert_called_once_with(geometryState)
        restoreState.assert_called_once_with(windowState)

    def testSpsImportDialogUsesAppSettingsAsFormatOwner(self):
        self.mainWindow.appSettings.spsDialect = 'New Zealand'

        dialog = SpsImportDialog(self.mainWindow, self.mainWindow.survey.crs, self.mainWindow.importDirectory)
        try:
            self.assertEqual(dialog.spsFormatList.currentItem().text(), 'New Zealand')

            dialog.spsFormatList.setCurrentRow(0)
            dialog.spsCombo.setCurrentIndex(1)
            dialog.onSpsComboHighlighted(1)

            originalFromColumn = self.mainWindow.appSettings.spsFormatList[0]['line'][0]
            dialog.spsFromSpin.setValue(originalFromColumn + 2)

            self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['line'][0], originalFromColumn + 1)

            dialog.spsFormatList.setCurrentRow(1)
            dialog.accepted()

            self.assertEqual(self.mainWindow.appSettings.spsDialect, dialog.spsFormatList.currentItem().text())
        finally:
            dialog.close()
            dialog.deleteLater()

    def testSpsImportDialogResetUsesBuiltInDefaultsNotLiveConfigLists(self):
        self.mainWindow.appSettings.spsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.xpsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.rpsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.spsDialect = 'Broken'

        dialog = SpsImportDialog(self.mainWindow, self.mainWindow.survey.crs, self.mainWindow.importDirectory)
        try:
            with patch.object(spsImportDialogModule.QMessageBox, 'question', return_value=spsImportDialogModule.QMessageBox.StandardButton.Yes):
                dialog.onResetSpsDatabase()

            self.assertNotIn('Broken', [entry['name'] for entry in self.mainWindow.appSettings.spsFormatList])
            self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['name'], config.getDefaultSpsFormats()[0]['name'])
        finally:
            dialog.close()
            dialog.deleteLater()

    def testReadSettingsResetsInvalidStoredSpsFormatsToBuiltInDefaults(self):
        self.mainWindow.settings.beginGroup('settings/sps/spsFormatList')
        self.mainWindow.settings.setValue('Broken', '{"name": "Broken"}')
        self.mainWindow.settings.endGroup()
        self.mainWindow.settings.beginGroup('settings/sps/xpsFormatList')
        self.mainWindow.settings.remove('')
        self.mainWindow.settings.endGroup()
        self.mainWindow.settings.beginGroup('settings/sps/rpsFormatList')
        self.mainWindow.settings.remove('')
        self.mainWindow.settings.endGroup()

        self.mainWindow.appSettings.spsDialect = 'Broken'
        readSettings(self.mainWindow)

        self.assertNotIn('Broken', [entry['name'] for entry in self.mainWindow.appSettings.spsFormatList])
        self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['name'], config.getDefaultSpsFormats()[0]['name'])

    def testExportSpsAndSrcToQgisUseAppSettingsParallelFlag(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.appSettings.spsParallel = True

        with patch.object(rollMainWindowModule, 'exportPointLayerToQgis', return_value=object()) as exportPointLayer:
            self.mainWindow.exportSpsToQgis()
            self.mainWindow.exportSrcToQgis()

        self.assertEqual(exportPointLayer.call_count, 2)
        self.assertTrue(exportPointLayer.call_args_list[0].kwargs['spsParallel'])
        self.assertTrue(exportPointLayer.call_args_list[1].kwargs['spsParallel'])

    def testFileSaveUsesAppSettingsRelativePathFlag(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath
            self.mainWindow.survey = self.createSurvey()
            self.mainWindow.appSettings.useRelativePaths = False

            with patch.object(self.mainWindow.projectService, 'writeProjectXml') as writeProjectXml:
                writeProjectXml.return_value = type('WriteResult', (), {'success': True, 'errorText': ''})()
                with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars'):
                    with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars'):
                        self.mainWindow.fileSave()

            self.assertFalse(writeProjectXml.call_args.args[3])

    def testAppendLogMessageUsesAppSettingsDebugFlag(self):
        self.mainWindow.appSettings.debug = False
        originalText = self.mainWindow.logEdit.toPlainText()

        self.mainWindow.appendLogMessage('hidden-debug-message', rollMainWindowModule.MsgType.Debug)

        self.assertEqual(self.mainWindow.logEdit.toPlainText(), originalText)

        self.mainWindow.appSettings.debug = True
        self.mainWindow.appendLogMessage('visible-debug-message', rollMainWindowModule.MsgType.Debug)

        self.assertIn('visible-debug-message', self.mainWindow.logEdit.toPlainText())

    def testActivateUpdatesActiveDebugLogging(self):
        self.mainWindow.appSettings.debug = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isDebugLoggingEnabled())

        self.mainWindow.appSettings.debug = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isDebugLoggingEnabled())

    def testMyPrintUsesActiveDebugLoggingSetting(self):
        with patch('builtins.print') as mockPrint:
            setActiveDebugLogging(False)
            myPrint('hidden-debug-print')
            mockPrint.assert_not_called()

            setActiveDebugLogging(True)
            myPrint('visible-debug-print')
            mockPrint.assert_called_once_with('visible-debug-print')

    def testActivateUpdatesActiveShowSummaries(self):
        self.mainWindow.appSettings.showSummaries = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isShowSummariesEnabled())

        self.mainWindow.appSettings.showSummaries = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isShowSummariesEnabled())

    def testActivateUpdatesActiveShowUnfinished(self):
        self.mainWindow.appSettings.showUnfinished = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isShowUnfinishedEnabled())

        self.mainWindow.appSettings.showUnfinished = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isShowUnfinishedEnabled())

    def testBinFromTemplatesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.nShotPoints = 12

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinningWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromTemplates(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromTemplatesRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_called_once_with(threadStub.deleteLater)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinningWorkerRunEmitsTypedResultsOnSuccessAndFailure(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.anaOutput = None
                self.output.binOutput = np.ones((2, 2), dtype=np.float32)
                self.output.minOffset = np.full((2, 2), 10.0, dtype=np.float32)
                self.output.maxOffset = np.full((2, 2), 20.0, dtype=np.float32)
                self.output.minimumFold = 1
                self.output.maximumFold = 4
                self.output.minMinOffset = 10.0
                self.output.maxMinOffset = 10.0
                self.output.minMaxOffset = 20.0
                self.output.maxMaxOffset = 20.0
                self.output.minRmsOffset = 0.0
                self.output.maxRmsOffset = 0.0
                self.output.rmsOffset = None
                self.output.ofAziHist = None
                self.output.offstHist = None
                self.cmpTransform = 'cmp-transform'
                self.errorText = 'setup failed'
                self.shouldSucceed = True
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False
                self.extended: bool | None = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupBinFromTemplates(self, extended):
                self.extended = extended
                return self.shouldSucceed

        request = BinningFromTemplatesRequest(xmlString='<survey />', extended=True, analysisFile=None, debugpyEnabled=False)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = BinningWorker(request)

            resultEvents = []
            finishedEvents = []
            worker.resultReady.connect(resultEvents.append)
            worker.finished.connect(lambda: finishedEvents.append('finished'))

            worker.run()

            self.assertEqual(len(resultEvents), 1)
            self.assertIsInstance(resultEvents[0], BinningFromTemplatesResult)
            self.assertTrue(resultEvents[0].success)
            self.assertIs(resultEvents[0].binOutput, worker.survey.output.binOutput)
            self.assertIs(resultEvents[0].minOffset, worker.survey.output.minOffset)
            self.assertIs(resultEvents[0].maxOffset, worker.survey.output.maxOffset)
            self.assertIsNone(resultEvents[0].minRmsOffset)
            self.assertIsNone(resultEvents[0].maxRmsOffset)
            np.testing.assert_array_equal(resultEvents[0].binOutput, np.ones((2, 2), dtype=np.float32))
            self.assertEqual(resultEvents[0].cmpTransform, 'cmp-transform')
            self.assertEqual(finishedEvents, ['finished'])

            worker.survey.shouldSucceed = False
            resultEvents.clear()
            finishedEvents.clear()

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertIsInstance(resultEvents[0], BinningFromTemplatesResult)
        self.assertFalse(resultEvents[0].success)
        self.assertEqual(resultEvents[0].errorText, 'setup failed')
        self.assertEqual(finishedEvents, ['finished'])

    def testBinningTemplatesThreadFinishedUsesResultObject(self):
        result = BinningFromTemplatesResult(
            success=True,
            binOutput=np.ones((2, 2), dtype=np.float32),
            minOffset=np.full((2, 2), 10.0, dtype=np.float32),
            maxOffset=np.full((2, 2), 20.0, dtype=np.float32),
            minimumFold=1,
            maximumFold=4,
            minMinOffset=10.0,
            maxMinOffset=10.0,
            minMaxOffset=20.0,
            maxMaxOffset=20.0,
            minRmsOffset=0.0,
            maxRmsOffset=0.0,
            rmsOffset=None,
            ofAziHist=None,
            offstHist=None,
            cmpTransform='cmp-transform',
            anaOutputShape=None,
        )

        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.imageType = 1
        self.mainWindow.fileName = ''
        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningTemplatesThreadFinished(result)

        np.testing.assert_array_equal(self.mainWindow.output.binOutput, result.binOutput)
        np.testing.assert_array_equal(self.mainWindow.output.minOffset, result.minOffset)
        np.testing.assert_array_equal(self.mainWindow.output.maxOffset, result.maxOffset)
        self.assertEqual(self.mainWindow.output.maximumFold, 4)
        self.assertEqual(self.mainWindow.survey.cmpTransform, 'cmp-transform')
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testBinningTemplatesThreadFinishedHandlesFailureResult(self):
        result = BinningFromTemplatesResult(success=False, errorText='worker failed')

        self.mainWindow.layoutImg = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.layoutImItem = object()
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningTemplatesThreadFinished(result)

        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        appendLogMessage.assert_any_call('Thread : . . . aborted binning operation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testApplyPropertyChangesResetsAnalysisCachesWhenBinAreaChanges(self):
        self.mainWindow.fileName = os.path.join(tempfile.gettempdir(), 'phase0_refresh.roll')
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.x0lineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(3)
        self.mainWindow.plotRedrawHelper.storeXlineResponseKey(4)
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((1, 2, False, 0, 0), 5)
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((6, 7))
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.minOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.maxOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.rmsOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.offstHist = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.binAreaChanged = True

        with patch.object(self.mainWindow, 'setPlottingDetails'):
            with patch.object(self.mainWindow, 'resetAnaTableModel', return_value=False):
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'updatePatternList'):
                            with patch.object(self.mainWindow, 'plotLayout'):
                                self.mainWindow.applyPropertyChanges()

        self.assertFalse(self.mainWindow.binAreaChanged)
        self.assertIsNone(self.mainWindow.inlineStk)
        self.assertIsNone(self.mainWindow.x0lineStk)
        self.assertIsNone(self.mainWindow.xyCellStk)
        self.assertIsNone(self.mainWindow.xyPatResp)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.inlineStkKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.xlineStkKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellResponseKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellFold)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.patternResponseKey)
        self.assertIsNone(self.mainWindow.output.binOutput)
        self.assertIsNone(self.mainWindow.output.minOffset)
        self.assertIsNone(self.mainWindow.output.maxOffset)
        self.assertIsNone(self.mainWindow.output.rmsOffset)
        self.assertIsNone(self.mainWindow.output.ofAziHist)
        self.assertIsNone(self.mainWindow.output.offstHist)
        updateMenuStatus.assert_called_once_with(True)
        enableProcessingMenuItems.assert_called_once_with(True)

    def testResetSurveyPropertiesUsesSurveyDeepcopyForWorkingCopy(self):
        survey = self.createSurvey()
        surveyCopy = survey.deepcopy()
        self.mainWindow.survey = survey

        with patch.object(self.mainWindow.survey, 'deepcopy', return_value=surveyCopy) as deepcopy:
            with patch.object(self.mainWindow, 'updatePatternList') as updatePatternList:
                self.mainWindow.resetSurveyProperties()

        deepcopy.assert_called_once_with()
        updatePatternList.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesKeepsAnalysisCachesWhenBinAreaUnchanged(self):
        self.mainWindow.fileName = os.path.join(tempfile.gettempdir(), 'phase0_keep_caches.roll')
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.x0lineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.minOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.maxOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.rmsOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.offstHist = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.binAreaChanged = False

        with patch.object(self.mainWindow, 'setPlottingDetails'):
            with patch.object(self.mainWindow, 'resetAnaTableModel', return_value=False) as resetAnaTableModel:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'updatePatternList'):
                            with patch.object(self.mainWindow, 'plotLayout'):
                                self.mainWindow.applyPropertyChanges()

        resetAnaTableModel.assert_not_called()
        self.assertFalse(self.mainWindow.binAreaChanged)
        self.assertIsNotNone(self.mainWindow.inlineStk)
        self.assertIsNotNone(self.mainWindow.x0lineStk)
        self.assertIsNotNone(self.mainWindow.xyCellStk)
        self.assertIsNotNone(self.mainWindow.xyPatResp)
        self.assertIsNotNone(self.mainWindow.output.binOutput)
        self.assertIsNotNone(self.mainWindow.output.minOffset)
        self.assertIsNotNone(self.mainWindow.output.maxOffset)
        self.assertIsNotNone(self.mainWindow.output.rmsOffset)
        self.assertIsNotNone(self.mainWindow.output.ofAziHist)
        self.assertIsNotNone(self.mainWindow.output.offstHist)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)

    def testBinFromGeometryUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinFromGeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromGeometry(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromGeometryRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertIs(request.srcGeom, self.mainWindow.srcGeom)
        self.assertIs(request.relGeom, self.mainWindow.relGeom)
        self.assertIs(request.recGeom, self.mainWindow.recGeom)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_called_once_with(threadStub.deleteLater)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinFromSpsUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinFromGeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromSps(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromGeometryRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertIs(request.srcGeom, self.mainWindow.spsImport)
        self.assertIs(request.relGeom, self.mainWindow.xpsImport)
        self.assertIs(request.recGeom, self.mainWindow.rpsImport)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_called_once_with(threadStub.deleteLater)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinFromGeometryWorkerRunEmitsTypedResultsOnSuccessAndFailure(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.anaOutput = np.zeros((3, 2), dtype=np.float32)
                self.output.srcGeom = None
                self.output.relGeom = None
                self.output.recGeom = None
                self.output.binOutput = np.full((2, 2), 5.0, dtype=np.float32)
                self.output.minOffset = np.full((2, 2), 12.0, dtype=np.float32)
                self.output.maxOffset = np.full((2, 2), 24.0, dtype=np.float32)
                self.output.minimumFold = 2
                self.output.maximumFold = 5
                self.output.minMinOffset = 12.0
                self.output.maxMinOffset = 12.0
                self.output.minMaxOffset = 24.0
                self.output.maxMaxOffset = 24.0
                self.output.minRmsOffset = 0.0
                self.output.maxRmsOffset = 0.0
                self.output.rmsOffset = None
                self.output.ofAziHist = np.ones((2, 3), dtype=np.float32)
                self.output.offstHist = np.array([[0.0, 50.0], [1.0, 2.0]], dtype=np.float32)
                self.cmpTransform = 'cmp-transform'
                self.errorText = 'geometry failed'
                self.shouldSucceed = True
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False
                self.extended: bool | None = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupBinFromGeometry(self, extended):
                self.extended = extended
                return self.shouldSucceed

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        request = BinningFromGeometryRequest(
            xmlString='<survey />',
            srcGeom=srcGeom,
            relGeom=relGeom,
            recGeom=recGeom,
            extended=True,
            analysisFile=np.zeros((3, 2), dtype=np.float32),
            debugpyEnabled=False,
        )

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = BinFromGeometryWorker(request)

            resultEvents = []
            finishedEvents = []
            worker.resultReady.connect(resultEvents.append)
            worker.finished.connect(lambda: finishedEvents.append('finished'))

            worker.run()

            self.assertEqual(worker.survey.xmlString, '<survey />')
            self.assertTrue(worker.survey.createArrays)
            self.assertIs(worker.survey.output.srcGeom, srcGeom)
            self.assertIs(worker.survey.output.relGeom, relGeom)
            self.assertIs(worker.survey.output.recGeom, recGeom)
            self.assertTrue(worker.survey.calcCalled)
            self.assertTrue(worker.survey.extended)

            self.assertEqual(len(resultEvents), 1)
            self.assertIsInstance(resultEvents[0], BinningFromGeometryResult)
            self.assertTrue(resultEvents[0].success)
            self.assertIs(resultEvents[0].binOutput, worker.survey.output.binOutput)
            self.assertIs(resultEvents[0].minOffset, worker.survey.output.minOffset)
            self.assertIs(resultEvents[0].maxOffset, worker.survey.output.maxOffset)
            self.assertIs(resultEvents[0].ofAziHist, worker.survey.output.ofAziHist)
            self.assertIs(resultEvents[0].offstHist, worker.survey.output.offstHist)
            self.assertIsNone(resultEvents[0].minRmsOffset)
            self.assertIsNone(resultEvents[0].maxRmsOffset)
            self.assertEqual(resultEvents[0].anaOutputShape, (3, 2))
            self.assertEqual(resultEvents[0].cmpTransform, 'cmp-transform')
            self.assertEqual(finishedEvents, ['finished'])

            worker.survey.shouldSucceed = False
            resultEvents.clear()
            finishedEvents.clear()

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertIsInstance(resultEvents[0], BinningFromGeometryResult)
        self.assertFalse(resultEvents[0].success)
        self.assertEqual(resultEvents[0].errorText, 'geometry failed')
        self.assertEqual(finishedEvents, ['finished'])

    def testBinningGeometryThreadFinishedUsesResultObject(self):
        result = BinningFromGeometryResult(
            success=True,
            binOutput=np.ones((2, 2), dtype=np.float32),
            minOffset=np.full((2, 2), 10.0, dtype=np.float32),
            maxOffset=np.full((2, 2), 20.0, dtype=np.float32),
            minimumFold=1,
            maximumFold=4,
            minMinOffset=10.0,
            maxMinOffset=10.0,
            minMaxOffset=20.0,
            maxMaxOffset=20.0,
            minRmsOffset=0.0,
            maxRmsOffset=0.0,
            rmsOffset=None,
            ofAziHist=None,
            offstHist=None,
            cmpTransform='cmp-transform',
            anaOutputShape=None,
        )

        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.imageType = 1
        self.mainWindow.fileName = ''
        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningGeometryThreadFinished(result)

        np.testing.assert_array_equal(self.mainWindow.output.binOutput, result.binOutput)
        np.testing.assert_array_equal(self.mainWindow.output.minOffset, result.minOffset)
        np.testing.assert_array_equal(self.mainWindow.output.maxOffset, result.maxOffset)
        self.assertEqual(self.mainWindow.output.maximumFold, 4)
        self.assertEqual(self.mainWindow.survey.cmpTransform, 'cmp-transform')
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testBinningGeometryThreadFinishedHandlesFailureResult(self):
        result = BinningFromGeometryResult(success=False, errorText='geometry worker failed')

        self.mainWindow.layoutImg = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.layoutImItem = object()
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningGeometryThreadFinished(result)

        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        appendLogMessage.assert_any_call('Thread : . . . aborted binning operation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . geometry worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testCreateGeometryFromTemplatesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.nShotPoints = 12

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'GeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.createGeometryFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, GeometryFromTemplatesRequest)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.assertEqual(request.includeProfiling, self.mainWindow.appSettings.debug)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_called_once_with(threadStub.deleteLater)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testGeometryWorkerRunUsesOptionalProfilingPayload(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.recGeom = np.zeros(1, dtype=pntType1)
                self.output.relGeom = np.zeros(1, dtype=relType2)
                self.output.srcGeom = np.zeros(1, dtype=pntType1)
                self.errorText = 'geometry setup failed'
                self.shouldSucceed = True
                self.timerTmin = [0.0]
                self.timerTmax = [1.0]
                self.timerTtot = [2.0]
                self.timerFreq = [3]
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupGeometryFromTemplates(self):
                return self.shouldSucceed

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = GeometryWorker(GeometryFromTemplatesRequest(xmlString='<survey />', includeProfiling=True))

            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

            self.assertEqual(len(resultEvents), 1)
            self.assertIsInstance(resultEvents[0], GeometryFromTemplatesResult)
            self.assertIsInstance(resultEvents[0].profiling, GeometryProfilingPayload)
            self.assertEqual(resultEvents[0].profiling.timerTmin, (0.0,))
            self.assertEqual(resultEvents[0].profiling.timerTmax, (1.0,))
            self.assertEqual(resultEvents[0].profiling.timerTtot, (2.0,))
            self.assertEqual(resultEvents[0].profiling.timerFreq, (3,))

            worker = GeometryWorker(GeometryFromTemplatesRequest(xmlString='<survey />', includeProfiling=False))
            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertIsNone(resultEvents[0].profiling)

    def testGeometryThreadFinishedUsesResultObject(self):
        result = GeometryFromTemplatesResult(
            success=True,
            recGeom=np.zeros(1, dtype=pntType1),
            relGeom=np.zeros(1, dtype=relType2),
            srcGeom=np.zeros(1, dtype=pntType1),
            profiling=GeometryProfilingPayload(
                timerTmin=(0.0,),
                timerTmax=(0.0,),
                timerTtot=(0.0,),
                timerFreq=(1,),
            ),
        )

        self.mainWindow.startTime = 0.0
        self.mainWindow.fileName = ''
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow.sessionService, 'setArray') as setArray:
                with patch.object(self.mainWindow.recModel, 'setData') as recSetData:
                    with patch.object(self.mainWindow.relModel, 'setData') as relSetData:
                        with patch.object(self.mainWindow.srcModel, 'setData') as srcSetData:
                            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                            self.mainWindow.geometryThreadFinished(result)

        self.assertEqual(setArray.call_count, 3)
        recSetData.assert_called_once()
        relSetData.assert_called_once()
        srcSetData.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testGeometryThreadFinishedHandlesFailureResult(self):
        result = GeometryFromTemplatesResult(
            success=False,
            errorText='geometry worker failed',
            profiling=GeometryProfilingPayload(
                timerTmin=(),
                timerTmax=(),
                timerTtot=(),
                timerFreq=(),
            ),
        )
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                            self.mainWindow.geometryThreadFinished(result)

        appendLogMessage.assert_any_call('Thread : . . . aborted geometry creation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . geometry worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testStopWorkerThreadIgnoresLateResultAndResetsIdleUi(self):
        controller = self.mainWindow.workerOperationController or binningWorkerMixinModule.WorkerOperationController(
            self.mainWindow,
            self.mainWindow._getWorkerRuntimeDependencies,
        )
        self.mainWindow.workerOperationController = controller

        threadStub = MagicMock()
        threadStub.isRunning.return_value = True
        workerStub = MagicMock()
        controller.activeOperation = workerOperationControllerModule.ActiveWorkerOperation(
            job=workerOperationControllerModule.WorkerJobSpec(
                name='bin-from-templates',
                progressLabelText='x',
                startMessage='y',
                startMessageType=rollMainWindowModule.MsgType.Binning,
                workerFactory=lambda request: workerStub,
                request=object(),
                resultHandler=self.mainWindow.applyBinningWorkerResult,
            ),
            thread=threadStub,
            worker=workerStub,
        )
        self.mainWindow.thread = threadStub
        self.mainWindow.worker = workerStub
        self.mainWindow.layoutImg = np.ones((1, 1), dtype=np.float32)
        self.mainWindow.layoutImItem = object()

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(self.mainWindow, 'applyBinningWorkerResult') as applyBinningWorkerResult:
                            self.mainWindow.stopWorkerThread()
                            controller.finishCurrentOperation(
                                BinningFromTemplatesResult(success=True),
                                self.mainWindow.applyBinningWorkerResult,
                                resetAnalysis=False,
                            )

        threadStub.requestInterruption.assert_called_once_with()
        applyBinningWorkerResult.assert_not_called()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        updateMenuStatus.assert_called_once_with(True)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testReadStoredDebugpySettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/debug/debugpy', None)
        try:
            self.mainWindow.settings.setValue('settings/debug/debugpy', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredDebugpySetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/debug/debugpy')
            else:
                self.mainWindow.settings.setValue('settings/debug/debugpy', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredDebugSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/debug/logging', None)
        try:
            self.mainWindow.settings.setValue('settings/debug/logging', False)
            self.mainWindow.settings.sync()
            self.assertFalse(readStoredDebugSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/debug/logging')
            else:
                self.mainWindow.settings.setValue('settings/debug/logging', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredShowSummariesSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/misc/showSummaries', None)
        try:
            self.mainWindow.settings.setValue('settings/misc/showSummaries', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredShowSummariesSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/misc/showSummaries')
            else:
                self.mainWindow.settings.setValue('settings/misc/showSummaries', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredShowUnfinishedSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/misc/showUnfinished', None)
        try:
            self.mainWindow.settings.setValue('settings/misc/showUnfinished', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredShowUnfinishedSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/misc/showUnfinished')
            else:
                self.mainWindow.settings.setValue('settings/misc/showUnfinished', originalValue)
            self.mainWindow.settings.sync()

    def testUpdateRecentFileActionsKeepsRelativeEntriesInSettings(self):
        self.mainWindow.projectDirectory = os.path.join('D:\\', 'does-not-exist')
        self.mainWindow.recentFileList = ['relative-project.roll']

        self.mainWindow.updateRecentFileActions()

        self.assertEqual(self.mainWindow.recentFileList, ['relative-project.roll'])
        self.assertFalse(self.mainWindow.recentFileActions[0].isVisible())

    def testUpdateRecentFileActionsShowsResolvableRelativeEntries(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            relativeProject = os.path.basename(projectPath)
            self.mainWindow.projectDirectory = tempDir
            self.mainWindow.recentFileList = [relativeProject]

            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [relativeProject])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), relativeProject)

    def testFileNewLandSurveyIncrementsSessionSurveyNumberOnlyOnSuccess(self):
        self.mainWindow.sessionState.surveyNumber = 1
        wizardSurvey = self.createSurvey()
        wizardSurvey.name = 'Land Survey'

        class WizardStub:
            def __init__(self, _parent):
                self.survey = wizardSurvey

            def exec(self):
                return True

        with patch.object(rollMainWindowModule, 'LandSurveyWizard', WizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                with patch.object(self.mainWindow, 'updateAllViews'):
                    success = self.mainWindow.fileNewLandSurvey()

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 2)

        class CancelledWizardStub:
            def __init__(self, _parent):
                self.survey = None

            def exec(self):
                return False

        with patch.object(rollMainWindowModule, 'LandSurveyWizard', CancelledWizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                cancelled = self.mainWindow.fileNewLandSurvey()

        self.assertFalse(cancelled)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 2)

    def testFileNewMarineSurveyIncrementsSessionSurveyNumberOnlyOnSuccess(self):
        self.mainWindow.sessionState.surveyNumber = 3
        wizardSurvey = self.createSurvey()
        wizardSurvey.name = 'Marine Survey'

        class WizardStub:
            def __init__(self, _parent):
                self.survey = wizardSurvey

            def exec(self):
                return True

        with patch.object(rollMainWindowModule, 'MarineSurveyWizard', WizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                with patch.object(self.mainWindow, 'updateAllViews'):
                    success = self.mainWindow.fileNewMarineSurvey()

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 4)

        class CancelledWizardStub:
            def __init__(self, _parent):
                self.survey = None

            def exec(self):
                return False

        with patch.object(rollMainWindowModule, 'MarineSurveyWizard', CancelledWizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                cancelled = self.mainWindow.fileNewMarineSurvey()

        self.assertFalse(cancelled)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 4)

    def testFileSaveAsCommitsDocumentContextOnlyAfterSuccessfulSave(self):
        originalProjectDirectory = self.mainWindow.projectDirectory
        self.mainWindow.fileName = ''
        self.mainWindow.recentFileList = []
        self.mainWindow.textEdit.document().setModified(True)

        with tempfile.TemporaryDirectory() as tempDir:
            targetFileName = os.path.join(tempDir, 'saved_as.roll')

            with patch.object(rollMainWindowModule.QFileDialog, 'getSaveFileName', return_value=(targetFileName, '')):
                with patch.object(self.mainWindow.projectService, 'writeProjectXml', return_value=MagicMock(success=False, errorText='write failure')):
                    with patch.object(rollMainWindowModule.QMessageBox, 'information') as showWriteError:
                        with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars') as saveAnalysisSidecars:
                            with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars') as saveSurveyDataSidecars:
                                success = self.mainWindow.fileSaveAs()

            self.assertFalse(success)
            self.assertEqual(self.mainWindow.fileName, '')
            self.assertEqual(self.mainWindow.projectDirectory, originalProjectDirectory)
            self.assertEqual(self.mainWindow.recentFileList, [])
            self.assertTrue(self.mainWindow.textEdit.document().isModified())
            showWriteError.assert_called_once()
            saveAnalysisSidecars.assert_not_called()
            saveSurveyDataSidecars.assert_not_called()

            with patch.object(rollMainWindowModule.QFileDialog, 'getSaveFileName', return_value=(targetFileName, '')):
                with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars') as saveAnalysisSidecars:
                    with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars') as saveSurveyDataSidecars:
                        success = self.mainWindow.fileSaveAs()

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.fileName, targetFileName)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.recentFileList, [targetFileName])
            self.assertFalse(self.mainWindow.textEdit.document().isModified())
            saveAnalysisSidecars.assert_called_once_with(targetFileName, self.mainWindow.output, includeHistograms=True)
            saveSurveyDataSidecars.assert_called_once()


if __name__ == '__main__':
    unittest.main()
