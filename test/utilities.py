# coding=utf-8
import logging
import math
import os
import sys

import numpy as np
# QGIS imports (must run inside QGIS/OSGeo4W Python environment)
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import QRectF, QSize
from qgis.PyQt.QtWidgets import QWidget

LOGGER = logging.getLogger('QGIS')

# Ensure repo root is importable when tests are run directly
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TEST_DIR)
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

# Handle both package and direct-script test execution without falling back
# to the production qgis_interface module on internal import errors.
if __package__:
    from .plugin_loader import loadPluginModule
    from .qgis_interface import QgisInterface
else:
    from test.plugin_loader import loadPluginModule
    from test.qgis_interface import QgisInterface

QGIS_APP = None
CANVAS = None
PARENT = None
IFACE = None


def _toQgsArgv(argv=None):
    argv = sys.argv if argv is None else argv
    qgsArgv = []
    for arg in argv:
        if isinstance(arg, bytes):
            qgsArgv.append(arg)
        else:
            qgsArgv.append(str(arg).encode('utf-8', errors='ignore'))
    return qgsArgv


def getQgisApp():
    """Start one QGIS application instance for tests."""
    global QGIS_APP, CANVAS, PARENT, IFACE                                      # pylint: disable=W0603

    if QGIS_APP is None:
        QGIS_APP = QgsApplication(_toQgsArgv(), True)
        QGIS_APP.initQgis()
        LOGGER.debug(QGIS_APP.showSettings())

    if PARENT is None:
        PARENT = QWidget()

    if CANVAS is None:
        CANVAS = QgsMapCanvas(PARENT)
        CANVAS.resize(QSize(400, 400))

    if IFACE is None:
        IFACE = QgisInterface(CANVAS)

    return QGIS_APP, CANVAS, IFACE, PARENT


def createTestSurvey(name='Test-Survey', outputRect=None):
    rollSurveyModule = loadPluginModule('roll_survey')

    survey = rollSurveyModule.RollSurvey(name)
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
    survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 50.0) if outputRect is None else QRectF(outputRect)
    survey.calcTransforms()
    return survey


def writeMinimalProjectFixture(
    folder,
    projectName='minimal_fixture.roll',
    survey=None,
    includeSurveySidecars=False,
    includeAnalysisSidecars=False,
    includeHistograms=False,
):
    projectServiceModule = loadPluginModule('project_service')
    rollOutputModule = loadPluginModule('roll_output')
    spsModule = loadPluginModule('sps_io_and_qc')

    survey = createTestSurvey('Minimal-Project-Fixture') if survey is None else survey
    projectService = projectServiceModule.ProjectService()
    projectPath = os.path.join(folder, projectName)

    writeResult = projectService.writeProjectXml(projectPath, survey, folder, False, 2)
    if not writeResult.success:
        raise RuntimeError(writeResult.errorText)

    if includeSurveySidecars:
        rpsImport = np.zeros(1, dtype=spsModule.pntType1)
        rpsImport[0]['Line'] = 100.0
        rpsImport[0]['Point'] = 10.0
        rpsImport[0]['Index'] = 1
        rpsImport[0]['Code'] = 'AA'
        rpsImport[0]['East'] = 1000.0
        rpsImport[0]['North'] = 2000.0
        rpsImport[0]['InUse'] = 1

        spsImport = np.zeros(1, dtype=spsModule.pntType1)
        spsImport[0]['Line'] = 200.0
        spsImport[0]['Point'] = 20.0
        spsImport[0]['Index'] = 1
        spsImport[0]['Code'] = 'BB'
        spsImport[0]['East'] = 1100.0
        spsImport[0]['North'] = 2100.0
        spsImport[0]['InUse'] = 1

        recGeom = np.zeros(1, dtype=spsModule.pntType1)
        recGeom[0]['Line'] = 300.0
        recGeom[0]['Point'] = 30.0
        recGeom[0]['Index'] = 1
        recGeom[0]['Code'] = 'CC'
        recGeom[0]['East'] = 1200.0
        recGeom[0]['North'] = 2200.0
        recGeom[0]['InUse'] = 1

        srcGeom = np.zeros(1, dtype=spsModule.pntType1)
        srcGeom[0]['Line'] = 400.0
        srcGeom[0]['Point'] = 40.0
        srcGeom[0]['Index'] = 1
        srcGeom[0]['Code'] = 'DD'
        srcGeom[0]['East'] = 1300.0
        srcGeom[0]['North'] = 2300.0
        srcGeom[0]['InUse'] = 1

        xpsImport = np.zeros(1, dtype=spsModule.relType2)
        xpsImport[0]['SrcLin'] = 200.0
        xpsImport[0]['SrcPnt'] = 20.0
        xpsImport[0]['SrcInd'] = 1
        xpsImport[0]['RecInd'] = 1
        xpsImport[0]['RecLin'] = 100.0
        xpsImport[0]['RecMin'] = 10.0
        xpsImport[0]['RecMax'] = 10.0
        xpsImport[0]['RecNum'] = 1
        xpsImport[0]['Uniq'] = 1
        xpsImport[0]['InSps'] = 1
        xpsImport[0]['InRps'] = 1

        relGeom = np.zeros(1, dtype=spsModule.relType2)
        relGeom[0]['SrcLin'] = 400.0
        relGeom[0]['SrcPnt'] = 40.0
        relGeom[0]['SrcInd'] = 1
        relGeom[0]['RecInd'] = 1
        relGeom[0]['RecLin'] = 300.0
        relGeom[0]['RecMin'] = 30.0
        relGeom[0]['RecMax'] = 30.0
        relGeom[0]['RecNum'] = 1
        relGeom[0]['Uniq'] = 1
        relGeom[0]['InSps'] = 1
        relGeom[0]['InRps'] = 1

        projectService.saveSurveyDataSidecars(
            projectPath,
            rpsImport=rpsImport,
            spsImport=spsImport,
            xpsImport=xpsImport,
            recGeom=recGeom,
            relGeom=relGeom,
            srcGeom=srcGeom,
        )

    if includeAnalysisSidecars:
        dimensions = projectService.calculateAnalysisDimensions(survey)
        output = rollOutputModule.RollOutput()
        output.binOutput = np.ones((dimensions.nx, dimensions.ny), dtype=np.float32)
        output.minOffset = np.full((dimensions.nx, dimensions.ny), 50.0, dtype=np.float32)
        output.maxOffset = np.full((dimensions.nx, dimensions.ny), 150.0, dtype=np.float32)
        output.rmsOffset = np.full((dimensions.nx, dimensions.ny), 75.0, dtype=np.float32)

        if includeHistograms:
            output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
            histogramCols = int(math.ceil(150.0 / 100.0)) + 1
            output.ofAziHist = np.ones((360 // 5, histogramCols), dtype=np.float32)

        projectService.saveAnalysisSidecars(projectPath, output, includeHistograms=includeHistograms)

    return projectPath
