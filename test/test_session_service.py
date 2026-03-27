# coding=utf-8
import os
import tempfile
import unittest

from .plugin_loader import loadPluginModule

sessionServiceModule = loadPluginModule('session_service')

SessionService = sessionServiceModule.SessionService


class SessionServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = SessionService()

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
