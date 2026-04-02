# coding=utf-8

import pyqtgraph as pg

from . import config
from .aux_functions import convexHull
from .enums_and_int_flags import MsgType
from .sps_io_and_qc import getAliveAndDead


class ProjectLoadApplier:
    def __init__(self, mainWindow):
        self.mainWindow = mainWindow

    def apply(self, sidecarResult):
        self.applyAnalysisState(sidecarResult)
        self.applySurveyDataState(sidecarResult)

    def applyAnalysisState(self, sidecarResult):
        self._applyAnalysisState(sidecarResult)

    def applySurveyDataState(self, sidecarResult):
        self._applySurveyDataState(sidecarResult)

    def _applyAnalysisState(self, sidecarResult):
        mainWindow = self.mainWindow

        mainWindow.output.binOutput = sidecarResult.binOutput
        mainWindow.output.minOffset = sidecarResult.minOffset
        mainWindow.output.maxOffset = sidecarResult.maxOffset
        mainWindow.output.rmsOffset = sidecarResult.rmsOffset
        mainWindow.output.offstHist = sidecarResult.offstHist
        mainWindow.output.ofAziHist = sidecarResult.ofAziHist
        mainWindow.output.minimumFold = sidecarResult.minimumFold
        mainWindow.output.maximumFold = sidecarResult.maximumFold
        mainWindow.output.minMinOffset = sidecarResult.minMinOffset
        mainWindow.output.maxMinOffset = sidecarResult.maxMinOffset
        mainWindow.output.minMaxOffset = sidecarResult.minMaxOffset
        mainWindow.output.maxMaxOffset = sidecarResult.maxMaxOffset
        mainWindow.output.minRmsOffset = sidecarResult.minRmsOffset
        mainWindow.output.maxRmsOffset = sidecarResult.maxRmsOffset

        self._applyLayoutImageState()

        if sidecarResult.analysisMemmapResult is None:
            mainWindow.anaModel.setData(None)
            mainWindow.output.an2Output = None
            mainWindow.output.anaOutput = None
        else:
            mainWindow.output.anaOutput = sidecarResult.analysisMemmapResult.memmap
            mainWindow.output.an2Output = sidecarResult.analysisMemmapResult.an2Output

        mainWindow.setDataAnaTableModel()

    def _applyLayoutImageState(self):
        mainWindow = self.mainWindow

        if mainWindow.output.binOutput is None:
            mainWindow.actionArea.setChecked(True)
            mainWindow.imageType = 0
            return

        mainWindow.actionFold.setChecked(True)
        mainWindow.imageType = 1
        mainWindow.layoutImg = mainWindow.output.binOutput
        mainWindow.layoutMax = mainWindow.output.maximumFold
        mainWindow.layoutImItem = pg.ImageItem()
        mainWindow.layoutImItem.setImage(mainWindow.layoutImg, levels=(0.0, mainWindow.layoutMax))

        label = 'fold'
        colorMapObj = mainWindow.resolveColorMapObject(config.foldDispCmap, fallback='viridis')
        if mainWindow.layoutColorBar is None:
            try:
                mainWindow.layoutColorBar = mainWindow.layoutWidget.plotItem.addColorBar(
                    mainWindow.layoutImItem,
                    colorMap=colorMapObj,
                    label=label,
                    limits=(0, None),
                    rounding=10.0,
                    values=(0.0, mainWindow.layoutMax),
                )
            except TypeError as exc:
                mainWindow.appendLogMessage(f'Colorbar init failed: {exc}', MsgType.Error)
                mainWindow.layoutColorBar = None
        else:
            mainWindow.layoutColorBar.setImageItem(mainWindow.layoutImItem)
            mainWindow.layoutColorBar.setLevels(low=0.0, high=mainWindow.layoutMax)
            try:
                mainWindow.layoutColorBar.setColorMap(colorMapObj)
            except TypeError as exc:
                mainWindow.appendLogMessage(f'Colorbar setColorMap failed: {exc}', MsgType.Error)
            mainWindow.setColorbarLabel(label)

    def _applySurveyDataState(self, sidecarResult):
        mainWindow = self.mainWindow

        mainWindow.rpsImport = sidecarResult.rpsImport
        mainWindow.spsImport = sidecarResult.spsImport
        mainWindow.xpsImport = sidecarResult.xpsImport
        mainWindow.recGeom = sidecarResult.recGeom
        mainWindow.srcGeom = sidecarResult.srcGeom
        mainWindow.relGeom = sidecarResult.relGeom

        self._applyPointArrayState('rpsImport', ('rpsLiveE', 'rpsLiveN', 'rpsDeadE', 'rpsDeadN'), 'actionRpsPoints', boundAttr='rpsBound')
        self._applyPointArrayState('spsImport', ('spsLiveE', 'spsLiveN', 'spsDeadE', 'spsDeadN'), 'actionSpsPoints', boundAttr='spsBound')
        self._applyPointArrayState('recGeom', ('recLiveE', 'recLiveN', 'recDeadE', 'recDeadN'), 'actionRecPoints')
        self._applyPointArrayState('srcGeom', ('srcLiveE', 'srcLiveN', 'srcDeadE', 'srcDeadN'), 'actionSrcPoints')

        self._refreshModelAndView('rpsModel', 'rpsImport', 'rpsView')
        self._refreshModelAndView('spsModel', 'spsImport', 'spsView')
        self._refreshModelAndView('xpsModel', 'xpsImport', 'xpsView')
        self._refreshModelAndView('recModel', 'recGeom', 'recView')
        self._refreshModelAndView('relModel', 'relGeom', 'relView')
        self._refreshModelAndView('srcModel', 'srcGeom', 'srcView')

    def _applyPointArrayState(self, arrayAttr, liveDeadAttrs, actionAttr, boundAttr=None):
        mainWindow = self.mainWindow
        array = getattr(mainWindow, arrayAttr)
        action = getattr(mainWindow, actionAttr)

        if array is not None:
            liveE, liveN, deadE, deadN = getAliveAndDead(array)
            setattr(mainWindow, liveDeadAttrs[0], liveE)
            setattr(mainWindow, liveDeadAttrs[1], liveN)
            setattr(mainWindow, liveDeadAttrs[2], deadE)
            setattr(mainWindow, liveDeadAttrs[3], deadN)

            if boundAttr is not None:
                setattr(mainWindow, boundAttr, convexHull(liveE, liveN))

            nImport = array.shape[0]
            action.setChecked(nImport > 0)
            action.setEnabled(nImport > 0)
        else:
            setattr(mainWindow, liveDeadAttrs[0], None)
            setattr(mainWindow, liveDeadAttrs[1], None)
            setattr(mainWindow, liveDeadAttrs[2], None)
            setattr(mainWindow, liveDeadAttrs[3], None)
            if boundAttr is not None:
                setattr(mainWindow, boundAttr, None)
            action.setChecked(False)
            action.setEnabled(False)

    def _refreshModelAndView(self, modelAttr, dataAttr, viewAttr):
        mainWindow = self.mainWindow

        model = getattr(mainWindow, modelAttr)
        view = getattr(mainWindow, viewAttr)
        model.setData(getattr(mainWindow, dataAttr))
        if view is not None:
            view.reset()
