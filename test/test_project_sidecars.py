# coding=utf-8
import os
import tempfile
import unittest

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtWidgets import QAction

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP, _, IFACE, _ = getQgisApp()

rollMainWindowModule = loadPluginModule('roll_main_window')
rollSurveyModule = loadPluginModule('roll_survey')

RollMainWindow = rollMainWindowModule.RollMainWindow
RollSurvey = rollSurveyModule.RollSurvey


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

    def testFileOpenRecentRemovesMissingFileFromRecentList(self):
        with tempfile.TemporaryDirectory() as tempDir:
            missingProjectPath = os.path.join(tempDir, 'missing.roll')
            self.mainWindow.recentFileList = [missingProjectPath]
            self.mainWindow.updateRecentFileActions()

            action = self.mainWindow.recentFileActions[0]
            self.assertIsInstance(action, QAction)
            self.assertTrue(action.isVisible())

            action.trigger()

            self.assertEqual(self.mainWindow.recentFileList, [])
            self.assertFalse(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [])

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


if __name__ == '__main__':
    unittest.main()
