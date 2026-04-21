# coding=utf-8
import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QPointF, QRectF

from .utilities import getQgisApp

QGIS_APP = getQgisApp()

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TEST_DIR)
FAKE_PACKAGE = 'roll_testpkg'


def loadPluginModule(moduleName):
    if FAKE_PACKAGE not in sys.modules:
        package = types.ModuleType(FAKE_PACKAGE)
        package.__path__ = [PLUGIN_ROOT]
        sys.modules[FAKE_PACKAGE] = package

    qualifiedName = f'{FAKE_PACKAGE}.{moduleName}'
    if qualifiedName in sys.modules:
        return sys.modules[qualifiedName]

    filePath = os.path.join(PLUGIN_ROOT, f'{moduleName}.py')
    spec = importlib.util.spec_from_file_location(qualifiedName, filePath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualifiedName] = module
    spec.loader.exec_module(module)
    return module


rollSurveyModule = loadPluginModule('roll_survey')
rollWellModule = loadPluginModule('roll_well')

RollSurvey = rollSurveyModule.RollSurvey
RollWell = rollWellModule.RollWell


class RollWellTransformTest(unittest.TestCase):
    def createSurvey(self, originX=0.0, originY=0.0):
        survey = RollSurvey()
        survey.crs = QgsCoordinateReferenceSystem('EPSG:23095')
        survey.grid.orig.setX(originX)
        survey.grid.orig.setY(originY)
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

    def createWell(self, survey):
        well = RollWell('synthetic.well')
        well.crs = QgsCoordinateReferenceSystem(survey.crs)
        return well

    def readHeaderWithMockedFile(self, well, survey, header):
        sampleData = np.array([[0.0, 0.0, 0.0, 10.0]])

        def pathExists(path):
            return path == well.name

        with patch.object(rollWellModule.os.path, 'exists', side_effect=pathExists):
            with patch.object(rollWellModule.np, 'loadtxt', return_value=sampleData):
                with patch.object(well, 'readWellHeader', return_value=(header, 1)):
                    return well.readHeader(survey.crs, survey.glbTransform)

    def assertPointAlmostEqual(self, point, x, y):
        self.assertAlmostEqual(point.x(), x, places=2)
        self.assertAlmostEqual(point.y(), y, places=2)

    def testReadHeaderKeepsCoordinatesWithIdentityTransform(self):
        survey = self.createSurvey()
        well = self.createWell(survey)
        header = {
            'datum': 'dfe',
            'elevation_units': 'm',
            'elevation': 100.0,
            'surface_coordinates_units': 'm',
            'surface_easting': 1234.5,
            'surface_northing': 6789.0,
        }

        success = self.readHeaderWithMockedFile(well, survey, header)

        self.assertTrue(success)
        self.assertEqual(well.origW.z(), 100.0)
        self.assertPointAlmostEqual(well.origG, 1234.5, 6789.0)
        self.assertPointAlmostEqual(well.origL, 1234.5, 6789.0)

    def testReadHeaderAppliesInverseGlobalTransformToLocalCoordinates(self):
        survey = self.createSurvey(originX=1000.0, originY=2000.0)
        well = self.createWell(survey)
        header = {
            'datum': 'dfe',
            'elevation_units': 'm',
            'elevation': 100.0,
            'surface_coordinates_units': 'm',
            'surface_easting': 1250.0,
            'surface_northing': 2360.0,
        }

        success = self.readHeaderWithMockedFile(well, survey, header)

        self.assertTrue(success)
        self.assertPointAlmostEqual(well.origG, 1250.0, 2360.0)
        self.assertPointAlmostEqual(well.origL, 250.0, 360.0)

        remappedPoint = survey.glbTransform.map(QPointF(well.origL.x(), well.origL.y()))
        self.assertPointAlmostEqual(remappedPoint, well.origG.x(), well.origG.y())

    def testRefreshHeaderFromCurrentStateClearsOriginsOnFailure(self):
        survey = self.createSurvey()
        well = self.createWell(survey)
        well.setSurvey(survey)
        well.origW = rollWellModule.QVector3D(1.0, 2.0, 3.0)
        well.origG = QPointF(4.0, 5.0)
        well.origL = QPointF(6.0, 7.0)

        with patch.object(well, 'readHeader', return_value=False):
            success = well.refreshHeaderFromCurrentState()

        self.assertFalse(success)
        self.assertEqual((well.origW.x(), well.origW.y(), well.origW.z()), (-999.0, -999.0, -999.0))
        self.assertEqual((well.origG.x(), well.origG.y()), (-999.0, -999.0))
        self.assertEqual((well.origL.x(), well.origL.y()), (-999.0, -999.0))

    def testRefreshHeaderFromCurrentStateUsesExplicitSurveyContext(self):
        survey = self.createSurvey(originX=1000.0, originY=2000.0)
        well = self.createWell(survey)
        header = {
            'datum': 'dfe',
            'elevation_units': 'm',
            'elevation': 100.0,
            'surface_coordinates_units': 'm',
            'surface_easting': 1250.0,
            'surface_northing': 2360.0,
        }

        well._surveyRef = None

        sampleData = np.array([[0.0, 0.0, 0.0, 10.0]])

        def pathExists(path):
            return path == well.name

        with patch.object(rollWellModule.os.path, 'exists', side_effect=pathExists):
            with patch.object(rollWellModule.np, 'loadtxt', return_value=sampleData):
                with patch.object(well, 'readWellHeader', return_value=(header, 1)):
                    success = well.refreshHeaderFromCurrentState(
                        survey=survey,
                        surveyCrs=survey.crs,
                        glbTransform=survey.glbTransform,
                    )

        self.assertTrue(success)
        self.assertPointAlmostEqual(well.origG, 1250.0, 2360.0)
        self.assertPointAlmostEqual(well.origL, 250.0, 360.0)

    def testApplySamplingConstraintsClampsStartAndCount(self):
        well = RollWell()
        well.ahdMax = 100.9

        ahd0, dAhd, nAhd = well.applySamplingConstraints(ahd0=150.0, dAhd=15.0, nAhd=12)

        self.assertEqual((ahd0, dAhd, nAhd), (100, 15.0, 1))
        self.assertEqual((well.ahd0, well.dAhd, well.nAhd), (100, 15.0, 1))

    def testApplySamplingConstraintsLimitsPointCountToAvailableDepth(self):
        well = RollWell()
        well.ahdMax = 100.9

        ahd0, dAhd, nAhd = well.applySamplingConstraints(ahd0=10.0, dAhd=15.0, nAhd=12)

        self.assertEqual((ahd0, dAhd, nAhd), (10.0, 15.0, 7))
        self.assertEqual((well.ahd0, well.dAhd, well.nAhd), (10.0, 15.0, 7))


if __name__ == '__main__':
    unittest.main()
