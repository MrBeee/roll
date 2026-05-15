# coding=utf-8
import unittest
from unittest.mock import Mock

from qgis.core import QgsCoordinateReferenceSystem

from .plugin_loader import loadPluginModule
from .utilities import createTestSurvey

helpersModule = loadPluginModule('parameter_seed_well_helpers')
rollSeedModule = loadPluginModule('roll_seed')
rollWellModule = loadPluginModule('roll_well')

SeedParameterStateHelper = helpersModule.SeedParameterStateHelper
SeedPatternRefreshState = helpersModule.SeedPatternRefreshState
WellParameterStateHelper = helpersModule.WellParameterStateHelper
RollSeed = rollSeedModule.RollSeed
RollWell = rollWellModule.RollWell


class SeedParameterStateHelperTest(unittest.TestCase):
    def testApplySeedTypeClearsPatternForNonGridSeed(self):
        seed = RollSeed('Seed-1')
        seed.patternNo = 3
        helper = SeedParameterStateHelper(seed)

        visibility = helper.applySeedType('Circle')

        self.assertEqual(seed.patternNo, -1)
        self.assertFalse(visibility.showPattern)
        self.assertTrue(visibility.showCircle)

    def testPatternNamesFallsBackToSurvey(self):
        survey = createTestSurvey()
        patternOne = Mock()
        patternOne.name = 'Pattern-1'
        patternTwo = Mock()
        patternTwo.name = 'Pattern-2'
        survey.patternList = [patternOne, patternTwo]

        helper = SeedParameterStateHelper(RollSeed('Seed-1'), survey)

        self.assertEqual(helper.patternNames(), ['<None>', 'Pattern-1', 'Pattern-2'])

    def testRefreshedPatternStateUsesCurrentPatternSelectionForGridSeed(self):
        survey = createTestSurvey()
        patternOne = Mock()
        patternOne.name = 'Pattern-1'
        patternTwo = Mock()
        patternTwo.name = 'Pattern-2'
        survey.patternList = [patternOne, patternTwo]

        seed = RollSeed('Seed-1')
        seed.patternNo = 1
        helper = SeedParameterStateHelper(seed, survey)

        refreshState = helper.refreshedPatternState('Grid (stationary)')

        self.assertIsInstance(refreshState, SeedPatternRefreshState)
        self.assertEqual(refreshState.patterns, ['<None>', 'Pattern-1', 'Pattern-2'])
        self.assertEqual(refreshState.selectedPattern, 'Pattern-2')
        self.assertTrue(refreshState.visibilityState.showPattern)

    def testRefreshedPatternStateFallsBackToNoneForNonGridSeed(self):
        survey = createTestSurvey()
        patternOne = Mock()
        patternOne.name = 'Pattern-1'
        survey.patternList = [patternOne]

        seed = RollSeed('Seed-1')
        seed.patternNo = 0
        helper = SeedParameterStateHelper(seed, survey)

        refreshState = helper.refreshedPatternState('Circle')

        self.assertEqual(refreshState.selectedPattern, '<None>')
        self.assertFalse(refreshState.visibilityState.showPattern)


class WellParameterStateHelperTest(unittest.TestCase):
    def testRefreshHeaderPassesExplicitSurveyContext(self):
        survey = createTestSurvey()
        survey.crs = QgsCoordinateReferenceSystem('EPSG:28992')
        well = RollWell('synthetic.well')
        well.refreshHeaderFromCurrentState = Mock(return_value=True)

        helper = WellParameterStateHelper(well, survey)
        helper.refreshHeader()

        well.refreshHeaderFromCurrentState.assert_called_once_with(
            name=None,
            crs=None,
            survey=survey,
            surveyCrs=survey.crs,
            glbTransform=survey.glbTransform,
        )

    def testRefreshHeaderOrRaisePassesExplicitSurveyContext(self):
        survey = createTestSurvey()
        survey.crs = QgsCoordinateReferenceSystem('EPSG:28992')
        well = RollWell('synthetic.well')
        well.refreshHeaderFromCurrentStateOrRaise = Mock(return_value=True)

        helper = WellParameterStateHelper(well, survey)
        helper.refreshHeaderOrRaise()

        well.refreshHeaderFromCurrentStateOrRaise.assert_called_once_with(
            name=None,
            crs=None,
            survey=survey,
            surveyCrs=survey.crs,
            glbTransform=survey.glbTransform,
        )


if __name__ == '__main__':
    unittest.main()
