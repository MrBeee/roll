# coding=utf-8
import os
import sys
import tempfile
import types
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QEvent, QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QPen, QTransform, QVector3D
from qgis.PyQt.QtWidgets import QAction

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey, getQgisApp, writeMinimalProjectFixture


def _installProcessingTestShim():
    if 'processing' in sys.modules:
        return

    processingModule = types.ModuleType('processing')
    processingCoreModule = types.ModuleType('processing.core')
    processingCoreProcessingModule = types.ModuleType('processing.core.Processing')

    class _Processing:
        @staticmethod
        def initialize():
            return None

    processingCoreProcessingModule.Processing = _Processing
    processingCoreModule.Processing = processingCoreProcessingModule
    processingModule.core = processingCoreModule
    processingModule.run = lambda *args, **kwargs: None

    sys.modules['processing'] = processingModule
    sys.modules['processing.core'] = processingCoreModule
    sys.modules['processing.core.Processing'] = processingCoreProcessingModule


_installProcessingTestShim()

QGIS_APP, _, IFACE, _ = getQgisApp()

rollMainWindowModule = loadPluginModule('roll_main_window')
rollSurveyModule = loadPluginModule('roll_survey')
settingsModule = loadPluginModule('settings')
spsImportDialogModule = loadPluginModule('sps_import_dialog')
spsModule = loadPluginModule('sps_io_and_qc')
configModule = loadPluginModule('config')
appSettingsModule = loadPluginModule('app_settings')
auxFunctionsModule = loadPluginModule('aux_functions')
workerThreadsModule = loadPluginModule('worker_threads')
binningWorkerMixinModule = loadPluginModule('binning_worker_mixin')
workerOperationControllerModule = loadPluginModule('worker_operation_controller')
propertyPanelControllerModule = loadPluginModule('property_panel_controller')
printPresentationControllerModule = loadPluginModule('print_presentation_controller')
layoutTabModule = loadPluginModule('roll_main_window_create_layout_tab')
layout3DModule = loadPluginModule('layout_3D')
myPoint3DModule = loadPluginModule('my_point3D')
marineWizardModule = loadPluginModule('marine_wizard')

RollMainWindow = rollMainWindowModule.RollMainWindow
RollSurvey = rollSurveyModule.RollSurvey
readSettings = settingsModule.readSettings
writeSettings = settingsModule.writeSettings
SpsImportDialog = spsImportDialogModule.SpsImportDialog
pntType1 = spsModule.pntType1
pntType4 = spsModule.pntType4
relType2 = spsModule.relType2
config = configModule
myPrint = auxFunctionsModule.myPrint
isDebugLoggingEnabled = appSettingsModule.isDebugLoggingEnabled
isShowSummariesEnabled = appSettingsModule.isShowSummariesEnabled
isUseExperimentalEnabled = appSettingsModule.isUseExperimentalEnabled
readStoredDebugSetting = appSettingsModule.readStoredDebugSetting
readStoredDebugpySetting = appSettingsModule.readStoredDebugpySetting
readStoredShowSummariesSetting = appSettingsModule.readStoredShowSummariesSetting
readStoredUseExperimentalSetting = appSettingsModule.readStoredUseExperimentalSetting
setActiveDebugLogging = appSettingsModule.setActiveDebugLogging
setActiveShowSummaries = appSettingsModule.setActiveShowSummaries
setActiveUseExperimental = appSettingsModule.setActiveUseExperimental
BinningFromTemplatesRequest = workerThreadsModule.BinningFromTemplatesRequest
BinningFromTemplatesResult = workerThreadsModule.BinningFromTemplatesResult
BinningFromGeometryRequest = workerThreadsModule.BinningFromGeometryRequest
BinningFromGeometryResult = workerThreadsModule.BinningFromGeometryResult
GeometryFromTemplatesRequest = workerThreadsModule.GeometryFromTemplatesRequest
GeometryProfilingPayload = workerThreadsModule.GeometryProfilingPayload
GeometryFromTemplatesResult = workerThreadsModule.GeometryFromTemplatesResult
CfpFromTemplatesRequest = workerThreadsModule.CfpFromTemplatesRequest
CfpFromTemplatesResult = workerThreadsModule.CfpFromTemplatesResult
CfpFromGeometryTablesRequest = workerThreadsModule.CfpFromGeometryTablesRequest
CfpFromGeometryTablesResult = workerThreadsModule.CfpFromGeometryTablesResult
CfpAmplitudeMapRequest = workerThreadsModule.CfpAmplitudeMapRequest
CfpAmplitudeMapResult = workerThreadsModule.CfpAmplitudeMapResult
BinningWorker = workerThreadsModule.BinningWorker
BinFromGeometryWorker = workerThreadsModule.BinFromGeometryWorker
GeometryWorker = workerThreadsModule.GeometryWorker
CfpFromTemplatesWorker = workerThreadsModule.CfpFromTemplatesWorker
CfpFromGeometryTablesWorker = workerThreadsModule.CfpFromGeometryTablesWorker
CfpAmplitudeMapWorker = workerThreadsModule.CfpAmplitudeMapWorker
Layout3DWidget = layout3DModule.Layout3DWidget


class Layout3DHelperTest(unittest.TestCase):
    def testDataPointsLocalBoundingRectPreservesTightLocalFootprintForRotatedGlobalData(self):
        localCorners = np.array(
            [
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 5.0],
                [0.0, 5.0],
            ],
            dtype=np.float64,
        )
        transform = QTransform()
        transform.translate(1250.0, 2450.0)
        transform.rotate(30.0)

        globalCorners = np.array([transform.map(x, y) for x, y in localCorners], dtype=np.float64)
        dataPoints = [(globalCorners[:, 0], globalCorners[:, 1])]
        survey = SimpleNamespace(glbTransform=transform)

        tightLocalBbox = Layout3DWidget._dataPointsLocalBoundingRect(survey, dataPoints)
        inflatedCornerMappedBbox = Layout3DWidget._mapGlobalBboxToLocal(survey, *Layout3DWidget._dataPointsBoundingRect(dataPoints))

        self.assertIsNotNone(tightLocalBbox)
        self.assertAlmostEqual(tightLocalBbox[0], 0.0, places=6)
        self.assertAlmostEqual(tightLocalBbox[1], 0.0, places=6)
        self.assertAlmostEqual(tightLocalBbox[2], 10.0, places=6)
        self.assertAlmostEqual(tightLocalBbox[3], 5.0, places=6)
        self.assertLess(tightLocalBbox[0], tightLocalBbox[2])
        self.assertLess(tightLocalBbox[1], tightLocalBbox[3])

        self.assertLess(inflatedCornerMappedBbox[0], tightLocalBbox[0])
        self.assertLess(inflatedCornerMappedBbox[1], tightLocalBbox[1])
        self.assertGreater(inflatedCornerMappedBbox[2], tightLocalBbox[2])
        self.assertGreater(inflatedCornerMappedBbox[3], tightLocalBbox[3])

    def testDrawSpiderOverlayExtendsCachedDepthRangeToIncludeCmpDepths(self):
        widget = Layout3DWidget()
        try:
            widget._dataZMin = -100.0
            widget._dataZMax = -10.0

            spiderData = {
                'srcX': np.array([100.0, 110.0], dtype=np.float64),
                'srcY': np.array([200.0, 210.0], dtype=np.float64),
                'srcZ': np.array([0.0, -1200.0], dtype=np.float64),
                'recX': np.array([120.0, 110.0], dtype=np.float64),
                'recY': np.array([220.0, 210.0], dtype=np.float64),
                'recZ': np.array([0.0, -1350.0], dtype=np.float64),
            }
            survey = SimpleNamespace(glbTransform=None)

            widget._drawSpiderOverlay(survey, False, spiderData)

            self.assertEqual(widget._dataZMin, -1350.0)
            self.assertEqual(widget._dataZMax, 0.0)
            self.assertEqual(len(widget._artists), 5)
        finally:
            widget.close()
            widget.deleteLater()

    def testDrawPointSetsUsesProvidedDepthValues(self):
        class ScatterStub:
            def __init__(self):
                self.clipOn = None

            def set_clip_on(self, enabled):
                self.clipOn = enabled

        class AxesStub:
            def __init__(self):
                self.calls = []

            def scatter(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return ScatterStub()

        widget = Layout3DWidget()
        try:
            widget._axes = AxesStub()
            widget._artists = []
            survey = SimpleNamespace(glbTransform=None)

            widget._drawPointSets(
                survey,
                False,
                [
                    dict(
                        xs=np.array([10.0, 20.0], dtype=np.float64),
                        ys=np.array([30.0, 40.0], dtype=np.float64),
                        zs=np.array([-100.0, -250.0], dtype=np.float64),
                        symbol='o',
                        size=5.0,
                        faceColor='#ff0000',
                        edgeColor='#000000',
                    )
                ],
            )

            self.assertEqual(len(widget._axes.calls), 1)
            args, _ = widget._axes.calls[0]
            np.testing.assert_allclose(args[2], np.array([-100.0, -250.0], dtype=np.float64))
        finally:
            widget.close()
            widget.deleteLater()

    def testUpdateFromSurveyExpandsDepthRangeForPointSets(self):
        widget = Layout3DWidget()
        try:
            captured = {}
            survey = SimpleNamespace(
                glbTransform=None,
                binning=SimpleNamespace(method=None),
                boundingRect=lambda: QRectF(0.0, 0.0, 10.0, 10.0),
            )

            with patch.object(widget, '_applyAxisLimits', side_effect=lambda *args: captured.update(zMin=args[4], zMax=args[5])):
                widget.updateFromSurvey(
                    survey,
                    False,
                    showTemplates=False,
                    pointSets=[dict(xs=np.array([1.0], dtype=np.float64), ys=np.array([2.0], dtype=np.float64), zs=np.array([-4500.0], dtype=np.float64))],
                    dataPoints=[(np.array([1.0], dtype=np.float64), np.array([2.0], dtype=np.float64))],
                )

            self.assertEqual(captured['zMin'], -4500.0)
            self.assertEqual(captured['zMax'], 0.0)
        finally:
            widget.close()
            widget.deleteLater()

    def testCollectSeedGeometriesIncludesFixedGridAsInvariant3DGeometry(self):
        widget = Layout3DWidget()
        try:
            growList = [
                SimpleNamespace(steps=2, increment=QVector3D(10.0, 0.0, 0.0)),
                SimpleNamespace(steps=2, increment=QVector3D(0.0, 20.0, 0.0)),
                SimpleNamespace(steps=3, increment=QVector3D(0.0, 0.0, -5.0)),
            ]
            fixedGridSeed = SimpleNamespace(
                type=rollSurveyModule.SeedType.fixedGrid,
                origin=QVector3D(100.0, 200.0, 0.0),
                grid=SimpleNamespace(growList=growList),
                pointArray=np.array(
                    [
                        [100.0, 200.0, 0.0],
                        [100.0, 200.0, -5.0],
                        [100.0, 200.0, -10.0],
                        [100.0, 220.0, 0.0],
                        [100.0, 220.0, -5.0],
                        [100.0, 220.0, -10.0],
                        [110.0, 200.0, 0.0],
                        [110.0, 200.0, -5.0],
                        [110.0, 200.0, -10.0],
                        [110.0, 220.0, 0.0],
                        [110.0, 220.0, -5.0],
                        [110.0, 220.0, -10.0],
                    ],
                    dtype=np.float32,
                ),
                pointList=[],
                color=QColor('#7787A4D9'),
            )
            survey = SimpleNamespace(
                glbTransform=None,
                blockList=[
                    SimpleNamespace(
                        templateList=[SimpleNamespace(seedList=[fixedGridSeed])],
                    )
                ],
            )

            items = widget._collectSeedGeometries(survey, False)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['kind'], 'fixedGrid')
            np.testing.assert_allclose(items[0]['points'], fixedGridSeed.pointArray.astype(np.float64))
            np.testing.assert_allclose(items[0]['samplePoints'], fixedGridSeed.pointArray.astype(np.float64))
            self.assertEqual(items[0]['segments'].shape, (4, 2, 3))
            np.testing.assert_allclose(items[0]['segments'][0, 0], np.array([100.0, 200.0, 0.0], dtype=np.float64))
            np.testing.assert_allclose(items[0]['segments'][0, 1], np.array([100.0, 200.0, -10.0], dtype=np.float64))
            np.testing.assert_allclose(items[0]['segments'][-1, 0], np.array([110.0, 220.0, 0.0], dtype=np.float64))
            np.testing.assert_allclose(items[0]['segments'][-1, 1], np.array([110.0, 220.0, -10.0], dtype=np.float64))
        finally:
            widget.close()
            widget.deleteLater()

    def testCollectSeedGeometriesBuildsFixedGridFromGrowListWhenPointArrayMissing(self):
        widget = Layout3DWidget()
        try:
            growList = [
                SimpleNamespace(steps=2, increment=QVector3D(10.0, 0.0, 0.0)),
                SimpleNamespace(steps=2, increment=QVector3D(0.0, 20.0, 0.0)),
                SimpleNamespace(steps=3, increment=QVector3D(0.0, 0.0, -5.0)),
            ]
            fixedGridSeed = SimpleNamespace(
                type=rollSurveyModule.SeedType.fixedGrid,
                origin=QVector3D(100.0, 200.0, 0.0),
                grid=SimpleNamespace(
                    growList=growList,
                    iterPoints=lambda origin: [
                        QVector3D(origin.x() + dx, origin.y() + dy, origin.z() + dz)
                        for dx in (0.0, 10.0)
                        for dy in (0.0, 20.0)
                        for dz in (0.0, -5.0, -10.0)
                    ],
                ),
                pointArray=None,
                pointList=[],
                color=QColor('#7787A4D9'),
            )
            survey = SimpleNamespace(
                glbTransform=None,
                blockList=[
                    SimpleNamespace(
                        templateList=[SimpleNamespace(seedList=[fixedGridSeed])],
                    )
                ],
            )

            items = widget._collectSeedGeometries(survey, False)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['kind'], 'fixedGrid')
            self.assertEqual(items[0]['points'].shape, (12, 3))
            self.assertEqual(items[0]['samplePoints'].shape, (12, 3))
            self.assertEqual(items[0]['segments'].shape, (4, 2, 3))
            np.testing.assert_allclose(items[0]['points'][0], np.array([100.0, 200.0, 0.0], dtype=np.float64))
            np.testing.assert_allclose(items[0]['points'][-1], np.array([110.0, 220.0, -10.0], dtype=np.float64))
        finally:
            widget.close()
            widget.deleteLater()

    def testCollectSeedGeometriesTransformsFixedGridSegmentsInGlobalMode(self):
        widget = Layout3DWidget()
        try:
            growList = [
                SimpleNamespace(steps=2, increment=QVector3D(10.0, 0.0, 0.0)),
                SimpleNamespace(steps=2, increment=QVector3D(0.0, 20.0, 0.0)),
                SimpleNamespace(steps=3, increment=QVector3D(0.0, 0.0, -5.0)),
            ]
            fixedGridSeed = SimpleNamespace(
                type=rollSurveyModule.SeedType.fixedGrid,
                origin=QVector3D(100.0, 200.0, 0.0),
                grid=SimpleNamespace(growList=growList),
                pointArray=np.array(
                    [
                        [100.0, 200.0, 0.0],
                        [100.0, 200.0, -5.0],
                        [100.0, 200.0, -10.0],
                        [100.0, 220.0, 0.0],
                        [100.0, 220.0, -5.0],
                        [100.0, 220.0, -10.0],
                        [110.0, 200.0, 0.0],
                        [110.0, 200.0, -5.0],
                        [110.0, 200.0, -10.0],
                        [110.0, 220.0, 0.0],
                        [110.0, 220.0, -5.0],
                        [110.0, 220.0, -10.0],
                    ],
                    dtype=np.float32,
                ),
                pointList=[],
                color=QColor('#7787A4D9'),
            )
            transform = QTransform()
            transform.translate(1250.0, 2450.0)
            transform.rotate(30.0)
            survey = SimpleNamespace(
                glbTransform=transform,
                blockList=[
                    SimpleNamespace(
                        templateList=[SimpleNamespace(seedList=[fixedGridSeed])],
                    )
                ],
            )

            items = widget._collectSeedGeometries(survey, True)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['segments'].shape, (4, 2, 3))

            expectedStart = np.array(transform.map(100.0, 200.0), dtype=np.float64)
            expectedEnd = np.array(transform.map(110.0, 220.0), dtype=np.float64)
            np.testing.assert_allclose(items[0]['segments'][0, 0, :2], expectedStart)
            np.testing.assert_allclose(items[0]['segments'][-1, 0, :2], expectedEnd)

            expectedY0 = transform.map(100.0, 200.0)[1]
            self.assertAlmostEqual(float(items[0]['segments'][0, 1, 1]), expectedY0)
        finally:
            widget.close()
            widget.deleteLater()

    def testPgSymbolToMplMarkerMapsCommonPyqtgraphSymbols(self):
        self.assertEqual(layout3DModule._pgSymbolToMplMarker('o'), 'o')
        self.assertEqual(layout3DModule._pgSymbolToMplMarker('t1'), '^')
        self.assertEqual(layout3DModule._pgSymbolToMplMarker('t2'), '>')
        self.assertEqual(layout3DModule._pgSymbolToMplMarker('star'), '*')
        self.assertEqual(layout3DModule._pgSymbolToMplMarker('crosshair'), 'x')

    def testRenderBaseLayersDrawsAreasInJustBlocksMode(self):
        class FakePainter:
            def __init__(self):
                self.rects = []

            def worldTransform(self):
                return QTransform()

            def setPen(self, *_):
                pass

            def setBrush(self, *_):
                pass

            def drawRect(self, rect):
                self.rects.append(QRectF(rect))

        class FakeOption:
            @staticmethod
            def levelOfDetailFromTransform(_):
                return 1.0

        invariantCalls = []
        block = SimpleNamespace(
            boundingBox=QRectF(0.0, 0.0, 100.0, 50.0),
            recBoundingRect=QRectF(1.0, 2.0, 10.0, 11.0),
            srcBoundingRect=QRectF(3.0, 4.0, 12.0, 13.0),
            cmpBoundingRect=QRectF(5.0, 6.0, 14.0, 15.0),
            templateList=[SimpleNamespace(totTemplateRect=QRectF(0.0, 0.0, 1.0, 1.0))],
        )
        survey = SimpleNamespace(
            blockList=[block],
            paintMode=rollSurveyModule.PaintMode.justBlocks,
            paintDetails=(
                rollSurveyModule.PaintDetails.recArea |  # noqa: W503, W504
                rollSurveyModule.PaintDetails.srcArea |  # noqa: W503, W504
                rollSurveyModule.PaintDetails.cmpArea
            ),
            lodScale=1.0,
            viewRect=lambda: QRectF(-10.0, -10.0, 200.0, 200.0),
            boundingRect=lambda: QRectF(-20.0, -20.0, 240.0, 240.0),
            _renderInvariantSeedsIntoBase=lambda *args, **kwargs: invariantCalls.append((args, kwargs)),
        )
        painter = FakePainter()
        option = FakeOption()
        appSettings = SimpleNamespace(
            lod0=0.1,
            recAreaPen='rec-pen',
            recAreaColor='#110000ff',
            srcAreaPen='src-pen',
            srcAreaColor='#11ff0000',
            cmpAreaPen='cmp-pen',
            cmpAreaColor='#1100ff00',
        )

        with patch.object(rollSurveyModule, 'getActiveAppSettings', return_value=appSettings):
            rollSurveyModule.RollSurvey._renderBaseLayers(survey, painter, option)

        self.assertEqual(painter.rects, [block.recBoundingRect, block.srcBoundingRect, block.cmpBoundingRect, block.boundingBox])
        self.assertEqual(invariantCalls, [])


class MyPoint3DParameterTest(unittest.TestCase):
    def testAxisEditEmitsParentValueChanged(self):
        param = myPoint3DModule.MyPoint3DParameter(name='Seed origin', value=QVector3D(10.0, 20.0, -5.0))
        received = []

        def onValueChanged(changedParam, value):
            received.append((changedParam, QVector3D(value)))

        param.sigValueChanged.connect(onValueChanged)

        param.child('X').setValue(15.0)

        self.assertEqual(len(received), 1)
        self.assertIs(received[0][0], param)
        self.assertEqual((received[0][1].x(), received[0][1].y(), received[0][1].z()), (15.0, 20.0, -5.0))


