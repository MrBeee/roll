# coding=utf-8
import unittest

import numpy as np

from .plugin_loader import loadPluginModule

sessionStateModule = loadPluginModule('session_state')

SessionState = sessionStateModule.SessionState


class SessionStateTest(unittest.TestCase):
    def testSurveyNumberStartsAtOneForNewSession(self):
        state = SessionState()

        self.assertEqual(state.surveyNumber, 1)

    def testClearSurveyArraysResetsImportedGeometryAndDerivedState(self):
        state = SessionState(
            rpsImport=np.zeros((1, 2), dtype=np.float32),
            spsImport=np.zeros((2, 2), dtype=np.float32),
            xpsImport=np.zeros((3, 2), dtype=np.float32),
            recGeom=np.zeros((4, 2), dtype=np.float32),
            srcGeom=np.zeros((5, 2), dtype=np.float32),
            relGeom=np.zeros((6, 2), dtype=np.float32),
            rpsLiveE=np.zeros(1, dtype=np.float32),
            spsLiveE=np.zeros(1, dtype=np.float32),
            recLiveE=np.zeros(1, dtype=np.float32),
            srcLiveE=np.zeros(1, dtype=np.float32),
            rpsBound=np.zeros((1, 2), dtype=np.float32),
            spsBound=np.zeros((1, 2), dtype=np.float32),
        )

        state.clearSurveyArrays()

        self.assertIsNone(state.rpsImport)
        self.assertIsNone(state.spsImport)
        self.assertIsNone(state.xpsImport)
        self.assertIsNone(state.recGeom)
        self.assertIsNone(state.srcGeom)
        self.assertIsNone(state.relGeom)
        self.assertIsNone(state.rpsLiveE)
        self.assertIsNone(state.spsLiveE)
        self.assertIsNone(state.recLiveE)
        self.assertIsNone(state.srcLiveE)
        self.assertIsNone(state.rpsBound)
        self.assertIsNone(state.spsBound)


if __name__ == '__main__':
    unittest.main()
