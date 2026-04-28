# coding=utf-8
import unittest

from pyqtgraph.parametertree import ParameterTree
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey, getQgisApp

myParametersModule = loadPluginModule('my_parameters')

MyAnalysisParameter = myParametersModule.MyAnalysisParameter
MyBlockParameter = myParametersModule.MyBlockParameter
MyConfigurationParameter = myParametersModule.MyConfigurationParameter
MyGridParameter = myParametersModule.MyGridParameter
MyReflectorsParameter = myParametersModule.MyReflectorsParameter
MyTemplateParameter = myParametersModule.MyTemplateParameter

creationHelpersModule = loadPluginModule('parameter_creation_helpers')

createDefaultBlock = creationHelpersModule.createDefaultBlock
createDefaultTemplate = creationHelpersModule.createDefaultTemplate


class AggregateParameterWrapperTest(unittest.TestCase):
    def setUp(self):
        self.qgisApp, _, _, self.parent = getQgisApp()

    def testConfigurationParameterWritesBackToSurvey(self):
        survey = createTestSurvey()
        parameter = MyConfigurationParameter(name='Survey configuration', value=survey)
        tree = ParameterTree(parent=self.parent)
        tree.setParameters(parameter, showTop=False)

        parameter.parC.setValue(QgsCoordinateReferenceSystem('EPSG:4326'))
        parameter.parT.setValue('Marine')
        parameter.parN.setValue('Renamed-Survey')
        self.qgisApp.processEvents()

        values = parameter.value()

        self.assertEqual(survey.crs.authid(), 'EPSG:4326')
        self.assertEqual(survey.type.name, 'Marine')
        self.assertEqual(survey.name, 'Renamed-Survey')
        self.assertEqual(values[0].authid(), 'EPSG:4326')
        self.assertEqual(values[1:], ('Marine', 'Renamed-Survey'))

        tree.setParameters(None)
        tree.deleteLater()
        self.qgisApp.processEvents()

    def testAnalysisParameterKeepsExpectedValueTupleOrder(self):
        survey = createTestSurvey()
        parameter = MyAnalysisParameter(name='Survey analysis', value=survey)

        parameter.parM.child('Interval velocity').setValue(3100.0)
        parameter.parU.child('Delta offset').setValue(42.0)
        self.qgisApp.processEvents()

        area, angles, binning, offset, unique = parameter.value()

        self.assertEqual((area, angles, binning, offset, unique), (survey.output.rctOutput, survey.angles, survey.binning, survey.offset, survey.unique))
        self.assertEqual(binning.vint, 3100.0)
        self.assertEqual(unique.dOffset, 42.0)

    def testGridParameterWritesLocalAndGlobalChangesBackToGrid(self):
        survey = createTestSurvey()
        parameter = MyGridParameter(name='Survey grid', value=survey.grid)

        parameter.parL.child('Max fold').setValue(12)
        parameter.parG.child('Azimuth').setValue(33.0)
        self.qgisApp.processEvents()

        self.assertEqual(parameter.value().fold, 12)
        self.assertEqual(parameter.value().angle, 33.0)

    def testReflectorsParameterKeepsExpectedValueTupleOrder(self):
        survey = createTestSurvey()
        parameter = MyReflectorsParameter(name='Survey reflectors', value=survey)

        parameter.parP.child('Plane dip').setValue(25.0)
        parameter.parS.child('Sphere radius').setValue(450.0)
        self.qgisApp.processEvents()

        plane, sphere = parameter.value()

        self.assertEqual((plane, sphere), (survey.globalPlane, survey.globalSphere))
        self.assertEqual(plane.dip, 25.0)
        self.assertEqual(sphere.radius, 450.0)

    def testBlockParameterWritesTemplateListBackToBlock(self):
        survey = createTestSurvey()
        block = createDefaultBlock('Block-1', survey)
        parameter = MyBlockParameter(name='Block-1', value=block, survey=survey)

        newTemplate = createDefaultTemplate('Template-2', survey)
        updatedTemplateList = block.templateList[:] + [newTemplate]
        parameter.parS.setValue(QRectF(10.0, 20.0, 30.0, 40.0))
        parameter.parT.setValue(updatedTemplateList)
        self.qgisApp.processEvents()

        self.assertEqual(parameter.value().borders.srcBorder, QRectF(10.0, 20.0, 30.0, 40.0))
        self.assertEqual(len(parameter.value().templateList), 2)
        self.assertEqual(parameter.value().templateList[-1].name, 'Template-2')

    def testTemplateParameterWritesSeedListBackToTemplate(self):
        survey = createTestSurvey()
        template = createDefaultTemplate('Template-1', survey)
        parameter = MyTemplateParameter(name='Template-1', value=template, survey=survey)

        updatedRollList = template.rollList[:1]
        updatedSeedList = template.seedList[:1]
        parameter.parR.setValue(updatedRollList)
        parameter.parS.setValue(updatedSeedList)
        self.qgisApp.processEvents()

        self.assertEqual(len(parameter.value().rollList), 1)
        self.assertEqual(len(parameter.value().seedList), 1)
        self.assertEqual(parameter.value().seedList[0].name, template.seedList[0].name)


if __name__ == '__main__':
    unittest.main()
