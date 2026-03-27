# coding=utf-8
import os
import tempfile
import unittest

from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

projectServiceModule = loadPluginModule('project_service')
rollSurveyModule = loadPluginModule('roll_survey')

ProjectService = projectServiceModule.ProjectService
RollSurvey = rollSurveyModule.RollSurvey


class ProjectServiceTest(unittest.TestCase):
    def createSurvey(self):
        survey = RollSurvey('ProjectService-Test')
        survey.crs = QgsCoordinateReferenceSystem('EPSG:23095')
        survey.grid.orig.setX(123.5)
        survey.grid.orig.setY(456.25)
        survey.grid.angle = 12.5
        survey.grid.scale.setX(1.25)
        survey.grid.scale.setY(1.25)
        survey.grid.binSize.setX(10.0)
        survey.grid.binSize.setY(20.0)
        survey.grid.stakeOrig.setX(1000.0)
        survey.grid.stakeOrig.setY(2000.0)
        survey.grid.stakeSize.setX(25.0)
        survey.grid.stakeSize.setY(50.0)
        survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 80.0)
        survey.calcTransforms()
        return survey

    def testWriteAndReadProjectXml(self):
        service = ProjectService()
        survey = self.createSurvey()

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'project_service.roll')

            writeResult = service.writeProjectXml(projectPath, survey, tempDir, False, 2)
            self.assertTrue(writeResult.success)
            self.assertIn('<survey', writeResult.xmlText)

            readResult = service.readProjectText(projectPath)
            self.assertTrue(readResult.success)
            self.assertIn('<survey', readResult.plainText)

            restored = RollSurvey()
            success = restored.fromXmlString(readResult.plainText)

            self.assertTrue(success)
            self.assertEqual(restored.name, survey.name)
            self.assertEqual(restored.crs.authid(), survey.crs.authid())
            self.assertEqual(restored.output.rctOutput, survey.output.rctOutput)

    def testReadProjectTextReturnsErrorForMissingFile(self):
        service = ProjectService()

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'missing.roll')
            readResult = service.readProjectText(projectPath)

        self.assertFalse(readResult.success)
        self.assertNotEqual(readResult.errorText, '')


if __name__ == '__main__':
    unittest.main()