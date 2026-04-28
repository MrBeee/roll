# coding=utf-8


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
        mainWindow.output.offsetGap = sidecarResult.offsetGap
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
        mainWindow.output.minOffsetGap = sidecarResult.minOffsetGap
        mainWindow.output.maxOffsetGap = sidecarResult.maxOffsetGap

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
        mainWindow.prepareLayoutImageAndColorBar(
            mainWindow.layoutImg,
            mainWindow.appSettings.foldDispCmap,
            'fold',
            levels=(0.0, mainWindow.layoutMax),
        )

    def _applySurveyDataState(self, sidecarResult):
        mainWindow = self.mainWindow

        mainWindow.sessionService.setArray(mainWindow.sessionState, 'rpsImport', sidecarResult.rpsImport)
        mainWindow.sessionService.setArray(mainWindow.sessionState, 'spsImport', sidecarResult.spsImport)
        mainWindow.sessionService.setArray(mainWindow.sessionState, 'xpsImport', sidecarResult.xpsImport)
        mainWindow.sessionService.setArray(mainWindow.sessionState, 'recGeom', sidecarResult.recGeom)
        mainWindow.sessionService.setArray(mainWindow.sessionState, 'srcGeom', sidecarResult.srcGeom)
        mainWindow.sessionService.setArray(mainWindow.sessionState, 'relGeom', sidecarResult.relGeom)

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
        del liveDeadAttrs, boundAttr
        mainWindow = self.mainWindow
        array = getattr(mainWindow, arrayAttr)
        action = getattr(mainWindow, actionAttr)

        if array is not None:
            nImport = array.shape[0]
            action.setChecked(nImport > 0)
            action.setEnabled(nImport > 0)
        else:
            action.setChecked(False)
            action.setEnabled(False)

    def _refreshModelAndView(self, modelAttr, dataAttr, viewAttr):
        mainWindow = self.mainWindow

        model = getattr(mainWindow, modelAttr)
        view = getattr(mainWindow, viewAttr)
        model.setData(getattr(mainWindow, dataAttr))
        if view is not None:
            view.reset()
