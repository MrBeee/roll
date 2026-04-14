# coding=utf-8

from dataclasses import dataclass

from .enums_and_int_flags import AnalysisRedrawReason


@dataclass
class PlotRedrawCache:
    inlineStkKey: object = None
    xlineStkKey: object = None
    stackCellResponseKey: object = None
    stackCellFold: int | None = None
    patternResponseKey: object = None


class PlotRedrawHelper:
    def __init__(self):
        self.cache = PlotRedrawCache()

    def reset(self):
        self.cache = PlotRedrawCache()

    @staticmethod
    def shouldInvalidatePatternResponse(reason: AnalysisRedrawReason) -> bool:
        return reason in (AnalysisRedrawReason.controller, AnalysisRedrawReason.patternSelectionChanged)

    @staticmethod
    def shouldInvalidateOffAziHistogram(reason: AnalysisRedrawReason) -> bool:
        return reason == AnalysisRedrawReason.controller

    @staticmethod
    def shouldInvalidateOffsetHistogram(reason: AnalysisRedrawReason) -> bool:
        return reason == AnalysisRedrawReason.controller

    @staticmethod
    def shouldInvalidateStackResponse(surface: str, reason: AnalysisRedrawReason) -> bool:
        if reason == AnalysisRedrawReason.controller:
            return True

        if surface == 'stack-cell' and reason == AnalysisRedrawReason.stackPatternChanged:
            return True

        return False

    def applySurfaceInvalidation(self, window, surface: str, reason: AnalysisRedrawReason) -> None:
        if surface == 'patterns':
            if self.shouldInvalidatePatternResponse(reason):
                self.invalidatePatternCache(window)
            return

        if surface == 'off-azi':
            if self.shouldInvalidateOffAziHistogram(reason):
                self.invalidateOffAziHistogram(window)
            return

        if surface == 'offset':
            if self.shouldInvalidateOffsetHistogram(reason):
                self.invalidateOffsetHistogram(window)
            return

        if surface in ('stack-inline', 'stack-xline', 'stack-cell'):
            if self.shouldInvalidateStackResponse(surface, reason):
                self.invalidateStackResponseCache(window, surface)
            return

        raise NotImplementedError(f'unsupported analysis redraw surface: {surface}')

    @staticmethod
    def buildInlineResponseKey(nY: int):
        return nY

    @staticmethod
    def buildXlineResponseKey(nX: int):
        return nX

    @staticmethod
    def buildStackCellResponseKey(window, nX: int, nY: int):
        return (
            nX,
            nY,
            window.tbStackPatterns.isChecked(),
            window.pattern3.currentIndex(),
            window.pattern4.currentIndex(),
        )

    @staticmethod
    def buildPatternResponseKey(window):
        return (window.pattern1.currentIndex(), window.pattern2.currentIndex())

    @staticmethod
    def buildPatternAxisValues(window):
        kMin = 0.001 * window.appSettings.kxyArray.x()
        dK = 0.001 * window.appSettings.kxyArray.z()
        kStart = 1000.0 * (kMin - 0.5 * dK)
        kDelta = 1000.0 * dK
        return (kStart, kDelta)

    @staticmethod
    def buildInlineStackAxisValues(window):
        dK = 0.001 * window.appSettings.kraStack.z()
        kMax = 0.001 * window.appSettings.kraStack.y() + dK
        kStart = 1000.0 * (0.0 - 0.5 * dK)
        kDelta = 1000.0 * dK
        return (kMax, dK, kStart, kDelta)

    @staticmethod
    def buildXlineStackAxisValues(window):
        dK = 0.001 * window.appSettings.kraStack.z()
        kMax = 0.001 * window.appSettings.kraStack.y() + dK
        kStart = 1000.0 * (0.0 - 0.5 * dK)
        kDelta = 1000.0 * dK
        return (kMax, dK, kStart, kDelta)

    def buildStackCellCachedAxisValues(self, window):
        kMin = 0.001 * window.appSettings.kxyStack.x()
        dK = 0.001 * window.appSettings.kxyStack.z()
        kStart = 1000.0 * (kMin - 0.5 * dK)
        kDelta = 1000.0 * dK
        fold = self.cache.stackCellFold if self.cache.stackCellFold is not None else 0
        return (kStart, kDelta, fold)

    def invalidatePatternCache(self, window) -> None:
        window.xyPatResp = None
        self.cache.patternResponseKey = None

    @staticmethod
    def invalidateOffAziHistogram(window) -> None:
        window.output.ofAziHist = None

    @staticmethod
    def invalidateOffsetHistogram(window) -> None:
        window.output.offstHist = None

    def invalidateStackResponseCache(self, window, surface: str) -> None:
        if surface == 'stack-inline':
            window.inlineStk = None
            self.cache.inlineStkKey = None
            return

        if surface == 'stack-xline':
            window.x0lineStk = None
            self.cache.xlineStkKey = None
            return

        if surface == 'stack-cell':
            window.xyCellStk = None
            self.cache.stackCellResponseKey = None
            self.cache.stackCellFold = None
            return

        raise NotImplementedError(f'unsupported stack-response surface: {surface}')

    def canReusePatternResponse(self, window, responseKey) -> bool:
        return window.xyPatResp is not None and self.cache.patternResponseKey == responseKey

    def storePatternResponseKey(self, responseKey) -> None:
        self.cache.patternResponseKey = responseKey

    def canReuseInlineResponse(self, window, responseKey) -> bool:
        return window.inlineStk is not None and self.cache.inlineStkKey == responseKey

    def storeInlineResponseKey(self, responseKey) -> None:
        self.cache.inlineStkKey = responseKey

    def canReuseXlineResponse(self, window, responseKey) -> bool:
        return window.x0lineStk is not None and self.cache.xlineStkKey == responseKey

    def storeXlineResponseKey(self, responseKey) -> None:
        self.cache.xlineStkKey = responseKey

    def canReuseStackCellResponse(self, window, responseKey) -> bool:
        return window.xyCellStk is not None and self.cache.stackCellResponseKey == responseKey

    def storeStackCellResponse(self, responseKey, fold: int) -> None:
        self.cache.stackCellResponseKey = responseKey
        self.cache.stackCellFold = fold

    def getStackCellFold(self) -> int | None:
        return self.cache.stackCellFold
