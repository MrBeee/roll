# coding=utf-8
import unittest
from collections import defaultdict
from unittest.mock import patch

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtGui import QVector3D
from qgis.PyQt.QtXml import QDomDocument

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

rollSurveyModule = loadPluginModule('roll_survey')
rollGridModule = loadPluginModule('roll_grid')

RollSurvey = rollSurveyModule.RollSurvey
RollGrid = rollGridModule.RollGrid


class RollSurveyGeometryTest(unittest.TestCase):
    def createSurvey(self):
        survey = RollSurvey('Geometry-Test')
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
        survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 100.0)
        survey.calcTransforms()
        return survey

    def testSetupGeometryFromTemplatesBuildsSingleSourceReceiverAndRelation(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        template = survey.blockList[0].templateList[0]
        self.assertEqual(len(template.rollList), 3)

        srcSeed = next(seed for seed in template.seedList if seed.bSource)
        recSeed = next(seed for seed in template.seedList if not seed.bSource)

        self.assertEqual(len(srcSeed.grid.growList), 3)
        self.assertEqual(len(recSeed.grid.growList), 3)

        srcSeed.origin = QVector3D(0.0, 0.0, 0.0)
        recSeed.origin = QVector3D(20.0, 0.0, 0.0)

        success = survey.setupGeometryFromTemplates()

        self.assertTrue(success)
        self.assertEqual(survey.nShotPoints, 1)
        self.assertEqual(survey.output.srcGeom.shape[0], 1)
        self.assertEqual(survey.output.recGeom.shape[0], 1)
        self.assertEqual(survey.output.relGeom.shape[0], 1)

        srcRecord = survey.output.srcGeom[0]
        recRecord = survey.output.recGeom[0]
        relRecord = survey.output.relGeom[0]

        self.assertEqual(srcRecord['Code'], 'E1')
        self.assertEqual(recRecord['Code'], 'G1')
        self.assertEqual(srcRecord['Index'], 1)
        self.assertEqual(recRecord['Index'], 1)
        self.assertEqual(srcRecord['Uniq'], 1)
        self.assertEqual(recRecord['Uniq'], 1)
        self.assertEqual(srcRecord['InUse'], 1)
        self.assertEqual(recRecord['InUse'], 1)
        self.assertAlmostEqual(srcRecord['LocX'], 0.0, places=4)
        self.assertAlmostEqual(srcRecord['LocY'], 0.0, places=4)
        self.assertAlmostEqual(recRecord['LocX'], 20.0, places=4)
        self.assertAlmostEqual(recRecord['LocY'], 0.0, places=4)

        self.assertEqual(relRecord['SrcInd'], srcRecord['Index'])
        self.assertEqual(relRecord['SrcLin'], srcRecord['Line'])
        self.assertEqual(relRecord['SrcPnt'], srcRecord['Point'])
        self.assertEqual(relRecord['RecInd'], recRecord['Index'])
        self.assertEqual(relRecord['RecLin'], recRecord['Line'])
        self.assertEqual(relRecord['RecMin'], recRecord['Point'])
        self.assertEqual(relRecord['RecMax'], recRecord['Point'])
        self.assertEqual(relRecord['RecNum'], 1)
        self.assertEqual(relRecord['Uniq'], 1)
        self.assertEqual(relRecord['InSps'], 1)
        self.assertEqual(relRecord['InRps'], 1)

    def testSetupGeometryFromTemplatesBuildsRolledTemplateShotsReceiversAndRelations(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        template = survey.blockList[0].templateList[0]
        template.rollList[2].steps = 2
        template.rollList[2].increment = QVector3D(10.0, 0.0, 0.0)

        srcSeed = next(seed for seed in template.seedList if seed.bSource)
        recSeed = next(seed for seed in template.seedList if not seed.bSource)
        srcSeed.origin = QVector3D(0.0, 0.0, 0.0)
        recSeed.origin = QVector3D(20.0, 0.0, 0.0)

        success = survey.setupGeometryFromTemplates()

        self.assertTrue(success)
        self.assertEqual(survey.nShotPoints, 2)
        self.assertEqual(survey.output.srcGeom.shape[0], 2)
        self.assertEqual(survey.output.recGeom.shape[0], 2)
        self.assertEqual(survey.output.relGeom.shape[0], 2)

        np.testing.assert_array_equal(survey.output.srcGeom['Point'], np.array([1000, 1001]))
        np.testing.assert_array_equal(survey.output.recGeom['Point'], np.array([1002, 1003]))
        np.testing.assert_array_equal(survey.output.relGeom['SrcPnt'], np.array([1000, 1001]))
        np.testing.assert_array_equal(survey.output.relGeom['RecMin'], np.array([1002, 1003]))
        np.testing.assert_array_equal(survey.output.relGeom['RecMax'], np.array([1002, 1003]))

    def testCheckIntegrityRejectsMalformedTemplateWithoutRepairingRollList(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        template = survey.blockList[0].templateList[0]
        template.rollList.pop()

        self.assertEqual(len(template.rollList), 2)

        with patch.object(rollSurveyModule.QMessageBox, 'warning') as warningMock:
            success = survey.checkIntegrity()

        self.assertFalse(success)
        self.assertEqual(len(template.rollList), 2)
        warningMock.assert_called_once_with(None, 'Survey format error', 'Template "template-1" should have exactly three roll steps')

    def testLegacyGrowListXmlIsNormalizedToThreeGrowSteps(self):
        doc = QDomDocument()
        result = doc.setContent(
            '<root>'
            '<grow_list roll="True" points="0">'
            '<translate n="2" dx="5" dy="0" dz="0"/>'
            '</grow_list>'
            '</root>'
        )
        success = result[0] if isinstance(result, tuple) else result

        self.assertTrue(success)

        grid = RollGrid()
        readSuccess = grid.readXml(doc.documentElement())

        self.assertTrue(readSuccess)
        self.assertEqual(len(grid.growList), 3)
        self.assertEqual(grid.growList[2].steps, 2)
        self.assertAlmostEqual(grid.growList[2].increment.x(), 5.0, places=4)

    def testCalcPointListAssertsOnMalformedGrowList(self):
        grid = RollGrid()
        grid.growList.pop()

        self.assertEqual(len(grid.growList), 2)

        with self.assertRaisesRegex(AssertionError, 'there must always be 3 grow steps for pattern grids'):
            grid.calcPointList(QVector3D())

    def testIterSeedGrowOffsetsUsesThreeGrowStepInvariant(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        template = survey.blockList[0].templateList[0]
        srcSeed = next(seed for seed in template.seedList if seed.bSource)

        offsets = list(survey.iterSeedGrowOffsets(srcSeed, QVector3D(1.0, 2.0, 3.0)))

        self.assertEqual(len(offsets), 1)
        self.assertAlmostEqual(offsets[0].x(), 1.0, places=4)
        self.assertAlmostEqual(offsets[0].y(), 2.0, places=4)
        self.assertAlmostEqual(offsets[0].z(), 3.0, places=4)

    def testCheckIntegrityRejectsMalformedGridGrowListWithoutRepairingIt(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        template = survey.blockList[0].templateList[0]
        srcSeed = next(seed for seed in template.seedList if seed.bSource)
        srcSeed.grid.growList.pop()

        self.assertEqual(len(srcSeed.grid.growList), 2)

        with patch.object(rollSurveyModule.QMessageBox, 'warning') as warningMock:
            success = survey.checkIntegrity()

        self.assertFalse(success)
        self.assertEqual(len(srcSeed.grid.growList), 2)
        warningMock.assert_called_once_with(None, 'Survey format error', 'Seed "src-1" should have exactly three grow steps')

    def testCreateBasicSkeletonPatternSeedsStartWithThreeGrowSteps(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=1)

        patternSeed = survey.patternList[0].seedList[0]

        self.assertEqual(len(patternSeed.grid.growList), 3)

    def testPopulateTemplateReceiversInRelTempUsesBlockAwareDedupAndLineGrouping(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=2, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        for block in survey.blockList:
            template = block.templateList[0]
            recSeed = next(seed for seed in template.seedList if not seed.bSource)
            recSeed.origin = QVector3D(20.0, 0.0, 0.0)
            recSeed.grid.growList[2].steps = 2
            recSeed.grid.growList[2].increment = QVector3D(10.0, 0.0, 0.0)

        survey.calcPointArrays()
        survey.output.recDict = defaultdict(lambda: defaultdict(dict))
        survey.output.recGeom = np.zeros(shape=(10), dtype=rollSurveyModule.pntType1)
        survey.output.relTemp = np.zeros(shape=(10), dtype=rollSurveyModule.relType2)
        survey.nRecRecord = 0

        firstRecordCount = survey.populateTemplateReceiversInRelTemp(0, survey.blockList[0], survey.blockList[0].templateList[0], np.zeros(3, dtype=np.float32))

        self.assertEqual(firstRecordCount, 0)
        self.assertEqual(survey.nRecRecord, 2)
        self.assertEqual(survey.output.relTemp[0]['RecInd'], 1)
        self.assertEqual(survey.output.relTemp[0]['RecMin'], 1002)
        self.assertEqual(survey.output.relTemp[0]['RecMax'], 1003)

        secondRecordCount = survey.populateTemplateReceiversInRelTemp(1, survey.blockList[1], survey.blockList[1].templateList[0], np.zeros(3, dtype=np.float32))

        self.assertEqual(secondRecordCount, 0)
        self.assertEqual(survey.nRecRecord, 4)
        self.assertEqual(survey.output.relTemp[0]['RecInd'], 2)

    def testAppendTemplateSourceRecordsAppendsFilteredSources(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=1, nPatterns=0)

        block = survey.blockList[0]
        template = block.templateList[0]
        srcSeed = next(seed for seed in template.seedList if seed.bSource)
        srcSeed.origin = QVector3D(20.0, 0.0, 0.0)
        srcSeed.grid.growList[2].steps = 2
        srcSeed.grid.growList[2].increment = QVector3D(10.0, 0.0, 0.0)

        block.borders.srcBorder = QRectF(0.0, -5.0, 25.0, 10.0)

        survey.calcPointArrays()
        survey.output.srcGeom = np.zeros(shape=(10), dtype=rollSurveyModule.pntType1)
        survey.nShotPoint = 0

        survey.appendTemplateSourceRecords(0, block, template, np.zeros(3, dtype=np.float32))

        self.assertEqual(survey.nShotPoint, 1)
        self.assertEqual(survey.output.srcGeom[0]['Index'], 1)
        self.assertEqual(survey.output.srcGeom[0]['Point'], 1002)
        self.assertAlmostEqual(survey.output.srcGeom[0]['LocX'], 20.0, places=4)

    def testAppendTemplateRelationsFromRelTempExpandsAllShots(self):
        survey = self.createSurvey()
        survey.output.srcGeom = np.zeros(shape=(2), dtype=rollSurveyModule.pntType1)
        survey.output.relGeom = np.zeros(shape=(10), dtype=rollSurveyModule.relType2)
        survey.output.relTemp = np.zeros(shape=(2), dtype=rollSurveyModule.relType2)

        survey.output.srcGeom[0]['Line'] = 1001
        survey.output.srcGeom[0]['Point'] = 1002
        survey.output.srcGeom[0]['Index'] = 1
        survey.output.srcGeom[1]['Line'] = 1001
        survey.output.srcGeom[1]['Point'] = 1003
        survey.output.srcGeom[1]['Index'] = 1

        survey.output.relTemp[0]['RecLin'] = 2001
        survey.output.relTemp[0]['RecMin'] = 3001
        survey.output.relTemp[0]['RecMax'] = 3002
        survey.output.relTemp[1]['RecLin'] = 2002
        survey.output.relTemp[1]['RecMin'] = 3005
        survey.output.relTemp[1]['RecMax'] = 3007

        survey.nShotPoint = 2
        survey.nRelRecord = 0

        survey.appendTemplateRelationsFromRelTemp(0, 1)

        self.assertEqual(survey.nRelRecord, 4)
        self.assertEqual(survey.output.relGeom[0]['SrcPnt'], 1002)
        self.assertEqual(survey.output.relGeom[1]['SrcPnt'], 1002)
        self.assertEqual(survey.output.relGeom[2]['SrcPnt'], 1003)
        self.assertEqual(survey.output.relGeom[3]['SrcPnt'], 1003)
        self.assertEqual(survey.output.relGeom[0]['RecLin'], 2001)
        self.assertEqual(survey.output.relGeom[1]['RecLin'], 2002)
        self.assertEqual(survey.output.relGeom[2]['RecLin'], 2001)
        self.assertEqual(survey.output.relGeom[3]['RecLin'], 2002)
        self.assertEqual(survey.output.relGeom[0]['RecMin'], 3001)
        self.assertEqual(survey.output.relGeom[3]['RecMax'], 3007)

    def testUpdateBinOutputsForValidCmpPointsFiltersInvalidBinsAndWritesAnalysis(self):
        survey = self.createSurvey()
        survey.grid.fold = 2
        survey.output.binOutput = np.zeros((2, 2), dtype=np.int32)
        survey.output.minOffset = np.full((2, 2), np.inf, dtype=np.float32)
        survey.output.maxOffset = np.zeros((2, 2), dtype=np.float32)
        survey.output.anaOutput = np.zeros((2, 2, survey.grid.fold, 12), dtype=np.float32)

        src = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        cmpPoints = np.array([
            [5.0, 5.0, 0.0],
            [15.0, 5.0, 0.0],
            [-15.0, 5.0, 0.0],
        ], dtype=np.float32)
        recPoints = np.array([
            [10.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [30.0, 0.0, 0.0],
        ], dtype=np.float32)
        hypArray = np.array([10.0, 20.0, 30.0], dtype=np.float32)
        aziArray = np.array([45.0, 90.0, 135.0], dtype=np.float32)

        updated = survey.updateBinOutputsForValidCmpPoints(src, cmpPoints, recPoints, hypArray, aziArray, True)

        self.assertTrue(updated)
        np.testing.assert_array_equal(survey.output.binOutput, np.array([[1, 0], [1, 0]], dtype=np.int32))
        self.assertAlmostEqual(survey.output.minOffset[0, 0], 10.0, places=4)
        self.assertAlmostEqual(survey.output.maxOffset[0, 0], 10.0, places=4)
        self.assertAlmostEqual(survey.output.minOffset[1, 0], 20.0, places=4)
        self.assertAlmostEqual(survey.output.maxOffset[1, 0], 20.0, places=4)

        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 3], 0.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 4], 0.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 5], 10.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 7], 5.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 8], 5.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 10], 10.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[0, 0, 0, 11], 45.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[1, 0, 0, 5], 20.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[1, 0, 0, 7], 15.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[1, 0, 0, 10], 20.0, places=4)
        self.assertAlmostEqual(survey.output.anaOutput[1, 0, 0, 11], 90.0, places=4)

    def testBuildBinningArraysFromSelectedReceiversAppliesCmpOffsetAndRadialFilters(self):
        survey = self.createSurvey()
        survey.binning.method = rollSurveyModule.BinningType.cmp
        survey.output.rctOutput = QRectF(0.0, 0.0, 20.0, 20.0)
        survey.offset.rctOffsets = QRectF(0.0, -5.0, 30.0, 10.0)
        survey.offset.radOffsets.setX(15.0)
        survey.offset.radOffsets.setY(25.0)

        src = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        recPoints = np.array([
            [20.0, 0.0, 0.0],
            [40.0, 0.0, 0.0],
            [20.0, 20.0, 0.0],
            [10.0, 0.0, 0.0],
        ], dtype=np.float32)

        traceArrays = survey.buildBinningArraysFromSelectedReceivers(src, recPoints)

        self.assertIsNotNone(traceArrays)
        cmpPoints, filteredRecPoints, hypArray, aziArray = traceArrays

        self.assertEqual(cmpPoints.shape, (1, 3))
        self.assertEqual(filteredRecPoints.shape, (1, 3))
        self.assertAlmostEqual(cmpPoints[0, 0], 10.0, places=4)
        self.assertAlmostEqual(cmpPoints[0, 1], 0.0, places=4)
        self.assertAlmostEqual(filteredRecPoints[0, 0], 20.0, places=4)
        self.assertAlmostEqual(filteredRecPoints[0, 1], 0.0, places=4)
        self.assertAlmostEqual(hypArray[0], 20.0, places=4)
        self.assertAlmostEqual(aziArray[0], 90.0, places=4)

    def testSelectReceiversForSourceRelationSliceUsesSortedSourceSpecificRanges(self):
        survey = self.createSurvey()
        survey.output.srcGeom = np.zeros(shape=(2), dtype=rollSurveyModule.pntType1)
        survey.output.recGeom = np.zeros(shape=(4), dtype=rollSurveyModule.pntType1)
        survey.output.relGeom = np.zeros(shape=(2), dtype=rollSurveyModule.relType2)

        survey.output.srcGeom[0]['Index'] = 1
        survey.output.srcGeom[0]['Line'] = 1001
        survey.output.srcGeom[0]['Point'] = 1002
        survey.output.srcGeom[0]['LocX'] = 20.0
        survey.output.srcGeom[1]['Index'] = 1
        survey.output.srcGeom[1]['Line'] = 1001
        survey.output.srcGeom[1]['Point'] = 1001
        survey.output.srcGeom[1]['LocX'] = 10.0

        survey.output.recGeom[0]['Index'] = 1
        survey.output.recGeom[0]['Line'] = 2001
        survey.output.recGeom[0]['Point'] = 3003
        survey.output.recGeom[0]['LocX'] = 30.0
        survey.output.recGeom[0]['InUse'] = 1
        survey.output.recGeom[1]['Index'] = 1
        survey.output.recGeom[1]['Line'] = 2001
        survey.output.recGeom[1]['Point'] = 3001
        survey.output.recGeom[1]['LocX'] = 10.0
        survey.output.recGeom[1]['InUse'] = 1
        survey.output.recGeom[2]['Index'] = 1
        survey.output.recGeom[2]['Line'] = 2001
        survey.output.recGeom[2]['Point'] = 3002
        survey.output.recGeom[2]['LocX'] = 20.0
        survey.output.recGeom[2]['InUse'] = 1
        survey.output.recGeom[3]['Index'] = 1
        survey.output.recGeom[3]['Line'] = 2002
        survey.output.recGeom[3]['Point'] = 4001
        survey.output.recGeom[3]['LocX'] = 40.0
        survey.output.recGeom[3]['InUse'] = 1

        survey.output.relGeom[0]['SrcInd'] = 1
        survey.output.relGeom[0]['SrcLin'] = 1001
        survey.output.relGeom[0]['SrcPnt'] = 1002
        survey.output.relGeom[0]['RecInd'] = 1
        survey.output.relGeom[0]['RecLin'] = 2001
        survey.output.relGeom[0]['RecMin'] = 3003
        survey.output.relGeom[0]['RecMax'] = 3003
        survey.output.relGeom[1]['SrcInd'] = 1
        survey.output.relGeom[1]['SrcLin'] = 1001
        survey.output.relGeom[1]['SrcPnt'] = 1001
        survey.output.relGeom[1]['RecInd'] = 1
        survey.output.relGeom[1]['RecLin'] = 2001
        survey.output.relGeom[1]['RecMin'] = 3001
        survey.output.relGeom[1]['RecMax'] = 3002

        lookup = survey.prepareGeometryRelationBinningLookup()

        self.assertEqual(survey.output.srcGeom[0]['Point'], 1001)
        self.assertEqual(survey.output.srcGeom[1]['Point'], 1002)
        np.testing.assert_array_equal(lookup.relLeft, np.array([0, 1]))
        np.testing.assert_array_equal(lookup.relRight, np.array([1, 2]))

        firstSourceRecPoints = survey.selectReceiversForSourceRelationSlice(0, lookup)
        secondSourceRecPoints = survey.selectReceiversForSourceRelationSlice(1, lookup)

        self.assertEqual(firstSourceRecPoints.shape, (2, 3))
        self.assertEqual(secondSourceRecPoints.shape, (1, 3))
        np.testing.assert_array_equal(firstSourceRecPoints[:, 0], np.array([10.0, 20.0], dtype=np.float32))
        np.testing.assert_array_equal(secondSourceRecPoints[:, 0], np.array([30.0], dtype=np.float32))

    def testLiveBinningPathsPopulateMissingLocalCoordinatesConsistently(self):
        relationSurvey = self.createSurvey()
        noRelSurvey = self.createSurvey()

        for survey in (relationSurvey, noRelSurvey):
            survey.grid.orig.setX(1000.0)
            survey.grid.orig.setY(2000.0)
            survey.calcTransforms()

        srcGeom = np.zeros(shape=(1), dtype=rollSurveyModule.pntType1)
        srcGeom[0]['Index'] = 1
        srcGeom[0]['Line'] = 1001
        srcGeom[0]['Point'] = 1001
        srcGeom[0]['East'] = 1010.0
        srcGeom[0]['North'] = 2005.0
        srcGeom[0]['InUse'] = 1

        recGeom = np.zeros(shape=(1), dtype=rollSurveyModule.pntType1)
        recGeom[0]['Index'] = 1
        recGeom[0]['Line'] = 2001
        recGeom[0]['Point'] = 3001
        recGeom[0]['East'] = 1020.0
        recGeom[0]['North'] = 2025.0
        recGeom[0]['InUse'] = 1

        relationSurvey.output.srcGeom = srcGeom.copy()
        relationSurvey.output.recGeom = recGeom.copy()
        relationSurvey.output.relGeom = np.zeros(shape=(0), dtype=rollSurveyModule.relType2)
        relationSurvey.prepareGeometryRelationBinningLookup()

        noRelSurvey.output.srcGeom = srcGeom.copy()
        noRelSurvey.output.recGeom = recGeom.copy()
        noRelSurvey.output.recGeom[0]['InUse'] = 0

        success = noRelSurvey.binFromGeometryNoRel(False)

        self.assertTrue(success)
        np.testing.assert_allclose(noRelSurvey.output.srcGeom['LocX'], relationSurvey.output.srcGeom['LocX'])
        np.testing.assert_allclose(noRelSurvey.output.srcGeom['LocY'], relationSurvey.output.srcGeom['LocY'])
        np.testing.assert_allclose(noRelSurvey.output.recGeom['LocX'], relationSurvey.output.recGeom['LocX'])
        np.testing.assert_allclose(noRelSurvey.output.recGeom['LocY'], relationSurvey.output.recGeom['LocY'])
        self.assertNotEqual(float(noRelSurvey.output.srcGeom[0]['LocX']), 0.0)
        self.assertNotEqual(float(noRelSurvey.output.recGeom[0]['LocY']), 0.0)

    def testFinalizeLiveBinningOutputsRunsPostProcessingOrClearsAnalysis(self):
        survey = self.createSurvey()
        survey.output.anaOutput = np.ones((1, 1, 1, 12), dtype=np.float32)

        with patch.object(survey, 'calcFoldAndOffsetEssentials') as foldHelper:
            with patch.object(survey, 'calcRmsOffsetValues') as rmsHelper:
                with patch.object(survey, 'calcUniqueFoldValues') as uniqueHelper:
                    with patch.object(survey, 'calcOffsetAndAzimuthDistribution') as offAziHelper:
                        survey.finalizeLiveBinningOutputs(True)

        foldHelper.assert_called_once_with()
        rmsHelper.assert_called_once_with()
        uniqueHelper.assert_called_once_with()
        offAziHelper.assert_called_once_with()
        self.assertIsNotNone(survey.output.anaOutput)

        survey.output.anaOutput = np.ones((1, 1, 1, 12), dtype=np.float32)

        with patch.object(survey, 'calcFoldAndOffsetEssentials') as foldHelper:
            with patch.object(survey, 'calcRmsOffsetValues') as rmsHelper:
                with patch.object(survey, 'calcUniqueFoldValues') as uniqueHelper:
                    with patch.object(survey, 'calcOffsetAndAzimuthDistribution') as offAziHelper:
                        survey.finalizeLiveBinningOutputs(False)

        foldHelper.assert_called_once_with()
        rmsHelper.assert_not_called()
        uniqueHelper.assert_not_called()
        offAziHelper.assert_not_called()
        self.assertIsNone(survey.output.anaOutput)


if __name__ == '__main__':
    unittest.main()
