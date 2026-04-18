# coding=utf-8

import os

import pyqtgraph as pg

from .enums_and_int_flags import SurveyType
from .roll_survey import RollSurvey


class PropertyPanelController:
    def __init__(self, window) -> None:
        self.window = window

    def resetSurveyProperties(self):
        window = self.window

        window.paramTree.clear()

        surveyCopy = window.survey.deepcopy()
        if surveyCopy is None:
            return

        window.updatePatternList(surveyCopy)

        window.parameters = pg.parametertree.Parameter.create(
            name='Survey Properties',
            type='group',
            children=self._buildSurveyParameters(surveyCopy),
        )
        window.parameters.sigTreeStateChanged.connect(window.propertyTreeStateChanged)

        window.paramTree.blockSignals(True)
        window.paramTree.setParameters(window.parameters, showTop=False)
        window.paramTree.blockSignals(False)

        self._connectBinningWatchers()
        nItem = self._configureParameterTreeItems()
        window.appendLogMessage(f'Params : {window.fileName} survey object read, containing {nItem} parameters')
        window.enableProcessingMenuItems(True)

    def updatePatternList(self, survey):
        assert isinstance(survey, RollSurvey), 'make sure we have a RollSurvey object here'

        patternNames = [pattern.name for pattern in survey.patternList]
        combos = [self.window.pattern1, self.window.pattern2, self.window.pattern3, self.window.pattern4]

        for combo in combos:
            combo.blockSignals(True)

        try:
            self._populatePatternCombo(self.window.pattern1, patternNames)
            self._populatePatternCombo(self.window.pattern2, patternNames)
            self._populatePatternCombo(self.window.pattern3, patternNames)
            self._populatePatternCombo(self.window.pattern4, patternNames)

            listSize = len(patternNames)
            self.window.pattern1.setCurrentIndex(min(listSize, 1))
            self.window.pattern2.setCurrentIndex(min(listSize, 2))
            self.window.pattern3.setCurrentIndex(min(listSize, 1))
            self.window.pattern4.setCurrentIndex(min(listSize, 2))
        finally:
            for combo in combos:
                combo.blockSignals(False)

    def applyPropertyChanges(self):
        window = self.window

        surveyCopy = self._buildSurveyFromParameters()
        if surveyCopy.checkIntegrity() is False:
            return

        self._commitSurveyCopy(surveyCopy)

        if window.binAreaChanged:
            self._invalidateAnalysisOutputs()
        else:
            window.updateMenuStatus(False)

        window.enableProcessingMenuItems(True)
        window.appendLogMessage(f'Edited : {window.fileName} survey object updated')
        window.updatePatternList(window.survey)
        window.plotLayout()

    def _buildSurveyParameters(self, surveyCopy):
        brush = '#add8e6'

        return [
            dict(brush=brush, name='Survey configuration', type='myConfiguration', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey analysis', type='myAnalysis', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey reflectors', type='myReflectors', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey grid', type='myGrid', value=surveyCopy.grid, default=surveyCopy.grid),
            dict(brush=brush, name='Block list', type='myBlockList', value=surveyCopy.blockList, default=surveyCopy.blockList, directory=self.window.projectDirectory, survey=surveyCopy),
            dict(brush=brush, name='Pattern list', type='myPatternList', value=surveyCopy.patternList, default=surveyCopy.patternList, survey=surveyCopy),
        ]

    def _connectBinningWatchers(self):
        window = self.window

        window.binChild = window.parameters.child('Survey analysis', 'Binning area')
        window.binChild.sigTreeStateChanged.connect(window.binningSettingsHaveChanged)

        window.grdChild = window.parameters.child('Survey grid')
        window.grdChild.sigTreeStateChanged.connect(window.binningSettingsHaveChanged)

    def _configureParameterTreeItems(self):
        nItem = 0

        for item in self.window.paramTree.listAllItems():
            parameter = item.param
            if 'tip' in parameter.opts:
                item.setToolTip(0, parameter.opts['tip'])
            if hasattr(item, 'updateDefaultBtn'):
                parameter.setToDefault()
                item.updateDefaultBtn()
            nItem += 1

        return nItem

    def _populatePatternCombo(self, combo, patternNames):
        combo.clear()
        combo.addItem('<no pattern>')
        for name in patternNames:
            combo.addItem(name)

    def _buildSurveyFromParameters(self):
        window = self.window
        surveyCopy = RollSurvey()

        configuration = window.parameters.child('Survey configuration')
        surveyCopy.crs, surveyType, surveyCopy.name = configuration.value()
        surveyCopy.type = SurveyType[surveyType]

        analysis = window.parameters.child('Survey analysis')
        surveyCopy.output.rctOutput, surveyCopy.angles, surveyCopy.binning, surveyCopy.offset, surveyCopy.unique = analysis.value()

        reflectors = window.parameters.child('Survey reflectors')
        surveyCopy.globalPlane, surveyCopy.globalSphere = reflectors.value()

        surveyGrid = window.parameters.child('Survey grid')
        surveyCopy.grid = surveyGrid.value()

        blockList = window.parameters.child('Block list')
        surveyCopy.blockList = blockList.value()

        patternList = window.parameters.child('Pattern list')
        surveyCopy.patternList = patternList.value()

        surveyCopy.bindSeedsToSurvey()
        return surveyCopy

    def _commitSurveyCopy(self, surveyCopy):
        window = self.window

        window.survey = surveyCopy.deepcopy()
        window.survey.calcTransforms()
        window.survey.calcSeedData()
        window.survey.calcBoundingRect()
        window.survey.calcNoShotPoints()

        window.setPlottingDetails()

        plainText = window.survey.toXmlString()
        window.textEdit.setTextViaCursor(plainText)
        window.textEdit.document().setModified(True)

    def _invalidateAnalysisOutputs(self):
        window = self.window

        window.binAreaChanged = False

        window.inlineStk = None
        window.x0lineStk = None
        window.xyCellStk = None
        window.xyPatResp = None
        window.plotRedrawHelper.reset()

        window.output.binOutput = None
        window.output.minOffset = None
        window.output.maxOffset = None
        window.output.rmsOffset = None
        window.output.ofAziHist = None
        window.output.offstHist = None

        if window.resetAnaTableModel():
            window.appendLogMessage(f"Edited : Closing memory mapped file {window.fileName + '.ana.npy'}")

        self._deleteAnalysisSidecars()
        window.updateMenuStatus(True)

    def _deleteAnalysisSidecars(self):
        sidecarPaths = [
            self.window.fileName + '.bin.npy',
            self.window.fileName + '.min.npy',
            self.window.fileName + '.max.npy',
            self.window.fileName + '.rms.npy',
            self.window.fileName + '.ana.npy',
        ]

        try:
            for sidecarPath in sidecarPaths:
                if os.path.exists(sidecarPath):
                    os.remove(sidecarPath)
        except OSError as exc:
            self.window.appendLogMessage(f"Can't delete file, {exc}")
