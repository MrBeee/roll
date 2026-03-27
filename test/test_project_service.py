# coding=utf-8
import gc
import os
import tempfile
import unittest

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

projectServiceModule = loadPluginModule('project_service')
rollOutputModule = loadPluginModule('roll_output')
rollSurveyModule = loadPluginModule('roll_survey')

ProjectService = projectServiceModule.ProjectService
RollOutput = rollOutputModule.RollOutput
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

    def testCalculateAnalysisDimensionsUsesSurveyOutputAndBinSize(self):
        service = ProjectService()
        survey = self.createSurvey()

        dims = service.calculateAnalysisDimensions(survey)

        self.assertEqual((dims.nx, dims.ny), (10, 4))

    def testSaveAndLoadAnalysisSidecars(self):
        service = ProjectService()
        output = RollOutput()
        output.binOutput = np.arange(40, dtype=np.float32).reshape(10, 4)
        output.minOffset = np.full((10, 4), 50.0, dtype=np.float32)
        output.maxOffset = np.full((10, 4), 250.0, dtype=np.float32)
        output.rmsOffset = np.full((10, 4), 125.0, dtype=np.float32)
        output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        output.ofAziHist = np.ones((360 // 5, 3), dtype=np.float32)

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'project_service.roll')

            success = service.saveAnalysisSidecars(projectPath, output, includeHistograms=True)

            self.assertTrue(success)
            self.assertTrue(service.loadSizedArraySidecar(projectPath, '.bin.npy', (10, 4)).valid)
            self.assertTrue(service.loadSizedArraySidecar(projectPath, '.min.npy', (10, 4)).valid)
            self.assertTrue(service.loadSizedArraySidecar(projectPath, '.max.npy', (10, 4)).valid)
            self.assertTrue(service.loadSizedArraySidecar(projectPath, '.rms.npy', (10, 4)).valid)
            self.assertTrue(service.loadHistogramSidecar(projectPath, '.off.npy', 2).valid)
            self.assertTrue(service.loadHistogramSidecar(projectPath, '.azi.npy', 360 // 5).valid)

    def testSaveSurveyDataSidecars(self):
        service = ProjectService()
        rps = np.arange(5, dtype=np.float32)
        rec = np.arange(8, dtype=np.float32).reshape(4, 2)

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'project_service.roll')

            success = service.saveSurveyDataSidecars(projectPath, rpsImport=rps, recGeom=rec)

            self.assertTrue(success)
            np.testing.assert_array_equal(service.loadArraySidecar(projectPath, '.rps.npy').array, rps)
            np.testing.assert_array_equal(service.loadArraySidecar(projectPath, '.rec.npy').array, rec)

    def testOpenAnalysisMemmapReturnsFlattenedView(self):
        service = ProjectService()
        shape = (2, 3, 1, 13)

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'project_service.roll')
            path = service.sidecarPath(projectPath, '.ana.npy')
            memmap = np.memmap(path, dtype=np.float32, mode='w+', shape=shape)
            memmap.fill(3.0)
            memmap.flush()

            result = service.openAnalysisMemmap(projectPath, shape, mode='r+')

            self.assertTrue(result.success)
            self.assertEqual(result.memmap.shape, shape)
            self.assertEqual(result.an2Output.shape, (shape[0] * shape[1] * shape[2], shape[3]))

            result.memmap.flush()
            del result
            del memmap
            gc.collect()

    def testLoadProjectSidecarsLoadsBatchState(self):
        service = ProjectService()
        survey = self.createSurvey()
        survey.grid.fold = 2

        binOutput = np.array(
            [
                [0, 1, 2, 1],
                [2, 2, 1, 0],
                [1, 0, 2, 2],
                [0, 1, 1, 2],
                [2, 1, 0, 1],
                [1, 2, 2, 0],
                [0, 1, 2, 2],
                [2, 0, 1, 1],
                [1, 2, 0, 2],
                [0, 1, 1, 0],
            ],
            dtype=np.float32,
        )
        minOffset = np.full((10, 4), 50.0, dtype=np.float32)
        maxOffset = np.full((10, 4), 150.0, dtype=np.float32)
        rmsOffset = np.full((10, 4), 75.0, dtype=np.float32)
        offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 3.0]], dtype=np.float32)
        ofAziHist = np.ones((360 // 5, 3), dtype=np.float32)
        rpsDtype = np.dtype([('Record', np.int32), ('Line', np.int32)])
        relDtype = np.dtype([('Record', np.int32), ('Src', np.int32)])
        rpsImport = np.array([(1, 100), (2, 200)], dtype=rpsDtype)
        relGeom = np.array([(3, 300), (4, 400)], dtype=relDtype)
        spsImport = np.arange(6, dtype=np.float32).reshape(3, 2)
        xpsImport = np.arange(4, dtype=np.float32).reshape(2, 2)
        recGeom = np.arange(8, dtype=np.float32).reshape(4, 2)
        srcGeom = np.arange(10, dtype=np.float32).reshape(5, 2)

        output = RollOutput()
        output.binOutput = binOutput
        output.minOffset = minOffset
        output.maxOffset = maxOffset
        output.rmsOffset = rmsOffset
        output.offstHist = offstHist
        output.ofAziHist = ofAziHist

        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = os.path.join(tempDir, 'project_service.roll')
            service.writeProjectXml(projectPath, survey, tempDir, False, 2)
            service.saveAnalysisSidecars(projectPath, output, includeHistograms=True)
            service.saveSurveyDataSidecars(
                projectPath,
                rpsImport=rpsImport,
                spsImport=spsImport,
                xpsImport=xpsImport,
                recGeom=recGeom,
                relGeom=relGeom,
                srcGeom=srcGeom,
            )

            anaShape = (10, 4, 2, 13)
            anaPath = service.sidecarPath(projectPath, '.ana.npy')
            anaMemmap = np.memmap(anaPath, dtype=np.float32, mode='w+', shape=anaShape)
            anaMemmap.fill(5.0)
            anaMemmap.flush()

            result = service.loadProjectSidecars(projectPath, survey)

            self.assertEqual((result.dimensions.nx, result.dimensions.ny), (10, 4))
            self.assertIsNotNone(result.binOutput)
            self.assertEqual(result.maximumFold, 2)
            self.assertEqual(result.minimumFold, 0)
            self.assertTrue(result.analysisMemmapResult.success)
            self.assertEqual(result.analysisMemmapResult.memmap.shape, anaShape)
            self.assertEqual(result.analysisMemmapResult.an2Output.shape, (10 * 4 * 2, 13))
            self.assertIn('RecNum', result.rpsImport.dtype.names)
            self.assertIn('RecNum', result.relGeom.dtype.names)
            np.testing.assert_array_equal(result.spsImport, spsImport)
            np.testing.assert_array_equal(result.xpsImport, xpsImport)
            np.testing.assert_array_equal(result.recGeom, recGeom)
            np.testing.assert_array_equal(result.srcGeom, srcGeom)
            self.assertTrue(any(message.text.startswith('Loaded : . . . Fold map') for message in result.messages))

            result.analysisMemmapResult.memmap.flush()
            del result
            del anaMemmap
            gc.collect()


if __name__ == '__main__':
    unittest.main()
