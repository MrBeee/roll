# coding=utf-8

import os
import tempfile
import unittest

from .plugin_loader import loadPluginModule

documentContextServiceModule = loadPluginModule('document_context_service')
runtimeStateModule = loadPluginModule('runtime_state')

DocumentContextService = documentContextServiceModule.DocumentContextService
RuntimeState = runtimeStateModule.RuntimeState


class DocumentContextServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = DocumentContextService()
        self.state = RuntimeState()

    def testLoadStoredValuesNormalizesRuntimeContext(self):
        self.service.loadStoredValues(
            self.state,
            projectDirectory='D:\\projects',
            importDirectory='D:\\imports',
            recentFileList=['one.roll'],
        )

        self.assertEqual(self.state.projectDirectory, 'D:\\projects')
        self.assertEqual(self.state.importDirectory, 'D:\\imports')
        self.assertEqual(self.state.recentFileList, ['one.roll'])

    def testCommitOpenedFileUpdatesCurrentPathAndRecentFiles(self):
        projectPath = os.path.join('D:\\', 'projects', 'example.roll')

        self.service.commitOpenedFile(self.state, projectPath, 5)

        self.assertEqual(self.state.fileName, projectPath)
        self.assertEqual(self.state.projectDirectory, os.path.dirname(projectPath))
        self.assertEqual(self.state.recentFileList, [projectPath])

    def testCommitSavedFileMovesExistingEntryToFront(self):
        first = os.path.join('D:\\', 'projects', 'first.roll')
        second = os.path.join('D:\\', 'projects', 'second.roll')
        self.state.recentFileList = [first, second]

        self.service.commitSavedFile(self.state, second, 5)

        self.assertEqual(self.state.recentFileList, [second, first])

    def testBuildRecentFileMenuPrunesMissingAbsoluteFileButKeepsRelativeEntry(self):
        with tempfile.TemporaryDirectory() as tempDir:
            existingProject = os.path.join(tempDir, 'existing.roll')
            with open(existingProject, 'w', encoding='utf-8') as handle:
                handle.write('ok')

            self.state.projectDirectory = tempDir
            self.state.recentFileList = [os.path.join(tempDir, 'missing.roll'), 'relative.roll', existingProject]

            result = self.service.buildRecentFileMenu(self.state, 5)

        self.assertTrue(result.changed)
        self.assertEqual(result.recentFileList, ['relative.roll', existingProject])
        self.assertEqual([entry.storedName for entry in result.visibleEntries], [existingProject])

    def testRemoveRecentFileUpdatesOwnedList(self):
        self.state.recentFileList = ['a.roll', 'b.roll']

        removed = self.service.removeRecentFile(self.state, 'a.roll')

        self.assertTrue(removed)
        self.assertEqual(self.state.recentFileList, ['b.roll'])


if __name__ == '__main__':
    unittest.main()