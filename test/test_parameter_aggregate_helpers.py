# coding=utf-8
import unittest

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey

helpersModule = loadPluginModule('parameter_aggregate_helpers')

analysisValuesFromParameters = helpersModule.analysisValuesFromParameters
analysisValuesFromSurvey = helpersModule.analysisValuesFromSurvey
applyBlockValues = helpersModule.applyBlockValues
applyGlobalGridValues = helpersModule.applyGlobalGridValues
applyConfigurationValues = helpersModule.applyConfigurationValues
applyLocalGridValues = helpersModule.applyLocalGridValues
applyTemplateValues = helpersModule.applyTemplateValues
blockValuesFromBlock = helpersModule.blockValuesFromBlock
configurationValuesFromSurvey = helpersModule.configurationValuesFromSurvey
reflectorValuesFromParameters = helpersModule.reflectorValuesFromParameters
reflectorValuesFromSurvey = helpersModule.reflectorValuesFromSurvey
templateValuesFromTemplate = helpersModule.templateValuesFromTemplate

creationHelpersModule = loadPluginModule('parameter_creation_helpers')

createDefaultBlock = creationHelpersModule.createDefaultBlock
createDefaultTemplate = creationHelpersModule.createDefaultTemplate


class ParameterAggregateHelpersTest(unittest.TestCase):
    def testAnalysisValuesFromSurveyKeepsExpectedTupleOrder(self):
        survey = createTestSurvey()

        values = analysisValuesFromSurvey(survey)

        self.assertEqual(
            values.asTuple(),
            (survey.output.rctOutput, survey.angles, survey.binning, survey.offset, survey.unique),
        )

    def testAnalysisValuesFromParametersBuildsExpectedTupleOrder(self):
        survey = createTestSurvey()

        values = analysisValuesFromParameters(
            area=survey.output.rctOutput,
            angles=survey.angles,
            binning=survey.binning,
            offset=survey.offset,
            unique=survey.unique,
        )

        self.assertEqual(
            values.asTuple(),
            (survey.output.rctOutput, survey.angles, survey.binning, survey.offset, survey.unique),
        )

    def testApplyConfigurationValuesUpdatesSurveyAndReturnsTuple(self):
        survey = createTestSurvey()
        newCrs = survey.crs.__class__('EPSG:28992')

        values = applyConfigurationValues(survey, crs=newCrs, typ='Marine', nam='Renamed-Survey')

        self.assertEqual(values.asTuple(), (newCrs, 'Marine', 'Renamed-Survey'))
        self.assertEqual(survey.crs, newCrs)
        self.assertEqual(survey.type.name, 'Marine')
        self.assertEqual(survey.name, 'Renamed-Survey')

    def testConfigurationValuesFromSurveyReturnsStringTypeName(self):
        survey = createTestSurvey()

        values = configurationValuesFromSurvey(survey)

        self.assertEqual(values.crs, survey.crs)
        self.assertEqual(values.typ, survey.type.name)
        self.assertEqual(values.nam, survey.name)

    def testApplyLocalGridValuesCopiesLocalGridFields(self):
        survey = createTestSurvey()
        sourceGrid = survey.grid.__class__()
        sourceGrid.binSize = survey.grid.binSize
        sourceGrid.binShift = survey.grid.binShift
        sourceGrid.stakeOrig = survey.grid.stakeOrig
        sourceGrid.stakeSize = survey.grid.stakeSize
        sourceGrid.fold = 9

        targetGrid = survey.grid.__class__()
        applyLocalGridValues(targetGrid, sourceGrid)

        self.assertEqual(targetGrid.binSize, sourceGrid.binSize)
        self.assertEqual(targetGrid.binShift, sourceGrid.binShift)
        self.assertEqual(targetGrid.stakeOrig, sourceGrid.stakeOrig)
        self.assertEqual(targetGrid.stakeSize, sourceGrid.stakeSize)
        self.assertEqual(targetGrid.fold, sourceGrid.fold)

    def testApplyGlobalGridValuesCopiesGlobalGridFields(self):
        survey = createTestSurvey()
        sourceGrid = survey.grid.__class__()
        sourceGrid.orig = survey.grid.orig
        sourceGrid.scale = survey.grid.scale
        sourceGrid.angle = 22.5

        targetGrid = survey.grid.__class__()
        applyGlobalGridValues(targetGrid, sourceGrid)

        self.assertEqual(targetGrid.orig, sourceGrid.orig)
        self.assertEqual(targetGrid.scale, sourceGrid.scale)
        self.assertEqual(targetGrid.angle, sourceGrid.angle)

    def testReflectorValuesHelpersKeepExpectedTupleOrder(self):
        survey = createTestSurvey()

        surveyValues = reflectorValuesFromSurvey(survey)
        parameterValues = reflectorValuesFromParameters(plane=survey.globalPlane, sphere=survey.globalSphere)

        self.assertEqual(surveyValues.asTuple(), (survey.globalPlane, survey.globalSphere))
        self.assertEqual(parameterValues.asTuple(), (survey.globalPlane, survey.globalSphere))

    def testBlockValuesHelpersKeepExpectedTupleOrderAndApply(self):
        survey = createTestSurvey()
        block = createDefaultBlock('Block-1', survey)
        values = blockValuesFromBlock(block)

        self.assertEqual(values.asTuple(), (block.borders.srcBorder, block.borders.recBorder, block.templateList))

        newTemplateList = block.templateList[:]
        applied = applyBlockValues(
            block,
            srcBorder=block.borders.srcBorder,
            recBorder=block.borders.recBorder,
            templateList=newTemplateList,
        )

        self.assertEqual(applied.asTuple(), (block.borders.srcBorder, block.borders.recBorder, newTemplateList))
        self.assertIs(block.templateList, newTemplateList)

    def testTemplateValuesHelpersKeepExpectedTupleOrderAndApply(self):
        survey = createTestSurvey()
        template = createDefaultTemplate('Template-1', survey)
        values = templateValuesFromTemplate(template)

        self.assertEqual(values.asTuple(), (template.rollList, template.seedList))

        newSeedList = template.seedList[:]
        applied = applyTemplateValues(template, rollList=template.rollList, seedList=newSeedList)

        self.assertEqual(applied.asTuple(), (template.rollList, newSeedList))
        self.assertIs(template.seedList, newSeedList)


if __name__ == '__main__':
    unittest.main()