class ProjectSidecarsTest(unittest.TestCase):
    def setUp(self):
        self.mainWindow = RollMainWindow(IFACE, standaloneMode=True)

    def tearDown(self):
        if self.mainWindow is not None:
            self.mainWindow.textEdit.document().setModified(False)
            self.mainWindow.close()
            self.mainWindow.deleteLater()
        self.mainWindow = None

    def createSurvey(self):
        return createTestSurvey('Phase0-Sidecars', QRectF(0.0, 0.0, 100.0, 50.0))

    def testPlotLayoutDrawsCmpMarkerWhenSpiderBinHasNoLegs(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.binTransform = QTransform()
        self.mainWindow.survey.glbTransform = None
        self.mainWindow.layoutImItem = None
        self.mainWindow.imageType = 0
        self.mainWindow.output.anaOutput = object()
        self.mainWindow.output.binOutput = object()
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(12, 34)
        self.mainWindow.spiderSrcX = None
        self.mainWindow.spiderRecX = None
        self.mainWindow.spiderText = pg.TextItem(text='spiderLabel')
        self.mainWindow.spiderText.setPos(99.0, 101.0)

        self.mainWindow.tbArea.setChecked(False)
        self.mainWindow.tbTemplat.setChecked(False)
        self.mainWindow.tbSpider.setChecked(True)
        self.mainWindow.tbSpsList.setChecked(False)
        self.mainWindow.tbRpsList.setChecked(False)
        self.mainWindow.tbSrcList.setChecked(False)
        self.mainWindow.tbRecList.setChecked(False)

        plotResult = MagicMock()
        with patch.object(self.mainWindow.layoutWidget, 'plot', return_value=plotResult) as plot:
            self.mainWindow.plotLayout()

        plot.assert_called_once_with(
            x=[12.0],
            y=[34.0],
            symbol='o',
            symbolSize=6,
            symbolPen=(0, 0, 0, 100),
            symbolBrush='g',
        )

    def testPlotLayoutDrawsCfpTargetMarkerAtBinningAreaCenterWhenAreaShown(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.cfp.useBinningAreaCenter = True
        self.mainWindow.survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 50.0)
        self.mainWindow.layoutImItem = None
        self.mainWindow.imageType = 0
        self.mainWindow.output.anaOutput = None
        self.mainWindow.output.binOutput = None

        self.mainWindow.tbArea.setChecked(True)
        self.mainWindow.tbTemplat.setChecked(False)
        self.mainWindow.tbSpider.setChecked(False)
        self.mainWindow.tbSpsList.setChecked(False)
        self.mainWindow.tbRpsList.setChecked(False)
        self.mainWindow.tbSrcList.setChecked(False)
        self.mainWindow.tbRecList.setChecked(False)

        with patch.object(self.mainWindow.layoutWidget, 'plot') as plot:
            self.mainWindow.plotLayout()

        targetCall = None
        for call in plot.call_args_list:
            kwargs = call.kwargs
            if kwargs.get('symbol') == 'd' and kwargs.get('symbolSize') == 12:
                targetCall = call
                break

        self.assertIsNotNone(targetCall)
        self.assertEqual(targetCall.kwargs['x'], [50.0])
        self.assertEqual(targetCall.kwargs['y'], [25.0])
        self.assertEqual(targetCall.kwargs['symbolPen'], (0, 0, 0, 100))
        self.assertEqual(targetCall.kwargs['symbolBrush'], (170, 0, 220, 100))

    def testPlotLayoutDrawsCfpTargetMarkerAtSpecificAnalysisLocationWhenAreaShown(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.cfp.useBinningAreaCenter = False
        self.mainWindow.survey.cfp.analysisLocation = QVector3D(12.0, 34.0, 0.0)
        self.mainWindow.layoutImItem = None
        self.mainWindow.imageType = 0
        self.mainWindow.output.anaOutput = None
        self.mainWindow.output.binOutput = None

        self.mainWindow.tbArea.setChecked(True)
        self.mainWindow.tbTemplat.setChecked(False)
        self.mainWindow.tbSpider.setChecked(False)
        self.mainWindow.tbSpsList.setChecked(False)
        self.mainWindow.tbRpsList.setChecked(False)
        self.mainWindow.tbSrcList.setChecked(False)
        self.mainWindow.tbRecList.setChecked(False)

        with patch.object(self.mainWindow.layoutWidget, 'plot') as plot:
            self.mainWindow.plotLayout()

        targetCall = None
        for call in plot.call_args_list:
            kwargs = call.kwargs
            if kwargs.get('symbol') == 'd' and kwargs.get('symbolSize') == 12:
                targetCall = call
                break

        self.assertIsNotNone(targetCall)
        self.assertEqual(targetCall.kwargs['x'], [12.0])
        self.assertEqual(targetCall.kwargs['y'], [34.0])
        self.assertEqual(targetCall.kwargs['symbolPen'], (0, 0, 0, 100))
        self.assertEqual(targetCall.kwargs['symbolBrush'], (170, 0, 220, 100))

    def suppressModalDialogs(self):
        messageBox = rollMainWindowModule.QMessageBox
        dialogPatches = (
            patch.object(messageBox, 'information', return_value=messageBox.StandardButton.Ok),
            patch.object(messageBox, 'warning', return_value=messageBox.StandardButton.Discard),
            patch.object(messageBox, 'question', return_value=messageBox.StandardButton.Yes),
        )

        for dialogPatch in dialogPatches:
            dialogPatch.start()
            self.addCleanup(dialogPatch.stop)

    def writeProjectFixture(self, folder):
        return writeMinimalProjectFixture(folder, 'phase0_sidecars.roll', survey=self.createSurvey())

    def testMinimalProjectFixtureLoadsSurveyAndAnalysisSidecars(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = writeMinimalProjectFixture(
                tempDir,
                'phase0_minimal_fixture.roll',
                survey=self.createSurvey(),
                includeSurveySidecars=True,
                includeAnalysisSidecars=True,
                includeHistograms=True,
            )

            success = self.mainWindow.fileLoad(projectPath)

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.rpsImport.shape[0], 1)
        self.assertEqual(self.mainWindow.spsImport.shape[0], 1)
        self.assertEqual(self.mainWindow.recGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.srcGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.relGeom.shape[0], 1)
        self.assertEqual(self.mainWindow.xpsImport.shape[0], 1)
        self.assertIsNotNone(self.mainWindow.output.binOutput)
        self.assertIsNotNone(self.mainWindow.output.minOffset)
        self.assertIsNotNone(self.mainWindow.output.maxOffset)
        self.assertIsNotNone(self.mainWindow.output.rmsOffset)
        self.assertIsNotNone(self.mainWindow.output.gapOffset)
        self.assertIsNotNone(self.mainWindow.output.offstHist)
        self.assertIsNotNone(self.mainWindow.output.ofAziHist)

    def testCreatePlotWidgetDisablesPyqtgraphExportContextMenu(self):
        plotWidget = self.mainWindow.createPlotWidget('Context menu test')

        try:
            self.assertIsNone(plotWidget.scene().contextMenu)
        finally:
            plotWidget.close()
            plotWidget.deleteLater()

    def testFileLoadIgnoresFoldSidecarWithWrongDimensions(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            np.save(projectPath + '.bin.npy', np.ones((3, 4), dtype=np.float32))

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIsNone(self.mainWindow.output.binOutput)
            self.assertEqual(self.mainWindow.imageType, 0)

    def testFileLoadLoadsFoldSidecarWithExpectedDimensions(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            expected = np.arange(50, dtype=np.float32).reshape(10, 5)
            np.save(projectPath + '.bin.npy', expected)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIsNotNone(self.mainWindow.output.binOutput)
            self.assertEqual(self.mainWindow.output.binOutput.shape, expected.shape)
            self.assertEqual(self.mainWindow.output.maximumFold, expected.max())
            self.assertEqual(self.mainWindow.imageType, 1)

    def testFileLoadLoadsSurveySidecarsAndRebuildsPointState(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            rpsImport = np.zeros(2, dtype=pntType1)
            rpsImport[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0)
            rpsImport[1] = (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 1, 0.0, 0.0)

            spsImport = np.zeros(1, dtype=pntType1)
            spsImport[0] = (200.0, 20.0, 1, 'BB', 0.0, 1100.0, 2100.0, 0.0, 1, 1, 1, 0.0, 0.0)

            recGeom = np.zeros(1, dtype=pntType1)
            recGeom[0] = (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0)

            srcGeom = np.zeros(1, dtype=pntType1)
            srcGeom[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 1, 1, 1, 0.0, 0.0)

            xpsImport = np.zeros(1, dtype=relType2)
            xpsImport[0] = (200.0, 20.0, 1, 1, 100.0, 10.0, 11.0, 1, 1, 1, 1)

            relGeom = np.zeros(1, dtype=relType2)
            relGeom[0] = (400.0, 40.0, 1, 1, 300.0, 30.0, 31.0, 1, 1, 1, 1)

            self.mainWindow.projectService.saveSurveyDataSidecars(
                projectPath,
                rpsImport=rpsImport,
                spsImport=spsImport,
                xpsImport=xpsImport,
                recGeom=recGeom,
                relGeom=relGeom,
                srcGeom=srcGeom,
            )

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.rpsImport.shape[0], 2)
            self.assertEqual(self.mainWindow.spsImport.shape[0], 1)
            self.assertEqual(self.mainWindow.recGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.srcGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.relGeom.shape[0], 1)
            self.assertEqual(self.mainWindow.xpsImport.shape[0], 1)
            self.assertIs(self.mainWindow.sessionState.rpsImport, self.mainWindow.rpsImport)
            self.assertIs(self.mainWindow.sessionState.spsImport, self.mainWindow.spsImport)
            self.assertIs(self.mainWindow.sessionState.xpsImport, self.mainWindow.xpsImport)
            self.assertIs(self.mainWindow.sessionState.recGeom, self.mainWindow.recGeom)
            self.assertIs(self.mainWindow.sessionState.srcGeom, self.mainWindow.srcGeom)
            self.assertIs(self.mainWindow.sessionState.relGeom, self.mainWindow.relGeom)
            self.assertTrue(self.mainWindow.actionRpsPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionSpsPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionRecPoints.isEnabled())
            self.assertTrue(self.mainWindow.actionSrcPoints.isEnabled())
            self.assertFalse(self.mainWindow.actionRpsPoints.isChecked())
            self.assertFalse(self.mainWindow.actionSpsPoints.isChecked())
            self.assertFalse(self.mainWindow.actionRecPoints.isChecked())
            self.assertFalse(self.mainWindow.actionSrcPoints.isChecked())
            self.assertEqual(self.mainWindow.rpsLiveE.shape[0], 2)
            self.assertEqual(self.mainWindow.spsLiveE.shape[0], 1)
            self.assertEqual(self.mainWindow.recLiveE.shape[0], 1)
            self.assertEqual(self.mainWindow.srcLiveE.shape[0], 1)
            self.assertIsNotNone(self.mainWindow.rpsBound)
            self.assertIsNotNone(self.mainWindow.spsBound)

    def testFileLoadNormalizesLegacyPointSidecarsWithoutInUse(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            legacyRps = np.zeros(1, dtype=pntType4)
            legacyRps[0] = (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 100, 12, 30, 0, 0)

            legacySrc = np.zeros(1, dtype=pntType4)
            legacySrc[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 100, 12, 30, 0, 0)

            np.save(projectPath + '.rps.npy', legacyRps)
            np.save(projectPath + '.src.npy', legacySrc)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertIn('InUse', self.mainWindow.rpsImport.dtype.names)
            self.assertIn('InUse', self.mainWindow.srcGeom.dtype.names)
            self.assertEqual(self.mainWindow.rpsImport['InUse'].tolist(), [1])
            self.assertEqual(self.mainWindow.srcGeom['InUse'].tolist(), [1])

    def testResetNumpyArraysAndModelsClearsSurveyArraysFromSessionState(self):
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)

        self.mainWindow.resetNumpyArraysAndModels()

        self.assertIsNone(self.mainWindow.sessionState.rpsImport)
        self.assertIsNone(self.mainWindow.sessionState.spsImport)
        self.assertIsNone(self.mainWindow.sessionState.xpsImport)
        self.assertIsNone(self.mainWindow.sessionState.recGeom)
        self.assertIsNone(self.mainWindow.sessionState.srcGeom)
        self.assertIsNone(self.mainWindow.sessionState.relGeom)

    def testSessionBackedArrayPropertiesRefreshDerivedState(self):
        rpsImport = np.array(
            [
                (100.0, 10.0, 1, 'AA', 0.0, 1000.0, 2000.0, 0.0, 1, 1, 1, 0.0, 0.0),
                (101.0, 11.0, 1, 'AA', 0.0, 1010.0, 2010.0, 0.0, 1, 1, 0, 0.0, 0.0),
            ],
            dtype=pntType1,
        )
        recGeom = np.array(
            [
                (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0),
                (301.0, 31.0, 1, 'CC', 0.0, 1210.0, 2210.0, 0.0, 1, 1, 0, 0.0, 0.0),
            ],
            dtype=pntType1,
        )

        self.mainWindow.rpsImport = rpsImport
        self.mainWindow.recGeom = recGeom

        self.assertIs(self.mainWindow.sessionState.rpsImport, rpsImport)
        self.assertIs(self.mainWindow.sessionState.recGeom, recGeom)
        self.assertEqual(self.mainWindow.rpsLiveE.tolist(), [1000.0])
        self.assertEqual(self.mainWindow.rpsDeadE.tolist(), [1010.0])
        self.assertEqual(self.mainWindow.recLiveE.tolist(), [1200.0])
        self.assertEqual(self.mainWindow.recDeadE.tolist(), [1210.0])
        self.assertIsNotNone(self.mainWindow.rpsBound)

    def testFileOpenRecentRemovesMissingFileFromRecentList(self):
        with tempfile.TemporaryDirectory() as tempDir:
            missingProjectPath = os.path.join(tempDir, 'missing.roll')
            self.mainWindow.recentFileList = [missingProjectPath]

            action = self.mainWindow.recentFileActions[0]
            self.assertIsInstance(action, QAction)
            action.setData(missingProjectPath)
            action.setVisible(True)

            action.trigger()

            self.assertEqual(self.mainWindow.recentFileList, [])
            self.assertFalse(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [])

    def testFileOpenRecentLoadsExistingFile(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.recentFileList = [projectPath]
            self.mainWindow.updateRecentFileActions()

            action = self.mainWindow.recentFileActions[0]
            self.assertIsInstance(action, QAction)
            self.assertTrue(action.isVisible())

            action.trigger()

            self.assertEqual(self.mainWindow.fileName, projectPath)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.recentFileList[0], projectPath)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [projectPath])

    def testFileLoadPersistsRecentFileList(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.recentFileList[0], projectPath)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', [])[0], projectPath)

    def testFileLoadReadFailurePreservesProjectDirectory(self):
        originalProjectDirectory = self.mainWindow.projectDirectory

        with patch.object(self.mainWindow.projectService, 'readProjectText', return_value=MagicMock(success=False, errorText='read failure')):
            success = self.mainWindow.fileLoad(os.path.join('D:\\', 'missing', 'broken.roll'))

        self.assertFalse(success)
        self.assertEqual(self.mainWindow.projectDirectory, originalProjectDirectory)

    def testSaveAnalysisSidecarsWritesHistogramFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath

            self.mainWindow.output.binOutput = np.arange(50, dtype=np.float32).reshape(10, 5)
            self.mainWindow.output.minOffset = np.full((10, 5), 100.0, dtype=np.float32)
            self.mainWindow.output.maxOffset = np.full((10, 5), 250.0, dtype=np.float32)
            self.mainWindow.output.rmsOffset = np.full((10, 5), 175.0, dtype=np.float32)
            self.mainWindow.output.gapOffset = np.full((10, 5), 80.0, dtype=np.float32)
            self.mainWindow.output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
            self.mainWindow.output.ofAziHist = np.ones((360 // 5, 4), dtype=np.float32)

            success = self.mainWindow.saveAnalysisSidecars(includeHistograms=True)

            self.assertTrue(success)
            np.testing.assert_array_equal(np.load(projectPath + '.gap.npy'), self.mainWindow.output.gapOffset)
            np.testing.assert_array_equal(np.load(projectPath + '.off.npy'), self.mainWindow.output.offstHist)
            np.testing.assert_array_equal(np.load(projectPath + '.azi.npy'), self.mainWindow.output.ofAziHist)

    def testOffAziDisplayMethodDefaultsToRectangular(self):
        self.assertTrue(self.mainWindow.actionOffAziRectangular.isChecked())
        self.assertFalse(self.mainWindow.actionOffAziPolar.isChecked())

    def testPlotOffAziUsesSelectedDisplayMethod(self):
        self.mainWindow.output.ofAziHist = np.ones((360 // 5, 4), dtype=np.float32)
        self.mainWindow.output.maxMaxOffset = 400.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.actionOffAziRectangular.setChecked(True)
                self.mainWindow.plotOffAzi()

        renderRectangular.assert_called_once()
        renderPolar.assert_not_called()

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.actionOffAziPolar.setChecked(True)
                self.mainWindow.plotOffAzi()

        renderPolar.assert_called_once()
        renderRectangular.assert_not_called()

    def testPlotOffAziDelegatesToRedrawOffAzi(self):
        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.plotOffAzi()

        redrawOffAzi.assert_called_once()

    def testPlotOffsetDelegatesToRedrawOffset(self):
        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.plotOffset()

        redrawOffset.assert_called_once()

    def testRedrawOffsetUsesPreparedInputs(self):
        plotInputs = {
            'xValues': np.array([0.0, 50.0, 100.0], dtype=np.float32),
            'yValues': np.array([1.0, 2.0], dtype=np.float32),
            'plotTitle': 'Offset Histogram [4 traces]',
        }

        with patch.object(self.mainWindow, 'prepareOffsetPlotInputs', return_value=plotInputs) as prepareHelper:
            with patch.object(self.mainWindow, 'renderPreparedOffsetPlot') as renderPrepared:
                with patch.object(self.mainWindow.offsetWidget, 'setTitle') as setTitle:
                    self.mainWindow.redrawOffset()

        prepareHelper.assert_called_once()
        renderPrepared.assert_called_once_with(plotInputs)
        setTitle.assert_called_once_with(plotInputs['plotTitle'], color='b', size='16pt')

    def testPrepareOffsetPlotInputsUsesHistogramHelper(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        histogramInputs = {
            'histogram': histogram,
            'count': 4,
        }

        with patch.object(self.mainWindow, 'prepareOffsetHistogramInputs', return_value=histogramInputs) as histogramHelper:
            plotInputs = self.mainWindow.prepareOffsetPlotInputs()

        histogramHelper.assert_called_once()
        np.testing.assert_array_equal(plotInputs['xValues'], histogram[0, :])
        np.testing.assert_array_equal(plotInputs['yValues'], histogram[1, :-1])
        self.assertEqual(plotInputs['plotTitle'], f'{self.mainWindow.plotTitles[8]} [4 traces]')

    def testRenderPreparedOffsetPlotUpdatesWidget(self):
        plotInputs = {
            'xValues': np.array([0.0, 50.0, 100.0], dtype=np.float32),
            'yValues': np.array([1.0, 2.0], dtype=np.float32),
        }

        with patch.object(self.mainWindow.offsetWidget.plotItem, 'clear') as clearPlot:
            with patch.object(self.mainWindow.offsetWidget, 'plot') as plotHistogram:
                self.mainWindow.renderPreparedOffsetPlot(plotInputs)

        clearPlot.assert_called_once()
        plotHistogram.assert_called_once()
        self.assertIs(plotHistogram.call_args.args[0], plotInputs['xValues'])
        self.assertIs(plotHistogram.call_args.args[1], plotInputs['yValues'])
        self.assertEqual(plotHistogram.call_args.kwargs['stepMode'], 'center')
        self.assertEqual(plotHistogram.call_args.kwargs['fillLevel'], 0)
        self.assertTrue(plotHistogram.call_args.kwargs['fillOutline'])
        self.assertEqual(plotHistogram.call_args.kwargs['brush'], (0, 0, 255, 150))
        self.assertIsNotNone(plotHistogram.call_args.kwargs['pen'])

    def testRedrawOffAziUsesPreparedInputs(self):
        plotInputs = {
            'displayHistogram': np.ones((2, 2), dtype=np.float32),
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'colorMapObj': object(),
            'count': 4,
            'isPolar': False,
            'modeText': 'rectangular',
            'plotTitle': 'Offset/Azimuth [4 traces, rectangular]',
        }

        with patch.object(self.mainWindow, 'prepareOffAziPlotInputs', return_value=plotInputs) as prepareHelper:
            with patch.object(self.mainWindow, 'renderPreparedOffAziPlot') as renderPrepared:
                with patch.object(self.mainWindow.offAziWidget, 'setTitle') as setTitle:
                    self.mainWindow.actionOffAziRectangular.setChecked(True)
                    self.mainWindow.redrawOffAzi()

        prepareHelper.assert_called_once()
        renderPrepared.assert_called_once_with(plotInputs)
        setTitle.assert_called_once_with(plotInputs['plotTitle'], color='b', size='16pt')

    def testPrepareOffAziPlotInputsUsesHistogramHelper(self):
        histogram = np.full((2, 2), 2000.0, dtype=np.float32)
        histogramInputs = {
            'histogram': histogram,
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'count': 4,
        }

        with patch.object(self.mainWindow, 'prepareOffAziHistogramInputs', return_value=histogramInputs) as histogramHelper:
            with patch.object(self.mainWindow, 'resolveColorMapObject', return_value='viridis-map') as colorMapHelper:
                self.mainWindow.actionOffAziRectangular.setChecked(True)
                plotInputs = self.mainWindow.prepareOffAziPlotInputs()

        histogramHelper.assert_called_once()
        colorMapHelper.assert_called_once_with(self.mainWindow.appSettings.analysisCmap, fallback='viridis')
        np.testing.assert_array_equal(plotInputs['displayHistogram'], histogram / 1000.0)
        self.assertFalse(plotInputs['isPolar'])
        self.assertEqual(plotInputs['plotTitle'], f"{self.mainWindow.plotTitles[9]} [4 traces, rectangular]")

    def testRenderPreparedOffAziPlotUsesPolarRendererWhenRequested(self):
        plotInputs = {
            'displayHistogram': np.ones((2, 2), dtype=np.float32),
            'dA': 5.0,
            'dO': 100.0,
            'aMin': 0.0,
            'oMax': 500.0,
            'colorMapObj': object(),
            'isPolar': True,
        }

        with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                self.mainWindow.renderPreparedOffAziPlot(plotInputs)

        renderPolar.assert_called_once_with(plotInputs['displayHistogram'], 5.0, 100.0, 500.0, plotInputs['colorMapObj'])
        renderRectangular.assert_not_called()

    def testFileLoadResetsOffAziDisplayLevelsToDefaultRange(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            projectPath = self.writeProjectFixture(tmpDir)

            self.mainWindow.offAziColorBar = MagicMock()
            self.mainWindow.offAziColorBar.levels.return_value = (1.5, 2.5)

            success = self.mainWindow.fileLoad(projectPath)

            self.assertTrue(success)
            self.mainWindow.output.ofAziHist = np.full((360 // 5, 4), 5000.0, dtype=np.float32)
            self.mainWindow.output.maxMaxOffset = 400.0
            self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
            self.mainWindow.actionOffAziRectangular.setChecked(True)

            with patch.object(self.mainWindow, 'updateOffAziColorBar') as updateColorBar:
                self.mainWindow.plotOffAzi()

        updateColorBar.assert_called_once()
        _, levelLow, levelHigh = updateColorBar.call_args.args
        self.assertEqual(levelLow, 0.0)
        self.assertEqual(levelHigh, 5.0)

    def testPrepareAnalysisImageAndColorBarStoresImageAndColorBar(self):
        imageData = np.ones((2, 3), dtype=np.float32)

        imageItem = self.mainWindow.prepareAnalysisImageAndColorBar(
            self.mainWindow.stkTrkWidget,
            imageData,
            10.0,
            20.0,
            5.0,
            2.5,
            'stkTrkImItem',
            'stkTrkColorBar',
        )

        self.assertIs(self.mainWindow.stkTrkImItem, imageItem)
        self.assertIsNotNone(self.mainWindow.stkTrkColorBar)

    def testPrepareLayoutImageAndColorBarStoresImageAndColorBar(self):
        imageData = np.ones((2, 3), dtype=np.float32)

        imageItem = self.mainWindow.prepareLayoutImageAndColorBar(
            imageData,
            'CET-L4',
            'fold',
            levels=(0.0, 12.0),
        )

        self.assertIs(self.mainWindow.layoutImItem, imageItem)
        self.assertIsNotNone(self.mainWindow.layoutColorBar)

    def testProjectLoadApplierUsesLayoutImageHelperForAnalysisState(self):
        sidecarResult = SimpleNamespace(
            binOutput=np.ones((2, 3), dtype=np.float32),
            minOffset=None,
            maxOffset=None,
            rmsOffset=None,
            gapOffset=None,
            offstHist=None,
            ofAziHist=None,
            minimumFold=1,
            maximumFold=8,
            minMinOffset=0.0,
            maxMinOffset=0.0,
            minMaxOffset=0.0,
            maxMaxOffset=0.0,
            minRmsOffset=0.0,
            maxRmsOffset=0.0,
            minOffsetGap=0.0,
            maxOffsetGap=0.0,
            analysisMemmapResult=None,
        )

        with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar') as layoutHelper:
            self.mainWindow.projectLoadApplier.applyAnalysisState(sidecarResult)

        layoutHelper.assert_called_once_with(
            sidecarResult.binOutput,
            self.mainWindow.appSettings.foldDispCmap,
            'fold',
            levels=(0.0, sidecarResult.maximumFold),
        )
        self.assertEqual(self.mainWindow.imageType, 1)
        self.assertIs(self.mainWindow.layoutImg, sidecarResult.binOutput)
        self.assertEqual(self.mainWindow.layoutMax, sidecarResult.maximumFold)

    def testHandleImageSelectionUsesLayoutImageHelper(self):
        self.mainWindow.imageType = 1
        self.mainWindow.output.binOutput = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.output.maximumFold = 8

        with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar') as layoutHelper:
            with patch.object(self.mainWindow, 'plotLayout') as plotLayout:
                self.mainWindow.handleImageSelection()

        layoutHelper.assert_called_once()
        self.assertIs(layoutHelper.call_args.args[0], self.mainWindow.layoutImg)
        self.assertEqual(layoutHelper.call_args.args[2], 'fold')
        self.assertEqual(layoutHelper.call_args.kwargs['levels'], (0.0, 8))
        plotLayout.assert_called_once()

    def testHandleImageSelectionUsesLayoutMetadataForGapSurface(self):
        self.mainWindow.imageType = 5
        self.mainWindow.output.binOutput = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.output.gapOffset = np.full((2, 3), 4.5, dtype=np.float32)
        self.mainWindow.output.maxOffsetGap = 9.0

        with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar') as layoutHelper:
            with patch.object(self.mainWindow, 'plotLayout') as plotLayout:
                self.mainWindow.handleImageSelection()

        layoutHelper.assert_called_once()
        np.testing.assert_array_equal(layoutHelper.call_args.args[0], self.mainWindow.layoutImg)
        self.assertEqual(layoutHelper.call_args.args[2], 'maximum offset gap')
        self.assertEqual(layoutHelper.call_args.kwargs['levels'], (0.0, 9.0))
        plotLayout.assert_called_once()

    def testFileExportOffsetGapsUsesLayoutMetadata(self):
        self.mainWindow.fileName = os.path.join('D:\\temp', 'layout-metadata')
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.gapOffset = np.full((2, 3), 2.5, dtype=np.float32)

        with patch.object(rollMainWindowModule, 'CreateQgisRasterLayer', return_value=self.mainWindow.fileName + '.gap.tif') as exportRaster:
            self.mainWindow.fileExportOffsetGaps()

        exportRaster.assert_called_once_with(self.mainWindow.fileName + '.gap.tif', self.mainWindow.output.gapOffset, self.mainWindow.survey)

    def testSetLayoutMouseStatusUsesLayoutMetadataForGapSurface(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.imageType = 5
        self.mainWindow.output.binOutput = np.ones((10, 5), dtype=np.uint32)
        self.mainWindow.output.gapOffset = np.full((10, 5), 4.5, dtype=np.float32)
        self.mainWindow.output.maxOffsetGap = 9.0
        self.mainWindow.layoutImg = self.mainWindow.output.gapOffset

        self.mainWindow._setLayoutMouseStatus(QPointF(5.0, 5.0))

        statusText = self.mainWindow.posWidgetStatusbar.text()
        self.assertIn('max offset gap: 4.50', statusText)
        self.assertIn('L:(5.00, 5.00, 0.00)', statusText)
        self.assertIn('W:(5.00, 5.00, 0.00)', statusText)

    def testDispatchAnalysisRedrawRoutesPatternsToPlotPatterns(self):
        with patch.object(self.mainWindow, 'plotPatterns') as plotPatterns:
            self.mainWindow.dispatchAnalysisRedraw('patterns', rollMainWindowModule.AnalysisRedrawReason.controller)

        plotPatterns.assert_called_once()

    def testDispatchAnalysisRedrawInvalidatesPatternResponseOnSelectionChange(self):
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((1, 2))

        with patch.object(self.mainWindow, 'plotPatterns') as plotPatterns:
            self.mainWindow.dispatchAnalysisRedraw('patterns', rollMainWindowModule.AnalysisRedrawReason.patternSelectionChanged)

        self.assertIsNone(self.mainWindow.xyPatResp)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.patternResponseKey)
        plotPatterns.assert_called_once()

    def testDispatchAnalysisRedrawRoutesOffAziToRedrawOffAzi(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.output.ofAziHist)
        redrawOffAzi.assert_called_once()

    def testDispatchAnalysisRedrawKeepsOffAziHistogramForDisplayModeChange(self):
        histogram = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = histogram

        with patch.object(self.mainWindow, 'redrawOffAzi') as redrawOffAzi:
            self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

        self.assertIs(self.mainWindow.output.ofAziHist, histogram)
        redrawOffAzi.assert_called_once()

    def testDispatchAnalysisRedrawOffAziPresentationReasonSkipsHistogramRecompute(self):
        histogram = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.ofAziHist = histogram
        self.mainWindow.output.maxMaxOffset = 400.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.actionOffAziPolar.setChecked(True)

        with patch.object(rollMainWindowModule.fnb, 'numbaSliceStats') as sliceStats:
            with patch.object(self.mainWindow, 'renderOffAziPolar') as renderPolar:
                with patch.object(self.mainWindow, 'renderOffAziRectangular') as renderRectangular:
                    self.mainWindow.dispatchAnalysisRedraw('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

        sliceStats.assert_not_called()
        self.assertIs(self.mainWindow.output.ofAziHist, histogram)
        renderPolar.assert_called_once()
        renderRectangular.assert_not_called()

    def testDispatchAnalysisRedrawRoutesOffsetToRedrawOffset(self):
        self.mainWindow.output.offstHist = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)

        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.output.offstHist)
        redrawOffset.assert_called_once()

    def testDispatchAnalysisRedrawKeepsOffsetHistogramForVisibleActivation(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        self.mainWindow.output.offstHist = histogram

        with patch.object(self.mainWindow, 'redrawOffset') as redrawOffset:
            self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

        self.assertIs(self.mainWindow.output.offstHist, histogram)
        redrawOffset.assert_called_once()

    def testDispatchAnalysisRedrawOffsetVisibleActivationReusesHistogramButControllerRecomputes(self):
        histogram = np.array([[0.0, 50.0, 100.0], [1.0, 2.0, 0.0]], dtype=np.float32)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.offstHist = histogram
        self.mainWindow.output.maxMaxOffset = 100.0
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.anaOutput = np.ones((1, 1, 1, 16), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSliceStats', return_value=(np.array([10.0, 20.0], dtype=np.float32), np.array([0.0, 0.0], dtype=np.float32), False)) as sliceStats:
            with patch.object(self.mainWindow, 'renderPreparedOffsetPlot') as renderPrepared:
                with patch.object(self.mainWindow.offsetWidget, 'setTitle'):
                    self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

                    self.assertIs(self.mainWindow.output.offstHist, histogram)
                    sliceStats.assert_not_called()

                    self.mainWindow.dispatchAnalysisRedraw('offset', rollMainWindowModule.AnalysisRedrawReason.controller)

        sliceStats.assert_called_once_with(self.mainWindow.output.anaOutput, self.mainWindow.survey.unique.apply)
        self.assertIsNot(self.mainWindow.output.offstHist, histogram)
        self.assertEqual(renderPrepared.call_count, 2)

    def testDispatchAnalysisRedrawRoutesStackInlineUsingContext(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context) as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-inline', rollMainWindowModule.AnalysisRedrawReason.controller)

        contextHelper.assert_called_once()
        redrawStackResponse.assert_called_once_with('stack-inline', context)

    def testDispatchAnalysisRedrawInvalidatesStackInlineCacheOnControllerReason(self):
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(3)
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context):
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-inline', rollMainWindowModule.AnalysisRedrawReason.controller)

        self.assertIsNone(self.mainWindow.inlineStk)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.inlineStkKey)
        redrawStackResponse.assert_called_once_with('stack-inline', context)

    def testDispatchAnalysisRedrawSkipsStackInlineForHorizontalMovement(self):
        with patch.object(self.mainWindow, 'getStackResponseRedrawContext') as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-inline',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Rt,
                )

        contextHelper.assert_not_called()
        redrawStackResponse.assert_not_called()

    def testDispatchAnalysisRedrawSkipsStackXlineForVerticalMovement(self):
        with patch.object(self.mainWindow, 'getStackResponseRedrawContext') as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-xline',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Up,
                )

        contextHelper.assert_not_called()
        redrawStackResponse.assert_not_called()

    def testDispatchAnalysisRedrawKeepsStackCellResponsiveInBothDirections(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context) as contextHelper:
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw(
                    'stack-cell',
                    rollMainWindowModule.AnalysisRedrawReason.controller,
                    direction=rollMainWindowModule.Direction.Up,
                )

        contextHelper.assert_called_once()
        redrawStackResponse.assert_called_once_with('stack-cell', context)

    def testDispatchAnalysisRedrawInvalidatesStackCellCacheOnPatternChange(self):
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((2, 3, True, 1, 2), 7)
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'getStackResponseRedrawContext', return_value=context):
            with patch.object(self.mainWindow, 'redrawStackResponse') as redrawStackResponse:
                self.mainWindow.dispatchAnalysisRedraw('stack-cell', rollMainWindowModule.AnalysisRedrawReason.stackPatternChanged)

        self.assertIsNone(self.mainWindow.xyCellStk)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellResponseKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellFold)
        redrawStackResponse.assert_called_once_with('stack-cell', context)

    def testRedrawStackResponseRoutesStackInlineToPlotMethod(self):
        context = {
            'nX': 2,
            'nY': 3,
            'stkX': 100.0,
            'stkY': 200.0,
            'x0': 25.0,
            'y0': 35.0,
            'dx': 10.0,
            'dy': 20.0,
        }

        with patch.object(self.mainWindow, 'plotStkTrk') as plotStkTrk:
            self.mainWindow.redrawStackResponse('stack-inline', context)

        plotStkTrk.assert_called_once_with(3, 200.0, 25.0, 10.0)

    def testOnPattern1IndexChangedUsesAnalysisDispatcher(self):
        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onPattern1IndexChanged()

        dispatcher.assert_called_once_with('patterns', rollMainWindowModule.AnalysisRedrawReason.patternSelectionChanged)

    def testOnOffAziDisplayMethodChangedUsesAnalysisDispatcher(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onOffAziDisplayMethodChanged()

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziDisplayModeChanged)

    def testOnOffAziColorBarLevelsChangedUsesPresentationReasonInPolarMode(self):
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.actionOffAziPolar.setChecked(True)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onOffAziColorBarLevelsChanged()

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.offAziColorBarLevelsChanged)

    def testGetVisiblePlotIndexMapsPatternResponseWidget(self):
        self.assertEqual(self.mainWindow.getVisiblePlotIndex(self.mainWindow.arraysWidget), 10)

    def testGetVisiblePlotWidgetReturnsFirstVisiblePlot(self):
        with patch.object(self.mainWindow.layoutWidget, 'isVisible', return_value=False):
            with patch.object(self.mainWindow.offTrkWidget, 'isVisible', return_value=True):
                plotWidget, index = self.mainWindow.getVisiblePlotWidget()

        self.assertIs(plotWidget, self.mainWindow.offTrkWidget)
        self.assertEqual(index, 1)

    def testUpdateVisiblePlotWidgetRoutesOffsetInlineUsingDerivedContext(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'plotOffTrk') as plotOffTrk:
            self.mainWindow.updateVisiblePlotWidget(1)

        plotOffTrk.assert_called_once()
        self.assertEqual(plotOffTrk.call_args[0][0], 1)
        self.assertEqual(plotOffTrk.call_args[0][2], 5.0)

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForStackInline(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(5, direction=rollMainWindowModule.Direction.Up)

        dispatcher.assert_called_once_with(
            'stack-inline',
            rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated,
            direction=rollMainWindowModule.Direction.Up,
        )

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForOffAzi(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(9)

        dispatcher.assert_called_once_with('off-azi', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

    def testUpdateVisiblePlotWidgetUsesAnalysisDispatcherForOffset(self):
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)

        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.updateVisiblePlotWidget(8)

        dispatcher.assert_called_once_with('offset', rollMainWindowModule.AnalysisRedrawReason.visiblePlotActivated)

    def testEventFilterSyncsToolbarStateForVisiblePlot(self):
        self.mainWindow.offTrkWidget.showGrid(x=False, y=False)
        self.mainWindow.offTrkWidget.setAspectLocked(False)
        self.mainWindow.offTrkWidget.getViewBox().setMouseMode(pg.ViewBox.RectMode)

        with patch.object(self.mainWindow, 'updateVisiblePlotWidget') as updater:
            handled = self.mainWindow.eventFilter(self.mainWindow.offTrkWidget, QEvent(QEvent.Type.Show))

        self.assertTrue(handled)
        self.assertTrue(self.mainWindow.actionZoomAll.isEnabled())
        self.assertTrue(self.mainWindow.actionZoomRect.isEnabled())
        self.assertTrue(self.mainWindow.actionAspectRatio.isEnabled())
        self.assertTrue(self.mainWindow.actionAntiAlias.isEnabled())
        self.assertFalse(self.mainWindow.actionRuler.isEnabled())
        self.assertFalse(self.mainWindow.actionProjected.isEnabled())
        self.assertFalse(self.mainWindow.actionPlotGridX.isChecked())
        self.assertFalse(self.mainWindow.actionPlotGridY.isChecked())
        self.assertFalse(self.mainWindow.actionAspectRatio.isChecked())
        self.assertTrue(self.mainWindow.actionZoomRect.isChecked())
        updater.assert_called_once_with(1)

    def testEventFilterDisablesPlotToolbarActionsForNonPlotWidget(self):
        self.mainWindow.actionZoomAll.setEnabled(True)
        self.mainWindow.actionZoomRect.setEnabled(True)
        self.mainWindow.actionAspectRatio.setEnabled(True)
        self.mainWindow.actionAntiAlias.setEnabled(True)
        self.mainWindow.actionRuler.setEnabled(True)
        self.mainWindow.actionProjected.setEnabled(True)

        handled = self.mainWindow.eventFilter(self.mainWindow.tabGeom, QEvent(QEvent.Type.Show))

        self.assertTrue(handled)
        self.assertFalse(self.mainWindow.actionZoomAll.isEnabled())
        self.assertFalse(self.mainWindow.actionZoomRect.isEnabled())
        self.assertFalse(self.mainWindow.actionAspectRatio.isEnabled())
        self.assertFalse(self.mainWindow.actionAntiAlias.isEnabled())
        self.assertFalse(self.mainWindow.actionRuler.isEnabled())
        self.assertFalse(self.mainWindow.actionProjected.isEnabled())

    def testPlotZoomRectTogglesMouseModeOnVisiblePlot(self):
        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.offTrkWidget.getViewBox().setMouseMode(pg.ViewBox.PanMode)

            self.mainWindow.plotZoomRect()
            self.assertEqual(self.mainWindow.offTrkWidget.getViewBox().getState()['mouseMode'], pg.ViewBox.RectMode)

            self.mainWindow.plotZoomRect()
            self.assertEqual(self.mainWindow.offTrkWidget.getViewBox().getState()['mouseMode'], pg.ViewBox.PanMode)

    def testPlotAntiAliasTogglesStoredStateForVisiblePlot(self):
        self.mainWindow.antiA[1] = False

        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.plotAntiAlias()
            self.assertTrue(self.mainWindow.antiA[1])

            self.mainWindow.plotAntiAlias()
            self.assertFalse(self.mainWindow.antiA[1])

    def testPlotGridActionsToggleVisiblePlotGridState(self):
        with patch.object(self.mainWindow, 'getVisiblePlotWidget', return_value=(self.mainWindow.offTrkWidget, 1)):
            self.mainWindow.offTrkWidget.showGrid(x=True, y=True, alpha=0.75)

            self.mainWindow.plotGridX()
            self.mainWindow.plotGridY()

            state = self.mainWindow.offTrkWidget.getPlotItem().saveState()
            self.assertFalse(state['xGridCheck'])
            self.assertFalse(state['yGridCheck'])

    def testUpdateMenuStatusResetsAnalysisAndSyncsRepresentativeActions(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.anaOutput = np.zeros((2, 2, 1, 1), dtype=np.float32)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.fileName = 'example.roll'
        self.mainWindow.imageType = 4

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            self.mainWindow.updateMenuStatus(True)

        handleImageSelection.assert_called_once()
        self.assertEqual(self.mainWindow.imageType, 0)
        self.assertTrue(self.mainWindow.actionExportFoldMap.isEnabled())
        self.assertTrue(self.mainWindow.actionExportRecAsCsv.isEnabled())
        self.assertTrue(self.mainWindow.actionExportAreasToQGIS.isEnabled())
        self.assertTrue(self.mainWindow.actionMoveLt.isEnabled())
        self.assertFalse(self.mainWindow.actionSrcPoints.isEnabled())

    def testEnableProcessingMenuItemsUsesAvailableInputs(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertTrue(self.mainWindow.actionBasicBinFromTemplates.isEnabled())
        self.assertTrue(self.mainWindow.actionFullBinFromGeometry.isEnabled())
        self.assertTrue(self.mainWindow.actionFullBinFromSps.isEnabled())
        self.assertFalse(self.mainWindow.actionStopThread.isEnabled())

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=0):
            self.mainWindow.enableProcessingMenuItems(False)

        self.assertFalse(self.mainWindow.actionBasicBinFromTemplates.isEnabled())
        self.assertFalse(self.mainWindow.actionFullBinFromGeometry.isEnabled())
        self.assertFalse(self.mainWindow.actionFullBinFromSps.isEnabled())
        self.assertTrue(self.mainWindow.actionStopThread.isEnabled())

    def testEnableProcessingMenuItemsControlsCfpActionsFromExperimentalFlagAndGeometryTables(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromTemplates.isVisible())
        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromGeometry.isVisible())
        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromTemplates.isEnabled())
        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromGeometry.isEnabled())

        self.mainWindow.relGeom = None

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromTemplates.isEnabled())
        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromGeometry.isEnabled())
        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromSPSInput.isEnabled())

    def testEnableProcessingMenuItemsEnablesCfpSpsActionsOnlyWhenFullSpsTablesAreAvailable(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromSPSInput.isEnabled())
        self.assertFalse(self.mainWindow.actionCFPPlaneAnalysisFromSPSInput.isEnabled())

        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        self.assertTrue(self.mainWindow.actionCFPPointAnalysisFromSPSInput.isEnabled())
        self.assertTrue(self.mainWindow.actionCFPPlaneAnalysisFromSPSInput.isEnabled())

    def testCfpMenuActionsMapOneToOneToTheirRoutines(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow._ensureWorkerOperationComponents()

        with patch.object(self.mainWindow.survey, 'calcNoTemplates', return_value=2):
            self.mainWindow.enableProcessingMenuItems(True)

        with patch.object(self.mainWindow.workerOperationController, 'startCfpAnalysisFromTemplates', return_value=True) as pointTemplatesStart:
            with patch.object(self.mainWindow.workerOperationController, 'startCfpAnalysisFromGeometryTables', return_value=True) as pointGeometryStart:
                with patch.object(self.mainWindow.workerOperationController, 'startCfpAnalysisFromSpsTables', return_value=True) as pointSpsStart:
                    with patch.object(self.mainWindow.workerOperationController, 'startCfpPlaneAnalysisFromTemplates', return_value=True) as planeTemplatesStart:
                        with patch.object(self.mainWindow.workerOperationController, 'startCfpPlaneAnalysisFromGeometryTables', return_value=True) as planeGeometryStart:
                            with patch.object(self.mainWindow.workerOperationController, 'startCfpPlaneAnalysisFromSpsTables', return_value=True) as planeSpsStart:
                                self.mainWindow.actionCFPPointAnalysisFromTemplates.trigger()
                                self.mainWindow.actionCFPPointAnalysisFromGeometry.trigger()
                                self.mainWindow.actionCFPPointAnalysisFromSPSInput.trigger()
                                self.mainWindow.actionCFPPlaneAnalysisFromTemplates.trigger()
                                self.mainWindow.actionCFPPlaneAnalysisFromGeometry.trigger()
                                self.mainWindow.actionCFPPlaneAnalysisFromSPSInput.trigger()

        pointTemplatesStart.assert_called_once_with()
        pointGeometryStart.assert_called_once_with()
        pointSpsStart.assert_called_once_with()
        planeTemplatesStart.assert_called_once_with()
        planeGeometryStart.assert_called_once_with()
        planeSpsStart.assert_called_once_with()

    def testUpdateSettingsHidesCfpActionsWhenExperimentalCodeIsDisabled(self):
        self.mainWindow.appSettings.useExperimental = False
        self.mainWindow.appSettings.activate()

        with patch.object(self.mainWindow, 'handleImageSelection'), patch.object(self.mainWindow, 'plotLayout'):
            self.mainWindow.updateSettings()

        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromTemplates.isVisible())
        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromGeometry.isVisible())
        self.assertFalse(self.mainWindow.actionCFPPointAnalysisFromSPSInput.isVisible())

    def testCfpAnalysisTabIsInsertedWithImageAndColorBar(self):
        cfpTabIndex = self.mainWindow.analysisTabWidget.indexOf(self.mainWindow.tabCfp)

        self.assertGreaterEqual(cfpTabIndex, 0)
        self.assertEqual(self.mainWindow.analysisTabWidget.tabText(cfpTabIndex), 'CFP Analysis')
        self.assertEqual(self.mainWindow.analysisTabWidget.tabText(cfpTabIndex - 1), 'Kx-Ky Stack')
        self.assertEqual(self.mainWindow.analysisTabWidget.tabText(cfpTabIndex + 1), '|O| Histogram')
        self.assertIsNotNone(self.mainWindow.cfpImItem)
        self.assertIsNotNone(self.mainWindow.cfpColorBar)
        self.assertEqual(self.mainWindow.cfpSliceChoice.title(), 'XY slices')
        self.assertEqual(self.mainWindow.cfpRadonChoice.title(), 'Radon transforms')
        self.assertTrue(self.mainWindow.actionCfpSliceSourceBeam.isChecked())
        self.assertFalse(self.mainWindow.actionCfpRadonSrcBeam.isChecked())

    def testUpdateSettingsHidesCfpAnalysisTabWhenExperimentalCodeIsDisabled(self):
        cfpTabIndex = self.mainWindow.analysisTabWidget.indexOf(self.mainWindow.tabCfp)
        self.mainWindow.appSettings.useExperimental = False
        self.mainWindow.appSettings.activate()

        with patch.object(self.mainWindow, 'handleImageSelection'), patch.object(self.mainWindow, 'plotLayout'):
            self.mainWindow.updateSettings()

        self.assertFalse(self.mainWindow.analysisTabWidget.isTabVisible(cfpTabIndex))

        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.appSettings.activate()

        with patch.object(self.mainWindow, 'handleImageSelection'), patch.object(self.mainWindow, 'plotLayout'):
            self.mainWindow.updateSettings()

        self.assertTrue(self.mainWindow.analysisTabWidget.isTabVisible(cfpTabIndex))

    def testCopyFallsBackToPlotClipboardWhenFocusCopyUnavailable(self):
        with patch.object(self.mainWindow.actionStateController, 'invokeFocusMethod', return_value=False) as invokeFocusMethod:
            with patch.object(self.mainWindow.actionStateController, 'copyPlotWidgetToClipboard', return_value=True) as copyPlotWidgetToClipboard:
                with patch.object(self.mainWindow.actionStateController, 'clipboardHasText', return_value=True):
                    self.mainWindow.copy()

        invokeFocusMethod.assert_called_once_with('copy')
        copyPlotWidgetToClipboard.assert_called_once_with()
        self.assertTrue(self.mainWindow.actionPaste.isEnabled())

    def testGrabPlotWidgetForPrintReturnsActiveAnalysisPlot(self):
        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.analysisTabWidget):
            with patch.object(self.mainWindow.analysisTabWidget, 'currentWidget', return_value=self.mainWindow.offTrkWidget):
                plotWidget = self.mainWindow._grabPlotWidgetForPrint()

        self.assertIs(plotWidget, self.mainWindow.offTrkWidget)

    def testFilePrintDelegatesToPrintPresentationController(self):
        with patch.object(self.mainWindow.printPresentationController, 'filePrint') as filePrint:
            self.mainWindow.filePrint()

        filePrint.assert_called_once_with()

    def testPrintPreviewPrintsXmlWhenXmlTabIsActive(self):
        printer = MagicMock()

        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.textEdit):
            with patch.object(self.mainWindow.textEdit, 'print') as textPrint:
                self.mainWindow.printPreview(printer)

        textPrint.assert_called_once_with(printer)

    def testPrintPreviewUsesPlotBranchWhenActivePlotExists(self):
        printer = MagicMock()

        with patch.object(self.mainWindow.mainTabWidget, 'currentWidget', return_value=self.mainWindow.tabGeom):
            with patch.object(self.mainWindow, '_grabPlotWidgetForPrint', return_value=self.mainWindow.offTrkWidget):
                with patch.object(self.mainWindow.printPresentationController, '_printPlotWidget') as printPlotWidget:
                    self.mainWindow.printPreview(printer)

        printPlotWidget.assert_called_once_with(printer, self.mainWindow.offTrkWidget)

    def testFilePrintPdfAppendsPdfSuffixBeforePrinting(self):
        printer = MagicMock()
        qprinterFactory = MagicMock(return_value=printer)
        qprinterFactory.PrinterMode = MagicMock(HighResolution='high-resolution')
        qprinterFactory.OutputFormat = MagicMock(PdfFormat='pdf-format')
        document = MagicMock()

        with patch.object(printPresentationControllerModule.QFileDialog, 'getSaveFileName', return_value=('report', 'PDF files (*.pdf)')):
            with patch.object(printPresentationControllerModule, 'QPrinter', qprinterFactory):
                with patch.object(self.mainWindow.textEdit, 'document', return_value=document):
                    self.mainWindow.filePrintPdf()

        qprinterFactory.assert_called_once_with(qprinterFactory.PrinterMode.HighResolution)
        printer.setOutputFormat.assert_called_once_with(qprinterFactory.OutputFormat.PdfFormat)
        printer.setOutputFileName.assert_called_once_with('report.pdf')
        document.print.assert_called_once_with(printer)

    def testPlotStkTrkUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 1, 1, 1), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D', return_value=(np.ones((2, 1, 1), dtype=np.float32), np.array([0, 1], dtype=np.int32))):
            with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D', return_value=np.ones((3, 4), dtype=np.float32)):
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkTrk(0, 1000, 25.0, 10.0)

        helper.assert_called_once()
        self.assertEqual(helper.call_args[0][6], 'stkTrkImItem')
        self.assertEqual(helper.call_args[0][7], 'stkTrkColorBar')

    def testPlotStkTrkReusesCachedResponseWhenLineIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((2, 1, 1, 1), dtype=np.float32)
        cached = np.full((3, 4), -8.0, dtype=np.float32)
        self.mainWindow.inlineStk = cached
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(0)

        with patch.object(self.mainWindow.plotRedrawHelper, 'buildInlineStackAxisValues', return_value=(0.15, 0.05, -25.0, 50.0)) as axisHelper:
            with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D') as sliceHelper:
                with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D') as computeHelper:
                    with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                        self.mainWindow.plotStkTrk(0, 1000, 25.0, 10.0)

        axisHelper.assert_called_once_with(self.mainWindow)
        sliceHelper.assert_not_called()
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotStkBinUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 2, 1, 1), dtype=np.float32)

        with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D', return_value=(np.ones((2, 1, 1), dtype=np.float32), np.array([0, 1], dtype=np.int32))):
            with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D', return_value=np.ones((3, 4), dtype=np.float32)):
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkBin(0, 1000, 25.0, 10.0)

        helper.assert_called_once()
        self.assertEqual(helper.call_args[0][6], 'stkBinImItem')
        self.assertEqual(helper.call_args[0][7], 'stkBinColorBar')

    def testPlotStkBinReusesCachedResponseWhenStakeIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 2, 1, 1), dtype=np.float32)
        cached = np.full((3, 4), -7.0, dtype=np.float32)
        self.mainWindow.x0lineStk = cached
        self.mainWindow.plotRedrawHelper.storeXlineResponseKey(0)

        with patch.object(self.mainWindow.plotRedrawHelper, 'buildXlineStackAxisValues', return_value=(0.15, 0.05, -25.0, 50.0)) as axisHelper:
            with patch.object(rollMainWindowModule.fnb, 'numbaSlice3D') as sliceHelper:
                with patch.object(rollMainWindowModule.fnb, 'numbaNdft1D') as computeHelper:
                    with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                        self.mainWindow.plotStkBin(0, 1000, 25.0, 10.0)

        axisHelper.assert_called_once_with(self.mainWindow)
        sliceHelper.assert_not_called()
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotStkCelUsesSharedAnalysisImageHelper(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 1, 1, 1), dtype=np.float32)
        expected = np.ones((3, 3), dtype=np.float32)
        selectedPatterns = (object(), object())

        with patch.object(self.mainWindow, 'getSelectedStackCellPatterns', return_value=selectedPatterns) as selectionHelper:
            with patch.object(self.mainWindow, 'computeStackCellResponse', return_value=(expected, 25.0, 10.0, 7)) as computeHelper:
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                    self.mainWindow.plotStkCel(0, 0, 1000, 1000)

        selectionHelper.assert_called_once()
        computeHelper.assert_called_once_with(0, 0, selectedPatterns[0], selectedPatterns[1])
        helper.assert_called_once()
        self.assertIs(self.mainWindow.xyCellStk, expected)
        self.assertIs(helper.call_args[0][1], expected)
        self.assertEqual(helper.call_args[0][6], 'stkCelImItem')
        self.assertEqual(helper.call_args[0][7], 'stkCelColorBar')

    def testPlotStkCelReusesCachedResponseWhenCellAndPatternsAreUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.output.anaOutput = np.zeros((1, 1, 1, 1), dtype=np.float32)
        cached = np.full((3, 3), -6.0, dtype=np.float32)
        selectedPatterns = (object(), object())

        self.mainWindow.xyCellStk = cached
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((0, 0, False, 0, 0), 9)

        with patch.object(self.mainWindow, 'getSelectedStackCellPatterns', return_value=selectedPatterns) as selectionHelper:
            with patch.object(self.mainWindow.plotRedrawHelper, 'buildStackCellResponseKey', return_value=(0, 0, False, 0, 0)) as keyHelper:
                with patch.object(self.mainWindow.plotRedrawHelper, 'buildStackCellCachedAxisValues', return_value=(25.0, 10.0, 9)) as axisHelper:
                    with patch.object(self.mainWindow, 'computeStackCellResponse') as computeHelper:
                        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as helper:
                            self.mainWindow.plotStkCel(0, 0, 1000, 1000)

        selectionHelper.assert_called_once()
        keyHelper.assert_called_once_with(self.mainWindow, 0, 0)
        axisHelper.assert_called_once_with(self.mainWindow)
        computeHelper.assert_not_called()
        helper.assert_called_once()
        self.assertIs(helper.call_args[0][1], cached)

    def testPlotPatternsUsesSharedAnalysisImageHelperInKxKyMode(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.patternLayout = False
        expected = np.full((3, 3), -12.5, dtype=np.float32)
        selectedPatterns = (object(), object())
        selectedTexts = ('Pattern A', 'Pattern B')

        with patch.object(self.mainWindow, 'getSelectedPatternInputs', return_value=(selectedPatterns[0], selectedPatterns[1], selectedTexts[0], selectedTexts[1])) as selectionHelper:
            with patch.object(self.mainWindow, 'computeKxyPatternResponse', return_value=(expected, 25.0, 10.0)) as computeHelper:
                with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as imageHelper:
                    self.mainWindow.plotPatterns()

        selectionHelper.assert_called_once()
        computeHelper.assert_called_once()
        self.assertIs(computeHelper.call_args[0][0], selectedPatterns[0])
        self.assertIs(computeHelper.call_args[0][1], selectedPatterns[1])
        imageHelper.assert_called_once()
        self.assertIs(self.mainWindow.xyPatResp, expected)
        self.assertIs(imageHelper.call_args[0][1], expected)
        self.assertEqual(imageHelper.call_args[0][6], 'kxyPatImItem')
        self.assertEqual(imageHelper.call_args[0][7], 'kxyPatColorBar')

    def testPlotPatternsReusesCachedResponseWhenSelectionIsUnchanged(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.patternLayout = False
        cachedResponse = np.full((3, 3), -9.0, dtype=np.float32)
        selectedPatterns = (object(), object())
        selectedTexts = ('Pattern A', 'Pattern B')

        self.mainWindow.xyPatResp = cachedResponse
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((1, 2))

        with patch.object(self.mainWindow, 'getSelectedPatternInputs', return_value=(selectedPatterns[0], selectedPatterns[1], selectedTexts[0], selectedTexts[1])) as selectionHelper:
            with patch.object(self.mainWindow.plotRedrawHelper, 'buildPatternResponseKey', return_value=(1, 2)) as keyHelper:
                with patch.object(self.mainWindow.plotRedrawHelper, 'buildPatternAxisValues', return_value=(25.0, 10.0)) as axisHelper:
                    with patch.object(self.mainWindow, 'computeKxyPatternResponse') as computeHelper:
                        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as imageHelper:
                            self.mainWindow.plotPatterns()

        selectionHelper.assert_called_once()
        keyHelper.assert_called_once_with(self.mainWindow)
        axisHelper.assert_called_once_with(self.mainWindow)
        computeHelper.assert_not_called()
        imageHelper.assert_called_once()
        self.assertIs(imageHelper.call_args[0][1], cachedResponse)

    def testOnStackPatternIndexChangedUsesAnalysisDispatcher(self):
        with patch.object(self.mainWindow, 'dispatchAnalysisRedraw') as dispatcher:
            self.mainWindow.onStackPatternIndexChanged()

        dispatcher.assert_called_once_with('stack-cell', rollMainWindowModule.AnalysisRedrawReason.stackPatternChanged)

    def testFinalizeAnalysisMemmapRefreshesTimestampAndReopensFile(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            anaPath = projectPath + '.ana.npy'
            shape = (2, 2, 1, 16)
            oldTimestamp = 1_700_000_000

            self.mainWindow.fileName = projectPath
            self.mainWindow.output.anaOutput = np.memmap(anaPath, dtype=np.float32, mode='w+', shape=shape)
            self.mainWindow.output.anaOutput.fill(7.0)
            self.mainWindow.output.an2Output = self.mainWindow.output.anaOutput.reshape(shape[0] * shape[1] * shape[2], shape[3])
            os.utime(anaPath, (oldTimestamp, oldTimestamp))

            success = self.mainWindow.finalizeAnalysisMemmap(shape)

            self.assertTrue(success)
            self.assertIsNotNone(self.mainWindow.output.anaOutput)
            self.assertEqual(self.mainWindow.output.an2Output.shape, (4, 16))
            self.assertGreater(os.path.getmtime(anaPath), oldTimestamp)

            self.mainWindow.resetAnaTableModel()

    def testPrepFullBinningConditionsRecreatesExistingAnalysisSidecar(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            anaPath = projectPath + '.ana.npy'

            self.mainWindow.fileName = projectPath
            self.mainWindow.survey = self.createSurvey()
            self.mainWindow.survey.grid.fold = 5

            # Simulate a stale header-bearing file left behind by an older writer.
            np.save(anaPath, np.zeros((10, 5, 5, 16), dtype=np.float32))
            staleSize = os.path.getsize(anaPath)

            success = self.mainWindow.prepFullBinningConditions()

            self.assertTrue(success)
            self.assertIsInstance(self.mainWindow.output.anaOutput, np.memmap)
            expectedSize = 10 * 5 * 5 * 16 * 4
            self.assertEqual(os.path.getsize(anaPath), expectedSize)
            self.assertNotEqual(staleSize, expectedSize)

            self.mainWindow.resetAnaTableModel()

    def testSaveSurveyDataSidecarsWritesGeometryFiles(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath

            self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.recGeom[0] = (300.0, 30.0, 1, 'CC', 0.0, 1200.0, 2200.0, 0.0, 1, 1, 1, 0.0, 0.0)
            self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.srcGeom[0] = (400.0, 40.0, 1, 'DD', 0.0, 1300.0, 2300.0, 0.0, 1, 1, 1, 0.0, 0.0)
            self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
            self.mainWindow.relGeom[0] = (400.0, 40.0, 1, 1, 300.0, 30.0, 31.0, 1, 1, 1, 1)

            success = self.mainWindow.saveSurveyDataSidecars()

            self.assertTrue(success)
            np.testing.assert_array_equal(np.load(projectPath + '.rec.npy'), self.mainWindow.recGeom)
            np.testing.assert_array_equal(np.load(projectPath + '.rel.npy'), self.mainWindow.relGeom)
            np.testing.assert_array_equal(np.load(projectPath + '.src.npy'), self.mainWindow.srcGeom)

    def testFileOpenRecentUsesSameOpenGuardsAsFileOpen(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.recentFileList = [projectPath]
            self.mainWindow.updateRecentFileActions()

            action = self.mainWindow.recentFileActions[0]

            with patch.object(self.mainWindow, 'maybeKillThread', return_value=False) as maybeKillThread:
                with patch.object(self.mainWindow, 'maybeSave', return_value=True) as maybeSave:
                    with patch.object(self.mainWindow, 'fileLoad', return_value=True) as fileLoad:
                        action.trigger()

            maybeKillThread.assert_called_once()
            maybeSave.assert_not_called()
            fileLoad.assert_not_called()

    def testUpdateRecentFileActionsPrunesMissingFilesAutomatically(self):
        with tempfile.TemporaryDirectory() as tempDir:
            existingProjectPath = self.writeProjectFixture(tempDir)
            missingProjectPath = os.path.join(tempDir, 'missing.roll')

            self.mainWindow.recentFileList = [missingProjectPath, existingProjectPath]
            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [existingProjectPath])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), existingProjectPath)
            self.assertFalse(self.mainWindow.recentFileActions[1].isVisible())
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [existingProjectPath])

    def testReadSettingsNormalizesSingleRecentFileString(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)

            self.mainWindow.settings.setValue('settings/recentFileList', projectPath)
            self.mainWindow.recentFileList = []

            readSettings(self.mainWindow)
            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [projectPath])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), projectPath)

    def testSettingsUseRuntimeAndAppStateOwners(self):
        with tempfile.TemporaryDirectory() as tempDir:
            importDir = os.path.join(tempDir, 'imports')
            os.makedirs(importDir)
            projectPath = self.writeProjectFixture(tempDir)

            self.mainWindow.settings.setValue('settings/projectDirectory', tempDir)
            self.mainWindow.settings.setValue('settings/importDirectory', importDir)
            self.mainWindow.settings.setValue('settings/recentFileList', [projectPath])
            self.mainWindow.settings.setValue('settings/sps/spsDialect', 'SEG rev2.1')
            self.mainWindow.settings.setValue('settings/colors/analysisCmap', 'CET-L5')
            self.mainWindow.settings.setValue('settings/colors/reflectColor', '#40223344')
            self.mainWindow.settings.setValue('settings/colors/reflectPen', str(((10, 20, 30, 255), 3, 'DashLine', 'RoundCap', 'RoundJoin', False)))

            readSettings(self.mainWindow)

            self.assertEqual(self.mainWindow.runtimeState.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.runtimeState.importDirectory, importDir)
            self.assertEqual(self.mainWindow.importDirectory, importDir)
            self.assertEqual(self.mainWindow.runtimeState.recentFileList, [projectPath])
            self.assertEqual(self.mainWindow.recentFileList, [projectPath])
            self.assertEqual(self.mainWindow.appSettings.spsDialect, 'SEG rev2.1')
            self.assertEqual(self.mainWindow.appSettings.analysisCmap, 'CET-L5')
            self.assertEqual(self.mainWindow.appSettings.reflectColor, '#40223344')
            self.assertEqual(auxFunctionsModule.makeParmsFromPen(self.mainWindow.appSettings.reflectPen), ((10, 20, 30, 255), 3, 'DashLine', 'RoundCap', 'RoundJoin', False))

            self.mainWindow.appSettings.useRelativePaths = False
            self.mainWindow.appSettings.spsDialect = 'New Zealand'
            self.mainWindow.appSettings.reflectColor = '#40556677'
            self.mainWindow.appSettings.reflectPen = QPen(QColor(40, 50, 60, 255), 2, Qt.PenStyle.DotLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self.mainWindow.projectDirectory = tempDir
            self.mainWindow.importDirectory = importDir
            self.mainWindow.recentFileList = [projectPath]

            writeSettings(self.mainWindow)

            self.assertFalse(self.mainWindow.settings.value('settings/misc/useRelativePaths', True, type=bool))
            self.assertEqual(self.mainWindow.settings.value('settings/projectDirectory', ''), tempDir)
            self.assertEqual(self.mainWindow.settings.value('settings/importDirectory', ''), importDir)
            self.assertEqual(self.mainWindow.settings.value('settings/recentFileList', []), [projectPath])
            self.assertEqual(self.mainWindow.settings.value('settings/sps/spsDialect', ''), 'New Zealand')
            self.assertEqual(self.mainWindow.settings.value('settings/colors/reflectColor', ''), '#40556677')
            self.assertEqual(self.mainWindow.settings.value('settings/colors/reflectPen', ''), str(auxFunctionsModule.makeParmsFromPen(self.mainWindow.appSettings.reflectPen)))

    def testReflectorStyleConfigUsesConfiguredReflectColor(self):
        self.mainWindow.appSettings.reflectColor = '#40223344'
        self.mainWindow.appSettings.reflectPen = QPen(QColor(50, 60, 70, 255), 4, Qt.PenStyle.DashDotLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        style = layoutTabModule._buildReflectorStyleConfig(self.mainWindow)

        self.assertEqual(style['faceColor'], layoutTabModule._qColorToRgba(QColor('#40223344')))
        self.assertEqual(style['edgeColor'], layoutTabModule._qColorToRgba(QColor(50, 60, 70, 255)))
        self.assertEqual(style['edgeWidth'], 4.0)
        self.assertEqual(style['edgeStyle'], '-.')

    def testDefaultReflectPenMatchesConfig(self):
        self.assertEqual(
            auxFunctionsModule.makeParmsFromPen(appSettingsModule.AppSettings().reflectPen),
            auxFunctionsModule.makeParmsFromPen(config.reflectPen),
        )

    def testReadSettingsRestoresSavedWindowState(self):
        geometryState = b'geometry-bytes'
        windowState = b'window-state-bytes'

        self.mainWindow.settings.setValue('mainWindow/geometry', geometryState)
        self.mainWindow.settings.setValue('mainWindow/state', windowState)

        with patch.object(self.mainWindow, 'restoreGeometry') as restoreGeometry:
            with patch.object(self.mainWindow, 'restoreState') as restoreState:
                readSettings(self.mainWindow)

        restoreGeometry.assert_called_once_with(geometryState)
        restoreState.assert_called_once_with(windowState)

    def testReadSettingsIgnoresStoredLayoutViewMode(self):
        self.mainWindow.settings.setValue('mainWindow/layoutViewMode', '3d')

        readSettings(self.mainWindow)

        self.assertEqual(self.mainWindow.layoutViewMode, '2d')
        self.assertTrue(self.mainWindow.actionLayout2D.isChecked())
        self.assertIs(self.mainWindow.layoutViewStack.currentWidget(), self.mainWindow.layoutWidget)

    def testWriteSettingsRemovesStoredLayoutViewMode(self):
        self.mainWindow.settings.setValue('mainWindow/layoutViewMode', '3d')
        self.mainWindow.actionLayout3D.setChecked(True)

        writeSettings(self.mainWindow)

        self.assertIsNone(self.mainWindow.settings.value('mainWindow/layoutViewMode'))

        self.mainWindow.actionLayout2D.setChecked(True)

        writeSettings(self.mainWindow)

        self.assertIsNone(self.mainWindow.settings.value('mainWindow/layoutViewMode'))

    def testSpsImportDialogUsesAppSettingsAsFormatOwner(self):
        self.mainWindow.appSettings.spsDialect = 'New Zealand'

        dialog = SpsImportDialog(self.mainWindow, self.mainWindow.survey.crs, self.mainWindow.importDirectory)
        try:
            self.assertEqual(dialog.spsFormatList.currentItem().text(), 'New Zealand')

            dialog.spsFormatList.setCurrentRow(0)
            dialog.spsCombo.setCurrentIndex(1)
            dialog.onSpsComboHighlighted(1)

            originalFromColumn = self.mainWindow.appSettings.spsFormatList[0]['line'][0]
            dialog.spsFromSpin.setValue(originalFromColumn + 2)

            self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['line'][0], originalFromColumn + 1)

            dialog.spsFormatList.setCurrentRow(1)
            dialog.accepted()

            self.assertEqual(self.mainWindow.appSettings.spsDialect, dialog.spsFormatList.currentItem().text())
        finally:
            dialog.close()
            dialog.deleteLater()

    def testSpsImportDialogResetUsesBuiltInDefaultsNotLiveConfigLists(self):
        self.mainWindow.appSettings.spsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.xpsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.rpsFormatList = [{'name': 'Broken'}]
        self.mainWindow.appSettings.spsDialect = 'Broken'

        dialog = SpsImportDialog(self.mainWindow, self.mainWindow.survey.crs, self.mainWindow.importDirectory)
        try:
            with patch.object(spsImportDialogModule.QMessageBox, 'question', return_value=spsImportDialogModule.QMessageBox.StandardButton.Yes):
                dialog.onResetSpsDatabase()

            self.assertNotIn('Broken', [entry['name'] for entry in self.mainWindow.appSettings.spsFormatList])
            self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['name'], config.getDefaultSpsFormats()[0]['name'])
        finally:
            dialog.close()
            dialog.deleteLater()

    def testSpsImportDialogShowsFileLoadProgressWhilePopulatingPreviewTabs(self):
        dialog = SpsImportDialog(self.mainWindow, self.mainWindow.survey.crs, self.mainWindow.importDirectory)
        try:
            with tempfile.TemporaryDirectory() as tempDir:
                spsPath = os.path.join(tempDir, 'example.sps')
                rpsPath = os.path.join(tempDir, 'example.rps')
                with open(spsPath, 'w', encoding='utf-8') as handle:
                    handle.write('SPS-LINE-1\n' * 20000)

                with open(rpsPath, 'w', encoding='utf-8') as handle:
                    handle.write('RPS-LINE-1\n' * 20000)

                with patch.object(dialog, '_updateFileLoadProgress', wraps=dialog._updateFileLoadProgress) as progressMock:
                    with patch.object(dialog, '_showPreviewPopulateProgress', wraps=dialog._showPreviewPopulateProgress) as previewMock:
                        dialog.onSpsFilesChanged(f'"{spsPath}" "{rpsPath}"')

                self.assertTrue(dialog.spsTab.toPlainText().startswith('SPS-LINE-1\n'))
                self.assertTrue(dialog.rpsTab.toPlainText().startswith('RPS-LINE-1\n'))
                self.assertEqual(dialog.progressLabel.text(), 'Ready reading input data')
                self.assertEqual(dialog.progressBar.value(), 0)
                self.assertFalse(dialog.progressBar.isVisible())
                self.assertEqual(previewMock.call_count, 1)
                self.assertTrue(any(call.args[0] == spsPath for call in progressMock.call_args_list))
                self.assertTrue(any(call.args[0] == rpsPath for call in progressMock.call_args_list))
                self.assertTrue(any(0 < call.args[1] < 100 for call in progressMock.call_args_list))

                spsCalls = [call.args[1] for call in progressMock.call_args_list if call.args[0] == spsPath]
                rpsCalls = [call.args[1] for call in progressMock.call_args_list if call.args[0] == rpsPath]

                self.assertIn(0, spsCalls)
                self.assertIn(100, spsCalls)
                self.assertIn(0, rpsCalls)
                self.assertIn(100, rpsCalls)
        finally:
            dialog.close()
            dialog.deleteLater()

    def testReadSettingsResetsInvalidStoredSpsFormatsToBuiltInDefaults(self):
        self.mainWindow.settings.beginGroup('settings/sps/spsFormatList')
        self.mainWindow.settings.setValue('Broken', '{"name": "Broken"}')
        self.mainWindow.settings.endGroup()
        self.mainWindow.settings.beginGroup('settings/sps/xpsFormatList')
        self.mainWindow.settings.remove('')
        self.mainWindow.settings.endGroup()
        self.mainWindow.settings.beginGroup('settings/sps/rpsFormatList')
        self.mainWindow.settings.remove('')
        self.mainWindow.settings.endGroup()

        self.mainWindow.appSettings.spsDialect = 'Broken'
        readSettings(self.mainWindow)

        self.assertNotIn('Broken', [entry['name'] for entry in self.mainWindow.appSettings.spsFormatList])
        self.assertEqual(self.mainWindow.appSettings.spsFormatList[0]['name'], config.getDefaultSpsFormats()[0]['name'])

    def testExportSpsAndSrcToQgisUseAppSettingsParallelFlag(self):
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.appSettings.spsParallel = True

        with patch.object(rollMainWindowModule, 'exportPointLayerToQgis', return_value=object()) as exportPointLayer:
            self.mainWindow.exportSpsToQgis()
            self.mainWindow.exportSrcToQgis()

        self.assertEqual(exportPointLayer.call_count, 2)
        self.assertTrue(exportPointLayer.call_args_list[0].kwargs['spsParallel'])
        self.assertTrue(exportPointLayer.call_args_list[1].kwargs['spsParallel'])

    def testFileSaveUsesAppSettingsRelativePathFlag(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.fileName = projectPath
            self.mainWindow.survey = self.createSurvey()
            self.mainWindow.appSettings.useRelativePaths = False

            with patch.object(self.mainWindow.projectService, 'writeProjectXml') as writeProjectXml:
                writeProjectXml.return_value = type('WriteResult', (), {'success': True, 'errorText': ''})()
                with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars'):
                    with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars'):
                        self.mainWindow.fileSave()

            self.assertFalse(writeProjectXml.call_args.args[3])

    def testAppendLogMessageUsesAppSettingsDebugFlag(self):
        self.mainWindow.appSettings.debug = False
        originalText = self.mainWindow.logEdit.toPlainText()

        self.mainWindow.appendLogMessage('hidden-debug-message', rollMainWindowModule.MsgType.Debug)

        self.assertEqual(self.mainWindow.logEdit.toPlainText(), originalText)

        self.mainWindow.appSettings.debug = True
        self.mainWindow.appendLogMessage('visible-debug-message', rollMainWindowModule.MsgType.Debug)

        self.assertIn('visible-debug-message', self.mainWindow.logEdit.toPlainText())

    def testActivateUpdatesActiveDebugLogging(self):
        self.mainWindow.appSettings.debug = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isDebugLoggingEnabled())

        self.mainWindow.appSettings.debug = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isDebugLoggingEnabled())

    def testMyPrintUsesActiveDebugLoggingSetting(self):
        with patch('builtins.print') as mockPrint:
            setActiveDebugLogging(False)
            myPrint('hidden-debug-print')
            mockPrint.assert_not_called()

            setActiveDebugLogging(True)
            myPrint('visible-debug-print')
            mockPrint.assert_called_once_with('visible-debug-print')

    def testActivateUpdatesActiveShowSummaries(self):
        self.mainWindow.appSettings.showSummaries = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isShowSummariesEnabled())

        self.mainWindow.appSettings.showSummaries = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isShowSummariesEnabled())

    def testActivateUpdatesActiveUseExperimental(self):
        self.mainWindow.appSettings.useExperimental = False
        self.mainWindow.appSettings.activate()
        self.assertFalse(isUseExperimentalEnabled())

        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.appSettings.activate()
        self.assertTrue(isUseExperimentalEnabled())

    def testLayoutMethodControlsAreHiddenWhenExperimentalCodeIsDisabled(self):
        self.mainWindow.appSettings.useExperimental = False
        self.mainWindow.appSettings.activate()

        with patch.object(self.mainWindow, 'handleImageSelection'), patch.object(self.mainWindow, 'plotLayout'):
            self.mainWindow.updateSettings()

        self.assertFalse(self.mainWindow.layoutMethodSidePanel.isHidden())
        self.assertFalse(self.mainWindow.layoutMethodChoice.isHidden())
        self.assertGreater(self.mainWindow.layoutMethodSplitter.sizes()[0], 0)
        self.assertTrue(self.mainWindow.actionLayout2D.isChecked())

    def testLayoutMethodControlsAreShownWhenExperimentalCodeIsEnabled(self):
        self.mainWindow.appSettings.useExperimental = True
        self.mainWindow.appSettings.activate()

        with patch.object(self.mainWindow, 'handleImageSelection'), patch.object(self.mainWindow, 'plotLayout'):
            self.mainWindow.updateSettings()

        self.assertFalse(self.mainWindow.layoutMethodSidePanel.isHidden())
        self.assertFalse(self.mainWindow.layoutMethodChoice.isHidden())
        self.assertGreater(self.mainWindow.layoutMethodSplitter.sizes()[0], 0)
        self.assertTrue(self.mainWindow.actionLayout2D.isChecked())

    def testMainTabChangeKeeps3DSubsetSelected(self):
        self.mainWindow.actionLayout3D.setChecked(True)
        originalWidget = self.mainWindow.layout3DWidget

        self.mainWindow.onMainTabChange(1)

        self.assertTrue(self.mainWindow.actionLayout3D.isChecked())
        self.assertIs(self.mainWindow.layout3DWidget, originalWidget)

    def testFileLoadReturnsTo2DMapViewAndRefreshes3DSubset(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            self.mainWindow.actionLayout3D.setChecked(True)
            originalWidget = self.mainWindow.layout3DWidget

            with patch.object(rollMainWindowModule, 'refreshLayout3DFromSurvey', wraps=rollMainWindowModule.refreshLayout3DFromSurvey) as refreshLayout3D:
                success = self.mainWindow.fileLoad(projectPath)

        self.assertTrue(success)
        self.assertTrue(self.mainWindow.actionLayout2D.isChecked())
        self.assertIs(self.mainWindow.layoutViewStack.currentWidget(), self.mainWindow.layoutWidget)
        self.assertIs(self.mainWindow.layout3DWidget, originalWidget)
        self.assertGreaterEqual(refreshLayout3D.call_count, 1)

    def testRefreshLayout3DForwardsVisiblePointSetsWith2DStyles(self):
        updateFromSurvey = MagicMock()
        self.mainWindow.layout3DWidget = SimpleNamespace(updateFromSurvey=updateFromSurvey)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.actionShowPoints.setChecked(True)
        self.mainWindow.tbAllList.setChecked(True)
        self.mainWindow.tbSpsList.setChecked(True)
        self.mainWindow.tbRpsList.setChecked(True)
        self.mainWindow.tbSrcList.setChecked(True)
        self.mainWindow.tbRecList.setChecked(True)

        self.mainWindow.spsLiveE = np.array([10.0], dtype=np.float64)
        self.mainWindow.spsLiveN = np.array([20.0], dtype=np.float64)
        self.mainWindow.spsDeadE = np.array([11.0], dtype=np.float64)
        self.mainWindow.spsDeadN = np.array([21.0], dtype=np.float64)
        self.mainWindow.rpsLiveE = np.array([30.0], dtype=np.float64)
        self.mainWindow.rpsLiveN = np.array([40.0], dtype=np.float64)
        self.mainWindow.rpsDeadE = np.array([31.0], dtype=np.float64)
        self.mainWindow.rpsDeadN = np.array([41.0], dtype=np.float64)
        self.mainWindow.srcLiveE = np.array([50.0], dtype=np.float64)
        self.mainWindow.srcLiveN = np.array([60.0], dtype=np.float64)
        self.mainWindow.srcDeadE = np.array([51.0], dtype=np.float64)
        self.mainWindow.srcDeadN = np.array([61.0], dtype=np.float64)
        self.mainWindow.recLiveE = np.array([70.0], dtype=np.float64)
        self.mainWindow.recLiveN = np.array([80.0], dtype=np.float64)
        self.mainWindow.recDeadE = np.array([71.0], dtype=np.float64)
        self.mainWindow.recDeadN = np.array([81.0], dtype=np.float64)

        layoutTabModule.refreshLayout3DFromSurvey(self.mainWindow)

        kwargs = updateFromSurvey.call_args.kwargs
        pointSets = kwargs['pointSets']

        self.assertEqual(len(pointSets), 8)
        self.assertEqual(pointSets[0]['symbol'], self.mainWindow.appSettings.spsPointSymbol)
        self.assertEqual(pointSets[0]['faceColor'], self.mainWindow.appSettings.spsBrushColor)
        self.assertEqual(pointSets[1]['faceColor'], config.spsBrushGrey)
        self.assertEqual(pointSets[2]['symbol'], self.mainWindow.appSettings.rpsPointSymbol)
        self.assertEqual(pointSets[2]['faceColor'], self.mainWindow.appSettings.rpsBrushColor)
        self.assertEqual(pointSets[3]['faceColor'], config.rpsBrushGrey)
        self.assertEqual(pointSets[4]['symbol'], self.mainWindow.appSettings.srcPointSymbol)
        self.assertEqual(pointSets[4]['faceColor'], self.mainWindow.appSettings.srcBrushColor)
        self.assertEqual(pointSets[5]['faceColor'], config.srcBrushGrey)
        self.assertEqual(pointSets[6]['symbol'], self.mainWindow.appSettings.recPointSymbol)
        self.assertEqual(pointSets[6]['faceColor'], self.mainWindow.appSettings.recBrushColor)
        self.assertEqual(pointSets[7]['faceColor'], config.recBrushGrey)
        self.assertEqual(len(kwargs['dataPoints']), 8)

    def testRefreshLayout3DForwardsPointDepthsFromGeometryRecords(self):
        updateFromSurvey = MagicMock()
        self.mainWindow.layout3DWidget = SimpleNamespace(updateFromSurvey=updateFromSurvey)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.tbAllList.setChecked(True)
        self.mainWindow.tbSrcList.setChecked(True)
        self.mainWindow.tbRecList.setChecked(True)

        srcGeom = np.zeros(2, dtype=pntType1)
        srcGeom[0]['East'] = 100.0
        srcGeom[0]['North'] = 200.0
        srcGeom[0]['Elev'] = 0.0
        srcGeom[0]['Depth'] = 1500.0
        srcGeom[0]['InUse'] = 1
        srcGeom[1]['East'] = 110.0
        srcGeom[1]['North'] = 210.0
        srcGeom[1]['Elev'] = 10.0
        srcGeom[1]['Depth'] = 810.0
        srcGeom[1]['InUse'] = 0

        recGeom = np.zeros(1, dtype=pntType1)
        recGeom[0]['East'] = 300.0
        recGeom[0]['North'] = 400.0
        recGeom[0]['Elev'] = 5.0
        recGeom[0]['Depth'] = 905.0
        recGeom[0]['InUse'] = 1

        self.mainWindow.srcGeom = srcGeom
        self.mainWindow.recGeom = recGeom

        layoutTabModule.refreshLayout3DFromSurvey(self.mainWindow)

        pointSets = updateFromSurvey.call_args.kwargs['pointSets']
        self.assertEqual(len(pointSets), 3)
        np.testing.assert_allclose(pointSets[0]['zs'], np.array([-1500.0], dtype=np.float64))
        np.testing.assert_allclose(pointSets[1]['zs'], np.array([-800.0], dtype=np.float64))
        np.testing.assert_allclose(pointSets[2]['zs'], np.array([-900.0], dtype=np.float64))

    def testRefreshLayout3DForwardsPointSetsEvenWhenShowPointsIsOff(self):
        updateFromSurvey = MagicMock()
        self.mainWindow.layout3DWidget = SimpleNamespace(updateFromSurvey=updateFromSurvey)
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.actionShowPoints.setChecked(False)
        self.mainWindow.tbSpsList.setChecked(True)
        self.mainWindow.spsLiveE = np.array([10.0], dtype=np.float64)
        self.mainWindow.spsLiveN = np.array([20.0], dtype=np.float64)

        layoutTabModule.refreshLayout3DFromSurvey(self.mainWindow)

        kwargs = updateFromSurvey.call_args.kwargs
        self.assertEqual(len(kwargs['pointSets']), 1)
        self.assertEqual(len(kwargs['dataPoints']), 1)

    def testApplySurveyAreaShiftMovesTemplateSeedsRebuildsDerivedStateAndKeepsWellAnchored(self):
        survey = self.createSurvey()
        survey.createBasicSkeleton(nBlocks=1, nTemplates=1, nSrcSeeds=1, nRecSeeds=4, nPatterns=1)

        template = survey.blockList[0].templateList[0]
        srcSeed = template.seedList[0]
        recSeed = template.seedList[1]
        circleSeed = template.seedList[2]
        spiralSeed = template.seedList[3]
        wellSeed = template.seedList[4]
        patternSeed = survey.patternList[0].seedList[0]

        srcSeed.origin = QVector3D(10.0, 20.0, -5.0)
        recSeed.origin = QVector3D(40.0, 50.0, 0.0)

        circleSeed.type = rollSurveyModule.SeedType.circle
        circleSeed.origin = QVector3D(100.0, 200.0, 0.0)
        circleSeed.circle.radius = 10.0
        circleSeed.circle.dist = 5.0
        circleSeed.circle.calcNoPoints()

        spiralSeed.type = rollSurveyModule.SeedType.spiral
        spiralSeed.origin = QVector3D(300.0, 400.0, 0.0)
        spiralSeed.spiral.radMin = 10.0
        spiralSeed.spiral.radMax = 20.0
        spiralSeed.spiral.radInc = 10.0
        spiralSeed.spiral.dist = 5.0
        spiralSeed.spiral.calcNoPoints()

        wellSeed.type = rollSurveyModule.SeedType.well
        wellSeed.origin = QVector3D(500.0, 600.0, -50.0)
        patternSeed.origin = QVector3D(700.0, 800.0, 10.0)

        with patch.object(wellSeed.well, 'calcPointList', return_value=([QVector3D(500.0, 600.0, -50.0), QVector3D(501.0, 601.0, -55.0)], QVector3D(500.0, 600.0, -50.0))):
            survey.calcTransforms()
            survey.calcSeedData()
            survey.calcPointArrays()
            survey.calcBoundingRect()
            survey.calcNoShotPoints()

            originalCirclePoint = QVector3D(circleSeed.pointList[0])
            originalSpiralPoint = QVector3D(spiralSeed.pointList[0])
            originalSpiralBounds = spiralSeed.spiral.path.boundingRect()

            self.mainWindow.survey = survey
            self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)
            self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
            self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
            self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)
            self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
            self.mainWindow.output.binOutput = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.minOffset = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.maxOffset = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.rmsOffset = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.gapOffset = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.anaOutput = object()
            self.mainWindow.output.an2Output = object()
            self.mainWindow.output.ofAziHist = np.ones((1, 1), dtype=np.float32)
            self.mainWindow.output.offstHist = np.ones((1, 1), dtype=np.float32)

            with patch.object(self.mainWindow, 'resetSurveyProperties') as resetSurveyProperties:
                with patch.object(self.mainWindow, 'plotLayout') as plotLayout:
                    with patch.object(rollMainWindowModule, 'refreshLayout3DFromSurvey') as refreshLayout3D:
                        success = self.mainWindow.applySurveyAreaShift(12.5, -7.5)

        self.assertTrue(success)
        self.assertEqual((srcSeed.origin.x(), srcSeed.origin.y(), srcSeed.origin.z()), (22.5, 12.5, -5.0))
        self.assertEqual((recSeed.origin.x(), recSeed.origin.y(), recSeed.origin.z()), (52.5, 42.5, 0.0))
        self.assertEqual((circleSeed.origin.x(), circleSeed.origin.y(), circleSeed.origin.z()), (112.5, 192.5, 0.0))
        self.assertEqual((spiralSeed.origin.x(), spiralSeed.origin.y(), spiralSeed.origin.z()), (312.5, 392.5, 0.0))
        self.assertEqual((wellSeed.origin.x(), wellSeed.origin.y(), wellSeed.origin.z()), (500.0, 600.0, -50.0))
        self.assertEqual((patternSeed.origin.x(), patternSeed.origin.y(), patternSeed.origin.z()), (700.0, 800.0, 10.0))

        self.assertAlmostEqual(circleSeed.pointList[0].x() - originalCirclePoint.x(), 12.5)
        self.assertAlmostEqual(circleSeed.pointList[0].y() - originalCirclePoint.y(), -7.5)
        self.assertAlmostEqual(float(circleSeed.pointArray[0, 0]) - originalCirclePoint.x(), 12.5)
        self.assertAlmostEqual(float(circleSeed.pointArray[0, 1]) - originalCirclePoint.y(), -7.5)

        self.assertAlmostEqual(spiralSeed.pointList[0].x() - originalSpiralPoint.x(), 12.5)
        self.assertAlmostEqual(spiralSeed.pointList[0].y() - originalSpiralPoint.y(), -7.5)
        self.assertAlmostEqual(float(spiralSeed.pointArray[0, 0]) - originalSpiralPoint.x(), 12.5)
        self.assertAlmostEqual(float(spiralSeed.pointArray[0, 1]) - originalSpiralPoint.y(), -7.5)
        shiftedSpiralBounds = spiralSeed.spiral.path.boundingRect()
        self.assertAlmostEqual(shiftedSpiralBounds.left() - originalSpiralBounds.left(), 12.5)
        self.assertAlmostEqual(shiftedSpiralBounds.top() - originalSpiralBounds.top(), -7.5)

        self.assertIsNone(self.mainWindow.srcGeom)
        self.assertIsNone(self.mainWindow.recGeom)
        self.assertIsNone(self.mainWindow.relGeom)
        self.assertIsNotNone(self.mainWindow.rpsImport)
        self.assertIsNotNone(self.mainWindow.spsImport)
        self.assertIsNotNone(self.mainWindow.xpsImport)
        self.assertIsNone(self.mainWindow.output.binOutput)
        self.assertIsNone(self.mainWindow.output.gapOffset)
        self.assertIsNone(self.mainWindow.output.anaOutput)
        self.assertIsNone(self.mainWindow.output.an2Output)
        self.assertIsNone(self.mainWindow.output.ofAziHist)
        self.assertIsNone(self.mainWindow.output.offstHist)

        xmlText = self.mainWindow.textEdit.getTextViaCursor()
        self.assertIn('x0="22.5"', xmlText)
        self.assertIn('y0="12.5"', xmlText)
        self.assertIn('x0="700.0"', xmlText)
        self.assertTrue(self.mainWindow.textEdit.document().isModified())
        resetSurveyProperties.assert_called_once_with()
        self.assertGreaterEqual(plotLayout.call_count, 1)
        refreshLayout3D.assert_called_once_with(self.mainWindow)

    def testReplotLayoutRefreshes3DSubset(self):
        self.mainWindow.survey = self.createSurvey()

        with patch.object(self.mainWindow, 'plotLayout'), patch.object(rollMainWindowModule, 'refreshLayout3DFromSurvey') as refreshLayout3D:
            self.mainWindow.replotLayout()

        refreshLayout3D.assert_called_once_with(self.mainWindow)

    def testBinFromTemplatesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.nShotPoints = 12

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinningWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromTemplates(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromTemplatesRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.assertEqual(request.includeProfiling, self.mainWindow.appSettings.debug)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        self.assertEqual(threadStub.finished.connect.call_count, 2)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinningWorkerRunEmitsTypedResultsOnSuccessAndFailure(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.anaOutput = None
                self.output.binOutput = np.ones((2, 2), dtype=np.float32)
                self.output.minOffset = np.full((2, 2), 10.0, dtype=np.float32)
                self.output.maxOffset = np.full((2, 2), 20.0, dtype=np.float32)
                self.output.minimumFold = 1
                self.output.maximumFold = 4
                self.output.minMinOffset = 10.0
                self.output.maxMinOffset = 10.0
                self.output.minMaxOffset = 20.0
                self.output.maxMaxOffset = 20.0
                self.output.minRmsOffset = 0.0
                self.output.maxRmsOffset = 0.0
                self.output.rmsOffset = None
                self.output.ofAziHist = None
                self.output.offstHist = None
                self.cmpTransform = 'cmp-transform'
                self.errorText = 'setup failed'
                self.shouldSucceed = True
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False
                self.extended: bool | None = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupBinFromTemplates(self, extended):
                self.extended = extended
                return self.shouldSucceed

        request = BinningFromTemplatesRequest(xmlString='<survey />', extended=True, analysisFile=None, debugpyEnabled=False, includeProfiling=False)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = BinningWorker(request)

            resultEvents = []
            finishedEvents = []
            worker.resultReady.connect(resultEvents.append)
            worker.finished.connect(lambda: finishedEvents.append('finished'))

            worker.run()

            self.assertEqual(len(resultEvents), 1)
            self.assertEqual(type(resultEvents[0]).__name__, 'BinningFromTemplatesResult')
            self.assertTrue(resultEvents[0].success)
            self.assertIs(resultEvents[0].binOutput, worker.survey.output.binOutput)
            self.assertIs(resultEvents[0].minOffset, worker.survey.output.minOffset)
            self.assertIs(resultEvents[0].maxOffset, worker.survey.output.maxOffset)
            self.assertIsNone(resultEvents[0].minRmsOffset)
            self.assertIsNone(resultEvents[0].maxRmsOffset)
            np.testing.assert_array_equal(resultEvents[0].binOutput, np.ones((2, 2), dtype=np.float32))
            self.assertEqual(resultEvents[0].cmpTransform, 'cmp-transform')
            self.assertEqual(finishedEvents, ['finished'])

            worker.survey.shouldSucceed = False
            resultEvents.clear()
            finishedEvents.clear()

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertEqual(type(resultEvents[0]).__name__, 'BinningFromTemplatesResult')
        self.assertFalse(resultEvents[0].success)
        self.assertEqual(resultEvents[0].errorText, 'setup failed')
        self.assertEqual(finishedEvents, ['finished'])

    def testBinningWorkerRunUsesOptionalProfilingPayload(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.anaOutput = None
                self.output.binOutput = np.ones((1, 1), dtype=np.float32)
                self.output.minOffset = np.ones((1, 1), dtype=np.float32)
                self.output.maxOffset = np.ones((1, 1), dtype=np.float32)
                self.output.minimumFold = 1
                self.output.maximumFold = 1
                self.output.minMinOffset = 1.0
                self.output.maxMinOffset = 1.0
                self.output.minMaxOffset = 1.0
                self.output.maxMaxOffset = 1.0
                self.output.minRmsOffset = 0.0
                self.output.maxRmsOffset = 0.0
                self.output.rmsOffset = None
                self.output.minOffsetGap = 0.0
                self.output.maxOffsetGap = 0.0
                self.output.gapOffset = None
                self.output.ofAziHist = None
                self.output.offstHist = None
                self.cmpTransform = 'cmp-transform'
                self.errorText = 'binning failed'
                self.shouldSucceed = True
                self.timerTmin = [0.0]
                self.timerTmax = [1.0]
                self.timerTtot = [2.0]
                self.timerFreq = [3]
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupBinFromTemplates(self, _):
                return self.shouldSucceed

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = BinningWorker(BinningFromTemplatesRequest(xmlString='<survey />', includeProfiling=True))

            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

            self.assertEqual(len(resultEvents), 1)
            self.assertEqual(type(resultEvents[0]).__name__, 'BinningFromTemplatesResult')
            self.assertEqual(type(resultEvents[0].profiling).__name__, 'GeometryProfilingPayload')
            self.assertEqual(resultEvents[0].profiling.timerTmin, (0.0,))
            self.assertEqual(resultEvents[0].profiling.timerTmax, (1.0,))
            self.assertEqual(resultEvents[0].profiling.timerTtot, (2.0,))
            self.assertEqual(resultEvents[0].profiling.timerFreq, (3,))

            worker = BinningWorker(BinningFromTemplatesRequest(xmlString='<survey />', includeProfiling=False))
            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertIsNone(resultEvents[0].profiling)

    def testBinningTemplatesThreadFinishedUsesResultObject(self):
        result = BinningFromTemplatesResult(
            success=True,
            binOutput=np.ones((2, 2), dtype=np.float32),
            minOffset=np.full((2, 2), 10.0, dtype=np.float32),
            maxOffset=np.full((2, 2), 20.0, dtype=np.float32),
            minimumFold=1,
            maximumFold=4,
            minMinOffset=10.0,
            maxMinOffset=10.0,
            minMaxOffset=20.0,
            maxMaxOffset=20.0,
            minRmsOffset=0.0,
            maxRmsOffset=0.0,
            rmsOffset=None,
            minOffsetGap=5.0,
            maxOffsetGap=15.0,
            gapOffset=np.full((2, 2), 15.0, dtype=np.float32),
            ofAziHist=None,
            offstHist=None,
            cmpTransform='cmp-transform',
            anaOutputShape=None,
        )

        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.imageType = 1
        self.mainWindow.fileName = ''
        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningTemplatesThreadFinished(result)

        np.testing.assert_array_equal(self.mainWindow.output.binOutput, result.binOutput)
        np.testing.assert_array_equal(self.mainWindow.output.minOffset, result.minOffset)
        np.testing.assert_array_equal(self.mainWindow.output.maxOffset, result.maxOffset)
        np.testing.assert_array_equal(self.mainWindow.output.gapOffset, result.gapOffset)
        self.assertEqual(self.mainWindow.output.maximumFold, 4)
        self.assertEqual(self.mainWindow.survey.cmpTransform, 'cmp-transform')
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testBinningTemplatesThreadFinishedHandlesFailureResult(self):
        result = BinningFromTemplatesResult(success=False, errorText='worker failed')

        self.mainWindow.layoutImg = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.layoutImItem = object()
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningTemplatesThreadFinished(result)

        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        appendLogMessage.assert_any_call('Thread : . . . aborted binning operation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testApplyPropertyChangesResetsAnalysisCachesWhenBinAreaChanges(self):
        self.mainWindow.fileName = os.path.join(tempfile.gettempdir(), 'phase0_refresh.roll')
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.x0lineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.plotRedrawHelper.storeInlineResponseKey(3)
        self.mainWindow.plotRedrawHelper.storeXlineResponseKey(4)
        self.mainWindow.plotRedrawHelper.storeStackCellResponse((1, 2, False, 0, 0), 5)
        self.mainWindow.plotRedrawHelper.storePatternResponseKey((6, 7))
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.minOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.maxOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.rmsOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.gapOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.offstHist = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.binAreaChanged = True

        with patch.object(self.mainWindow, 'setPlottingDetails'):
            with patch.object(self.mainWindow, 'resetAnaTableModel', return_value=False):
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'updatePatternList'):
                            with patch.object(self.mainWindow, 'plotLayout'):
                                self.mainWindow.applyPropertyChanges()

        self.assertFalse(self.mainWindow.binAreaChanged)
        self.assertIsNone(self.mainWindow.inlineStk)
        self.assertIsNone(self.mainWindow.x0lineStk)
        self.assertIsNone(self.mainWindow.xyCellStk)
        self.assertIsNone(self.mainWindow.xyPatResp)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.inlineStkKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.xlineStkKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellResponseKey)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.stackCellFold)
        self.assertIsNone(self.mainWindow.plotRedrawHelper.cache.patternResponseKey)
        self.assertIsNone(self.mainWindow.output.binOutput)
        self.assertIsNone(self.mainWindow.output.minOffset)
        self.assertIsNone(self.mainWindow.output.maxOffset)
        self.assertIsNone(self.mainWindow.output.rmsOffset)
        self.assertIsNone(self.mainWindow.output.gapOffset)
        self.assertIsNone(self.mainWindow.output.ofAziHist)
        self.assertIsNone(self.mainWindow.output.offstHist)
        updateMenuStatus.assert_called_once_with(True)
        enableProcessingMenuItems.assert_called_once_with(True)

    def testResetSurveyPropertiesUsesSurveyDeepcopyForWorkingCopy(self):
        survey = self.createSurvey()
        surveyCopy = survey.deepcopy()
        self.mainWindow.survey = survey

        with patch.object(self.mainWindow.survey, 'deepcopy', return_value=surveyCopy) as deepcopy:
            with patch.object(self.mainWindow, 'updatePatternList') as updatePatternList:
                self.mainWindow.resetSurveyProperties()

        deepcopy.assert_called_once_with()
        updatePatternList.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesKeepsAnalysisCachesWhenBinAreaUnchanged(self):
        self.mainWindow.fileName = os.path.join(tempfile.gettempdir(), 'phase0_keep_caches.roll')
        self.mainWindow.inlineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.x0lineStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyCellStk = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.xyPatResp = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.binOutput = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.minOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.maxOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.rmsOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.gapOffset = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.ofAziHist = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.offstHist = np.ones((2, 3), dtype=np.float32)
        self.mainWindow.binAreaChanged = False

        with patch.object(self.mainWindow, 'setPlottingDetails'):
            with patch.object(self.mainWindow, 'resetAnaTableModel', return_value=False) as resetAnaTableModel:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'updatePatternList'):
                            with patch.object(self.mainWindow, 'plotLayout'):
                                self.mainWindow.applyPropertyChanges()

        resetAnaTableModel.assert_not_called()
        self.assertFalse(self.mainWindow.binAreaChanged)
        self.assertIsNotNone(self.mainWindow.inlineStk)
        self.assertIsNotNone(self.mainWindow.x0lineStk)
        self.assertIsNotNone(self.mainWindow.xyCellStk)
        self.assertIsNotNone(self.mainWindow.xyPatResp)
        self.assertIsNotNone(self.mainWindow.output.binOutput)
        self.assertIsNotNone(self.mainWindow.output.minOffset)
        self.assertIsNotNone(self.mainWindow.output.maxOffset)
        self.assertIsNotNone(self.mainWindow.output.rmsOffset)
        self.assertIsNotNone(self.mainWindow.output.gapOffset)
        self.assertIsNotNone(self.mainWindow.output.ofAziHist)
        self.assertIsNotNone(self.mainWindow.output.offstHist)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)

    def testApplyPropertyChangesPreservesStreamerPlottingDetails(self):
        surveyCopy = self.createSurvey()
        surveyCopy.type = rollMainWindowModule.SurveyType.Streamer
        self.mainWindow.survey.type = rollMainWindowModule.SurveyType.Streamer
        self.mainWindow.survey.paintDetails = rollMainWindowModule.PaintDetails.srcAndRec | rollMainWindowModule.PaintDetails.templat
        self.mainWindow.survey.paintMode = rollMainWindowModule.PaintMode.all
        self.mainWindow.binAreaChanged = False

        with patch.object(self.mainWindow.propertyPanelController, '_buildSurveyFromParameters', return_value=surveyCopy):
            with patch.object(self.mainWindow, 'setPlottingDetails') as setPlottingDetails:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'updatePatternList'):
                            with patch.object(self.mainWindow, 'plotLayout'):
                                with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                    self.mainWindow.applyPropertyChanges()

        setPlottingDetails.assert_not_called()
        self.assertEqual(self.mainWindow.survey.type, rollMainWindowModule.SurveyType.Streamer)
        self.assertEqual(
            self.mainWindow.survey.paintDetails,
            rollMainWindowModule.PaintDetails.srcAndRec | rollMainWindowModule.PaintDetails.templat,
        )
        self.assertEqual(self.mainWindow.survey.paintMode, rollMainWindowModule.PaintMode.all)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)

    def testPropertyTreeStateChangedUpdatesWellDirectoryForWellFileValue(self):
        class FakeParam:
            def name(self):
                return 'Well file'

        param = FakeParam()
        wellFile = os.path.join(tempfile.gettempdir(), 'wells', 'survey.well')
        expectedDirectory = os.path.dirname(wellFile)
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'Seed', 'Well file'])
        self.mainWindow.wellDirectory = ''

        with patch.object(propertyPanelControllerModule, 'syncWellDirectoryForParameterTree') as syncWellDirectory:
            self.mainWindow.propertyTreeStateChanged(param, [(param, 'value', wellFile)])

        self.assertEqual(self.mainWindow.wellDirectory, expectedDirectory)
        syncWellDirectory.assert_called_once_with(param, expectedDirectory)

    def testPropertyTreeStateChangedIgnoresNonMatchingWellDirectoryChanges(self):
        class FakeParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'Seed'])
        self.mainWindow.wellDirectory = 'D:/existing'

        testCases = [
            ('not-value', FakeParam('Well file'), 'value.tmp'),
            ('value', FakeParam('Not well file'), 'value.tmp'),
            ('value', FakeParam('Well file'), None),
            ('value', FakeParam('Well file'), ''),
            ('value', FakeParam('Well file'), 'survey.well'),
        ]

        with patch.object(propertyPanelControllerModule, 'syncWellDirectoryForParameterTree') as syncWellDirectory:
            for change, param, data in testCases:
                with self.subTest(change=change, name=param.name(), data=data):
                    self.mainWindow.propertyTreeStateChanged(param, [(param, change, data)])

        self.assertEqual(self.mainWindow.wellDirectory, 'D:/existing')
        syncWellDirectory.assert_not_called()

    def testSeedNameChangeDetectedTracksNormalSeedRename(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        param = FakeSeedParam('src-2')
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedNames[id(param)] = 'src-1'
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-2'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(param, [(param, 'name', 'src-2')])

        self.assertEqual(controller._pendingSeedRenames[id(param)]['oldName'], 'src-1')
        self.assertEqual(controller._pendingSeedRenames[id(param)]['newName'], 'src-2')

    def testSeedColorChangeDetectedTracksNormalSeedColorChange(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakeColorParam:
            def __init__(self, seedParam, color):
                self._seedParam = seedParam
                self._color = color

            def name(self):
                return 'Seed color'

            def parent(self):
                return self._seedParam

            def value(self):
                return self._color

        seedParam = FakeSeedParam('src-1')
        colorParam = FakeColorParam(seedParam, QColor('#77ff0000'))
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedColors[id(seedParam)] = QColor('#7700ff00')
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Seed color'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(colorParam, [(colorParam, 'value', QColor('#77ff0000'))])

        self.assertEqual(
            controller._pendingSeedColors[id(seedParam)]['oldColor'].name(QColor.NameFormat.HexArgb),
            QColor('#7700ff00').name(QColor.NameFormat.HexArgb),
        )
        self.assertEqual(
            controller._pendingSeedColors[id(seedParam)]['newColor'].name(QColor.NameFormat.HexArgb),
            QColor('#77ff0000').name(QColor.NameFormat.HexArgb),
        )

    def testSeedOriginShiftDetectedTracksNormalSeedOriginShift(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakeOriginParam:
            def __init__(self, seedParam, origin):
                self._seedParam = seedParam
                self._origin = QVector3D(origin)

            def name(self):
                return 'Seed origin'

            def parent(self):
                return self._seedParam

            def value(self):
                return QVector3D(self._origin)

        oldOrigin = QVector3D(10.0, 20.0, -5.0)
        newOrigin = QVector3D(15.0, 18.0, -3.0)
        seedParam = FakeSeedParam('src-1')
        originParam = FakeOriginParam(seedParam, newOrigin)
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedOrigins[id(seedParam)] = QVector3D(oldOrigin)
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Seed origin'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(originParam, [(originParam, 'value', QVector3D(newOrigin))])

        pendingOrigin = controller._pendingSeedOrigins[id(seedParam)]
        self.assertEqual((pendingOrigin['oldOrigin'].x(), pendingOrigin['oldOrigin'].y(), pendingOrigin['oldOrigin'].z()), (10.0, 20.0, -5.0))
        self.assertEqual((pendingOrigin['newOrigin'].x(), pendingOrigin['newOrigin'].y(), pendingOrigin['newOrigin'].z()), (15.0, 18.0, -3.0))

    def testSeedOriginShiftDetectedFromOriginAxisChildChange(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakeOriginParam:
            def __init__(self, seedParam, origin):
                self._seedParam = seedParam
                self._origin = QVector3D(origin)

            def name(self):
                return 'Seed origin'

            def parent(self):
                return self._seedParam

            def value(self):
                return QVector3D(self._origin)

        class FakeAxisParam:
            def __init__(self, originParam, name):
                self._originParam = originParam
                self._name = name

            def name(self):
                return self._name

            def parent(self):
                return self._originParam

        oldOrigin = QVector3D(10.0, 20.0, -5.0)
        newOrigin = QVector3D(15.0, 20.0, -5.0)
        seedParam = FakeSeedParam('src-1')
        originParam = FakeOriginParam(seedParam, newOrigin)
        axisParam = FakeAxisParam(originParam, 'X')
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedOrigins[id(seedParam)] = QVector3D(oldOrigin)
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Seed origin', 'X'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(axisParam, [(axisParam, 'value', 15.0)])

        pendingOrigin = controller._pendingSeedOrigins[id(seedParam)]
        self.assertEqual((pendingOrigin['oldOrigin'].x(), pendingOrigin['oldOrigin'].y(), pendingOrigin['oldOrigin'].z()), (10.0, 20.0, -5.0))
        self.assertEqual((pendingOrigin['newOrigin'].x(), pendingOrigin['newOrigin'].y(), pendingOrigin['newOrigin'].z()), (15.0, 20.0, -5.0))

    def testSeedPatternChangeDetectedTracksNormalSeedPatternChange(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakePatternParam:
            def __init__(self, seedParam, value):
                self._seedParam = seedParam
                self._value = value

            def name(self):
                return 'Seed pattern'

            def parent(self):
                return self._seedParam

            def value(self):
                return self._value

        seedParam = FakeSeedParam('src-1')
        patternParam = FakePatternParam(seedParam, 'pat-2')
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedPatterns[id(seedParam)] = 'pat-1'
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Seed pattern'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(patternParam, [(patternParam, 'value', 'pat-2')])

        pendingPattern = controller._pendingSeedPatterns[id(seedParam)]
        self.assertEqual(pendingPattern['oldPattern'], 'pat-1')
        self.assertEqual(pendingPattern['newPattern'], 'pat-2')

    def testSeedGridGrowStepsChangeDetectedFromNestedChildChange(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakeGridParam:
            def __init__(self, seedParam, growList):
                self._seedParam = seedParam
                self._growList = growList

            def name(self):
                return 'Grid grow steps'

            def parent(self):
                return self._seedParam

            def value(self):
                return self._growList

        class FakeStepParam:
            def __init__(self, gridParam, name):
                self._gridParam = gridParam
                self._name = name

            def name(self):
                return self._name

            def parent(self):
                return self._gridParam

        class FakeLeafParam:
            def __init__(self, stepParam, name):
                self._stepParam = stepParam
                self._name = name

            def name(self):
                return self._name

            def parent(self):
                return self._stepParam

        def makeGrowList(values):
            growList = []
            for steps, dx, dy, dz in values:
                translate = propertyPanelControllerModule.RollTranslate()
                translate.steps = steps
                translate.increment.setX(dx)
                translate.increment.setY(dy)
                translate.increment.setZ(dz)
                growList.append(translate)
            return growList

        oldGrowList = makeGrowList(((1, 0.0, 0.0, 0.0), (2, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0)))
        newGrowList = makeGrowList(((1, 0.0, 0.0, 0.0), (4, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0)))
        seedParam = FakeSeedParam('src-1')
        gridParam = FakeGridParam(seedParam, newGrowList)
        stepParam = FakeStepParam(gridParam, 'Lines')
        leafParam = FakeLeafParam(stepParam, 'N')
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedGridGrowLists[id(seedParam)] = controller._copyGrowList(oldGrowList)
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Grid grow steps', 'Lines', 'N'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(leafParam, [(leafParam, 'value', 4)])

        pendingGrowList = controller._pendingSeedGridGrowLists[id(seedParam)]
        self.assertEqual(controller._growListKey(pendingGrowList['oldGrowList']), controller._growListKey(oldGrowList))
        self.assertEqual(controller._growListKey(pendingGrowList['newGrowList']), controller._growListKey(newGrowList))

    def testSeedGridGrowStepsChangeDetectedWhenParentValueIsStale(self):
        class FakeSeedParam:
            def __init__(self, name):
                self._name = name

            def name(self):
                return self._name

        class FakeValueParam:
            def __init__(self, parent, name, value):
                self._parent = parent
                self._name = name
                self._value = value

            def name(self):
                return self._name

            def parent(self):
                return self._parent

            def value(self):
                return self._value

        class FakeStepParam:
            def __init__(self, gridParam, name, values, *, staleTranslate):
                self._gridParam = gridParam
                self._name = name
                self._staleTranslate = staleTranslate
                self._children = {
                    'N': FakeValueParam(self, 'N', values[0]),
                    'dX': FakeValueParam(self, 'dX', values[1]),
                    'dY': FakeValueParam(self, 'dY', values[2]),
                    'dZ': FakeValueParam(self, 'dZ', values[3]),
                }

            def name(self):
                return self._name

            def parent(self):
                return self._gridParam

            def child(self, name):
                return self._children[name]

            def value(self):
                return self._staleTranslate

        class FakeGridParam:
            def __init__(self, seedParam, oldGrowList, newGrowValues):
                self._seedParam = seedParam
                self._oldGrowList = oldGrowList
                self._children = {
                    stepName: FakeStepParam(self, stepName, stepValues, staleTranslate=oldGrowList[index])
                    for index, (stepName, stepValues) in enumerate(zip(('Planes', 'Lines', 'Points'), newGrowValues))
                }

            def name(self):
                return 'Grid grow steps'

            def parent(self):
                return self._seedParam

            def child(self, name):
                return self._children[name]

            def value(self):
                return self._oldGrowList

        class FakeLeafParam:
            def __init__(self, stepParam, name):
                self._stepParam = stepParam
                self._name = name

            def name(self):
                return self._name

            def parent(self):
                return self._stepParam

        def makeGrowList(values):
            growList = []
            for steps, dx, dy, dz in values:
                translate = propertyPanelControllerModule.RollTranslate()
                translate.steps = steps
                translate.increment.setX(dx)
                translate.increment.setY(dy)
                translate.increment.setZ(dz)
                growList.append(translate)
            return growList

        oldGrowList = makeGrowList(((1, 0.0, 0.0, 0.0), (2, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0)))
        newGrowValues = ((1, 0.0, 0.0, 0.0), (4, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0))
        newGrowList = makeGrowList(newGrowValues)
        seedParam = FakeSeedParam('src-1')
        gridParam = FakeGridParam(seedParam, oldGrowList, newGrowValues)
        stepParam = gridParam.child('Lines')
        leafParam = FakeLeafParam(stepParam, 'N')
        controller = self.mainWindow.propertyPanelController
        controller._trackedSeedGridGrowLists[id(seedParam)] = controller._copyGrowList(oldGrowList)
        self.mainWindow.parameters = SimpleNamespace(childPath=lambda _: ['Block list', 'template-1', 'src-1', 'Grid grow steps', 'Lines', 'N'])

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            self.mainWindow.propertyTreeStateChanged(leafParam, [(leafParam, 'value', 4)])

        pendingGrowList = controller._pendingSeedGridGrowLists[id(seedParam)]
        self.assertEqual(controller._growListKey(pendingGrowList['oldGrowList']), controller._growListKey(oldGrowList))
        self.assertEqual(controller._growListKey(pendingGrowList['newGrowList']), controller._growListKey(newGrowList))

    def testApplyPropertyChangesPropagatesConfirmedSeedRenameToNormalSeeds(self):
        class FakeColorValue:
            def __init__(self, color):
                self._color = QColor(color)

            def value(self):
                return QColor(self._color)

        class FakeFloatValue:
            def __init__(self, value):
                self._value = float(value)

            def value(self):
                return self._value

        class FakePoint3DValue:
            def __init__(self, x=0.0, y=0.0, z=0.0):
                self._x = FakeFloatValue(x)
                self._y = FakeFloatValue(y)
                self._z = FakeFloatValue(z)

            def value(self):
                return QVector3D(self._x.value(), self._y.value(), self._z.value())

        class FakeSeedParam:
            def __init__(self, name, color='#7700ff00'):
                self._name = name
                self.parL = FakeColorValue(color)
                self.parO = FakePoint3DValue()

            def name(self):
                return self._name

            def setName(self, name):
                self._name = name

        renamedSeed = SimpleNamespace(name='src-2')
        matchingSeedA = SimpleNamespace(name='src-1')
        matchingSeedB = SimpleNamespace(name='src-1')
        untouchedSeed = SimpleNamespace(name='rec-1')
        workingTreeRenamedSeed = FakeSeedParam('src-2')
        workingTreeMatchingSeedA = FakeSeedParam('src-1')
        workingTreeMatchingSeedB = FakeSeedParam('src-1')
        workingTreeUntouchedSeed = FakeSeedParam('rec-1')
        surveyCopy = SimpleNamespace(
            blockList=[
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[renamedSeed, matchingSeedA, untouchedSeed]),
                        SimpleNamespace(seedList=[matchingSeedB]),
                    ]
                )
            ],
            checkIntegrity=lambda: True,
        )

        controller = self.mainWindow.propertyPanelController
        controller._pendingSeedRenames = {1: {'oldName': 'src-1', 'newName': 'src-2'}}
        self.mainWindow.paramTree = SimpleNamespace(
            listAllItems=lambda: [
                SimpleNamespace(param=workingTreeRenamedSeed),
                SimpleNamespace(param=workingTreeMatchingSeedA),
                SimpleNamespace(param=workingTreeMatchingSeedB),
                SimpleNamespace(param=workingTreeUntouchedSeed),
            ]
        )

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            with patch.object(controller, '_buildSurveyFromParameters', return_value=surveyCopy):
                with patch.object(controller, '_commitSurveyCopy') as commitSurveyCopy:
                    with patch.object(self.mainWindow, 'setPlottingDetails'):
                        with patch.object(self.mainWindow, 'updateMenuStatus'):
                            with patch.object(self.mainWindow, 'enableProcessingMenuItems'):
                                with patch.object(self.mainWindow, 'updatePatternList'):
                                    with patch.object(self.mainWindow, 'plotLayout'):
                                        with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                            with patch.object(propertyPanelControllerModule.QMessageBox, 'question', return_value=propertyPanelControllerModule.QMessageBox.StandardButton.Yes) as question:
                                                self.mainWindow.applyPropertyChanges()

        question.assert_called_once()
        self.assertEqual(renamedSeed.name, 'src-2')
        self.assertEqual(matchingSeedA.name, 'src-2')
        self.assertEqual(matchingSeedB.name, 'src-2')
        self.assertEqual(untouchedSeed.name, 'rec-1')
        self.assertEqual(workingTreeRenamedSeed.name(), 'src-2')
        self.assertEqual(workingTreeMatchingSeedA.name(), 'src-2')
        self.assertEqual(workingTreeMatchingSeedB.name(), 'src-2')
        self.assertEqual(workingTreeUntouchedSeed.name(), 'rec-1')
        commitSurveyCopy.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesPropagatesConfirmedSeedColorToNormalSeeds(self):
        class FakeColorValue:
            def __init__(self, color):
                self._color = QColor(color)

            def value(self):
                return QColor(self._color)

            def setValue(self, color):
                self._color = QColor(color)

        class FakeSeedParam:
            def __init__(self, name, color):
                self._name = name
                self.parL = FakeColorValue(color)
                self.parO = FakePoint3DValue(QVector3D())

            def name(self):
                return self._name

        class FakeFloatValue:
            def __init__(self, value):
                self._value = float(value)

            def value(self):
                return self._value

            def setValue(self, value):
                self._value = float(value)

        class FakePoint3DValue:
            def __init__(self, vector):
                self._children = {
                    'X': FakeFloatValue(vector.x()),
                    'Y': FakeFloatValue(vector.y()),
                    'Z': FakeFloatValue(vector.z()),
                }

            def value(self):
                return QVector3D(self.child('X').value(), self.child('Y').value(), self.child('Z').value())

            def child(self, name):
                return self._children[name]

        newColor = QColor('#77ff0000')
        oldColor = QColor('#7700ff00')
        renamedSeed = SimpleNamespace(name='src-1', color=QColor(newColor))
        matchingSeedA = SimpleNamespace(name='src-1', color=QColor(oldColor))
        matchingSeedB = SimpleNamespace(name='src-1', color=QColor(oldColor))
        untouchedSeed = SimpleNamespace(name='rec-1', color=QColor(oldColor))
        workingTreeChangedSeed = FakeSeedParam('src-1', newColor)
        workingTreeMatchingSeedA = FakeSeedParam('src-1', oldColor)
        workingTreeMatchingSeedB = FakeSeedParam('src-1', oldColor)
        workingTreeUntouchedSeed = FakeSeedParam('rec-1', oldColor)
        surveyCopy = SimpleNamespace(
            blockList=[
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[renamedSeed, matchingSeedA, untouchedSeed]),
                        SimpleNamespace(seedList=[matchingSeedB]),
                    ]
                )
            ],
            checkIntegrity=lambda: True,
        )

        controller = self.mainWindow.propertyPanelController
        controller._pendingSeedColors = {1: {'param': workingTreeChangedSeed, 'oldColor': QColor(oldColor), 'newColor': QColor(newColor)}}
        self.mainWindow.paramTree = SimpleNamespace(
            listAllItems=lambda: [
                SimpleNamespace(param=workingTreeChangedSeed),
                SimpleNamespace(param=workingTreeMatchingSeedA),
                SimpleNamespace(param=workingTreeMatchingSeedB),
                SimpleNamespace(param=workingTreeUntouchedSeed),
            ]
        )

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            with patch.object(controller, '_buildSurveyFromParameters', return_value=surveyCopy):
                with patch.object(controller, '_commitSurveyCopy') as commitSurveyCopy:
                    with patch.object(self.mainWindow, 'setPlottingDetails'):
                        with patch.object(self.mainWindow, 'updateMenuStatus'):
                            with patch.object(self.mainWindow, 'enableProcessingMenuItems'):
                                with patch.object(self.mainWindow, 'updatePatternList'):
                                    with patch.object(self.mainWindow, 'plotLayout'):
                                        with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                            with patch.object(propertyPanelControllerModule.QMessageBox, 'question', return_value=propertyPanelControllerModule.QMessageBox.StandardButton.Yes) as question:
                                                self.mainWindow.applyPropertyChanges()

        question.assert_called_once()
        self.assertEqual(renamedSeed.color.name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(matchingSeedA.color.name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(matchingSeedB.color.name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(untouchedSeed.color.name(QColor.NameFormat.HexArgb), oldColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(workingTreeChangedSeed.parL.value().name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(workingTreeMatchingSeedA.parL.value().name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(workingTreeMatchingSeedB.parL.value().name(QColor.NameFormat.HexArgb), newColor.name(QColor.NameFormat.HexArgb))
        self.assertEqual(workingTreeUntouchedSeed.parL.value().name(QColor.NameFormat.HexArgb), oldColor.name(QColor.NameFormat.HexArgb))
        commitSurveyCopy.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesPropagatesConfirmedSeedOriginShiftToNormalSeeds(self):
        class FakeColorValue:
            def __init__(self, color):
                self._color = QColor(color)

            def value(self):
                return QColor(self._color)

        class FakeFloatValue:
            def __init__(self, value):
                self._value = float(value)

            def value(self):
                return self._value

            def setValue(self, value):
                self._value = float(value)

        class FakePoint3DValue:
            def __init__(self, vector):
                self._children = {
                    'X': FakeFloatValue(vector.x()),
                    'Y': FakeFloatValue(vector.y()),
                    'Z': FakeFloatValue(vector.z()),
                }

            def value(self):
                return QVector3D(self.child('X').value(), self.child('Y').value(), self.child('Z').value())

            def child(self, name):
                return self._children[name]

        class FakeSeedParam:
            def __init__(self, name, origin, color='#7700ff00'):
                self._name = name
                self.parL = FakeColorValue(color)
                self.parO = FakePoint3DValue(origin)

            def name(self):
                return self._name

        oldOrigin = QVector3D(10.0, 20.0, -5.0)
        newOrigin = QVector3D(15.0, 18.0, -3.0)
        shift = QVector3D(5.0, -2.0, 2.0)

        changedSeed = SimpleNamespace(name='src-1', origin=QVector3D(newOrigin))
        matchingSeedA = SimpleNamespace(name='src-1', origin=QVector3D(30.0, 40.0, 0.0))
        matchingSeedB = SimpleNamespace(name='src-1', origin=QVector3D(-10.0, 5.0, 8.0))
        matchingSeedC = SimpleNamespace(name='src-1', origin=QVector3D(100.0, -50.0, 12.0))
        untouchedSeed = SimpleNamespace(name='rec-1', origin=QVector3D(1.0, 2.0, 3.0))
        workingTreeChangedSeed = FakeSeedParam('src-1', newOrigin)
        workingTreeMatchingSeedA = FakeSeedParam('src-1', QVector3D(30.0, 40.0, 0.0))
        workingTreeMatchingSeedB = FakeSeedParam('src-1', QVector3D(-10.0, 5.0, 8.0))
        workingTreeMatchingSeedC = FakeSeedParam('src-1', QVector3D(100.0, -50.0, 12.0))
        workingTreeUntouchedSeed = FakeSeedParam('rec-1', QVector3D(1.0, 2.0, 3.0))
        surveyCopy = SimpleNamespace(
            blockList=[
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[changedSeed, matchingSeedA, untouchedSeed]),
                        SimpleNamespace(seedList=[matchingSeedB]),
                    ]
                ),
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[matchingSeedC]),
                    ]
                )
            ],
            checkIntegrity=lambda: True,
        )

        controller = self.mainWindow.propertyPanelController
        controller._pendingSeedOrigins = {1: {'param': workingTreeChangedSeed, 'oldOrigin': QVector3D(oldOrigin), 'newOrigin': QVector3D(newOrigin)}}
        self.mainWindow.paramTree = SimpleNamespace(
            listAllItems=lambda: [
                SimpleNamespace(param=workingTreeChangedSeed),
                SimpleNamespace(param=workingTreeMatchingSeedA),
                SimpleNamespace(param=workingTreeMatchingSeedB),
                SimpleNamespace(param=workingTreeMatchingSeedC),
                SimpleNamespace(param=workingTreeUntouchedSeed),
            ]
        )

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            with patch.object(controller, '_buildSurveyFromParameters', return_value=surveyCopy):
                with patch.object(controller, '_commitSurveyCopy') as commitSurveyCopy:
                    with patch.object(self.mainWindow, 'setPlottingDetails'):
                        with patch.object(self.mainWindow, 'updateMenuStatus'):
                            with patch.object(self.mainWindow, 'enableProcessingMenuItems'):
                                with patch.object(self.mainWindow, 'updatePatternList'):
                                    with patch.object(self.mainWindow, 'plotLayout'):
                                        with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                            with patch.object(propertyPanelControllerModule.QMessageBox, 'question', return_value=propertyPanelControllerModule.QMessageBox.StandardButton.Yes) as question:
                                                self.mainWindow.applyPropertyChanges()

        question.assert_called_once()
        self.assertEqual((changedSeed.origin.x(), changedSeed.origin.y(), changedSeed.origin.z()), (newOrigin.x(), newOrigin.y(), newOrigin.z()))
        self.assertEqual((matchingSeedA.origin.x(), matchingSeedA.origin.y(), matchingSeedA.origin.z()), (35.0, 38.0, 2.0))
        self.assertEqual((matchingSeedB.origin.x(), matchingSeedB.origin.y(), matchingSeedB.origin.z()), (-5.0, 3.0, 10.0))
        self.assertEqual((matchingSeedC.origin.x(), matchingSeedC.origin.y(), matchingSeedC.origin.z()), (105.0, -52.0, 14.0))
        self.assertEqual((untouchedSeed.origin.x(), untouchedSeed.origin.y(), untouchedSeed.origin.z()), (1.0, 2.0, 3.0))
        self.assertEqual((workingTreeChangedSeed.parO.value().x(), workingTreeChangedSeed.parO.value().y(), workingTreeChangedSeed.parO.value().z()), (newOrigin.x(), newOrigin.y(), newOrigin.z()))
        self.assertEqual((workingTreeMatchingSeedA.parO.value().x(), workingTreeMatchingSeedA.parO.value().y(), workingTreeMatchingSeedA.parO.value().z()), (35.0, 38.0, 2.0))
        self.assertEqual((workingTreeMatchingSeedB.parO.value().x(), workingTreeMatchingSeedB.parO.value().y(), workingTreeMatchingSeedB.parO.value().z()), (-5.0, 3.0, 10.0))
        self.assertEqual((workingTreeMatchingSeedC.parO.value().x(), workingTreeMatchingSeedC.parO.value().y(), workingTreeMatchingSeedC.parO.value().z()), (105.0, -52.0, 14.0))
        self.assertEqual((workingTreeUntouchedSeed.parO.value().x(), workingTreeUntouchedSeed.parO.value().y(), workingTreeUntouchedSeed.parO.value().z()), (1.0, 2.0, 3.0))
        self.assertEqual((shift.x(), shift.y(), shift.z()), (5.0, -2.0, 2.0))
        commitSurveyCopy.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesPropagatesConfirmedSeedGridGrowStepsToNormalSeeds(self):
        class FakeColorValue:
            def __init__(self, color):
                self._color = QColor(color)

            def value(self):
                return QColor(self._color)

        class FakeFloatValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

            def setValue(self, value):
                self._value = value

        class FakePoint3DValue:
            def __init__(self, vector):
                self._children = {
                    'X': FakeFloatValue(vector.x()),
                    'Y': FakeFloatValue(vector.y()),
                    'Z': FakeFloatValue(vector.z()),
                }

            def value(self):
                return QVector3D(self.child('X').value(), self.child('Y').value(), self.child('Z').value())

            def child(self, name):
                return self._children[name]

        class FakePatternValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

            def setValue(self, value):
                self._value = value

        class FakeRollValue:
            def __init__(self, steps, dx, dy, dz):
                self._children = {
                    'N': FakeFloatValue(steps),
                    'dX': FakeFloatValue(dx),
                    'dY': FakeFloatValue(dy),
                    'dZ': FakeFloatValue(dz),
                }

            def child(self, name):
                return self._children[name]

        class FakeGridValue:
            def __init__(self, growList):
                self._children = {
                    'Planes': FakeRollValue(growList[0].steps, growList[0].increment.x(), growList[0].increment.y(), growList[0].increment.z()),
                    'Lines': FakeRollValue(growList[1].steps, growList[1].increment.x(), growList[1].increment.y(), growList[1].increment.z()),
                    'Points': FakeRollValue(growList[2].steps, growList[2].increment.x(), growList[2].increment.y(), growList[2].increment.z()),
                }

            def child(self, name):
                return self._children[name]

            def value(self):
                values = []
                for stepName in ('Planes', 'Lines', 'Points'):
                    translate = propertyPanelControllerModule.RollTranslate()
                    stepParam = self.child(stepName)
                    translate.steps = stepParam.child('N').value()
                    translate.increment.setX(stepParam.child('dX').value())
                    translate.increment.setY(stepParam.child('dY').value())
                    translate.increment.setZ(stepParam.child('dZ').value())
                    values.append(translate)
                return values

        class FakeSeedTypeValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class FakeSeedParam:
            def __init__(self, name, growList, *, pattern='<None>', color='#7700ff00', origin=None, seedType='Grid (roll along)'):
                self._name = name
                self.parL = FakeColorValue(color)
                self.parO = FakePoint3DValue(QVector3D() if origin is None else origin)
                self.parP = FakePatternValue(pattern)
                self.parG = FakeGridValue(growList)
                self.parT = FakeSeedTypeValue(seedType)

            def name(self):
                return self._name

        def makeGrowList(values):
            growList = []
            for steps, dx, dy, dz in values:
                translate = propertyPanelControllerModule.RollTranslate()
                translate.steps = steps
                translate.increment.setX(dx)
                translate.increment.setY(dy)
                translate.increment.setZ(dz)
                growList.append(translate)
            return growList

        def growListKey(growList):
            return tuple((translate.steps, translate.increment.x(), translate.increment.y(), translate.increment.z()) for translate in growList)

        newGrowList = makeGrowList(((1, 0.0, 0.0, 0.0), (4, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0)))
        oldGrowList = makeGrowList(((1, 0.0, 0.0, 0.0), (2, 1.0, 0.0, 0.0), (5, 0.0, 2.0, 0.0)))
        changedSeed = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.rollingGrid, grid=SimpleNamespace(growList=makeGrowList(((1, 0.0, 0.0, 0.0), (4, 10.0, 0.0, 0.0), (3, 0.0, 5.0, 0.0)))))    # noqa: E501  # pylint: disable=C0301
        matchingSeedA = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.rollingGrid, grid=SimpleNamespace(growList=makeGrowList(((1, 0.0, 0.0, 0.0), (2, 1.0, 0.0, 0.0), (5, 0.0, 2.0, 0.0)))))   # noqa: E501  # pylint: disable=C0301
        matchingSeedB = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.fixedGrid, grid=SimpleNamespace(growList=makeGrowList(((1, 0.0, 0.0, 0.0), (1, 0.0, 1.0, 0.0), (2, 0.0, 0.0, 1.0)))))     # noqa: E501  # pylint: disable=C0301
        untouchedSeed = SimpleNamespace(name='rec-1', type=propertyPanelControllerModule.SeedType.rollingGrid, grid=SimpleNamespace(growList=makeGrowList(((1, 0.0, 0.0, 0.0), (7, 7.0, 0.0, 0.0), (8, 0.0, 8.0, 0.0)))))   # noqa: E501  # pylint: disable=C0301
        workingTreeChangedSeed = FakeSeedParam('src-1', newGrowList)
        workingTreeMatchingSeedA = FakeSeedParam('src-1', oldGrowList)
        workingTreeMatchingSeedB = FakeSeedParam('src-1', makeGrowList(((1, 0.0, 0.0, 0.0), (1, 0.0, 1.0, 0.0), (2, 0.0, 0.0, 1.0))), seedType='Grid (stationary)')
        workingTreeUntouchedSeed = FakeSeedParam('rec-1', makeGrowList(((1, 0.0, 0.0, 0.0), (7, 7.0, 0.0, 0.0), (8, 0.0, 8.0, 0.0))))
        surveyCopy = SimpleNamespace(
            blockList=[
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[changedSeed, matchingSeedA, untouchedSeed]),
                        SimpleNamespace(seedList=[matchingSeedB]),
                    ]
                )
            ],
            patternList=[],
            checkIntegrity=lambda: True,
        )

        controller = self.mainWindow.propertyPanelController
        controller._pendingSeedGridGrowLists = {1: {'param': workingTreeChangedSeed, 'oldGrowList': controller._copyGrowList(oldGrowList), 'newGrowList': controller._copyGrowList(newGrowList)}}
        self.mainWindow.paramTree = SimpleNamespace(
            listAllItems=lambda: [
                SimpleNamespace(param=workingTreeChangedSeed),
                SimpleNamespace(param=workingTreeMatchingSeedA),
                SimpleNamespace(param=workingTreeMatchingSeedB),
                SimpleNamespace(param=workingTreeUntouchedSeed),
            ]
        )

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            with patch.object(controller, '_buildSurveyFromParameters', return_value=surveyCopy):
                with patch.object(controller, '_commitSurveyCopy') as commitSurveyCopy:
                    with patch.object(self.mainWindow, 'setPlottingDetails'):
                        with patch.object(self.mainWindow, 'updateMenuStatus'):
                            with patch.object(self.mainWindow, 'enableProcessingMenuItems'):
                                with patch.object(self.mainWindow, 'updatePatternList'):
                                    with patch.object(self.mainWindow, 'plotLayout'):
                                        with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                            with patch.object(propertyPanelControllerModule.QMessageBox, 'question', return_value=propertyPanelControllerModule.QMessageBox.StandardButton.Yes) as question:
                                                self.mainWindow.applyPropertyChanges()

        question.assert_called_once()
        self.assertEqual(growListKey(changedSeed.grid.growList), growListKey(newGrowList))
        self.assertEqual(growListKey(matchingSeedA.grid.growList), growListKey(newGrowList))
        self.assertEqual(growListKey(matchingSeedB.grid.growList), growListKey(newGrowList))
        self.assertNotEqual(growListKey(untouchedSeed.grid.growList), growListKey(newGrowList))
        self.assertEqual(growListKey(workingTreeChangedSeed.parG.value()), growListKey(newGrowList))
        self.assertEqual(growListKey(workingTreeMatchingSeedA.parG.value()), growListKey(newGrowList))
        self.assertEqual(growListKey(workingTreeMatchingSeedB.parG.value()), growListKey(newGrowList))
        self.assertNotEqual(growListKey(workingTreeUntouchedSeed.parG.value()), growListKey(newGrowList))
        commitSurveyCopy.assert_called_once_with(surveyCopy)

    def testApplyPropertyChangesPropagatesConfirmedSeedPatternToNormalSeeds(self):
        class FakeColorValue:
            def __init__(self, color):
                self._color = QColor(color)

            def value(self):
                return QColor(self._color)

        class FakeFloatValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class FakePoint3DValue:
            def __init__(self, vector):
                self._children = {
                    'X': FakeFloatValue(vector.x()),
                    'Y': FakeFloatValue(vector.y()),
                    'Z': FakeFloatValue(vector.z()),
                }

            def value(self):
                return QVector3D(self.child('X').value(), self.child('Y').value(), self.child('Z').value())

            def child(self, name):
                return self._children[name]

        class FakePatternValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

            def setValue(self, value):
                self._value = value

        class FakeSeedTypeValue:
            def __init__(self, value):
                self._value = value

            def value(self):
                return self._value

        class FakeGridValue:
            def value(self):
                return [propertyPanelControllerModule.RollTranslate(), propertyPanelControllerModule.RollTranslate(), propertyPanelControllerModule.RollTranslate()]

        class FakeSeedParam:
            def __init__(self, name, pattern, *, color='#7700ff00', origin=None, seedType='Grid (roll along)'):
                self._name = name
                self.parL = FakeColorValue(color)
                self.parO = FakePoint3DValue(QVector3D() if origin is None else origin)
                self.parP = FakePatternValue(pattern)
                self.parG = FakeGridValue()
                self.parT = FakeSeedTypeValue(seedType)

            def name(self):
                return self._name

        changedSeed = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.rollingGrid, patternNo=1)
        matchingSeedA = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.rollingGrid, patternNo=0)
        matchingSeedB = SimpleNamespace(name='src-1', type=propertyPanelControllerModule.SeedType.fixedGrid, patternNo=0)
        untouchedSeed = SimpleNamespace(name='rec-1', type=propertyPanelControllerModule.SeedType.rollingGrid, patternNo=0)
        workingTreeChangedSeed = FakeSeedParam('src-1', 'pat-2')
        workingTreeMatchingSeedA = FakeSeedParam('src-1', 'pat-1')
        workingTreeMatchingSeedB = FakeSeedParam('src-1', 'pat-1', seedType='Grid (stationary)')
        workingTreeUntouchedSeed = FakeSeedParam('rec-1', 'pat-1')
        surveyCopy = SimpleNamespace(
            blockList=[
                SimpleNamespace(
                    templateList=[
                        SimpleNamespace(seedList=[changedSeed, matchingSeedA, untouchedSeed]),
                        SimpleNamespace(seedList=[matchingSeedB]),
                    ]
                )
            ],
            patternList=[SimpleNamespace(name='pat-1'), SimpleNamespace(name='pat-2')],
            checkIntegrity=lambda: True,
        )

        controller = self.mainWindow.propertyPanelController
        controller._pendingSeedPatterns = {1: {'param': workingTreeChangedSeed, 'oldPattern': 'pat-1', 'newPattern': 'pat-2'}}
        self.mainWindow.paramTree = SimpleNamespace(
            listAllItems=lambda: [
                SimpleNamespace(param=workingTreeChangedSeed),
                SimpleNamespace(param=workingTreeMatchingSeedA),
                SimpleNamespace(param=workingTreeMatchingSeedB),
                SimpleNamespace(param=workingTreeUntouchedSeed),
            ]
        )

        with patch.object(propertyPanelControllerModule, 'MySeedParameter', FakeSeedParam):
            with patch.object(controller, '_buildSurveyFromParameters', return_value=surveyCopy):
                with patch.object(controller, '_commitSurveyCopy') as commitSurveyCopy:
                    with patch.object(self.mainWindow, 'setPlottingDetails'):
                        with patch.object(self.mainWindow, 'updateMenuStatus'):
                            with patch.object(self.mainWindow, 'enableProcessingMenuItems'):
                                with patch.object(self.mainWindow, 'updatePatternList'):
                                    with patch.object(self.mainWindow, 'plotLayout'):
                                        with patch.object(propertyPanelControllerModule, 'refreshLayout3DFromSurvey'):
                                            with patch.object(propertyPanelControllerModule.QMessageBox, 'question', return_value=propertyPanelControllerModule.QMessageBox.StandardButton.Yes) as question:
                                                self.mainWindow.applyPropertyChanges()

        question.assert_called_once()
        self.assertEqual(changedSeed.patternNo, 1)
        self.assertEqual(matchingSeedA.patternNo, 1)
        self.assertEqual(matchingSeedB.patternNo, 1)
        self.assertEqual(untouchedSeed.patternNo, 0)
        self.assertEqual(workingTreeChangedSeed.parP.value(), 'pat-2')
        self.assertEqual(workingTreeMatchingSeedA.parP.value(), 'pat-2')
        self.assertEqual(workingTreeMatchingSeedB.parP.value(), 'pat-2')
        self.assertEqual(workingTreeUntouchedSeed.parP.value(), 'pat-1')
        commitSurveyCopy.assert_called_once_with(surveyCopy)

    def testBinFromGeometryUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinFromGeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromGeometry(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromGeometryRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertIs(request.srcGeom, self.mainWindow.srcGeom)
        self.assertIs(request.relGeom, self.mainWindow.relGeom)
        self.assertIs(request.recGeom, self.mainWindow.recGeom)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        self.assertEqual(threadStub.finished.connect.call_count, 2)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinFromSpsUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spsImport = np.zeros(1, dtype=pntType1)
        self.mainWindow.xpsImport = np.zeros(1, dtype=relType2)
        self.mainWindow.rpsImport = np.zeros(1, dtype=pntType1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'BinFromGeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.binFromSps(False)

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, BinningFromGeometryRequest)
        self.assertEqual(request.extended, False)
        self.assertIs(request.analysisFile, self.mainWindow.output.anaOutput)
        self.assertIs(request.srcGeom, self.mainWindow.spsImport)
        self.assertIs(request.relGeom, self.mainWindow.xpsImport)
        self.assertIs(request.recGeom, self.mainWindow.rpsImport)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        self.assertEqual(threadStub.finished.connect.call_count, 2)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testBinFromGeometryWorkerRunEmitsTypedResultsOnSuccessAndFailure(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.anaOutput = np.zeros((3, 2), dtype=np.float32)
                self.output.srcGeom = None
                self.output.relGeom = None
                self.output.recGeom = None
                self.output.binOutput = np.full((2, 2), 5.0, dtype=np.float32)
                self.output.minOffset = np.full((2, 2), 12.0, dtype=np.float32)
                self.output.maxOffset = np.full((2, 2), 24.0, dtype=np.float32)
                self.output.minimumFold = 2
                self.output.maximumFold = 5
                self.output.minMinOffset = 12.0
                self.output.maxMinOffset = 12.0
                self.output.minMaxOffset = 24.0
                self.output.maxMaxOffset = 24.0
                self.output.minRmsOffset = 0.0
                self.output.maxRmsOffset = 0.0
                self.output.rmsOffset = None
                self.output.ofAziHist = np.ones((2, 3), dtype=np.float32)
                self.output.offstHist = np.array([[0.0, 50.0], [1.0, 2.0]], dtype=np.float32)
                self.cmpTransform = 'cmp-transform'
                self.errorText = 'geometry failed'
                self.shouldSucceed = True
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False
                self.extended: bool | None = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupBinFromGeometry(self, extended):
                self.extended = extended
                return self.shouldSucceed

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        request = BinningFromGeometryRequest(
            xmlString='<survey />',
            srcGeom=srcGeom,
            relGeom=relGeom,
            recGeom=recGeom,
            extended=True,
            analysisFile=np.zeros((3, 2), dtype=np.float32),
            debugpyEnabled=False,
        )

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = BinFromGeometryWorker(request)

            resultEvents = []
            finishedEvents = []
            worker.resultReady.connect(resultEvents.append)
            worker.finished.connect(lambda: finishedEvents.append('finished'))

            worker.run()

            self.assertEqual(worker.survey.xmlString, '<survey />')
            self.assertTrue(worker.survey.createArrays)
            self.assertIs(worker.survey.output.srcGeom, srcGeom)
            self.assertIs(worker.survey.output.relGeom, relGeom)
            self.assertIs(worker.survey.output.recGeom, recGeom)
            self.assertTrue(worker.survey.calcCalled)
            self.assertTrue(worker.survey.extended)

            self.assertEqual(len(resultEvents), 1)
            self.assertEqual(type(resultEvents[0]).__name__, 'BinningFromGeometryResult')
            self.assertTrue(resultEvents[0].success)
            self.assertIs(resultEvents[0].binOutput, worker.survey.output.binOutput)
            self.assertIs(resultEvents[0].minOffset, worker.survey.output.minOffset)
            self.assertIs(resultEvents[0].maxOffset, worker.survey.output.maxOffset)
            self.assertIs(resultEvents[0].ofAziHist, worker.survey.output.ofAziHist)
            self.assertIs(resultEvents[0].offstHist, worker.survey.output.offstHist)
            self.assertIsNone(resultEvents[0].minRmsOffset)
            self.assertIsNone(resultEvents[0].maxRmsOffset)
            self.assertEqual(resultEvents[0].anaOutputShape, (3, 2))
            self.assertEqual(resultEvents[0].cmpTransform, 'cmp-transform')
            self.assertEqual(finishedEvents, ['finished'])

            worker.survey.shouldSucceed = False
            resultEvents.clear()
            finishedEvents.clear()

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertEqual(type(resultEvents[0]).__name__, 'BinningFromGeometryResult')
        self.assertFalse(resultEvents[0].success)
        self.assertEqual(resultEvents[0].errorText, 'geometry failed')
        self.assertEqual(finishedEvents, ['finished'])

    def testBinningGeometryThreadFinishedUsesResultObject(self):
        result = BinningFromGeometryResult(
            success=True,
            binOutput=np.ones((2, 2), dtype=np.float32),
            minOffset=np.full((2, 2), 10.0, dtype=np.float32),
            maxOffset=np.full((2, 2), 20.0, dtype=np.float32),
            minimumFold=1,
            maximumFold=4,
            minMinOffset=10.0,
            maxMinOffset=10.0,
            minMaxOffset=20.0,
            maxMaxOffset=20.0,
            minRmsOffset=0.0,
            maxRmsOffset=0.0,
            rmsOffset=None,
            minOffsetGap=5.0,
            maxOffsetGap=15.0,
            gapOffset=np.full((2, 2), 15.0, dtype=np.float32),
            ofAziHist=None,
            offstHist=None,
            cmpTransform='cmp-transform',
            anaOutputShape=None,
        )

        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.imageType = 1
        self.mainWindow.fileName = ''
        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                    with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                        with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningGeometryThreadFinished(result)

        np.testing.assert_array_equal(self.mainWindow.output.binOutput, result.binOutput)
        np.testing.assert_array_equal(self.mainWindow.output.minOffset, result.minOffset)
        np.testing.assert_array_equal(self.mainWindow.output.maxOffset, result.maxOffset)
        np.testing.assert_array_equal(self.mainWindow.output.gapOffset, result.gapOffset)
        self.assertEqual(self.mainWindow.output.maximumFold, 4)
        self.assertEqual(self.mainWindow.survey.cmpTransform, 'cmp-transform')
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testBinningGeometryThreadFinishedHandlesFailureResult(self):
        result = BinningFromGeometryResult(success=False, errorText='geometry worker failed')

        self.mainWindow.layoutImg = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.layoutImItem = object()
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                            with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                self.mainWindow.binningGeometryThreadFinished(result)

        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        appendLogMessage.assert_any_call('Thread : . . . aborted binning operation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . geometry worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testApplyBinningWorkerResultHandlesGeometryResultWithoutProfiling(self):
        result = BinningFromGeometryResult(success=False, errorText='geometry worker failed')
        self.mainWindow._ensureWorkerOperationComponents()

        with patch.object(self.mainWindow.binningResultApplier, '_logProfiling') as logProfiling:
            with patch.object(self.mainWindow.binningResultApplier, '_applyFailure') as applyFailure:
                self.mainWindow.applyBinningWorkerResult(result, timedelta(seconds=1))

        logProfiling.assert_called_once_with(None)
        applyFailure.assert_called_once_with('geometry worker failed')

    def testBinningProfilingSummaryHighlightsBuildVsWriteTotals(self):
        self.mainWindow.appSettings.debug = True
        self.mainWindow._ensureWorkerOperationComponents()
        profiling = GeometryProfilingPayload(
            timerTmin=(float('Inf'), float('Inf'), 0.010, float('Inf'), float('Inf'), 0.030, float('Inf')),
            timerTmax=(0.0, 0.0, 0.040, 0.0, 0.0, 0.090, 0.0),
            timerTtot=(0.0, 0.0, 1.250, 0.0, 0.0, 3.750, 0.0),
            timerFreq=(0, 0, 5, 0, 0, 10, 0),
        )

        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
            self.mainWindow.binningResultApplier._logProfiling(profiling)

        appendLogMessage.assert_any_call(
            'Profiling summary: buildTraceArrays tot=0001250.000 ms (freq=0000005), '
            'analysisWrite tot=0003750.000 ms (freq=0000010), dominant=analysisWrite, '
            'analysisWrite/buildTraceArrays=3.00x',
            rollMainWindowModule.MsgType.Debug,
        )

    def testCreateGeometryFromTemplatesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.nShotPoints = 12

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'GeometryWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.createGeometryFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, GeometryFromTemplatesRequest)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.assertEqual(request.includeProfiling, self.mainWindow.appSettings.debug)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        self.assertEqual(threadStub.finished.connect.call_count, 2)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testCreateCfpAnalysisFromTemplatesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(3, 4)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'CfpFromTemplatesWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.cfpPointAnalysisFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, CfpFromTemplatesRequest)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.assertEqual(request.frequency, 40.0)
        self.assertEqual(request.maxDipDegrees, self.mainWindow.survey.angles.reflection.y())
        self.assertEqual(request.vint, self.mainWindow.survey.binning.vint)
        self.assertEqual(request.focalX, 50.0)
        self.assertEqual(request.focalY, 25.0)
        self.assertAlmostEqual(request.focalZ, self.mainWindow.survey.localPlane.anchor.z(), places=4)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testCreateCfpAnalysisFromTemplatesUsesConfigDefaultFrequencyWhenCfpNotLoadedFromXml(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.cfpLoadedFromXml = False
        self.mainWindow.survey.cfp.frequencyList = [40.0]
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(3, 4)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'CfpFromTemplatesWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.cfpPointAnalysisFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertEqual(request.frequency, float(config.cfpFrequencyList[0]))
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testCreateCfpAnalysisFromTemplatesPreservesXmlFrequencyWhenCfpLoadedFromXml(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.survey.cfpLoadedFromXml = True
        self.mainWindow.survey.cfp.frequencyList = [55.0]
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(3, 4)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'CfpFromTemplatesWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.cfpPointAnalysisFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertEqual(request.frequency, 55.0)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testCreateCfpAnalysisFromTemplatesFallsBackToAnalysisAreaCenterWithoutSpiderPoint(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(-1, -1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'CfpFromTemplatesWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.cfpPointAnalysisFromTemplates()

        request = workerFactory.call_args.args[0]
        self.assertEqual(request.focalX, 50.0)
        self.assertEqual(request.focalY, 25.0)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testCreateCfpAnalysisFromGeometryTablesUsesRequestObjectAndResultSignal(self):
        class SignalStub:
            def __init__(self):
                self.connect = MagicMock()

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()

        class WorkerStub:
            def __init__(self, request):
                self.request = request
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.moveToThread = MagicMock()
                self.deleteLater = MagicMock()

        threadStub = MagicMock()
        threadStub.isRunning.return_value = False
        threadStub.started = SignalStub()
        threadStub.finished = SignalStub()
        self.mainWindow.survey = self.createSurvey()
        self.mainWindow.spiderPoint = rollMainWindowModule.QPoint(3, 4)
        self.mainWindow.srcGeom = np.zeros(1, dtype=pntType1)
        self.mainWindow.relGeom = np.zeros(1, dtype=relType2)
        self.mainWindow.recGeom = np.zeros(1, dtype=pntType1)

        with patch.object(binningWorkerMixinModule, 'QThread', return_value=threadStub):
            with patch.object(binningWorkerMixinModule, 'CfpFromGeometryTablesWorker', side_effect=WorkerStub) as workerFactory:
                self.mainWindow.cfpPointAnalysisFromGeometryTables()

        request = workerFactory.call_args.args[0]
        self.assertIsInstance(request, CfpFromGeometryTablesRequest)
        self.assertIs(request.srcGeom, self.mainWindow.srcGeom)
        self.assertIs(request.relGeom, self.mainWindow.relGeom)
        self.assertIs(request.recGeom, self.mainWindow.recGeom)
        self.assertEqual(request.chunkSize, 25_000)
        self.assertEqual(request.sourceName, 'Geometry Tables')
        self.assertEqual(request.frequency, 40.0)
        self.assertEqual(request.debugpyEnabled, self.mainWindow.appSettings.debugpy)
        self.assertEqual(request.maxDipDegrees, self.mainWindow.survey.angles.reflection.y())
        self.assertEqual(request.vint, self.mainWindow.survey.binning.vint)
        self.assertEqual(request.focalX, 50.0)
        self.assertEqual(request.focalY, 25.0)
        self.assertAlmostEqual(request.focalZ, self.mainWindow.survey.localPlane.anchor.z(), places=4)
        self.mainWindow.worker.resultReady.connect.assert_called_once()
        self.mainWindow.worker.finished.connect.assert_any_call(threadStub.quit)
        self.mainWindow.worker.finished.connect.assert_any_call(self.mainWindow.worker.deleteLater)
        threadStub.finished.connect.assert_any_call(threadStub.deleteLater)
        threadStub.finished.connect.assert_any_call(self.mainWindow.workerOperationController._onThreadFinished)
        self.mainWindow.thread = None
        self.mainWindow.worker = None

    def testGeometryWorkerRunUsesOptionalProfilingPayload(self):
        class SurveyStub:
            def __init__(self):
                self.output = MagicMock()
                self.output.recGeom = np.zeros(1, dtype=pntType1)
                self.output.relGeom = np.zeros(1, dtype=relType2)
                self.output.srcGeom = np.zeros(1, dtype=pntType1)
                self.errorText = 'geometry setup failed'
                self.shouldSucceed = True
                self.timerTmin = [0.0]
                self.timerTmax = [1.0]
                self.timerTtot = [2.0]
                self.timerFreq = [3]
                self.xmlString: str | None = None
                self.createArrays: bool | None = None
                self.calcCalled: bool = False

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def calcNoShotPoints(self):
                self.calcCalled = True

            def setupGeometryFromTemplates(self):
                return self.shouldSucceed

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = GeometryWorker(GeometryFromTemplatesRequest(xmlString='<survey />', includeProfiling=True))

            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

            self.assertEqual(len(resultEvents), 1)
            self.assertEqual(type(resultEvents[0]).__name__, 'GeometryFromTemplatesResult')
            self.assertEqual(type(resultEvents[0].profiling).__name__, 'GeometryProfilingPayload')
            self.assertEqual(resultEvents[0].profiling.timerTmin, (0.0,))
            self.assertEqual(resultEvents[0].profiling.timerTmax, (1.0,))
            self.assertEqual(resultEvents[0].profiling.timerTtot, (2.0,))
            self.assertEqual(resultEvents[0].profiling.timerFreq, (3,))

            worker = GeometryWorker(GeometryFromTemplatesRequest(xmlString='<survey />', includeProfiling=False))
            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertIsNone(resultEvents[0].profiling)

    def testCfpFromTemplatesWorkerRunUsesResultPayload(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp setup failed'
                self.cfpTemplateContributionCount = 7
                self.nTemplates = 11
                self.cfpApertureRadius = 12.5
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.xmlString = None
                self.createArrays = None
                self.setupArgs = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

            def scanCfpTemplates(self, focalX, focalY, focalZ, maxDipDegrees, vint, contributionHandler=None, progressStart=0, progressEnd=100):
                self.setupArgs = (focalX, focalY, focalZ, maxDipDegrees, vint)
                self.progress.emit(progressEnd)
                if contributionHandler is not None:
                    contributionHandler(
                        np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]], dtype=np.float32),
                        np.array([[0.0, 5.0, 0.0], [10.0, 5.0, 0.0]], dtype=np.float32),
                    )
                return True

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = CfpFromTemplatesWorker(
                CfpFromTemplatesRequest(xmlString='<survey />', focalX=1.0, focalY=2.0, focalZ=-3.0, frequency=40.0, maxDipDegrees=40.0, vint=2500.0)
            )

            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertEqual(type(resultEvents[0]).__name__, 'CfpFromTemplatesResult')
        self.assertTrue(resultEvents[0].success)
        self.assertEqual(resultEvents[0].templateContributionCount, 7)
        self.assertEqual(resultEvents[0].totalTemplateCount, 11)
        self.assertEqual(resultEvents[0].frequency, 40.0)
        self.assertEqual(resultEvents[0].apertureRadius, 12.5)
        self.assertEqual(resultEvents[0].vint, 2500.0)
        self.assertEqual(resultEvents[0].sourceBeamImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].receiverBeamImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].resolutionImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].radonSourceBeamImage.shape, (128, 128))
        self.assertEqual(resultEvents[0].radonReceiverBeamImage.shape, (128, 128))
        self.assertEqual(resultEvents[0].radonAvpImage.shape, (128, 128))
        self.assertEqual(worker.survey.progress.values[0], 0)
        self.assertEqual(worker.survey.progress.values[-1], 100)
        # Verify two separate 0-100 progress phases: phase 1 ends at 100, then phase 2 starts at 0
        self.assertGreaterEqual(len(worker.survey.progress.values), 3)
        phase1_idx = next((i for i in range(len(worker.survey.progress.values) - 1) if worker.survey.progress.values[i] == 100 and worker.survey.progress.values[i + 1] == 0), None)
        self.assertIsNotNone(phase1_idx, "Expected phase 1 to end at 100 and phase 2 to start at 0")

    def testCfpFromGeometryTablesWorkerRunUsesChunkedResultPayload(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp geometry-tables failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))
                self.xmlString = None
                self.createArrays = None

            def fromXmlString(self, xmlString, createArrays):
                self.xmlString = xmlString
                self.createArrays = createArrays

        srcGeom = np.zeros(2, dtype=pntType1)
        srcGeom['Index'] = [1, 2]
        srcGeom['Line'] = [1.0, 1.0]
        srcGeom['Point'] = [1.0, 2.0]
        srcGeom['LocX'] = [0.0, 10.0]
        srcGeom['LocY'] = [0.0, 0.0]
        srcGeom['Elev'] = [0.0, 0.0]
        srcGeom['Depth'] = [0.0, 0.0]
        srcGeom['InUse'] = [1, 1]

        recGeom = np.zeros(2, dtype=pntType1)
        recGeom['Index'] = [1, 1]
        recGeom['Line'] = [10.0, 10.0]
        recGeom['Point'] = [1.0, 2.0]
        recGeom['LocX'] = [0.0, 10.0]
        recGeom['LocY'] = [5.0, 5.0]
        recGeom['Elev'] = [0.0, 0.0]
        recGeom['Depth'] = [0.0, 0.0]
        recGeom['InUse'] = [1, 1]

        relGeom = np.zeros(5, dtype=relType2)
        relGeom['SrcLin'] = [1.0, 1.0, 1.0, 1.0, 1.0]
        relGeom['SrcPnt'] = [1.0, 2.0, 1.0, 1.0, 1.0]
        relGeom['SrcInd'] = [1, 2, 1, 1, 1]
        relGeom['RecNum'] = [1, 2, 3, 4, 5]
        relGeom['RecLin'] = [10.0, 10.0, 10.0, 10.0, 10.0]
        relGeom['RecMin'] = [1.0, 2.0, 50.0, 3.0, 4.0]
        relGeom['RecMax'] = [1.0, 2.0, 50.0, 3.0, 40.0]
        relGeom['RecInd'] = [1, 1, 1, 1, 1]
        relGeom['Uniq'] = [1, 1, 1, 1, 1]
        relGeom['InSps'] = [1, 1, 1, 1, 1]
        relGeom['InRps'] = [1, 1, 1, 1, 1]

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = CfpFromGeometryTablesWorker(
                CfpFromGeometryTablesRequest(
                    xmlString='<survey />',
                    srcGeom=srcGeom,
                    relGeom=relGeom,
                    recGeom=recGeom,
                    focalX=0.0,
                    focalY=0.0,
                    focalZ=-10.0,
                    maxDipDegrees=45.0,
                    vint=2500.0,
                    chunkSize=2,
                )
            )

            resultEvents = []
            worker.resultReady.connect(resultEvents.append)

            worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertEqual(type(resultEvents[0]).__name__, 'CfpFromGeometryTablesResult')
        self.assertTrue(resultEvents[0].success)
        self.assertEqual(resultEvents[0].chunkCount, 3)
        self.assertGreaterEqual(resultEvents[0].totalTraceCount, 1)
        self.assertGreaterEqual(resultEvents[0].contributingTraceCount, 0)
        self.assertEqual(resultEvents[0].frequency, 40.0)
        self.assertAlmostEqual(resultEvents[0].apertureRadius, 10.0, places=4)
        self.assertEqual(resultEvents[0].vint, 2500.0)
        self.assertEqual(resultEvents[0].sourceBeamImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].receiverBeamImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].resolutionImage.shape, (2, 2))
        self.assertEqual(resultEvents[0].radonSourceBeamImage.shape, (128, 128))
        self.assertEqual(resultEvents[0].radonReceiverBeamImage.shape, (128, 128))
        self.assertEqual(resultEvents[0].radonAvpImage.shape, (128, 128))
        self.assertAlmostEqual(float(resultEvents[0].sourceBeamImage.max()), 0.0, places=4)
        self.assertAlmostEqual(float(resultEvents[0].radonSourceBeamImage.max()), 1.0, places=4)
        self.assertEqual(worker.survey.progress.values[0], 0)
        self.assertEqual(worker.survey.progress.values[-1], 100)
        # Verify two separate 0-100 progress phases: phase 1 ends at 100, then phase 2 starts at 0
        self.assertGreaterEqual(len(worker.survey.progress.values), 5)
        phase1_idx = next((i for i in range(len(worker.survey.progress.values) - 1) if worker.survey.progress.values[i] == 100 and worker.survey.progress.values[i + 1] == 0), None)
        self.assertIsNotNone(phase1_idx, "Expected phase 1 to end at 100 and phase 2 to start at 0")
        self.assertGreater(len(worker.survey.message.values), 3)

    def testCfpPlaneWorkerCoherentAcceptsSingleAndMultiFrequencyArrays(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp plane setup failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))

            def fromXmlString(self, xmlString, createArrays):
                _ = xmlString
                _ = createArrays

            def prepareGeometryRelationBinningLookup(self):
                return None

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        srcCoords = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        srcWeights = np.array([1.0], dtype=np.float32)
        recCoords = np.array([[0.0, 5.0, 0.0]], dtype=np.float32)
        recWeights = np.array([1.0], dtype=np.float32)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            for freqs in (np.array([40.0], dtype=np.float32), np.array([20.0, 40.0, 60.0], dtype=np.float32)):
                worker = CfpAmplitudeMapWorker(
                    CfpAmplitudeMapRequest(
                        xmlString='<survey />',
                        srcGeom=srcGeom,
                        relGeom=relGeom,
                        recGeom=recGeom,
                        focalZ=-10.0,
                        maxDipDegrees=45.0,
                        vint=2500.0,
                        frequencies=freqs,
                        computeIncoherentQc=False,
                    )
                )
                with patch.object(worker, '_gatherTracesFromRelations', return_value=(srcCoords, srcWeights, recCoords, recWeights)):
                    resultEvents = []
                    worker.resultReady.connect(resultEvents.append)
                    worker.run()

                self.assertEqual(len(resultEvents), 1)
                self.assertTrue(resultEvents[0].success)
                self.assertEqual(resultEvents[0].modeLabel, 'coherent')
                self.assertEqual(resultEvents[0].amplitudeMap.shape, (2, 2))
                self.assertTrue(np.isfinite(resultEvents[0].amplitudeMap).all())

    def testCfpPlaneWorkerIncoherentAcceptsSingleAndMultiFrequencyArrays(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp plane setup failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))

            def fromXmlString(self, xmlString, createArrays):
                _ = xmlString
                _ = createArrays

            def prepareGeometryRelationBinningLookup(self):
                return None

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        srcCoords = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        srcWeights = np.array([1.0], dtype=np.float32)
        recCoords = np.array([[0.0, 5.0, 0.0]], dtype=np.float32)
        recWeights = np.array([1.0], dtype=np.float32)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            for freqs in (np.array([40.0], dtype=np.float32), np.array([20.0, 40.0, 60.0], dtype=np.float32)):
                worker = CfpAmplitudeMapWorker(
                    CfpAmplitudeMapRequest(
                        xmlString='<survey />',
                        srcGeom=srcGeom,
                        relGeom=relGeom,
                        recGeom=recGeom,
                        focalZ=-10.0,
                        maxDipDegrees=45.0,
                        vint=2500.0,
                        frequencies=freqs,
                        computeIncoherentQc=True,
                    )
                )
                with patch.object(worker, '_gatherTracesFromRelations', return_value=(srcCoords, srcWeights, recCoords, recWeights)):
                    resultEvents = []
                    worker.resultReady.connect(resultEvents.append)
                    worker.run()

                self.assertEqual(len(resultEvents), 1)
                self.assertTrue(resultEvents[0].success)
                self.assertEqual(resultEvents[0].modeLabel, 'incoherent QC')
                self.assertEqual(resultEvents[0].amplitudeMap.shape, (2, 2))
                self.assertTrue(np.isfinite(resultEvents[0].amplitudeMap).all())

    def testCfpPlaneWorkerIncoherentDependsOnFrequencyValues(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp plane setup failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))

            def fromXmlString(self, xmlString, createArrays):
                _ = xmlString
                _ = createArrays

            def prepareGeometryRelationBinningLookup(self):
                return None

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        srcCoords = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        srcWeights = np.array([1.0], dtype=np.float32)
        recCoords = np.array([[0.0, 5.0, 0.0]], dtype=np.float32)
        recWeights = np.array([1.0], dtype=np.float32)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            frequencySets = (
                np.array([20.0, 40.0, 60.0], dtype=np.float32),
                np.array([10.0, 40.0, 80.0], dtype=np.float32),
            )
            amplitudeMaps = []

            for freqs in frequencySets:
                worker = CfpAmplitudeMapWorker(
                    CfpAmplitudeMapRequest(
                        xmlString='<survey />',
                        srcGeom=srcGeom,
                        relGeom=relGeom,
                        recGeom=recGeom,
                        focalZ=-10.0,
                        maxDipDegrees=45.0,
                        vint=2500.0,
                        frequencies=freqs,
                        computeIncoherentQc=True,
                    )
                )
                with patch.object(worker, '_gatherTracesFromRelations', return_value=(srcCoords, srcWeights, recCoords, recWeights)):
                    resultEvents = []
                    worker.resultReady.connect(resultEvents.append)
                    worker.run()

                self.assertEqual(len(resultEvents), 1)
                self.assertTrue(resultEvents[0].success)
                self.assertEqual(resultEvents[0].modeLabel, 'incoherent QC')
                amplitudeMaps.append(resultEvents[0].amplitudeMap)

        self.assertEqual(amplitudeMaps[0].shape, amplitudeMaps[1].shape)
        self.assertFalse(np.allclose(amplitudeMaps[0], amplitudeMaps[1], atol=1e-6))

    def testCfpPlaneWorkerCoherentNormalizesAmplitudeMap(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp plane setup failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))

            def fromXmlString(self, xmlString, createArrays):
                _ = xmlString
                _ = createArrays

            def prepareGeometryRelationBinningLookup(self):
                return None

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        srcCoords = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        srcWeights = np.array([1.0], dtype=np.float32)
        recCoords = np.array([[0.0, 5.0, 0.0]], dtype=np.float32)
        recWeights = np.array([1.0], dtype=np.float32)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = CfpAmplitudeMapWorker(
                CfpAmplitudeMapRequest(
                    xmlString='<survey />',
                    srcGeom=srcGeom,
                    relGeom=relGeom,
                    recGeom=recGeom,
                    focalZ=-10.0,
                    maxDipDegrees=45.0,
                    vint=2500.0,
                    frequencies=np.array([40.0], dtype=np.float32),
                    computeIncoherentQc=False,
                )
            )
            with patch.object(worker, '_gatherTracesFromRelations', return_value=(srcCoords, srcWeights, recCoords, recWeights)):
                with patch.object(workerThreadsModule, 'compute_illumination_row_numba', side_effect=[np.array([2.0, 4.0], dtype=np.float32), np.array([2.0, 4.0], dtype=np.float32)]):
                    resultEvents = []
                    worker.resultReady.connect(resultEvents.append)
                    worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertTrue(resultEvents[0].success)
        self.assertEqual(resultEvents[0].modeLabel, 'coherent')
        self.assertAlmostEqual(float(np.nanmax(resultEvents[0].amplitudeMap)), 1.0, places=6)
        self.assertAlmostEqual(float(resultEvents[0].normalizationFactor), 4.0, places=6)

    def testCfpPlaneWorkerIncoherentNormalizesAmplitudeMap(self):
        class SignalCollector:
            def __init__(self):
                self.values = []

            def emit(self, value):
                self.values.append(value)

        class SurveyStub:
            def __init__(self):
                self.errorText = 'cfp plane setup failed'
                self.progress = SignalCollector()
                self.message = SignalCollector()
                self.output = SimpleNamespace(rctOutput=QRectF(0.0, 0.0, 20.0, 10.0))
                self.grid = SimpleNamespace(binSize=QPointF(10.0, 5.0))

            def fromXmlString(self, xmlString, createArrays):
                _ = xmlString
                _ = createArrays

            def prepareGeometryRelationBinningLookup(self):
                return None

        srcGeom = np.zeros(1, dtype=pntType1)
        relGeom = np.zeros(1, dtype=relType2)
        recGeom = np.zeros(1, dtype=pntType1)
        srcCoords = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        srcWeights = np.array([1.0], dtype=np.float32)
        recCoords = np.array([[0.0, 5.0, 0.0]], dtype=np.float32)
        recWeights = np.array([1.0], dtype=np.float32)

        with patch.object(workerThreadsModule, 'RollSurvey', SurveyStub):
            worker = CfpAmplitudeMapWorker(
                CfpAmplitudeMapRequest(
                    xmlString='<survey />',
                    srcGeom=srcGeom,
                    relGeom=relGeom,
                    recGeom=recGeom,
                    focalZ=-10.0,
                    maxDipDegrees=45.0,
                    vint=2500.0,
                    frequencies=np.array([40.0], dtype=np.float32),
                    computeIncoherentQc=True,
                )
            )
            with patch.object(worker, '_gatherTracesFromRelations', return_value=(srcCoords, srcWeights, recCoords, recWeights)):
                with patch.object(workerThreadsModule, 'compute_illumination_row_incoherent_numba', side_effect=[np.array([2.0, 4.0], dtype=np.float32), np.array([2.0, 4.0], dtype=np.float32)]):
                    resultEvents = []
                    worker.resultReady.connect(resultEvents.append)
                    worker.run()

        self.assertEqual(len(resultEvents), 1)
        self.assertTrue(resultEvents[0].success)
        self.assertEqual(resultEvents[0].modeLabel, 'incoherent QC')
        self.assertAlmostEqual(float(np.nanmax(resultEvents[0].amplitudeMap)), 1.0, places=6)
        self.assertAlmostEqual(float(resultEvents[0].normalizationFactor), 4.0, places=6)

    def testCfpApplierUsesNormalizedDisplayLevelsForComparisonRuns(self):
        self.mainWindow._ensureWorkerOperationComponents()

        firstMap = np.array([[0.0, 10.0], [5.0, 2.0]], dtype=np.float32)
        secondMap = np.array([[0.0, 20.0], [10.0, 4.0]], dtype=np.float32)

        firstResult = workerThreadsModule.CfpAmplitudeMapResult(
            success=True,
            amplitudeMap=firstMap,
            incoherentAmplitudeMap=firstMap,
            normalizationFactor=10.0,
            sourceName='Geometry Tables',
            modeLabel='incoherent QC',
            isPartial=True,
        )
        secondResult = workerThreadsModule.CfpAmplitudeMapResult(
            success=True,
            amplitudeMap=secondMap,
            incoherentAmplitudeMap=secondMap,
            normalizationFactor=20.0,
            sourceName='Geometry Tables',
            modeLabel='incoherent QC',
            isPartial=True,
        )

        with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar') as prepareLayoutImageAndColorBar:
            with patch.object(self.mainWindow, 'plotLayout'):
                self.mainWindow.applyCfpAmplitudeMapWorkerResult(firstResult, timedelta(seconds=1))
                self.mainWindow.applyCfpAmplitudeMapWorkerResult(secondResult, timedelta(seconds=1))

        self.assertGreaterEqual(prepareLayoutImageAndColorBar.call_count, 2)
        firstLevels = prepareLayoutImageAndColorBar.call_args_list[0].kwargs['levels']
        secondLevels = prepareLayoutImageAndColorBar.call_args_list[1].kwargs['levels']
        self.assertEqual(firstLevels, (0.0, 1.0))
        self.assertEqual(secondLevels, (0.0, 1.0))

    def testCfpApplierCompletionLogIncludesNormalizationFactorForBothModes(self):
        self.mainWindow._ensureWorkerOperationComponents()

        coherentResult = workerThreadsModule.CfpAmplitudeMapResult(
            success=True,
            amplitudeMap=np.array([[0.0, 1.0], [0.5, 0.2]], dtype=np.float32),
            incoherentAmplitudeMap=None,
            normalizationFactor=12.5,
            sourceName='Geometry Tables',
            modeLabel='coherent',
            isPartial=False,
        )
        incoherentResult = workerThreadsModule.CfpAmplitudeMapResult(
            success=True,
            amplitudeMap=np.array([[0.0, 1.0], [0.5, 0.2]], dtype=np.float32),
            incoherentAmplitudeMap=np.array([[0.0, 1.0], [0.5, 0.2]], dtype=np.float32),
            normalizationFactor=7.5,
            sourceName='Geometry Tables',
            modeLabel='incoherent QC',
            isPartial=False,
        )

        qMessageBoxStub = SimpleNamespace(information=MagicMock())
        with patch.object(self.mainWindow.cfpAmplitudeMapResultApplier, 'runtimeDependenciesProvider', return_value={'QMessageBox': qMessageBoxStub}):
            with patch.object(self.mainWindow, 'prepareLayoutImageAndColorBar'):
                with patch.object(self.mainWindow, 'plotLayout'):
                    with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                        self.mainWindow.applyCfpAmplitudeMapWorkerResult(coherentResult, timedelta(seconds=2))
                        self.mainWindow.applyCfpAmplitudeMapWorkerResult(incoherentResult, timedelta(seconds=3))

        completedMessages = [call.args[0] for call in appendLogMessage.call_args_list if "Thread : Completed 'CFP Plane Illumination v1" in call.args[0]]
        self.assertEqual(len(completedMessages), 2)
        self.assertIn('normFactor=12.5', completedMessages[0])
        self.assertIn('normFactor=7.5', completedMessages[1])

    def testGeometryThreadFinishedUsesResultObject(self):
        result = GeometryFromTemplatesResult(
            success=True,
            recGeom=np.zeros(1, dtype=pntType1),
            relGeom=np.zeros(1, dtype=relType2),
            srcGeom=np.zeros(1, dtype=pntType1),
            profiling=GeometryProfilingPayload(
                timerTmin=(0.0,),
                timerTmax=(0.0,),
                timerTtot=(0.0,),
                timerFreq=(1,),
            ),
        )

        self.mainWindow.startTime = 0.0
        self.mainWindow.fileName = ''
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow.sessionService, 'setArray') as setArray:
                with patch.object(self.mainWindow.recModel, 'setData') as recSetData:
                    with patch.object(self.mainWindow.relModel, 'setData') as relSetData:
                        with patch.object(self.mainWindow.srcModel, 'setData') as srcSetData:
                            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                            self.mainWindow.geometryThreadFinished(result)

        self.assertEqual(setArray.call_count, 3)
        recSetData.assert_called_once()
        relSetData.assert_called_once()
        srcSetData.assert_called_once()
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testGeometryThreadFinishedHandlesFailureResult(self):
        result = GeometryFromTemplatesResult(
            success=False,
            errorText='geometry worker failed',
            profiling=GeometryProfilingPayload(
                timerTmin=(),
                timerTmax=(),
                timerTtot=(),
                timerFreq=(),
            ),
        )
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                            self.mainWindow.geometryThreadFinished(result)

        appendLogMessage.assert_any_call('Thread : . . . aborted geometry creation', rollMainWindowModule.MsgType.Error)
        appendLogMessage.assert_any_call('Thread : . . . geometry worker failed', rollMainWindowModule.MsgType.Error)
        information.assert_called_once_with(self.mainWindow, 'Interrupted', 'Worker thread aborted')
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testCfpFromTemplatesThreadFinishedUsesResultObject(self):
        result = CfpFromTemplatesResult(
            success=True,
            templateContributionCount=5,
            totalTemplateCount=12,
            focalX=10.0,
            focalY=20.0,
            focalZ=-2000.0,
            frequency=40.0,
            maxDipDegrees=40.0,
            apertureRadius=1678.199,
            vint=2200.0,
            sourceBeamImage=np.zeros((2, 3), dtype=np.float32),
            receiverBeamImage=np.ones((2, 3), dtype=np.float32),
            resolutionImage=np.full((2, 3), 2.0, dtype=np.float32),
            radonSourceBeamImage=np.zeros((4, 5), dtype=np.float32),
            radonReceiverBeamImage=np.ones((4, 5), dtype=np.float32),
            radonAvpImage=np.full((4, 5), 0.5, dtype=np.float32),
            sourceBeamX0=100.0,
            sourceBeamY0=200.0,
            sourceBeamDx=25.0,
            sourceBeamDy=50.0,
            radonX0=-0.25,
            radonY0=-0.25,
            radonDx=0.01,
            radonDy=0.01,
        )

        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                with patch.object(self.mainWindow, 'renderSelectedCfpSlice') as renderSelectedCfpSlice:
                    with patch.object(self.mainWindow.mainTabWidget, 'setCurrentWidget') as setMainCurrentWidget:
                        with patch.object(self.mainWindow.analysisTabWidget, 'setCurrentWidget') as setAnalysisCurrentWidget:
                            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                            self.mainWindow.cfpFromTemplatesThreadFinished(result)

        appendLogMessage.assert_any_call(
            "Thread : Completed 'CFP Point Analysis v1 (Templates)'. Elapsed time:0:00:01 ",
            rollMainWindowModule.MsgType.Analysis,
        )
        appendLogMessage.assert_any_call(
            'Thread : . . . contributing rolled template positions: 5 out of a total of: 12',
            rollMainWindowModule.MsgType.Analysis,
        )
        renderSelectedCfpSlice.assert_called_once_with()
        setMainCurrentWidget.assert_called_once_with(self.mainWindow.analysisTabWidget)
        setAnalysisCurrentWidget.assert_called_once_with(self.mainWindow.tabCfp)
        self.assertIs(self.mainWindow.output.cfpSourceBeamImage, result.sourceBeamImage)
        self.assertIs(self.mainWindow.output.cfpReceiverBeamImage, result.receiverBeamImage)
        self.assertIs(self.mainWindow.output.cfpResolutionImage, result.resolutionImage)
        self.assertIs(self.mainWindow.output.cfpRadonSourceBeamImage, result.radonSourceBeamImage)
        self.assertIs(self.mainWindow.output.cfpRadonReceiverBeamImage, result.radonReceiverBeamImage)
        self.assertIs(self.mainWindow.output.cfpRadonAvpImage, result.radonAvpImage)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamX0, 100.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamY0, 200.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamDx, 25.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamDy, 50.0)
        self.assertEqual(self.mainWindow.output.cfpRadonX0, -0.25)
        self.assertEqual(self.mainWindow.output.cfpRadonY0, -0.25)
        self.assertEqual(self.mainWindow.output.cfpRadonDx, 0.01)
        self.assertEqual(self.mainWindow.output.cfpRadonDy, 0.01)
        self.assertEqual(self.mainWindow.output.cfpFrequency, 40.0)
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testCfpFromGeometryTablesThreadFinishedUsesResultObject(self):
        result = CfpFromGeometryTablesResult(
            success=True,
            sourceName='Geometry Tables',
            chunkCount=3360,
            totalRelationCount=336000000,
            contributingRelationCount=12345,
            totalTraceCount=336000000,
            contributingTraceCount=12345,
            focalX=10.0,
            focalY=20.0,
            focalZ=-2000.0,
            frequency=40.0,
            maxDipDegrees=40.0,
            apertureRadius=1678.199,
            vint=2200.0,
            sourceBeamImage=np.zeros((2, 3), dtype=np.float32),
            receiverBeamImage=np.ones((2, 3), dtype=np.float32),
            resolutionImage=np.full((2, 3), 2.0, dtype=np.float32),
            radonSourceBeamImage=np.zeros((4, 5), dtype=np.float32),
            radonReceiverBeamImage=np.ones((4, 5), dtype=np.float32),
            radonAvpImage=np.full((4, 5), 0.5, dtype=np.float32),
            sourceBeamX0=100.0,
            sourceBeamY0=200.0,
            sourceBeamDx=25.0,
            sourceBeamDy=50.0,
            radonX0=-0.25,
            radonY0=-0.25,
            radonDx=0.01,
            radonDy=0.01,
        )

        self.mainWindow.startTime = 0.0
        self.mainWindow.thread = object()
        self.mainWindow.worker = object()

        with patch.object(binningWorkerMixinModule, 'timer', return_value=1.0):
            with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                with patch.object(self.mainWindow, 'renderSelectedCfpSlice') as renderSelectedCfpSlice:
                    with patch.object(self.mainWindow.mainTabWidget, 'setCurrentWidget') as setMainCurrentWidget:
                        with patch.object(self.mainWindow.analysisTabWidget, 'setCurrentWidget') as setAnalysisCurrentWidget:
                            with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                                with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                                    with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                        with patch.object(binningWorkerMixinModule.QMessageBox, 'information') as information:
                                            self.mainWindow.cfpFromGeometryTablesThreadFinished(result)

        appendLogMessage.assert_any_call(
            "Thread : Completed 'CFP Point Analysis v1 (Geometry Tables)'. Elapsed time:0:00:01 ",
            rollMainWindowModule.MsgType.Analysis,
        )
        appendLogMessage.assert_any_call(
            'Thread : . . . local target=(10.00, 20.00, -2000.00), aperture=40.0deg, radius=1678.20m, frequency=40.0Hz, Vint=2200.0m/s',
            rollMainWindowModule.MsgType.Analysis,
        )
        appendLogMessage.assert_any_call(
            'Thread : . . . contributing relation records: 12,345 out of: 336,000,000; contributing receiver traces: 12,345 out of: 336,000,000 resolved traces',
            rollMainWindowModule.MsgType.Analysis,
        )
        renderSelectedCfpSlice.assert_called_once_with()
        setMainCurrentWidget.assert_called_once_with(self.mainWindow.analysisTabWidget)
        setAnalysisCurrentWidget.assert_called_once_with(self.mainWindow.tabCfp)
        self.assertIs(self.mainWindow.output.cfpSourceBeamImage, result.sourceBeamImage)
        self.assertIs(self.mainWindow.output.cfpReceiverBeamImage, result.receiverBeamImage)
        self.assertIs(self.mainWindow.output.cfpResolutionImage, result.resolutionImage)
        self.assertIs(self.mainWindow.output.cfpRadonSourceBeamImage, result.radonSourceBeamImage)
        self.assertIs(self.mainWindow.output.cfpRadonReceiverBeamImage, result.radonReceiverBeamImage)
        self.assertIs(self.mainWindow.output.cfpRadonAvpImage, result.radonAvpImage)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamX0, 100.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamY0, 200.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamDx, 25.0)
        self.assertEqual(self.mainWindow.output.cfpSourceBeamDy, 50.0)
        self.assertEqual(self.mainWindow.output.cfpRadonX0, -0.25)
        self.assertEqual(self.mainWindow.output.cfpRadonY0, -0.25)
        self.assertEqual(self.mainWindow.output.cfpRadonDx, 0.01)
        self.assertEqual(self.mainWindow.output.cfpRadonDy, 0.01)
        self.assertEqual(self.mainWindow.output.cfpFrequency, 40.0)
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        updateMenuStatus.assert_called_once_with(False)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()
        information.assert_called_once()

    def testOnCfpSliceChangedRendersReceiverAndResolutionImages(self):
        self.mainWindow.output.cfpSourceBeamImage = np.zeros((2, 2), dtype=np.float32)
        self.mainWindow.output.cfpReceiverBeamImage = np.ones((2, 2), dtype=np.float32)
        self.mainWindow.output.cfpResolutionImage = np.full((2, 2), 2.0, dtype=np.float32)
        self.mainWindow.output.cfpSourceBeamX0 = 10.0
        self.mainWindow.output.cfpSourceBeamY0 = 20.0
        self.mainWindow.output.cfpSourceBeamDx = 5.0
        self.mainWindow.output.cfpSourceBeamDy = 6.0
        self.mainWindow.output.cfpFrequency = 40.0

        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as prepareAnalysisImageAndColorBar:
            self.mainWindow.actionCfpSliceReceiverBeam.setChecked(True)
            self.mainWindow.onCfpSliceChanged()

            prepareAnalysisImageAndColorBar.assert_called_once_with(
                self.mainWindow.cfpWidget,
                self.mainWindow.output.cfpReceiverBeamImage,
                10.0,
                20.0,
                5.0,
                6.0,
                'cfpImItem',
                'cfpColorBar',
                levels=(-60.0, 0.0),
                label='dB (-60 - 0)',
                limits=(-60.0, 0.0),
                rounding=10.0,
                colorBarTickSpacing=None,
            )

        self.assertEqual(self.mainWindow.cfpWidget.plotItem.titleLabel.text, 'xy-slice of receiver beam, frequency = 40 Hz, depth = 0 m')
        self.assertTrue(bool(self.mainWindow.cfpWidget.plotItem.getViewBox().state.get('aspectLocked', False)))

        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as prepareAnalysisImageAndColorBar:
            self.mainWindow.actionCfpSliceResolution.setChecked(True)
            self.mainWindow.onCfpSliceChanged()

            prepareAnalysisImageAndColorBar.assert_called_once_with(
                self.mainWindow.cfpWidget,
                self.mainWindow.output.cfpResolutionImage,
                10.0,
                20.0,
                5.0,
                6.0,
                'cfpImItem',
                'cfpColorBar',
                levels=(-60.0, 0.0),
                label='dB (-60 - 0)',
                limits=(-60.0, 0.0),
                rounding=10.0,
                colorBarTickSpacing=None,
            )

        self.assertEqual(self.mainWindow.cfpWidget.plotItem.titleLabel.text, 'xy-slice of resolution function, frequency = 40 Hz, depth = 0 m')
        self.assertTrue(bool(self.mainWindow.cfpWidget.plotItem.getViewBox().state.get('aspectLocked', False)))

    def testOnCfpRadonTransformChangedRendersRadonImages(self):
        self.mainWindow.output.cfpRadonSourceBeamImage = np.zeros((3, 3), dtype=np.float32)
        self.mainWindow.output.cfpRadonReceiverBeamImage = np.ones((3, 3), dtype=np.float32)
        self.mainWindow.output.cfpRadonAvpImage = np.full((3, 3), 0.5, dtype=np.float32)
        self.mainWindow.output.cfpRadonX0 = -0.25
        self.mainWindow.output.cfpRadonY0 = -0.20
        self.mainWindow.output.cfpRadonDx = 0.01
        self.mainWindow.output.cfpRadonDy = 0.02
        self.mainWindow.output.cfpFrequency = 40.0

        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as prepareAnalysisImageAndColorBar:
            self.mainWindow.actionCfpRadonRecBeam.setChecked(True)
            self.mainWindow.onCfpRadonTransformChanged()

            prepareAnalysisImageAndColorBar.assert_called_once()
            callArgs, callKwargs = prepareAnalysisImageAndColorBar.call_args
            self.assertIs(callArgs[0], self.mainWindow.cfpWidget)
            self.assertIs(callArgs[1], self.mainWindow.output.cfpRadonReceiverBeamImage)
            self.assertEqual(callArgs[2:], (-0.25, -0.20, 0.01, 0.02, 'cfpImItem', 'cfpColorBar'))
            self.assertEqual(
                callKwargs,
                {
                    'levels': (0.0, 1.0),
                    'label': 'amplitude (0 - 1)',
                    'limits': (0.0, 1.0),
                    'rounding': 0.1,
                    'colorBarTickSpacing': (0.1, 0.05),
                },
            )

        self.assertEqual(self.mainWindow.cfpWidget.plotItem.titleLabel.text, 'Radon transform of receiver beam, frequency = 40 Hz, depth = 0 m')
        self.assertTrue(bool(self.mainWindow.cfpWidget.plotItem.getViewBox().state.get('aspectLocked', False)))

        with patch.object(self.mainWindow, 'prepareAnalysisImageAndColorBar') as prepareAnalysisImageAndColorBar:
            self.mainWindow.actionCfpRadonRecBeam.setChecked(False)
            self.mainWindow.actionCfpRadonAvpFunction.setChecked(True)
            self.mainWindow.onCfpRadonTransformChanged()

            prepareAnalysisImageAndColorBar.assert_called_once()
            callArgs, callKwargs = prepareAnalysisImageAndColorBar.call_args
            self.assertIs(callArgs[0], self.mainWindow.cfpWidget)
            np.testing.assert_array_equal(callArgs[1], np.ones((3, 3), dtype=np.float32))
            self.assertEqual(callArgs[2:], (-0.25, -0.20, 0.01, 0.02, 'cfpImItem', 'cfpColorBar'))
            self.assertEqual(
                callKwargs,
                {
                    'levels': (0.0, 1.0),
                    'label': 'amplitude / local max (0 - 1)',
                    'limits': (0.0, 1.0),
                    'rounding': 0.1,
                    'colorBarTickSpacing': (0.1, 0.05),
                },
            )

        self.assertEqual(self.mainWindow.cfpWidget.plotItem.titleLabel.text, 'AVP-function in the Radon domain, frequency = 40 Hz, depth = 0 m')
        self.assertTrue(bool(self.mainWindow.cfpWidget.plotItem.getViewBox().state.get('aspectLocked', False)))

    def testCfpRadonPlotMouseStatusIncludesSampledAmplitude(self):
        class CheckedActionStub:
            def data(self):
                return 3

        class ActionGroupStub:
            def checkedAction(self):
                return CheckedActionStub()

        class ImageItemStub:
            def __init__(self):
                self.image = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)

            def scene(self):
                return object()

            def sceneBoundingRect(self):
                return SimpleNamespace(contains=lambda pos: True)

            def mapFromScene(self, _pos):
                return QPointF(1.2, 1.4)

        self.mainWindow.cfpViewActionGroup = ActionGroupStub()
        self.mainWindow.cfpImItem = ImageItemStub()

        self.mainWindow._setGenericPlotMouseStatus(self.mainWindow.cfpWidget, QPointF(16.0, 27.0), QPointF(16.0, 27.0))

        statusText = self.mainWindow.posWidgetStatusbar.text()
        self.assertIn('amplitude: 4.000', statusText)
        self.assertIn('x=16.00, y=27.00', statusText)

    def testStopWorkerThreadIgnoresLateResultAndResetsIdleUi(self):
        self.suppressModalDialogs()
        controller = self.mainWindow.workerOperationController or binningWorkerMixinModule.WorkerOperationController(
            self.mainWindow,
            self.mainWindow._getWorkerRuntimeDependencies,
        )
        self.mainWindow.workerOperationController = controller

        threadStub = MagicMock()
        threadStub.isRunning.return_value = True
        workerStub = MagicMock()
        controller.activeOperation = workerOperationControllerModule.ActiveWorkerOperation(
            job=workerOperationControllerModule.WorkerJobSpec(
                name='bin-from-templates',
                progressLabelText='x',
                startMessage='y',
                startMessageType=rollMainWindowModule.MsgType.Binning,
                workerFactory=lambda request: workerStub,
                request=object(),
                resultHandler=self.mainWindow.applyBinningWorkerResult,
            ),
            thread=threadStub,
            worker=workerStub,
        )
        self.mainWindow.thread = threadStub
        self.mainWindow.worker = workerStub
        self.mainWindow.layoutImg = np.ones((1, 1), dtype=np.float32)
        self.mainWindow.layoutImItem = object()

        qTimerStub = type('QTimerStub', (), {'singleShot': MagicMock()})
        with patch.object(binningWorkerMixinModule, 'QTimer', qTimerStub):
            with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                    with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                        with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                            with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                with patch.object(self.mainWindow, 'applyBinningWorkerResult') as applyBinningWorkerResult:
                                    self.mainWindow.stopWorkerThread()
                                    threadStub.isRunning.return_value = False
                                    controller.finishCurrentOperation(
                                        BinningFromTemplatesResult(success=True),
                                        self.mainWindow.applyBinningWorkerResult,
                                        resetAnalysis=False,
                                    )

        threadStub.requestInterruption.assert_called_once_with()
        qTimerStub.singleShot.assert_called_once()
        applyBinningWorkerResult.assert_not_called()
        appendLogMessage.assert_any_call('Thread : User interrupted worker thread', rollMainWindowModule.MsgType.Warning)
        appendLogMessage.assert_any_call('Thread : Worker thread has  stopped', rollMainWindowModule.MsgType.Warning)
        self.assertIsNone(self.mainWindow.thread)
        self.assertIsNone(self.mainWindow.worker)
        self.assertIsNone(self.mainWindow.layoutImg)
        self.assertIsNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_called_once()
        updateMenuStatus.assert_called_once_with(True)
        enableProcessingMenuItems.assert_called_once_with(True)
        hideStatusbarWidgets.assert_called_once()

    def testCancelCurrentOperationWaitTimeoutKeepsUiAliveUntilThreadStops(self):
        self.suppressModalDialogs()
        controller = self.mainWindow.workerOperationController or binningWorkerMixinModule.WorkerOperationController(
            self.mainWindow,
            self.mainWindow._getWorkerRuntimeDependencies,
        )
        self.mainWindow.workerOperationController = controller

        threadStub = MagicMock()
        threadStub.isRunning.return_value = True
        threadStub.wait.return_value = False
        workerStub = MagicMock()
        controller.activeOperation = workerOperationControllerModule.ActiveWorkerOperation(
            job=workerOperationControllerModule.WorkerJobSpec(
                name='bin-from-templates',
                progressLabelText='x',
                startMessage='y',
                startMessageType=rollMainWindowModule.MsgType.Binning,
                workerFactory=lambda request: workerStub,
                request=object(),
                resultHandler=self.mainWindow.applyBinningWorkerResult,
            ),
            thread=threadStub,
            worker=workerStub,
        )
        self.mainWindow.thread = threadStub
        self.mainWindow.worker = workerStub
        self.mainWindow.layoutImg = np.ones((1, 1), dtype=np.float32)
        self.mainWindow.layoutImItem = object()

        qTimerStub = type('QTimerStub', (), {'singleShot': MagicMock()})
        with patch.object(binningWorkerMixinModule, 'QTimer', qTimerStub):
            with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                with patch.object(self.mainWindow, 'handleImageSelection') as handleImageSelection:
                    with patch.object(self.mainWindow, 'updateMenuStatus') as updateMenuStatus:
                        with patch.object(self.mainWindow, 'enableProcessingMenuItems') as enableProcessingMenuItems:
                            with patch.object(self.mainWindow, 'hideStatusbarWidgets') as hideStatusbarWidgets:
                                stopped = controller.cancelCurrentOperation(waitTimeout=25, clearLayoutImage=True)

        self.assertFalse(stopped)
        threadStub.requestInterruption.assert_called_once_with()
        threadStub.quit.assert_called_once_with()
        threadStub.wait.assert_called_once_with(25)
        qTimerStub.singleShot.assert_called_once()
        appendLogMessage.assert_called_once_with('Thread : User interrupted worker thread', rollMainWindowModule.MsgType.Warning)
        self.assertIs(controller.activeOperation.thread, threadStub)
        self.assertIs(self.mainWindow.thread, threadStub)
        self.assertIs(self.mainWindow.worker, workerStub)
        self.assertIsNotNone(self.mainWindow.layoutImg)
        self.assertIsNotNone(self.mainWindow.layoutImItem)
        handleImageSelection.assert_not_called()
        updateMenuStatus.assert_not_called()
        enableProcessingMenuItems.assert_not_called()
        hideStatusbarWidgets.assert_not_called()

    def testStopCurrentOperationWarnsOnlyAfterDelayIfThreadStillRunning(self):
        self.suppressModalDialogs()
        controller = self.mainWindow.workerOperationController or binningWorkerMixinModule.WorkerOperationController(
            self.mainWindow,
            self.mainWindow._getWorkerRuntimeDependencies,
        )
        self.mainWindow.workerOperationController = controller

        threadStub = MagicMock()
        threadStub.isRunning.return_value = True
        workerStub = MagicMock()
        controller.activeOperation = workerOperationControllerModule.ActiveWorkerOperation(
            job=workerOperationControllerModule.WorkerJobSpec(
                name='bin-from-templates',
                progressLabelText='x',
                startMessage='y',
                startMessageType=rollMainWindowModule.MsgType.Binning,
                workerFactory=lambda request: workerStub,
                request=object(),
                resultHandler=self.mainWindow.applyBinningWorkerResult,
            ),
            thread=threadStub,
            worker=workerStub,
        )

        scheduledCallbacks = []

        class QTimerStub:
            @staticmethod
            def singleShot(timeout, callback):
                scheduledCallbacks.append((timeout, callback))

        with patch.object(binningWorkerMixinModule, 'QTimer', QTimerStub):
            with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                controller.stopCurrentOperation()

                self.assertEqual(len(scheduledCallbacks), 1)
                self.assertEqual(scheduledCallbacks[0][0], 4000)
                appendLogMessage.assert_called_once_with('Thread : User interrupted worker thread', rollMainWindowModule.MsgType.Warning)

                scheduledCallbacks[0][1]()

    def testBindJobSignalsRoutesSurveyLogMessagesUsingJobMessageType(self):
        class SignalStub:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

        class SurveyStub:
            def __init__(self):
                self.progress = SignalStub()
                self.message = SignalStub()
                self.logMessage = SignalStub()

        class WorkerStub:
            def __init__(self):
                self.survey = SurveyStub()
                self.resultReady = SignalStub()
                self.finished = SignalStub()
                self.run = MagicMock()
                self.deleteLater = MagicMock()

        class ThreadStub:
            def __init__(self):
                self.started = SignalStub()
                self.finished = SignalStub()
                self.quit = MagicMock()
                self.deleteLater = MagicMock()

        controller = self.mainWindow.workerOperationController or binningWorkerMixinModule.WorkerOperationController(
            self.mainWindow,
            self.mainWindow._getWorkerRuntimeDependencies,
        )
        self.mainWindow.workerOperationController = controller

        for msgType in (rollMainWindowModule.MsgType.Binning, rollMainWindowModule.MsgType.Geometry):
            with self.subTest(msgType=msgType):
                threadStub = ThreadStub()
                workerStub = WorkerStub()
                job = workerOperationControllerModule.WorkerJobSpec(
                    name='job',
                    progressLabelText='x',
                    startMessage='y',
                    startMessageType=msgType,
                    workerFactory=lambda request, worker=workerStub: worker,
                    request=object(),
                    resultHandler=self.mainWindow.applyGeometryWorkerResult,
                )

                with patch.object(self.mainWindow, 'appendLogMessage') as appendLogMessage:
                    scheduledCallbacks = []

                    class QTimerStub:
                        @staticmethod
                        def singleShot(timeout, callback):
                            scheduledCallbacks.append((timeout, callback))

                    originalProvider = controller.runtimeDependenciesProvider
                    controller.runtimeDependenciesProvider = lambda: {'QTimer': QTimerStub}
                    try:
                        controller._bindJobSignals(threadStub, workerStub, job)
                        self.assertEqual(len(workerStub.survey.logMessage.callbacks), 1)

                        workerStub.survey.logMessage.callbacks[0]('survey-log-line')

                        controller.activeOperation = workerOperationControllerModule.ActiveWorkerOperation(
                            job=job,
                            thread=threadStub,
                            worker=workerStub,
                            cancelRequested=True,
                        )
                        threadStub.isRunning = MagicMock(return_value=True)
                        controller._scheduleCancellationWarning(controller.activeOperation)
                        self.assertEqual(len(scheduledCallbacks), 1)
                        self.assertEqual(scheduledCallbacks[0][0], 4000)
                        scheduledCallbacks[0][1]()
                    finally:
                        controller.runtimeDependenciesProvider = originalProvider

                    controller.activeOperation = None

                appendLogMessage.assert_any_call('survey-log-line', msgType)

        appendLogMessage.assert_any_call('Thread : worker thread is still running; waiting for thread to finish', rollMainWindowModule.MsgType.Warning)

    def testOnAppAboutToQuitSkipsResetWhenWorkerShutdownTimesOut(self):
        self.suppressModalDialogs()
        self.mainWindow.workerOperationController = MagicMock()
        self.mainWindow.workerOperationController.shutdownCurrentOperation.return_value = False

        with patch.object(self.mainWindow, 'resetAnaTableModel') as resetAnaTableModel:
            self.mainWindow.onAppAboutToQuit()

        self.mainWindow.workerOperationController.shutdownCurrentOperation.assert_called_once_with(waitTimeout=2000)
        resetAnaTableModel.assert_not_called()

    def testReadStoredDebugpySettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/debug/debugpy', None)
        try:
            self.mainWindow.settings.setValue('settings/debug/debugpy', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredDebugpySetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/debug/debugpy')
            else:
                self.mainWindow.settings.setValue('settings/debug/debugpy', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredDebugSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/debug/logging', None)
        try:
            self.mainWindow.settings.setValue('settings/debug/logging', False)
            self.mainWindow.settings.sync()
            self.assertFalse(readStoredDebugSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/debug/logging')
            else:
                self.mainWindow.settings.setValue('settings/debug/logging', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredShowSummariesSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/misc/showSummaries', None)
        try:
            self.mainWindow.settings.setValue('settings/misc/showSummaries', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredShowSummariesSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/misc/showSummaries')
            else:
                self.mainWindow.settings.setValue('settings/misc/showSummaries', originalValue)
            self.mainWindow.settings.sync()

    def testReadStoredUseExperimentalSettingUsesPersistedValue(self):
        originalValue = self.mainWindow.settings.value('settings/misc/useExperimental', None)
        try:
            self.mainWindow.settings.setValue('settings/misc/useExperimental', True)
            self.mainWindow.settings.sync()
            self.assertTrue(readStoredUseExperimentalSetting())
        finally:
            if originalValue is None:
                self.mainWindow.settings.remove('settings/misc/useExperimental')
            else:
                self.mainWindow.settings.setValue('settings/misc/useExperimental', originalValue)
            self.mainWindow.settings.sync()

    def testUpdateRecentFileActionsKeepsRelativeEntriesInSettings(self):
        self.mainWindow.projectDirectory = os.path.join('D:\\', 'does-not-exist')
        self.mainWindow.recentFileList = ['relative-project.roll']

        self.mainWindow.updateRecentFileActions()

        self.assertEqual(self.mainWindow.recentFileList, ['relative-project.roll'])
        self.assertFalse(self.mainWindow.recentFileActions[0].isVisible())

    def testUpdateRecentFileActionsShowsResolvableRelativeEntries(self):
        with tempfile.TemporaryDirectory() as tempDir:
            projectPath = self.writeProjectFixture(tempDir)
            relativeProject = os.path.basename(projectPath)
            self.mainWindow.projectDirectory = tempDir
            self.mainWindow.recentFileList = [relativeProject]

            self.mainWindow.updateRecentFileActions()

            self.assertEqual(self.mainWindow.recentFileList, [relativeProject])
            self.assertTrue(self.mainWindow.recentFileActions[0].isVisible())
            self.assertEqual(self.mainWindow.recentFileActions[0].data(), relativeProject)

    def testFileNewLandSurveyIncrementsSessionSurveyNumberOnlyOnSuccess(self):
        self.mainWindow.sessionState.surveyNumber = 1
        wizardSurvey = self.createSurvey()
        wizardSurvey.name = 'Land Survey'

        class WizardStub:
            def __init__(self, _parent):
                self.survey = wizardSurvey

            def exec(self):
                return True

        with patch.object(rollMainWindowModule, 'LandSurveyWizard', WizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                with patch.object(self.mainWindow, 'updateAllViews'):
                    success = self.mainWindow.fileNewLandSurvey()

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 2)

        class CancelledWizardStub:
            def __init__(self, _parent):
                self.survey = None

            def exec(self):
                return False

        with patch.object(rollMainWindowModule, 'LandSurveyWizard', CancelledWizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                cancelled = self.mainWindow.fileNewLandSurvey()

        self.assertFalse(cancelled)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 2)

    def testFileNewMarineSurveyIncrementsSessionSurveyNumberOnlyOnSuccess(self):
        self.mainWindow.sessionState.surveyNumber = 3
        wizardSurvey = self.createSurvey()
        wizardSurvey.name = 'Marine Survey'

        class WizardStub:
            def __init__(self, _parent):
                self.survey = wizardSurvey

            def exec(self):
                return True

        with patch.object(rollMainWindowModule, 'MarineSurveyWizard', WizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                with patch.object(self.mainWindow, 'updateAllViews'):
                    success = self.mainWindow.fileNewMarineSurvey()

        self.assertTrue(success)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 4)

        class CancelledWizardStub:
            def __init__(self, _parent):
                self.survey = None

            def exec(self):
                return False

        with patch.object(rollMainWindowModule, 'MarineSurveyWizard', CancelledWizardStub):
            with patch.object(self.mainWindow, 'fileNew', return_value=True):
                cancelled = self.mainWindow.fileNewMarineSurvey()

        self.assertFalse(cancelled)
        self.assertEqual(self.mainWindow.sessionState.surveyNumber, 4)

    def testMarineWizardPage2InitializesSourceSeparationFromSourceCount(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()

            self.assertEqual(page2.srcSepFactor.value(), 1)
            self.assertAlmostEqual(page2.srcSeparation.value(), 25.0)
            self.assertAlmostEqual(page2.field('srcSeparation'), 25.0)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testMarineWizardPage2TopViewUpdatesWhenFactorChanges(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()
            page2.plotType.setCurrentIndex(1)

            page2.srcSepFactor.setValue(2)
            page2.updateSrcSepFactor()

            sourceA = page2.parent.survey.blockList[0].templateList[0].seedList[0].origin
            sourceB = page2.parent.survey.blockList[0].templateList[1].seedList[0].origin

            self.assertEqual(page2.srcSepFactor.value(), 2)
            self.assertAlmostEqual(page2.srcSeparation.value(), 50.0)
            self.assertAlmostEqual(sourceB.y() - sourceA.y(), 50.0)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testMarineWizardPage2TopViewFactorChangeInvalidatesSurveyPaintCache(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()
            page2.plotType.setCurrentIndex(1)
            initialEpoch = page2.parent.survey._paintEpoch

            page2.srcSepFactor.setValue(2)
            page2.updateSrcSepFactor()

            self.assertGreater(page2.parent.survey._paintEpoch, initialEpoch)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testMarineWizardPage3XlineBinSizeMatchesCmpActXSpacing(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)
            page3 = wizard.page(2)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()
            page3.initializePage()

            self.assertAlmostEqual(page3.xlineBinSize(), 12.5)
            self.assertAlmostEqual(page3.binX.value(), 12.5)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testMarineWizardPage3XlineBinSizeUsesUniqueCmpActXValues(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)
            page3 = wizard.page(2)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()
            page2.srcSepFactor.setValue(4)
            page2.updateSrcSepFactor()
            page3.initializePage()

            self.assertAlmostEqual(page3.xlineBinSize(), 50.0)
            self.assertAlmostEqual(page3.binX.value(), 50.0)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testMarineWizardPage3BinXUpdatesAfterReturningFromPage2FactorChange(self):
        wizard = marineWizardModule.MarineSurveyWizard(self.mainWindow)
        try:
            page1 = wizard.page(0)
            page2 = wizard.page(1)
            page3 = wizard.page(2)

            page1.nSrc.setValue(4)
            page1.updateParameters()

            page2.initializePage()
            page2.srcSepFactor.setValue(2)
            page2.updateSrcSepFactor()
            page3.initializePage()

            self.assertAlmostEqual(page3.binX.value(), 25.0)

            page2.srcSepFactor.setValue(1)
            page2.updateSrcSepFactor()
            page3.initializePage()

            self.assertAlmostEqual(page3.xlineBinSize(), 12.5)
            self.assertAlmostEqual(page3.binX.value(), 12.5)
        finally:
            wizard.close()
            wizard.deleteLater()

    def testFileSaveAsCommitsDocumentContextOnlyAfterSuccessfulSave(self):
        originalProjectDirectory = self.mainWindow.projectDirectory
        self.mainWindow.fileName = ''
        self.mainWindow.recentFileList = []
        self.mainWindow.textEdit.document().setModified(True)

        with tempfile.TemporaryDirectory() as tempDir:
            targetFileName = os.path.join(tempDir, 'saved_as.roll')

            with patch.object(rollMainWindowModule.QFileDialog, 'getSaveFileName', return_value=(targetFileName, '')):
                with patch.object(self.mainWindow.projectService, 'writeProjectXml', return_value=MagicMock(success=False, errorText='write failure')):
                    with patch.object(rollMainWindowModule.QMessageBox, 'information') as showWriteError:
                        with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars') as saveAnalysisSidecars:
                            with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars') as saveSurveyDataSidecars:
                                success = self.mainWindow.fileSaveAs()

            self.assertFalse(success)
            self.assertEqual(self.mainWindow.fileName, '')
            self.assertEqual(self.mainWindow.projectDirectory, originalProjectDirectory)
            self.assertEqual(self.mainWindow.recentFileList, [])
            self.assertTrue(self.mainWindow.textEdit.document().isModified())
            showWriteError.assert_called_once()
            saveAnalysisSidecars.assert_not_called()
            saveSurveyDataSidecars.assert_not_called()

            with patch.object(rollMainWindowModule.QFileDialog, 'getSaveFileName', return_value=(targetFileName, '')):
                with patch.object(self.mainWindow.projectService, 'saveAnalysisSidecars') as saveAnalysisSidecars:
                    with patch.object(self.mainWindow.projectService, 'saveSurveyDataSidecars') as saveSurveyDataSidecars:
                        success = self.mainWindow.fileSaveAs()

            self.assertTrue(success)
            self.assertEqual(self.mainWindow.fileName, targetFileName)
            self.assertEqual(self.mainWindow.projectDirectory, tempDir)
            self.assertEqual(self.mainWindow.recentFileList, [targetFileName])
            self.assertFalse(self.mainWindow.textEdit.document().isModified())
            saveAnalysisSidecars.assert_called_once_with(targetFileName, self.mainWindow.output, includeHistograms=True)
            saveSurveyDataSidecars.assert_called_once()


if __name__ == '__main__':
    unittest.main()
