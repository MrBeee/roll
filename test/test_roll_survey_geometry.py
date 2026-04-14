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


if __name__ == '__main__':
    unittest.main()
