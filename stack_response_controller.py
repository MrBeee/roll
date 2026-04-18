# coding=utf-8

import numpy as np
import pyqtgraph as pg
from qgis.PyQt.QtCore import QPoint

from . import functions_numba as fnb
from .enums_and_int_flags import Direction


class StackResponseController:
    def __init__(self, window) -> None:
        self.window = window

    def getStackResponseRedrawContext(self):
        window = self.window

        if window.output.anaOutput is None or window.survey is None or window.survey.binTransform is None:
            return None

        xAnaSize = window.output.anaOutput.shape[0]
        yAnaSize = window.output.anaOutput.shape[1]
        if xAnaSize == 0 or yAnaSize == 0:
            return None

        if window.spiderPoint == QPoint(-1, -1):
            window.spiderPoint = QPoint(xAnaSize // 2, yAnaSize // 2)

        if window.spiderPoint.x() < 0:
            window.spiderPoint.setX(0)

        if window.spiderPoint.y() < 0:
            window.spiderPoint.setY(0)

        if window.spiderPoint.x() >= xAnaSize:
            window.spiderPoint.setX(xAnaSize - 1)

        if window.spiderPoint.y() >= yAnaSize:
            window.spiderPoint.setY(yAnaSize - 1)

        nX = window.spiderPoint.x()
        nY = window.spiderPoint.y()

        invBinTransform, _ = window.survey.binTransform.inverted()
        cmpX, cmpY = invBinTransform.map(nX, nY)
        stkX, stkY = window.survey.st2Transform.map(cmpX, cmpY)

        return {
            'nX': nX,
            'nY': nY,
            'stkX': stkX,
            'stkY': stkY,
            'x0': window.survey.output.rctOutput.left(),
            'y0': window.survey.output.rctOutput.top(),
            'dx': window.survey.grid.binSize.x(),
            'dy': window.survey.grid.binSize.y(),
        }

    def redrawStackResponse(self, surface: str, context) -> None:
        if surface == 'stack-inline':
            self.window.plotStkTrk(context['nY'], context['stkY'], context['x0'], context['dx'])
            return

        if surface == 'stack-xline':
            self.window.plotStkBin(context['nX'], context['stkX'], context['y0'], context['dy'])
            return

        if surface == 'stack-cell':
            self.window.plotStkCel(context['nX'], context['nY'], context['stkX'], context['stkY'])
            return

        raise NotImplementedError(f'unsupported stack-response surface: {surface}')

    @staticmethod
    def shouldRedrawStackResponse(surface: str, direction: Direction) -> bool:
        if direction == Direction.NA:
            return True

        if surface == 'stack-inline':
            return direction in (Direction.Up, Direction.Dn)

        if surface == 'stack-xline':
            return direction in (Direction.Lt, Direction.Rt)

        if surface == 'stack-cell':
            return direction in (Direction.Up, Direction.Dn, Direction.Lt, Direction.Rt)

        raise NotImplementedError(f'unsupported stack-response surface: {surface}')

    def plotStkTrk(self, nY: int, stkY: int, x0: float, dx: float):
        window = self.window

        with pg.BusyCursor():
            kMax, dK, kStart, kDelta = window.plotRedrawHelper.buildInlineStackAxisValues(window)

            responseKey = window.plotRedrawHelper.buildInlineResponseKey(nY)
            if not window.plotRedrawHelper.canReuseInlineResponse(window, responseKey):
                slice3D, I = fnb.numbaSlice3D(window.output.anaOutput[:, nY, :, :], window.survey.unique.apply)
                if slice3D.shape[0] == 0:
                    return

                window.inlineStk = fnb.numbaNdft1D(kMax, dK, slice3D, I)
                window.plotRedrawHelper.storeInlineResponseKey(responseKey)

            window.prepareAnalysisImageAndColorBar(
                window.stkTrkWidget,
                window.inlineStk,
                x0,
                kStart,
                dx,
                kDelta,
                'stkTrkImItem',
                'stkTrkColorBar',
            )

            plotTitle = f'{window.plotTitles[5]} [line={stkY}]'
            window.stkTrkWidget.setTitle(plotTitle, color='b', size='16pt')

    def plotStkBin(self, nX: int, stkX: int, y0: float, dy: float):
        window = self.window

        with pg.BusyCursor():
            kMax, dK, kStart, kDelta = window.plotRedrawHelper.buildXlineStackAxisValues(window)

            responseKey = window.plotRedrawHelper.buildXlineResponseKey(nX)
            if not window.plotRedrawHelper.canReuseXlineResponse(window, responseKey):
                slice3D, I = fnb.numbaSlice3D(window.output.anaOutput[nX, :, :, :], window.survey.unique.apply)
                if slice3D.shape[0] == 0:
                    return

                window.x0lineStk = fnb.numbaNdft1D(kMax, dK, slice3D, I)
                window.plotRedrawHelper.storeXlineResponseKey(responseKey)

            window.prepareAnalysisImageAndColorBar(
                window.stkBinWidget,
                window.x0lineStk,
                y0,
                kStart,
                dy,
                kDelta,
                'stkBinImItem',
                'stkBinColorBar',
            )

            plotTitle = f'{window.plotTitles[6]} [stake={stkX}]'
            window.stkBinWidget.setTitle(plotTitle, color='b', size='16pt')

    def getSelectedStackCellPatterns(self):
        window = self.window

        if not window.tbStackPatterns.isChecked():
            return (None, None)

        maxPatterns = len(window.survey.patternList)
        patternIndex3 = window.pattern3.currentIndex() - 1
        patternIndex4 = window.pattern4.currentIndex() - 1

        pattern3 = window.survey.patternList[patternIndex3] if 0 <= patternIndex3 < maxPatterns else None
        pattern4 = window.survey.patternList[patternIndex4] if 0 <= patternIndex4 < maxPatterns else None

        return (pattern3, pattern4)

    def computeStackCellResponse(self, nX: int, nY: int, pattern3=None, pattern4=None):
        window = self.window

        kMin = 0.001 * window.appSettings.kxyStack.x()
        kMax = 0.001 * window.appSettings.kxyStack.y()
        dK = 0.001 * window.appSettings.kxyStack.z()
        kMax = kMax + dK

        kStart = 1000.0 * (kMin - 0.5 * dK)
        kDelta = 1000.0 * dK

        offsetX, offsetY, noData = fnb.numbaOffsetBin(window.output.anaOutput[nX, nY, :, :], window.survey.unique.apply)
        fold = 0 if noData else offsetX.shape[0]

        if noData or offsetX.size == 0:
            kX = np.arange(kMin, kMax, dK)
            responseSize = kX.shape[0]
            response = np.ones(shape=(responseSize, responseSize), dtype=np.float32) * -50.0
        else:
            response = fnb.numbaNdft2D(kMin, kMax, dK, offsetX, offsetY)

        for pattern in (pattern3, pattern4):
            if pattern is None:
                continue
            xPattern, yPattern = pattern.calcPatternPointArrays()
            response = response + fnb.numbaNdft2D(kMin, kMax, dK, xPattern, yPattern)

        return response, kStart, kDelta, fold

    def plotStkCel(self, nX: int, nY: int, stkX: int, stkY: int):
        window = self.window

        if window.output.anaOutput is None or window.output.anaOutput.shape[0] == 0 or window.output.anaOutput.shape[1] == 0:
            return

        with pg.BusyCursor():
            pattern3, pattern4 = window.getSelectedStackCellPatterns()
            responseKey = window.plotRedrawHelper.buildStackCellResponseKey(window, nX, nY)
            if not window.plotRedrawHelper.canReuseStackCellResponse(window, responseKey):
                window.xyCellStk, kStart, kDelta, fold = window.computeStackCellResponse(nX, nY, pattern3, pattern4)
                window.plotRedrawHelper.storeStackCellResponse(responseKey, fold)
            else:
                kStart, kDelta, fold = window.plotRedrawHelper.buildStackCellCachedAxisValues(window)

            window.prepareAnalysisImageAndColorBar(
                window.stkCelWidget,
                window.xyCellStk,
                kStart,
                kStart,
                kDelta,
                kDelta,
                'stkCelImItem',
                'stkCelColorBar',
            )

            plotTitle = f'{window.plotTitles[7]} [stake={stkX}, line={stkY}, fold={fold}]'
            window.stkCelWidget.setTitle(plotTitle, color='b', size='16pt')
