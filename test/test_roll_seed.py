# coding=utf-8
import unittest

from qgis.core import QgsCoordinateReferenceSystem

from .plugin_loader import loadPluginModule

enumsModule = loadPluginModule('enums_and_int_flags')
rollSeedModule = loadPluginModule('roll_seed')
rollSurveyModule = loadPluginModule('roll_survey')

SeedType = enumsModule.SeedType
RollSeed = rollSeedModule.RollSeed
RollSurvey = rollSurveyModule.RollSurvey


class RollSeedTest(unittest.TestCase):
    def testTypeAssignmentNormalizesIntToSeedType(self):
        seed = RollSeed()

        seed.type = 2

        self.assertIsInstance(seed.type, SeedType)
        self.assertEqual(seed.type, SeedType.circle)

    def testSetSurveyDefaultsNewWellCrsToSurveyCrs(self):
        survey = RollSurvey()
        survey.crs = QgsCoordinateReferenceSystem('EPSG:32631')

        seed = RollSeed()

        seed.setSurvey(survey)

        self.assertEqual(seed.survey, survey)
        self.assertEqual(seed.well.crs.authid(), 'EPSG:32631')

    def testSetSurveyPreservesConfiguredWellCrs(self):
        survey = RollSurvey()
        survey.crs = QgsCoordinateReferenceSystem('EPSG:32631')

        seed = RollSeed()
        seed.well.name = 'existing.well'
        seed.well.crs = QgsCoordinateReferenceSystem('EPSG:23095')

        seed.setSurvey(survey)

        self.assertEqual(seed.well.crs.authid(), 'EPSG:23095')


if __name__ == '__main__':
    unittest.main()
