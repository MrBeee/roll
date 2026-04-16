# coding=utf-8

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecentFileMenuEntry:
    storedName: str
    resolvedName: str
    displayName: str


@dataclass(frozen=True)
class RecentFileMenuResult:
    recentFileList: list[str]
    visibleEntries: list[RecentFileMenuEntry] = field(default_factory=list)
    changed: bool = False


@dataclass(frozen=True)
class RecentFileResolution:
    storedName: str
    resolvedName: str
    exists: bool


class DocumentContextService:
    def loadStoredValues(self, state, *, projectDirectory='', importDirectory='', recentFileList=None):
        state.projectDirectory = projectDirectory or ''
        state.importDirectory = importDirectory or ''
        state.recentFileList = list(recentFileList or [])

    def clearCurrentFile(self, state):
        state.fileName = ''

    def commitOpenedFile(self, state, fileName, maxRecentFiles):
        self._commitCurrentFile(state, fileName, maxRecentFiles)

    def commitSavedFile(self, state, fileName, maxRecentFiles):
        self._commitCurrentFile(state, fileName, maxRecentFiles)

    def _commitCurrentFile(self, state, fileName, maxRecentFiles):
        state.fileName = fileName or ''
        if not state.fileName:
            return

        state.projectDirectory = os.path.dirname(state.fileName) or ''
        state.recentFileList = self.recordCurrentFile(state.recentFileList, state.fileName, maxRecentFiles)

    def recordCurrentFile(self, recentFileList, fileName, maxRecentFiles):
        updated = [entry for entry in recentFileList if entry != fileName]
        updated.insert(0, fileName)
        return updated[:maxRecentFiles]

    def resolveRecentFileName(self, fileName, projectDirectory):
        if fileName and not os.path.isabs(fileName) and projectDirectory:
            return os.path.join(projectDirectory, fileName)
        return fileName

    def removeRecentFile(self, state, fileName):
        updated = [entry for entry in state.recentFileList if entry != fileName]
        changed = len(updated) != len(state.recentFileList)
        state.recentFileList = updated
        return changed

    def buildRecentFileMenu(self, state, maxRecentFiles):
        prunedRecentFiles = []
        visibleEntries = []

        for fileName in state.recentFileList:
            resolvedName = self.resolveRecentFileName(fileName, state.projectDirectory)
            if os.path.isabs(fileName):
                if resolvedName and os.path.exists(resolvedName):
                    prunedRecentFiles.append(fileName)
                    visibleEntries.append(RecentFileMenuEntry(fileName, resolvedName, os.path.basename(resolvedName)))
                continue

            prunedRecentFiles.append(fileName)
            if resolvedName and os.path.exists(resolvedName):
                visibleEntries.append(RecentFileMenuEntry(fileName, resolvedName, os.path.basename(resolvedName)))

        return RecentFileMenuResult(
            recentFileList=prunedRecentFiles,
            visibleEntries=visibleEntries[:maxRecentFiles],
            changed=prunedRecentFiles != list(state.recentFileList),
        )

    def resolveRecentSelection(self, state, recentName):
        resolvedName = self.resolveRecentFileName(recentName, state.projectDirectory)
        exists = bool(resolvedName and os.path.exists(resolvedName))
        return RecentFileResolution(storedName=recentName, resolvedName=resolvedName, exists=exists)
