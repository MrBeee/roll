# coding=utf-8

import os
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class _PointArraySpec:
    liveEAttr: str
    liveNAttr: str
    deadEAttr: str
    deadNAttr: str
    boundAttr: str | None = None


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
    _pointArraySpecs = {
        'rpsImport': _PointArraySpec('rpsLiveE', 'rpsLiveN', 'rpsDeadE', 'rpsDeadN', 'rpsBound'),
        'spsImport': _PointArraySpec('spsLiveE', 'spsLiveN', 'spsDeadE', 'spsDeadN', 'spsBound'),
        'recGeom': _PointArraySpec('recLiveE', 'recLiveN', 'recDeadE', 'recDeadN'),
        'srcGeom': _PointArraySpec('srcLiveE', 'srcLiveN', 'srcDeadE', 'srcDeadN'),
    }

    def recordCurrentFile(self, recentFileList, fileName, maxRecentFiles):
        updated = [entry for entry in recentFileList if entry != fileName]
        updated.insert(0, fileName)
        return updated[:maxRecentFiles]

    def setArray(self, state, arrayAttr, array):
        setattr(state, arrayAttr, array)
        self.refreshArrayState(state, arrayAttr)

    def clearSurveyArrays(self, state):
        state.clearSurveyArrays()

    def refreshArrayState(self, state, arrayAttr):
        spec = self._pointArraySpecs.get(arrayAttr)
        if spec is None:
            return

        array = getattr(state, arrayAttr)
        liveE, liveN, deadE, deadN = self._getAliveAndDead(array)
        setattr(state, spec.liveEAttr, liveE)
        setattr(state, spec.liveNAttr, liveN)
        setattr(state, spec.deadEAttr, deadE)
        setattr(state, spec.deadNAttr, deadN)

        if spec.boundAttr is not None:
            bound = None
            if liveE is not None and liveN is not None and liveE.shape[0] > 0:
                bound = self._convexHull(liveE, liveN)
            setattr(state, spec.boundAttr, bound)

    def _getAliveAndDead(self, geom):
        if geom is None or geom.shape[0] == 0:
            return (None, None, None, None)

        try:
            inUseMask = geom['InUse'] > 0
            nLive = np.count_nonzero(inUseMask)
        except (ValueError, KeyError):
            nLive = geom.shape[0]
            inUseMask = None

        nPoints = geom.shape[0]
        nDead = nPoints - nLive

        if nDead > 0 and inUseMask is not None:
            pointE = geom['East']
            pointN = geom['North']
            liveE = pointE[inUseMask]
            liveN = pointN[inUseMask]
            deadMask = np.logical_not(inUseMask)
            deadE = pointE[deadMask]
            deadN = pointN[deadMask]
            return (liveE, liveN, deadE, deadN)

        liveE = geom['East']
        liveN = geom['North']
        return (liveE, liveN, None, None)

    def _convexHull(self, x, y):
        points = np.column_stack((x, y))

        def link(a, b):
            return np.concatenate((a, b[1:]))

        def edge(a, b):
            return np.concatenate(([a], [b]))

        def dome(pointsToProcess, base):
            head, tail = base
            distances = np.dot(pointsToProcess - head, np.dot(((0, -1), (1, 0)), (tail - head)))
            outer = np.repeat(pointsToProcess, distances > 0, 0)
            if len(outer):
                pivot = pointsToProcess[np.argmax(distances)]
                return link(dome(outer, edge(head, pivot)), dome(outer, edge(pivot, tail)))
            return base

        if len(points) > 2:
            axis = points[:, 0]
            base = np.take(points, [np.argmin(axis), np.argmax(axis)], 0)
            return link(dome(points, base), dome(points, base[::-1]))
        return points

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
