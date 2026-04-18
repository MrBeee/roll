# coding=utf-8

from .enums_and_int_flags import AnalysisRedrawReason, Direction


class PlotNavigationController:
    PLOT_WIDGET_SPECS = (
        ('layoutWidget', 0),
        ('offTrkWidget', 1),
        ('offBinWidget', 2),
        ('aziTrkWidget', 3),
        ('aziBinWidget', 4),
        ('stkTrkWidget', 5),
        ('stkBinWidget', 6),
        ('stkCelWidget', 7),
        ('offsetWidget', 8),
        ('offAziWidget', 9),
        ('arraysWidget', 10),
    )

    def __init__(self, window) -> None:
        self.window = window

    def mouseMovedInPlot(self, plotWidget, pos):
        viewBox = plotWidget.plotItem.vb
        if not viewBox.sceneBoundingRect().contains(pos):
            return

        mousePoint = viewBox.mapSceneToView(pos)
        if plotWidget == self.window.layoutWidget:
            self.window._setLayoutMouseStatus(mousePoint)
            return

        self.window._setGenericPlotMouseStatus(plotWidget, pos, mousePoint)

    def getVisiblePlotIndex(self, plotWidget):
        for attrName, index in self.PLOT_WIDGET_SPECS:
            if plotWidget == getattr(self.window, attrName):
                return index

        return None

    def getVisiblePlotWidget(self):
        for attrName, index in self.PLOT_WIDGET_SPECS:
            plotWidget = getattr(self.window, attrName)
            if plotWidget.isVisible():
                return (plotWidget, index)

        return (None, None)

    def getVisibleAnalysisContext(self):
        context = self.window.getStackResponseRedrawContext()
        if context is None:
            return None

        context['ox'] = 0.5 * context['dx']
        context['oy'] = 0.5 * context['dy']
        return context

    def updateVisiblePlotWidget(self, index: int, direction: Direction = Direction.NA) -> None:
        window = self.window

        if index == 0:
            window.plotLayout()
            return

        if index == 10:
            window.dispatchAnalysisRedraw('patterns', AnalysisRedrawReason.visiblePlotActivated)
            return

        if window.output.anaOutput is None:
            return

        if index == 5:
            window.dispatchAnalysisRedraw('stack-inline', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 6:
            window.dispatchAnalysisRedraw('stack-xline', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 7:
            window.dispatchAnalysisRedraw('stack-cell', AnalysisRedrawReason.visiblePlotActivated, direction=direction)
            return

        if index == 8:
            window.dispatchAnalysisRedraw('offset', AnalysisRedrawReason.visiblePlotActivated)
            return

        if index == 9:
            window.dispatchAnalysisRedraw('off-azi', AnalysisRedrawReason.visiblePlotActivated)
            return

        context = self.getVisibleAnalysisContext()
        if context is None:
            return

        if index == 1:
            window.plotOffTrk(context['nY'], context['stkY'], context['ox'])
        elif index == 2:
            window.plotOffBin(context['nX'], context['stkX'], context['oy'])
        elif index == 3:
            window.plotAziTrk(context['nY'], context['stkY'], context['ox'])
        elif index == 4:
            window.plotAziBin(context['nX'], context['stkX'], context['oy'])
