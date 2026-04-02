# coding=utf-8
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtWidgets import QAction

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP, _, IFACE, _ = getQgisApp()

rollMainWindowModule = loadPluginModule('roll_main_window')
rollSurveyModule = loadPluginModule('roll_survey')
settingsModule = loadPluginModule('settings')
spsModule = loadPluginModule('sps_io_and_qc')

RollMainWindow = rollMainWindowModule.RollMainWindow
RollSurvey = rollSurveyModule.RollSurvey
readSettings = settingsModule.readSettings
pntType1 = spsModule.pntType1
relType2 = spsModule.relType2


class ProjectSidecarsTest(unittest.TestCase):
    def setUp(self):
        self.mainWindow = RollMainWindow(IFACE, standaloneMode=True)

    def tearDown(self):
        if self.mainWindow is not None:
            self.mainWindow.close()
            self.mainWindow.deleteLater()
        self.mainWindow = None

    def createSurvey(self):
        survey = RollSurvey('Phase0-Sidecars')
        survey.crs = QgsCoordinateReferenceSystem('EPSG:23095')
        survey.grid.orig.setX(0.0)
        survey.grid.orig.setY(0.0)
        survey.grid.angle = 0.0
        survey.grid.scale.setX(1.0)
        survey.grid.scale.setY(1.0)
        survey.grid.binSize.setX(10.0)
        survey.grid.binSize.setY(10.0)
        survey.grid.stakeOrig.setX(1000.0)
        survey.grid.stakeOrig.setY(1000.0)
        survey.grid.stakeSize.setX(10.0)
        survey.grid.stakeSize.setY(10.0)
        survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 50.0)
        survey.calcTransforms()
        return survey

    def writeProjectFixture(self, folder):
        survey = self.createSurvey()
        projectPath = os.path.join(folder, 'phase0_sidecars.roll')
        with open(projectPath, 'w', encoding='utf-8') as handle:
            handle.write(survey.toXmlString(2))
        return projectPath

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


if __name__ == '__main__':
    unittest.main()
