# coding=utf-8

import contextlib

import pyqtgraph as pg


class PlotViewStateController:
    def __init__(self, window) -> None:
        self.window = window

    def handleShownWidget(self, source) -> bool:
        if isinstance(source, pg.PlotWidget):
            return self._handleShownPlotWidget(source)

        self._disablePlotToolbarActions()
        return True

    def plotZoomRect(self) -> None:
        visiblePlot, _ = self.window.getVisiblePlotWidget()
        if visiblePlot is None:
            return

        viewBox = visiblePlot.getViewBox()
        self.window.rect = viewBox.getState()['mouseMode'] == pg.ViewBox.RectMode
        viewBox.setMouseMode(pg.ViewBox.PanMode if self.window.rect else pg.ViewBox.RectMode)

    def plotAspectRatio(self) -> None:
        visiblePlot, _ = self.window.getVisiblePlotWidget()
        if visiblePlot is None:
            return

        plotItem = visiblePlot.getPlotItem()
        self.window.XisY = not plotItem.saveState()['view']['aspectLocked']
        visiblePlot.setAspectLocked(self.window.XisY)

    def plotAntiAlias(self) -> None:
        visiblePlot, index = self.window.getVisiblePlotWidget()
        if visiblePlot is None:
            return

        self.window.antiA[index] = not self.window.antiA[index]
        visiblePlot.setAntialiasing(self.window.antiA[index])

    def plotGridX(self) -> None:
        visiblePlot, _ = self.window.getVisiblePlotWidget()
        if visiblePlot is None:
            return

        plotItem = visiblePlot.getPlotItem()
        self.window.gridX = not plotItem.saveState()['xGridCheck']
        if self.window.gridX:
            visiblePlot.showGrid(x=True, alpha=0.75)
        else:
            visiblePlot.showGrid(x=False)

    def plotGridY(self) -> None:
        visiblePlot, _ = self.window.getVisiblePlotWidget()
        if visiblePlot is None:
            return

        plotItem = visiblePlot.getPlotItem()
        self.window.gridY = not plotItem.saveState()['yGridCheck']
        if self.window.gridY:
            visiblePlot.showGrid(y=True, alpha=0.75)
        else:
            visiblePlot.showGrid(y=False)

    def _handleShownPlotWidget(self, plotWidget) -> bool:
        self._rebindZoomAll(plotWidget)

        plotIndex = self.window.getVisiblePlotIndex(plotWidget)
        if plotIndex is None:
            return False

        self._enablePlotToolbarActions(plotIndex)
        self._syncToolbarStateFromPlot(plotWidget, plotIndex)
        self.window.updateVisiblePlotWidget(plotIndex)
        return True

    def _rebindZoomAll(self, plotWidget) -> None:
        with contextlib.suppress(RuntimeError):
            self.window.actionZoomAll.triggered.disconnect()
        self.window.actionZoomAll.triggered.connect(plotWidget.autoRange)

    def _enablePlotToolbarActions(self, plotIndex: int) -> None:
        self.window.actionZoomAll.setEnabled(True)
        self.window.actionZoomRect.setEnabled(True)
        self.window.actionAspectRatio.setEnabled(True)
        self.window.actionAntiAlias.setEnabled(True)
        self.window.actionRuler.setEnabled(plotIndex == 0)
        self.window.actionProjected.setEnabled(plotIndex == 0)

    def _disablePlotToolbarActions(self) -> None:
        self.window.actionZoomAll.setEnabled(False)
        self.window.actionZoomRect.setEnabled(False)
        self.window.actionAspectRatio.setEnabled(False)
        self.window.actionAntiAlias.setEnabled(False)
        self.window.actionRuler.setEnabled(False)
        self.window.actionProjected.setEnabled(False)

    def _syncToolbarStateFromPlot(self, plotWidget, plotIndex: int) -> None:
        self.window.actionAntiAlias.setChecked(self.window.antiA[plotIndex])

        plotItem = plotWidget.getPlotItem()
        self.window.gridX = plotItem.saveState()['xGridCheck']
        self.window.actionPlotGridX.setChecked(self.window.gridX)

        self.window.gridY = plotItem.saveState()['yGridCheck']
        self.window.actionPlotGridY.setChecked(self.window.gridY)

        self.window.XisY = plotItem.saveState()['view']['aspectLocked']
        self.window.actionAspectRatio.setChecked(self.window.XisY)

        viewBox = plotItem.getViewBox()
        self.window.rect = viewBox.getState()['mouseMode'] == pg.ViewBox.RectMode
        self.window.actionZoomRect.setChecked(self.window.rect)
