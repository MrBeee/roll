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


if __name__ == '__main__':
    unittest.main()
