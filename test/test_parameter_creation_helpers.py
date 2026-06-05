# coding=utf-8
import unittest

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey

helpersModule = loadPluginModule('parameter_creation_helpers')

createAppendedTemplateSeed = helpersModule.createAppendedTemplateSeed
createDefaultBlock = helpersModule.createDefaultBlock
createDefaultTemplate = helpersModule.createDefaultTemplate
SOURCE_SEED_COLOR = helpersModule.SOURCE_SEED_COLOR
RECEIVER_SEED_COLOR = helpersModule.RECEIVER_SEED_COLOR


class ParameterCreationHelpersTest(unittest.TestCase):
    def testCreateAppendedTemplateSeedPrefersSourceWhenReceiverExists(self):
        survey = createTestSurvey()
        template = createDefaultTemplate('Template-1', survey)

        seed = createAppendedTemplateSeed('Seed-3', template.seedList, survey)

        self.assertTrue(seed.bSource)
        self.assertEqual(seed.color.name(seed.color.NameFormat.HexArgb).lower(), SOURCE_SEED_COLOR.lower())
        self.assertEqual(seed.survey, survey)
        self.assertEqual(seed.well.crs, survey.crs)

    def testCreateAppendedTemplateSeedFallsBackToReceiverWithoutReceiverSeed(self):
        survey = createTestSurvey()
        template = createDefaultTemplate('Template-1', survey)
        template.seedList = [template.seedList[0]]

        seed = createAppendedTemplateSeed('Seed-2', template.seedList, survey)

        self.assertFalse(seed.bSource)
        self.assertEqual(seed.color.name(seed.color.NameFormat.HexArgb).lower(), RECEIVER_SEED_COLOR.lower())
        self.assertEqual(seed.survey, survey)

    def testCreateDefaultTemplateBuildsTwoSurveyBoundSeeds(self):
        survey = createTestSurvey()

        template = createDefaultTemplate('Template-1', survey)

        self.assertEqual(template.name, 'Template-1')
        self.assertEqual(len(template.seedList), 2)
        self.assertTrue(template.seedList[0].bSource)
        self.assertFalse(template.seedList[1].bSource)
        self.assertEqual(template.seedList[0].survey, survey)
        self.assertEqual(template.seedList[1].survey, survey)
        self.assertEqual(template.seedList[0].well.crs, survey.crs)
        self.assertEqual(template.seedList[1].well.crs, survey.crs)

    def testCreateDefaultBlockBuildsOneDefaultTemplate(self):
        survey = createTestSurvey()

        block = createDefaultBlock('Block-1', survey)

        self.assertEqual(block.name, 'Block-1')
        self.assertEqual(len(block.templateList), 1)
        self.assertEqual(len(block.templateList[0].seedList), 2)
        self.assertEqual(block.templateList[0].seedList[0].survey, survey)
        self.assertEqual(block.templateList[0].seedList[1].survey, survey)


if __name__ == '__main__':
    unittest.main()
