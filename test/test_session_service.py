# coding=utf-8
import unittest
from time import perf_counter

import numpy as np

from .plugin_loader import loadPluginModule

sessionServiceModule = loadPluginModule('session_service')
sessionStateModule = loadPluginModule('session_state')

SessionService = sessionServiceModule.SessionService
SessionState = sessionStateModule.SessionState


class SessionServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = SessionService()
        self.state = SessionState()

    def testSetArrayRefreshesImportedPointDerivedState(self):
        rpsImport = np.array(
            [
                (10.0, 100.0, 1),
                (20.0, 200.0, 0),
            ],
            dtype=[('East', 'f4'), ('North', 'f4'), ('InUse', 'i4')],
        )

        self.service.setArray(self.state, 'rpsImport', rpsImport)

        self.assertIs(self.state.rpsImport, rpsImport)
        self.assertEqual(self.state.rpsLiveE.tolist(), [10.0])
        self.assertEqual(self.state.rpsLiveN.tolist(), [100.0])
        self.assertEqual(self.state.rpsDeadE.tolist(), [20.0])
        self.assertEqual(self.state.rpsDeadN.tolist(), [200.0])
        self.assertIsNotNone(self.state.rpsBound)

    def testSetArrayRefreshesGeometryDerivedState(self):
        recGeom = np.array(
            [
                (10.0, 100.0, 1),
                (20.0, 200.0, 1),
            ],
            dtype=[('East', 'f4'), ('North', 'f4'), ('InUse', 'i4')],
        )

        self.service.setArray(self.state, 'recGeom', recGeom)

        self.assertIs(self.state.recGeom, recGeom)
        self.assertEqual(self.state.recLiveE.tolist(), [10.0, 20.0])
        self.assertEqual(self.state.recLiveN.tolist(), [100.0, 200.0])
        self.assertIsNone(self.state.recDeadE)
        self.assertIsNone(self.state.recDeadN)

    def testClearSurveyArraysClearsImportedAndGeometryState(self):
        self.state.rpsImport = np.zeros(1, dtype=np.float32)
        self.state.recGeom = np.zeros(1, dtype=np.float32)
        self.state.rpsLiveE = np.zeros(1, dtype=np.float32)
        self.state.recLiveE = np.zeros(1, dtype=np.float32)

        self.service.clearSurveyArrays(self.state)

        self.assertIsNone(self.state.rpsImport)
        self.assertIsNone(self.state.recGeom)
        self.assertIsNone(self.state.rpsLiveE)
        self.assertIsNone(self.state.recLiveE)

    def testResetTimersInitializesRequestedTimerSlots(self):
        self.service.resetTimers(3)

        self.assertEqual(len(self.service.timerTmin), 3)
        self.assertEqual(len(self.service.timerTmax), 3)
        self.assertEqual(len(self.service.timerTtot), 3)
        self.assertEqual(len(self.service.timerFreq), 3)
        self.assertEqual(self.service.timerTmax, [0.0, 0.0, 0.0])
        self.assertEqual(self.service.timerTtot, [0.0, 0.0, 0.0])
        self.assertEqual(self.service.timerFreq, [0, 0, 0])
        self.assertTrue(all(value == float('Inf') for value in self.service.timerTmin))

    def testElapsedTimeAccumulatesTimingStats(self):
        self.service.resetTimers(1)

        nextStart = self.service.elapsedTime(perf_counter(), 0)

        self.assertIsInstance(nextStart, float)
        self.assertGreaterEqual(self.service.timerFreq[0], 1)
        self.assertGreaterEqual(self.service.timerTmax[0], 0.0)
        self.assertGreaterEqual(self.service.timerTtot[0], 0.0)
        self.assertNotEqual(self.service.timerTmin[0], float('Inf'))


if __name__ == '__main__':
    unittest.main()
