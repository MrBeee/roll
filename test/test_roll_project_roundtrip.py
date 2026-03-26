# coding=utf-8
import unittest

from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

rollSurveyModule = loadPluginModule('roll_survey')
RollSurvey = rollSurveyModule.RollSurvey


class RollProjectRoundTripTest(unittest.TestCase):
    def createSurvey(self):
        survey = RollSurvey('Phase0-RoundTrip')
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

    def assertRectAlmostEqual(self, left, right):
        self.assertAlmostEqual(left.left(), right.left(), places=4)
        self.assertAlmostEqual(left.right(), right.right(), places=4)
        self.assertAlmostEqual(left.top(), right.top(), places=4)
        self.assertAlmostEqual(left.bottom(), right.bottom(), places=4)

    def testMinimalSurveyRoundTripsThroughXml(self):
        survey = self.createSurvey()

        xmlText = survey.toXmlString(2)

        restored = RollSurvey()
        success = restored.fromXmlString(xmlText)

        self.assertTrue(success)
        self.assertEqual(restored.name, survey.name)
        self.assertEqual(restored.type, survey.type)
        self.assertEqual(restored.crs.authid(), survey.crs.authid())
        self.assertAlmostEqual(restored.grid.orig.x(), survey.grid.orig.x(), places=4)
        self.assertAlmostEqual(restored.grid.orig.y(), survey.grid.orig.y(), places=4)
        self.assertAlmostEqual(restored.grid.angle, survey.grid.angle, places=4)
        self.assertAlmostEqual(restored.grid.scale.x(), survey.grid.scale.x(), places=4)
        self.assertAlmostEqual(restored.grid.scale.y(), survey.grid.scale.y(), places=4)
        self.assertAlmostEqual(restored.grid.binSize.x(), survey.grid.binSize.x(), places=4)
        self.assertAlmostEqual(restored.grid.binSize.y(), survey.grid.binSize.y(), places=4)
        self.assertRectAlmostEqual(restored.output.rctOutput, survey.output.rctOutput)
        self.assertIsNotNone(restored.glbTransform)


if __name__ == '__main__':
    unittest.main()
