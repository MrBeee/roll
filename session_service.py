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


class SessionService:
    def recordCurrentFile(self, recentFileList, fileName, maxRecentFiles):
        updated = [entry for entry in recentFileList if entry != fileName]
        updated.insert(0, fileName)
        return updated[:maxRecentFiles]

    def resolveRecentFileName(self, fileName, projectDirectory):
        if fileName and not os.path.isabs(fileName) and projectDirectory:
            return os.path.join(projectDirectory, fileName)
        return fileName

    def removeRecentFile(self, recentFileList, fileName):
        updated = [entry for entry in recentFileList if entry != fileName]
        return updated, len(updated) != len(recentFileList)

    def buildRecentFileMenu(self, recentFileList, projectDirectory, maxRecentFiles):
        prunedRecentFiles = []
        visibleEntries = []

        for fileName in recentFileList:
            resolvedName = self.resolveRecentFileName(fileName, projectDirectory)
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
            changed=prunedRecentFiles != list(recentFileList),
        )

    def resolveRecentSelection(self, recentName, projectDirectory):
        resolvedName = self.resolveRecentFileName(recentName, projectDirectory)
        exists = bool(resolvedName and os.path.exists(resolvedName))
        return RecentFileResolution(storedName=recentName, resolvedName=resolvedName, exists=exists)
