# coding=utf-8
import os
import tempfile
import unittest

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

    def testRecordCurrentFileMovesEntryToFrontAndTruncates(self):
        recent = ['b.roll', 'a.roll', 'c.roll']

        updated = self.service.recordCurrentFile(recent, 'a.roll', 2)

        self.assertEqual(updated, ['a.roll', 'b.roll'])

    def testBuildRecentFileMenuKeepsUnresolvedRelativeEntryButHidesIt(self):
        result = self.service.buildRecentFileMenu(['relative.roll'], os.path.join('D:\\', 'missing'), 5)

        self.assertFalse(result.changed)
        self.assertEqual(result.recentFileList, ['relative.roll'])
        self.assertEqual(result.visibleEntries, [])

    def testBuildRecentFileMenuShowsResolvableEntries(self):
        with tempfile.TemporaryDirectory() as tempDir:
            absProject = os.path.join(tempDir, 'absolute.roll')
            relProject = os.path.join(tempDir, 'relative.roll')
            with open(absProject, 'w', encoding='utf-8') as handle:
                handle.write('abs')
            with open(relProject, 'w', encoding='utf-8') as handle:
                handle.write('rel')

            result = self.service.buildRecentFileMenu([absProject, 'relative.roll'], tempDir, 5)

            self.assertEqual(result.recentFileList, [absProject, 'relative.roll'])
            self.assertEqual([entry.storedName for entry in result.visibleEntries], [absProject, 'relative.roll'])
            self.assertEqual([entry.displayName for entry in result.visibleEntries], ['absolute.roll', 'relative.roll'])

    def testResolveRecentSelectionReturnsResolvedExistingPath(self):
        with tempfile.TemporaryDirectory() as tempDir:
            relProject = os.path.join(tempDir, 'relative.roll')
            with open(relProject, 'w', encoding='utf-8') as handle:
                handle.write('rel')

            result = self.service.resolveRecentSelection('relative.roll', tempDir)

            self.assertTrue(result.exists)
            self.assertEqual(result.resolvedName, relProject)


if __name__ == '__main__':
    unittest.main()
